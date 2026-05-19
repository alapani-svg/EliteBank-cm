"""
Single entry point for emitting in-app notifications and queueing emails.

Usage:
    from accounts.services.notifications import notify
    notify(user, 'TRANSFER', 'SUCCESS', 'Transfer received',
           body='You received 5,000 XAF from John Doe.',
           action_url='/transactions/<uuid>/')
"""
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)


def _send_email_async(subject: str, body: str, recipient: str) -> None:
    """Fire-and-forget email send. Errors are swallowed so they never break
    the parent flow (e.g. a transfer must succeed even if email is down)."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject       = subject,
            message       = body,
            from_email    = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@elitebank.test'),
            recipient_list= [recipient],
            fail_silently = True,
        )
    except Exception as exc:
        logger.warning('Email queue dispatch failed for %s: %s', recipient, exc)


def _queue_email(subject: str, body: str, recipient: str) -> None:
    """Run the email send on a daemon thread so the HTTP response isn't blocked."""
    if not recipient:
        return
    t = threading.Thread(
        target=_send_email_async,
        args=(subject, body, recipient),
        daemon=True,
    )
    t.start()


def notify(
    user,
    category: str,
    kind: str = 'INFO',
    title: str = '',
    body: str = '',
    action_url: str = '',
    send_email: Optional[bool] = None,
) -> None:
    """Create an in-app Notification and optionally queue an email.

    - `send_email`: if None, falls back to the user's `email_notifications` preference.
                    Pass False to suppress (e.g. low-importance events).
    """
    if user is None:
        return

    # Lazy import to avoid circular dependency with accounts.models
    from accounts.models import Notification

    try:
        Notification.objects.create(
            user       = user,
            kind       = kind,
            category   = category,
            title      = title[:160],
            body       = body[:500],
            action_url = action_url[:255],
        )
    except Exception as exc:
        logger.warning('Failed to create notification for %s: %s', getattr(user, 'email', '?'), exc)

    should_email = send_email if send_email is not None else getattr(user, 'email_notifications', False)
    if should_email and getattr(user, 'email', ''):
        plain = body or title
        _queue_email(subject=title or 'Elite Bank notification', body=plain, recipient=user.email)

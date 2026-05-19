"""
Stateless password-reset tokens.

Uses Django's `TimestampSigner` to mint signed strings that encode the user's
UUID plus the time of minting. Tokens are cryptographically tied to
`SECRET_KEY` so a leaked token is useless once the secret rotates. No DB table
is needed; each token is opaque to the client.

A single token is valid for `TOKEN_LIFETIME_SECONDS` (default: 1 hour). After
that, `unsign` raises `SignatureExpired` and the endpoint returns 400.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

from accounts.models import User

logger = logging.getLogger(__name__)

SIGNER_SALT = 'elite-bank-password-reset.v1'
TOKEN_LIFETIME_SECONDS = 3600  # 1 hour


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=SIGNER_SALT)


def make_token(user: User) -> str:
    """Mint a short-lived password-reset token for a user."""
    return _signer().sign(str(user.id))


def consume_token(token: str) -> Optional[User]:
    """Verify a token and return the matching user, or None.

    Returns `None` for any failure (expired, tampered, unknown user) — the
    caller should always render a generic 'invalid or expired link' message
    to avoid leaking which tokens were ever valid.
    """
    try:
        user_id = _signer().unsign(token, max_age=TOKEN_LIFETIME_SECONDS)
    except SignatureExpired:
        logger.info('password-reset token expired')
        return None
    except BadSignature:
        logger.warning('password-reset token tampered')
        return None

    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return None


def send_password_reset_email(user: User, token: str) -> None:
    """Email a reset link. Falls back gracefully if email isn't configured —
    the console backend logs the link to stdout, which is fine for dev / demo."""
    frontend_url = (
        getattr(settings, 'FRONTEND_URL', None)
        or 'http://localhost:4200'
    ).rstrip('/').split(',')[0].strip()

    reset_url = f"{frontend_url}/reset-password?token={token}"

    subject = "Reset your Elite Bank password"
    body = (
        f"Hi {user.full_name.split(' ')[0]},\n\n"
        f"We received a request to reset the password on your Elite Bank account.\n"
        f"Click the link below within the next hour to choose a new password:\n\n"
        f"  {reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email — your\n"
        f"password will stay the same.\n\n"
        f"— The Elite Bank team\n"
        f"Built by CORANTIN · promptforge237@gmail.com"
    )

    try:
        send_mail(
            subject,
            body,
            getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            [user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning('password-reset email failed for %s: %s', user.email, exc)

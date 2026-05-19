"""
One-time-password helpers for 2FA login.

Demo mode: when `AT_API_KEY` is empty, the OTP is logged to the Django
console instead of being SMS-sent. This lets the project be graded without
any SMS budget.

OTP characteristics:
- 6-digit numeric code (no leading zero ambiguity — formatted with leading zeros)
- SHA-256 hashed at rest (we never store the plain code in the DB)
- 5-minute TTL
- Max 5 verification attempts before the challenge is auto-consumed
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from accounts.models import OTPChallenge, User

logger = logging.getLogger(__name__)

OTP_LENGTH         = 6
OTP_TTL_MINUTES    = 5
MAX_ATTEMPTS       = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def _generate_code() -> str:
    """6 cryptographically random digits, zero-padded."""
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def issue_challenge(user: User) -> tuple[OTPChallenge, str]:
    """Mint a new OTP challenge for the user. Returns (challenge, plain_code).

    Caller is responsible for actually delivering `plain_code` to the user
    (SMS / email / console). The plain code is NEVER persisted.
    """
    code = _generate_code()
    expires_at = timezone.now() + timedelta(minutes=OTP_TTL_MINUTES)
    challenge = OTPChallenge.objects.create(
        user=user,
        code_hash=_hash_code(code),
        expires_at=expires_at,
    )
    return challenge, code


def send_otp(user: User, code: str) -> None:
    """Deliver the OTP to the user. Falls back to console-logging in demo mode."""
    at_key = getattr(settings, 'AT_API_KEY', '') or ''
    if at_key and user.phone_number:
        try:
            from .sms import send_otp as sms_send_otp
            sms_send_otp(user.phone_number, code)
            logger.info('OTP sent via SMS to %s (****%s)',
                        user.email, user.phone_number[-3:])
            return
        except Exception as exc:
            logger.warning('SMS gateway failed (%s) — falling back to console', exc)

    # DEMO MODE — never log the code to a real production log, but for a
    # student project this is the cheapest way to demo the feature.
    logger.warning('═══════════ OTP DEMO MODE ═══════════')
    logger.warning('User : %s', user.email)
    logger.warning('Code : %s', code)
    logger.warning('Valid: %d minutes', OTP_TTL_MINUTES)
    logger.warning('══════════════════════════════════════')


def verify_challenge(challenge_id: str, code: str) -> tuple[OTPChallenge | None, str]:
    """Verify a challenge. Returns (challenge_or_None, error_message).

    On success: challenge is marked consumed and returned (with empty error).
    On failure: attempts is incremented; once it hits MAX_ATTEMPTS the
    challenge is auto-consumed to prevent further brute-forcing.
    """
    try:
        challenge = OTPChallenge.objects.select_related('user').get(pk=challenge_id)
    except (OTPChallenge.DoesNotExist, ValueError):
        return None, 'This verification code is invalid or has expired.'

    if challenge.is_consumed():
        return None, 'This verification code has already been used.'
    if challenge.is_expired():
        return None, 'This verification code has expired. Please log in again.'
    if challenge.attempts >= MAX_ATTEMPTS:
        return None, 'Too many incorrect attempts. Please log in again.'

    if challenge.code_hash != _hash_code(code.strip()):
        challenge.attempts += 1
        # Auto-consume on final wrong attempt so it can't be brute-forced further.
        update_fields = ['attempts']
        if challenge.attempts >= MAX_ATTEMPTS:
            challenge.consumed_at = timezone.now()
            update_fields.append('consumed_at')
        challenge.save(update_fields=update_fields)
        remaining = MAX_ATTEMPTS - challenge.attempts
        if remaining <= 0:
            return None, 'Too many incorrect attempts. Please log in again.'
        return None, f'Incorrect code. {remaining} attempt(s) remaining.'

    # Success — mark consumed
    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=['consumed_at'])
    return challenge, ''


def mask_phone(phone: str) -> str:
    """Return e.g. '+237 6** *** *01' for display in the OTP page."""
    if not phone or len(phone) < 4:
        return '****'
    return f"{phone[:4]} *** *** *{phone[-2:]}"

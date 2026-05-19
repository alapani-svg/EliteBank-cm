import requests
from django.conf import settings

NOTCHPAY_BASE = "https://api.notchpay.co"

# Channel codes recognised by NotchPay for Cameroon mobile money
CHANNEL_MAP = {
    'orange': 'cm.orange',
    'mtn':    'cm.mtn',
}


def _headers():
    return {
        "Authorization": settings.NOTCHPAY_PUBLIC_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def initiate_deposit(*, amount, phone, payment_method, email, reference, description="Account recharge"):
    """
    Collect mobile-money from a user (they pay US).
    payment_method: 'orange' | 'mtn'
    Returns the full JSON response from NotchPay.
    """
    channel = CHANNEL_MAP.get(payment_method, 'cm.mtn')
    payload = {
        "amount":      str(amount),
        "currency":    "XAF",
        "email":       email,
        "phone":       phone,
        "channel":     channel,
        "reference":   reference,
        "description": description,
        "callback":    settings.NOTCHPAY_CALLBACK_URL,
    }
    response = requests.post(
        f"{NOTCHPAY_BASE}/payments/initialize",
        json=payload,
        headers=_headers(),
        timeout=15,
    )
    return response.json()


def verify_payment(reference):
    """
    Check the current status of a NotchPay payment.
    Returns the full JSON response.
    """
    response = requests.get(
        f"{NOTCHPAY_BASE}/payments/{reference}",
        headers=_headers(),
        timeout=10,
    )
    return response.json()


def initiate_transfer(amount, currency, email, phone, description):
    """Legacy outbound-transfer helper (kept for backwards compatibility)."""
    payload = {
        "amount":      amount,
        "currency":    currency,
        "email":       email,
        "phone":       phone,
        "description": description,
        "callback":    settings.NOTCHPAY_CALLBACK_URL,
    }
    response = requests.post(
        f"{NOTCHPAY_BASE}/payments/initialize",
        json=payload,
        headers=_headers(),
        timeout=15,
    )
    return response.json()

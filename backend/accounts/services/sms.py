import africastalking
from django.conf import settings

africastalking.initialize(
    username=settings.AT_USERNAME,
    api_key=settings.AT_API_KEY
)
sms = africastalking.SMS


def send_otp(phone_number: str, otp_code: str) -> dict:
    message = f"Your ELITE BANK verification code is: {otp_code}. Valid for 10 minutes. Do not share this code."
    response = sms.send(message, [phone_number])
    return response


def send_transaction_alert(phone_number: str, amount: int, tx_type: str, balance: int) -> dict:
    message = (
        f"ELITE BANK: {tx_type} of XAF {amount:,} successful. "
        f"New balance: XAF {balance:,}. "
        f"Not you? Call +237 000 000 000 immediately."
    )
    response = sms.send(message, [phone_number])
    return response
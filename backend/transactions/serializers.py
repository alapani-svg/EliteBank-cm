import logging
from decimal import Decimal
from django.db import transaction as db_transaction
from rest_framework import serializers
from accounts.models import User
from .models import Transaction

logger = logging.getLogger(__name__)


def _notify_transfer(txn, sender_obj, recipient_obj) -> None:
    """Fire email (and optional SMS) notifications in background threads, and
    create persistent in-app notifications for both parties."""
    from accounts.services.notifications import notify

    amount_str = f"{int(txn.amount):,} XAF"

    # ── In-app notifications ────────────────────────────────────────────────
    notify(
        sender_obj, 'TRANSFER', 'SUCCESS',
        title=f"Transfer sent — {amount_str}",
        body=f"You sent {amount_str} to {recipient_obj.full_name} ({recipient_obj.email}).",
        action_url=f"/transactions/{txn.id}/",
    )
    notify(
        recipient_obj, 'TRANSFER', 'SUCCESS',
        title=f"Transfer received — {amount_str}",
        body=f"You received {amount_str} from {sender_obj.full_name}.",
        action_url=f"/transactions/{txn.id}/",
    )

    # ── Email (legacy hooks, kept for compatibility) ────────────────────────
    try:
        from .services.email import notify_transfer_received, notify_transfer_sent
        notify_transfer_received(txn, recipient_obj, sender_obj)
        notify_transfer_sent(txn, sender_obj, recipient_obj)
    except Exception as exc:
        logger.warning('Transfer email notification failed: %s', exc)

    # SMS alert for recipient (only if they opted in)
    if getattr(recipient_obj, 'sms_alerts', False) and recipient_obj.phone_number:
        try:
            from accounts.services.sms import send_transaction_alert
            send_transaction_alert(
                phone_number=recipient_obj.phone_number,
                amount=int(txn.amount),
                tx_type='Credit',
                balance=int(recipient_obj.balance_xaf),
            )
        except Exception as exc:
            logger.warning('Transfer SMS notification failed: %s', exc)


MIN_TRANSFER_AMOUNT   = Decimal('100.00')
MIN_DEPOSIT_AMOUNT    = Decimal('100.00')
MIN_WITHDRAWAL_AMOUNT = Decimal('500.00')


class RecipientField(serializers.Field):
    """Accept a recipient by email or phone number."""

    def to_representation(self, value):
        return {
            'id':           str(value.id),
            'full_name':    value.full_name,
            'email':        value.email,
            'phone_number': value.phone_number,
        }

    def to_internal_value(self, data):
        try:
            return User.objects.get(email=data)
        except User.DoesNotExist:
            try:
                return User.objects.get(phone_number=data)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    "No user found with this email or phone number."
                )


class TransactionSerializer(serializers.ModelSerializer):
    sender_name    = serializers.CharField(source='sender.full_name',    read_only=True)
    sender_email   = serializers.CharField(source='sender.email',        read_only=True)
    recipient_name = serializers.CharField(source='recipient.full_name', read_only=True)
    recipient_email = serializers.CharField(source='recipient.email',    read_only=True)

    class Meta:
        model  = Transaction
        fields = [
            'id', 'reference', 'transaction_type', 'status',
            'amount', 'currency', 'description',
            'sender', 'sender_name', 'sender_email',
            'recipient', 'recipient_name', 'recipient_email',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'status', 'sender',
            'sender_name', 'sender_email',
            'recipient_name', 'recipient_email',
            'created_at', 'updated_at',
        ]


class TransferSerializer(serializers.Serializer):
    """Handles peer-to-peer transfers with full business-rule validation."""

    recipient_identifier = serializers.CharField(
        help_text="Recipient's email address or phone number."
    )
    amount      = serializers.DecimalField(max_digits=15, decimal_places=2)
    description = serializers.CharField(max_length=255, required=False, default='', allow_blank=True)

    def validate_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("Transfer amount must be greater than zero.")
        if value < MIN_TRANSFER_AMOUNT:
            raise serializers.ValidationError(
                f"Minimum transfer amount is {MIN_TRANSFER_AMOUNT} XAF."
            )
        return value

    def validate_recipient_identifier(self, value):
        try:
            recipient = User.objects.get(email=value)
        except User.DoesNotExist:
            try:
                recipient = User.objects.get(phone_number=value)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    "No account found with this email or phone number."
                )
        return recipient

    def validate(self, attrs):
        sender    = self.context['request'].user
        recipient = attrs['recipient_identifier']
        amount    = attrs['amount']

        if recipient.id == sender.id:
            raise serializers.ValidationError(
                {"recipient_identifier": "You cannot transfer money to yourself."}
            )

        if sender.balance_xaf < amount:
            raise serializers.ValidationError(
                {"amount": f"Insufficient balance. Your balance is {sender.balance_xaf} XAF."}
            )

        attrs['recipient'] = recipient
        return attrs

    def create(self, validated_data):
        sender      = self.context['request'].user
        recipient   = validated_data['recipient']
        amount      = validated_data['amount']
        description = validated_data.get('description', '')
        # The view pre-creates a PENDING record; we update it instead of inserting.
        pending_txn = self.context.get('pending_txn')

        with db_transaction.atomic():
            # Re-fetch both parties with SELECT FOR UPDATE to prevent races.
            sender_obj = User.objects.select_for_update().get(pk=sender.pk)
            if sender_obj.balance_xaf < amount:
                raise serializers.ValidationError(
                    {"amount": "Insufficient balance."}
                )
            sender_obj.balance_xaf -= amount
            sender_obj.save(update_fields=['balance_xaf'])

            recipient_obj = User.objects.select_for_update().get(pk=recipient.pk)
            recipient_obj.balance_xaf += amount
            recipient_obj.save(update_fields=['balance_xaf'])

            if pending_txn:
                # Update the pre-created PENDING record to its final state.
                pending_txn.sender      = sender_obj
                pending_txn.recipient   = recipient_obj
                pending_txn.amount      = amount
                pending_txn.description = description
                pending_txn.status      = Transaction.Status.COMPLETED
                pending_txn.save(update_fields=[
                    'sender', 'recipient', 'amount', 'description', 'status',
                ])
                txn = pending_txn
            else:
                txn = Transaction.objects.create(
                    sender           = sender_obj,
                    recipient        = recipient_obj,
                    transaction_type = Transaction.TransactionType.TRANSFER,
                    status           = Transaction.Status.COMPLETED,
                    amount           = amount,
                    currency         = 'XAF',
                    description      = description,
                )

        # Send notifications after the DB commit — never for rolled-back transactions.
        _notify_transfer(txn, sender_obj, recipient_obj)

        return txn


# ── Deposit (mobile-money recharge) ──────────────────────────────────────────

class DepositSerializer(serializers.Serializer):
    """Validate a mobile-money deposit request."""
    amount         = serializers.DecimalField(max_digits=15, decimal_places=2)
    phone          = serializers.CharField(max_length=25)
    payment_method = serializers.ChoiceField(choices=['orange', 'mtn'])

    def validate_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < MIN_DEPOSIT_AMOUNT:
            raise serializers.ValidationError(
                f"Minimum deposit amount is {MIN_DEPOSIT_AMOUNT} XAF."
            )
        return value

    def validate_phone(self, value):
        import re
        cleaned = re.sub(r'[\s\-]', '', value)
        if not re.match(r'^\+?237[0-9]{8,9}$', cleaned):
            raise serializers.ValidationError(
                "Enter a valid Cameroonian phone number (e.g. +237 670 000 001)."
            )
        return cleaned


# ── Bill Payment ──────────────────────────────────────────────────────────────

BILL_PROVIDERS = ['ENEO', 'CAMWATER', 'CANAL+', 'CAMTEL']
MIN_BILL_AMOUNT = Decimal('100.00')


class BillPaymentSerializer(serializers.Serializer):
    """Validate and execute a utility bill payment."""
    provider     = serializers.ChoiceField(choices=BILL_PROVIDERS)
    meter_number = serializers.CharField(max_length=60)
    amount       = serializers.DecimalField(max_digits=15, decimal_places=2)

    def validate_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < MIN_BILL_AMOUNT:
            raise serializers.ValidationError(
                f"Minimum payment amount is {MIN_BILL_AMOUNT} XAF."
            )
        return value

    def validate(self, attrs):
        sender = self.context['request'].user
        if sender.balance_xaf < attrs['amount']:
            raise serializers.ValidationError(
                {"amount": f"Insufficient balance. Your balance is {sender.balance_xaf} XAF."}
            )
        return attrs

    def create(self, validated_data):
        from accounts.models import User
        sender   = self.context['request'].user
        provider = validated_data['provider']
        meter    = validated_data['meter_number']
        amount   = validated_data['amount']

        with db_transaction.atomic():
            sender_obj = User.objects.select_for_update().get(pk=sender.pk)
            if sender_obj.balance_xaf < amount:
                raise serializers.ValidationError({"amount": "Insufficient balance."})
            sender_obj.balance_xaf -= amount
            sender_obj.save(update_fields=['balance_xaf'])

            txn = Transaction.objects.create(
                sender           = sender_obj,
                transaction_type = Transaction.TransactionType.BILL_PAYMENT,
                status           = Transaction.Status.COMPLETED,
                amount           = amount,
                currency         = 'XAF',
                description      = f"{provider} — Ref: {meter}",
            )

        from accounts.services.notifications import notify
        notify(
            sender_obj, 'BILL_PAYMENT', 'SUCCESS',
            title=f"{provider} bill paid — {int(amount):,} XAF",
            body=f"Your payment of {int(amount):,} XAF to {provider} (ref {meter}) was successful.",
            action_url=f"/transactions/{txn.id}/",
        )
        return txn


# ── Airtime Purchase ──────────────────────────────────────────────────────────

MIN_AIRTIME_AMOUNT = Decimal('100.00')


class AirtimeSerializer(serializers.Serializer):
    """Validate and execute an airtime purchase."""
    network = serializers.ChoiceField(choices=['mtn', 'orange'])
    phone   = serializers.CharField(max_length=25)
    amount  = serializers.DecimalField(max_digits=15, decimal_places=2)

    def validate_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < MIN_AIRTIME_AMOUNT:
            raise serializers.ValidationError(
                f"Minimum airtime amount is {MIN_AIRTIME_AMOUNT} XAF."
            )
        return value

    def validate_phone(self, value):
        import re
        cleaned = re.sub(r'[\s\-]', '', value)
        if not re.match(r'^\+?237[0-9]{8,9}$', cleaned):
            raise serializers.ValidationError(
                "Enter a valid Cameroonian phone number."
            )
        return cleaned

    def validate(self, attrs):
        sender = self.context['request'].user
        if sender.balance_xaf < attrs['amount']:
            raise serializers.ValidationError(
                {"amount": f"Insufficient balance. Your balance is {sender.balance_xaf} XAF."}
            )
        return attrs

    def create(self, validated_data):
        from accounts.models import User
        sender  = self.context['request'].user
        network = validated_data['network'].upper()
        phone   = validated_data['phone']
        amount  = validated_data['amount']

        with db_transaction.atomic():
            sender_obj = User.objects.select_for_update().get(pk=sender.pk)
            if sender_obj.balance_xaf < amount:
                raise serializers.ValidationError({"amount": "Insufficient balance."})
            sender_obj.balance_xaf -= amount
            sender_obj.save(update_fields=['balance_xaf'])

            txn = Transaction.objects.create(
                sender           = sender_obj,
                transaction_type = Transaction.TransactionType.AIRTIME,
                status           = Transaction.Status.COMPLETED,
                amount           = amount,
                currency         = 'XAF',
                description      = f"{network} Airtime — {phone}",
            )

        from accounts.services.notifications import notify
        notify(
            sender_obj, 'AIRTIME', 'SUCCESS',
            title=f"Airtime purchased — {int(amount):,} XAF",
            body=f"{int(amount):,} XAF of {network} airtime sent to {phone}.",
            action_url=f"/transactions/{txn.id}/",
        )
        return txn


# ── Withdrawal (mobile-money cash-out) ────────────────────────────────────────

class WithdrawalSerializer(serializers.Serializer):
    """Validate and execute a mobile-money withdrawal."""
    amount         = serializers.DecimalField(max_digits=15, decimal_places=2)
    phone          = serializers.CharField(max_length=25)
    payment_method = serializers.ChoiceField(choices=['orange', 'mtn'])

    def validate_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value < MIN_WITHDRAWAL_AMOUNT:
            raise serializers.ValidationError(
                f"Minimum withdrawal amount is {MIN_WITHDRAWAL_AMOUNT} XAF."
            )
        return value

    def validate_phone(self, value):
        import re
        cleaned = re.sub(r'[\s\-]', '', value)
        if not re.match(r'^\+?237[0-9]{8,9}$', cleaned):
            raise serializers.ValidationError(
                "Enter a valid Cameroonian phone number (e.g. +237 670 000 001)."
            )
        return cleaned

    def validate(self, attrs):
        sender = self.context['request'].user
        if sender.balance_xaf < attrs['amount']:
            raise serializers.ValidationError(
                {"amount": f"Insufficient balance. Your balance is {sender.balance_xaf} XAF."}
            )
        return attrs

    def create(self, validated_data):
        sender         = self.context['request'].user
        amount         = validated_data['amount']
        phone          = validated_data['phone']
        payment_method = validated_data['payment_method'].upper()
        pending_txn    = self.context.get('pending_txn')

        with db_transaction.atomic():
            sender_obj = User.objects.select_for_update().get(pk=sender.pk)
            if sender_obj.balance_xaf < amount:
                raise serializers.ValidationError({"amount": "Insufficient balance."})
            sender_obj.balance_xaf -= amount
            sender_obj.save(update_fields=['balance_xaf'])

            if pending_txn:
                pending_txn.sender         = sender_obj
                pending_txn.amount         = amount
                pending_txn.payment_method = payment_method
                pending_txn.payment_phone  = phone
                pending_txn.status         = Transaction.Status.COMPLETED
                pending_txn.description    = f"{payment_method} Money withdrawal — {phone}"
                pending_txn.save(update_fields=[
                    'sender', 'amount', 'payment_method', 'payment_phone',
                    'status', 'description',
                ])
                txn = pending_txn
            else:
                txn = Transaction.objects.create(
                    sender           = sender_obj,
                    transaction_type = Transaction.TransactionType.WITHDRAWAL,
                    status           = Transaction.Status.COMPLETED,
                    amount           = amount,
                    currency         = 'XAF',
                    description      = f"{payment_method} Money withdrawal — {phone}",
                    payment_method   = payment_method,
                    payment_phone    = phone,
                )

        from accounts.services.notifications import notify
        notify(
            sender_obj, 'WITHDRAWAL', 'SUCCESS',
            title=f"Withdrawal completed — {int(amount):,} XAF",
            body=f"{int(amount):,} XAF was cashed out to your {payment_method} Money number {phone}.",
            action_url=f"/transactions/{txn.id}/",
        )
        return txn

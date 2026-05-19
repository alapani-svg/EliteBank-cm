import uuid
from django.db import models
from django.conf import settings


class Transaction(models.Model):

    class TransactionType(models.TextChoices):
        TRANSFER     = 'TRANSFER',     'Transfer'
        DEPOSIT      = 'DEPOSIT',      'Deposit'
        WITHDRAWAL   = 'WITHDRAWAL',   'Withdrawal'
        BILL_PAYMENT = 'BILL_PAYMENT', 'Bill Payment'
        AIRTIME      = 'AIRTIME',      'Airtime'

    class Status(models.TextChoices):
        PENDING   = 'PENDING',   'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED    = 'FAILED',    'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference   = models.CharField(max_length=32, unique=True, editable=False)

    sender      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_transactions',
        null=True, blank=True,
    )
    recipient   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='received_transactions',
        null=True, blank=True,
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        default=TransactionType.TRANSFER,
    )
    status      = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )

    amount      = models.DecimalField(max_digits=15, decimal_places=2)
    currency    = models.CharField(max_length=10, default='XAF')
    description = models.CharField(max_length=255, blank=True, default='')

    # Mobile-money deposit fields
    payment_reference = models.CharField(max_length=100, blank=True, default='')
    payment_method    = models.CharField(max_length=20,  blank=True, default='')
    payment_phone     = models.CharField(max_length=25,  blank=True, default='')

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Transaction'
        verbose_name_plural = 'Transactions'

    def __str__(self):
        return f"[{self.transaction_type}] {self.reference} — {self.amount} {self.currency}"

    REFERENCE_PREFIX = {
        'TRANSFER':     'TXN',
        'DEPOSIT':      'DEP',
        'WITHDRAWAL':   'WTH',
        'BILL_PAYMENT': 'PAY',
        'AIRTIME':      'AIR',
    }

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = self.REFERENCE_PREFIX.get(self.transaction_type, 'TXN')
            code   = uuid.uuid4().hex[:8].upper()
            self.reference = f"ELITE-{prefix}-{code}"
        super().save(*args, **kwargs)

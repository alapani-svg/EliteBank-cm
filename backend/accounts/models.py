from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import uuid


class UserManager(BaseUserManager):
    def create_user(self, email, full_name, phone_number, password=None):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user  = self.model(email=email, full_name=full_name, phone_number=phone_number)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, phone_number, password=None):
        user = self.create_user(email, full_name, phone_number, password)
        user.is_staff     = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email        = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True)
    full_name    = models.CharField(max_length=150)

    # Profile extras
    avatar_url   = models.URLField(blank=True, default='')
    language     = models.CharField(max_length=10, default='en')

    # Preferences
    email_notifications = models.BooleanField(default=True)
    sms_alerts          = models.BooleanField(default=False)
    two_factor_enabled  = models.BooleanField(default=False)

    # Account flags
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)
    is_verified  = models.BooleanField(default=False)

    balance_xaf  = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    date_joined  = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # Password tracking
    password_changed_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone_number']

    objects = UserManager()

    class Meta:
        verbose_name        = 'User'
        verbose_name_plural = 'Users'
        ordering            = ['-date_joined']

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class Beneficiary(models.Model):
    """A saved recipient for transfers, airtime, or bill payments."""

    class Category(models.TextChoices):
        TRANSFER     = 'TRANSFER',     'Transfer'
        AIRTIME      = 'AIRTIME',      'Airtime'
        BILL_PAYMENT = 'BILL_PAYMENT', 'Bill Payment'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner      = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='beneficiaries',
    )
    name       = models.CharField(max_length=120)
    identifier = models.CharField(
        max_length=120,
        help_text='Email/phone for transfers & airtime, meter number for bills.',
    )
    category   = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.TRANSFER,
    )
    provider   = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='MTN/Orange for airtime, ENEO/CAMWATER/CANAL+/CAMTEL for bills.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Beneficiary'
        verbose_name_plural = 'Beneficiaries'
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'identifier', 'category', 'provider'],
                name='unique_beneficiary_per_owner',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.identifier})"


class OTPChallenge(models.Model):
    """
    Short-lived one-time password challenge issued during login when the user
    has `two_factor_enabled=True`.

    Flow:
      1. POST /api/auth/login/  → if 2FA on, create a challenge + send OTP via SMS
                                  (or log to console in demo mode). No JWT yet.
                                  Server returns { requires_otp: true, challenge_id }.
      2. POST /api/auth/2fa/verify/  → { challenge_id, code }. If valid + not
                                       expired + not consumed → issue JWT.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='otp_challenges',
    )
    code_hash   = models.CharField(max_length=128, help_text='SHA-256 of the 6-digit code')
    expires_at  = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts    = models.PositiveSmallIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'OTP challenge'
        verbose_name_plural = 'OTP challenges'

    def is_expired(self) -> bool:
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    def __str__(self):
        return f"OTP[{self.user.email}] {'used' if self.is_consumed() else 'live'}"


class Notification(models.Model):
    """An in-app notification for a user."""

    class Kind(models.TextChoices):
        INFO    = 'INFO',    'Info'
        SUCCESS = 'SUCCESS', 'Success'
        WARNING = 'WARNING', 'Warning'
        ERROR   = 'ERROR',   'Error'

    class Category(models.TextChoices):
        TRANSFER     = 'TRANSFER',     'Transfer'
        DEPOSIT      = 'DEPOSIT',      'Deposit'
        WITHDRAWAL   = 'WITHDRAWAL',   'Withdrawal'
        BILL_PAYMENT = 'BILL_PAYMENT', 'Bill Payment'
        AIRTIME      = 'AIRTIME',      'Airtime'
        SECURITY     = 'SECURITY',     'Security'
        ACCOUNT      = 'ACCOUNT',      'Account'
        SYSTEM       = 'SYSTEM',       'System'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind       = models.CharField(max_length=10, choices=Kind.choices,     default=Kind.INFO)
    category   = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM)
    title      = models.CharField(max_length=160)
    body       = models.CharField(max_length=500, blank=True, default='')
    action_url = models.CharField(max_length=255, blank=True, default='')
    read       = models.BooleanField(default=False)
    read_at    = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'read']),
        ]

    def __str__(self):
        return f"[{self.kind}] {self.title} → {self.user.email}"

    def mark_read(self):
        from django.utils import timezone
        if not self.read:
            self.read    = True
            self.read_at = timezone.now()
            self.save(update_fields=['read', 'read_at'])
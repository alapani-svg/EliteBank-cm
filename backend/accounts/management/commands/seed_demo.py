"""
Populate the database with realistic demo data for development & screenshots.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --wipe        # delete prior demo data first
    python manage.py seed_demo --users 5     # create N demo users (default 3)

All demo users have the password `demo1234` and emails ending in `@demo.local`.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import Beneficiary, Notification
from transactions.models import Transaction


User = get_user_model()

DEMO_EMAIL_SUFFIX = '@demo.local'

DEMO_USERS = [
    {'email': 'alice@demo.local',   'full_name': 'Alice Mbarga',    'phone': '+237670000001'},
    {'email': 'bob@demo.local',     'full_name': 'Bob Nguema',      'phone': '+237670000002'},
    {'email': 'claire@demo.local',  'full_name': 'Claire Ndongo',   'phone': '+237670000003'},
    {'email': 'david@demo.local',   'full_name': 'David Ekwalla',   'phone': '+237670000004'},
    {'email': 'eve@demo.local',     'full_name': 'Eve Tabi',        'phone': '+237670000005'},
]

BILL_PROVIDERS = ['ENEO', 'CAMWATER', 'CANAL+', 'CAMTEL']
BILL_DESCRIPTIONS = {
    'ENEO':     'Electricity bill',
    'CAMWATER': 'Water utility',
    'CANAL+':   'TV subscription',
    'CAMTEL':   'Fiber internet',
}


class Command(BaseCommand):
    help = 'Populate the DB with realistic Elite Bank demo data.'

    def add_arguments(self, parser):
        parser.add_argument('--wipe',  action='store_true',
                            help='Delete existing demo data before seeding.')
        parser.add_argument('--users', type=int, default=3,
                            help='How many demo users to create (max 5, default 3).')

    @db_transaction.atomic
    def handle(self, *args, **opts):
        n = max(2, min(5, opts['users']))
        wipe = opts['wipe']

        if wipe:
            self.stdout.write(self.style.WARNING('Wiping prior demo data…'))
            demo_users = User.objects.filter(email__endswith=DEMO_EMAIL_SUFFIX)
            from django.db.models import Q
            Transaction.objects.filter(Q(sender__in=demo_users) | Q(recipient__in=demo_users)).delete()
            Beneficiary.objects.filter(owner__in=demo_users).delete()
            Notification.objects.filter(user__in=demo_users).delete()
            demo_users.delete()
            self.stdout.write(self.style.WARNING('  removed.\n'))

        # ── Create users ─────────────────────────────────────────────────────
        users = []
        for d in DEMO_USERS[:n]:
            user, created = User.objects.get_or_create(
                email=d['email'],
                defaults={'full_name': d['full_name'], 'phone_number': d['phone']},
            )
            if created:
                user.set_password('demo1234')
                user.balance_xaf = Decimal(random.choice([50_000, 100_000, 250_000, 500_000]))
                user.is_verified = True
                user.email_notifications = True
                user.save()
                self.stdout.write(f'  + created {user.email} (balance: {user.balance_xaf:,.0f} XAF)')
            else:
                self.stdout.write(f'  . exists  {user.email}')
            users.append(user)

        if len(users) < 2:
            self.stdout.write(self.style.ERROR('Need at least 2 users.'))
            return

        # ── Transfers between users ──────────────────────────────────────────
        self.stdout.write('\nSeeding transfers…')
        descriptions = ['Rent', 'Dinner split', 'Loan repayment', 'Birthday gift', 'Refund']
        for _ in range(8):
            sender    = random.choice(users)
            recipient = random.choice([u for u in users if u != sender])
            amount    = Decimal(random.choice([500, 1500, 5000, 10_000, 25_000]))
            if sender.balance_xaf < amount:
                continue
            self._do_transfer(sender, recipient, amount, random.choice(descriptions))
        self.stdout.write(self.style.SUCCESS('  transfers done.'))

        # ── Deposits (mobile money recharges) ────────────────────────────────
        self.stdout.write('\nSeeding deposits…')
        for u in users:
            for _ in range(2):
                amt = Decimal(random.choice([5_000, 10_000, 50_000]))
                self._do_deposit(u, amt, random.choice(['mtn', 'orange']))
        self.stdout.write(self.style.SUCCESS('  deposits done.'))

        # ── Bill payments ────────────────────────────────────────────────────
        self.stdout.write('\nSeeding bill payments…')
        for u in users[:2]:
            provider = random.choice(BILL_PROVIDERS)
            self._do_bill(u, provider, str(random.randint(10000, 99999)),
                          Decimal(random.choice([8_000, 15_000, 22_500])))
        self.stdout.write(self.style.SUCCESS('  bills done.'))

        # ── Airtime ──────────────────────────────────────────────────────────
        self.stdout.write('\nSeeding airtime purchases…')
        for u in users:
            net = random.choice(['MTN', 'ORANGE'])
            self._do_airtime(u, net, u.phone_number,
                             Decimal(random.choice([500, 1_000, 2_000])))
        self.stdout.write(self.style.SUCCESS('  airtime done.'))

        # ── Withdrawals ──────────────────────────────────────────────────────
        self.stdout.write('\nSeeding withdrawals…')
        for u in users[:2]:
            self._do_withdrawal(u, Decimal('3000'), random.choice(['MTN', 'ORANGE']),
                                u.phone_number)
        self.stdout.write(self.style.SUCCESS('  withdrawals done.'))

        # ── Beneficiaries ────────────────────────────────────────────────────
        self.stdout.write('\nSeeding beneficiaries…')
        for u in users:
            others = [x for x in users if x != u]
            for other in others[:2]:
                Beneficiary.objects.get_or_create(
                    owner=u, identifier=other.email, category='TRANSFER',
                    defaults={'name': other.full_name.split()[0]},
                )
            Beneficiary.objects.get_or_create(
                owner=u, identifier=str(random.randint(10000, 99999)),
                category='BILL_PAYMENT', provider='ENEO',
                defaults={'name': 'Home ENEO'},
            )
            Beneficiary.objects.get_or_create(
                owner=u, identifier=u.phone_number, category='AIRTIME', provider='MTN',
                defaults={'name': 'My MTN'},
            )
        self.stdout.write(self.style.SUCCESS('  beneficiaries done.'))

        # ── Spread timestamps over the last 30 days for nicer-looking history ─
        self.stdout.write('\nSpreading transaction dates over last 30 days…')
        now = timezone.now()
        for tx in Transaction.objects.filter(
            sender__email__endswith=DEMO_EMAIL_SUFFIX,
        ):
            days_ago = random.randint(0, 30)
            hours    = random.randint(0, 23)
            new_dt   = now - timedelta(days=days_ago, hours=hours)
            Transaction.objects.filter(pk=tx.pk).update(created_at=new_dt, updated_at=new_dt)
        self.stdout.write(self.style.SUCCESS('  dates spread.'))

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed complete. Login with any of: '
            f'{", ".join(u.email for u in users)} (password: demo1234)'
        ))

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _do_transfer(self, sender, recipient, amount, desc):
        sender.balance_xaf -= amount
        recipient.balance_xaf += amount
        sender.save(update_fields=['balance_xaf'])
        recipient.save(update_fields=['balance_xaf'])
        Transaction.objects.create(
            sender=sender, recipient=recipient,
            transaction_type='TRANSFER', status='COMPLETED',
            amount=amount, currency='XAF', description=desc,
        )

    def _do_deposit(self, user, amount, method):
        user.balance_xaf += amount
        user.save(update_fields=['balance_xaf'])
        Transaction.objects.create(
            recipient=user, transaction_type='DEPOSIT', status='COMPLETED',
            amount=amount, currency='XAF',
            description=f'{method.upper()} Money recharge',
            payment_method=method.upper(), payment_phone=user.phone_number,
        )

    def _do_bill(self, user, provider, meter, amount):
        if user.balance_xaf < amount:
            return
        user.balance_xaf -= amount
        user.save(update_fields=['balance_xaf'])
        Transaction.objects.create(
            sender=user, transaction_type='BILL_PAYMENT', status='COMPLETED',
            amount=amount, currency='XAF',
            description=f'{provider} — Ref: {meter}',
        )

    def _do_airtime(self, user, network, phone, amount):
        if user.balance_xaf < amount:
            return
        user.balance_xaf -= amount
        user.save(update_fields=['balance_xaf'])
        Transaction.objects.create(
            sender=user, transaction_type='AIRTIME', status='COMPLETED',
            amount=amount, currency='XAF',
            description=f'{network} Airtime — {phone}',
        )

    def _do_withdrawal(self, user, amount, method, phone):
        if user.balance_xaf < amount:
            return
        user.balance_xaf -= amount
        user.save(update_fields=['balance_xaf'])
        Transaction.objects.create(
            sender=user, transaction_type='WITHDRAWAL', status='COMPLETED',
            amount=amount, currency='XAF',
            description=f'{method} Money withdrawal — {phone}',
            payment_method=method, payment_phone=phone,
        )

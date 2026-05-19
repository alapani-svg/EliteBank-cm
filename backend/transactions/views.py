import logging
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction as db_transaction
from django.db.models import Q
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from .models import Transaction
from .serializers import (
    TransactionSerializer, TransferSerializer, DepositSerializer,
    BillPaymentSerializer, AirtimeSerializer, WithdrawalSerializer,
)

logger = logging.getLogger(__name__)


def _notify_deposit(txn, user_obj) -> None:
    from accounts.services.notifications import notify
    notify(
        user_obj, 'DEPOSIT', 'SUCCESS',
        title=f"Deposit received — {int(txn.amount):,} XAF",
        body=f"{int(txn.amount):,} XAF was credited to your account via {txn.payment_method} Money.",
        action_url=f"/transactions/{txn.id}/",
    )
    try:
        from .services.email import notify_deposit_completed
        notify_deposit_completed(txn, user_obj)
    except Exception as exc:
        logger.warning('Deposit email notification failed: %s', exc)


class TransactionListView(generics.ListAPIView):
    """
    GET /api/transactions/
    Returns all transactions where the authenticated user is sender OR recipient.
    Supports ?type=TRANSFER|DEPOSIT|WITHDRAWAL and ?status=COMPLETED|PENDING|FAILED
    """
    serializer_class   = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs   = Transaction.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient')

        txn_type   = self.request.query_params.get('type')
        txn_status = self.request.query_params.get('status')

        if txn_type:
            qs = qs.filter(transaction_type=txn_type.upper())
        if txn_status:
            qs = qs.filter(status=txn_status.upper())

        return qs


class TransactionDetailView(generics.RetrieveAPIView):
    """
    GET /api/transactions/<id>/
    Returns a single transaction if the authenticated user is sender or recipient.
    """
    serializer_class   = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Transaction.objects.filter(
            Q(sender=user) | Q(recipient=user)
        ).select_related('sender', 'recipient')


class TransferView(APIView):
    """
    POST /api/transactions/transfer/
    Every attempt — successful or failed — is immediately written to the DB as
    a PENDING record and then updated to COMPLETED or FAILED before responding.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from accounts.models import User as UserModel

        # ── 1. Pre-record the attempt ─────────────────────────────────────────
        # Extract raw values defensively so we can persist the record even if
        # the payload is malformed.
        pending_txn = None
        try:
            raw_amount = Decimal(str(request.data.get('amount', '0')))
            if raw_amount <= 0:
                raise ValueError('non-positive amount')

            raw_recipient_id = str(request.data.get('recipient_identifier', '')).strip()
            raw_description  = str(request.data.get('description', '')).strip()

            # Try to resolve the recipient now (may not exist)
            recipient_obj = None
            try:
                recipient_obj = UserModel.objects.get(email=raw_recipient_id)
            except UserModel.DoesNotExist:
                try:
                    recipient_obj = UserModel.objects.get(phone_number=raw_recipient_id)
                except UserModel.DoesNotExist:
                    pass

            # When the recipient cannot be resolved, embed the attempted
            # identifier in the description so audit logs are meaningful.
            description = raw_description
            if not recipient_obj and raw_recipient_id:
                label = f"Attempted to: {raw_recipient_id}"
                description = f"{label} — {raw_description}" if raw_description else label

            pending_txn = Transaction.objects.create(
                sender           = request.user,
                recipient        = recipient_obj,
                transaction_type = Transaction.TransactionType.TRANSFER,
                status           = Transaction.Status.PENDING,
                amount           = raw_amount,
                currency         = 'XAF',
                description      = description,
            )
        except Exception:
            # Pre-recording failed (e.g. completely invalid payload).
            # Continue — the serializer will surface proper validation errors.
            pass

        # ── 2. Validate and execute ───────────────────────────────────────────
        serializer = TransferSerializer(
            data=request.data,
            context={'request': request, 'pending_txn': pending_txn},
        )
        if not serializer.is_valid():
            if pending_txn:
                pending_txn.status = Transaction.Status.FAILED
                pending_txn.save(update_fields=['status'])
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            txn = serializer.save()
        except Exception as exc:
            # Catch race-condition failures (e.g. balance changed between
            # validation and the final SELECT FOR UPDATE check in create()).
            if pending_txn and pending_txn.status == Transaction.Status.PENDING:
                pending_txn.status = Transaction.Status.FAILED
                pending_txn.save(update_fields=['status'])
            logger.exception('Transfer execution failed after validation: %s', exc)
            return Response(
                {'detail': 'Transfer could not be completed. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            TransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )


# ── Deposit (mobile-money recharge) ──────────────────────────────────────────

class DepositInitiateView(APIView):
    """
    POST /api/transactions/deposit/initiate/
    Always creates a Transaction record before touching the payment gateway.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ── 1. Pre-record the attempt ─────────────────────────────────────────
        pending_txn = None
        try:
            raw_amount  = Decimal(str(request.data.get('amount', '0')))
            raw_phone   = str(request.data.get('phone', '')).strip()
            raw_method  = str(request.data.get('payment_method', '')).upper()
            if raw_amount > 0 and raw_phone:
                internal_ref = f"ELITE-DEP-{uuid.uuid4().hex[:12].upper()}"
                pending_txn = Transaction.objects.create(
                    recipient        = request.user,
                    transaction_type = Transaction.TransactionType.DEPOSIT,
                    status           = Transaction.Status.PENDING,
                    amount           = raw_amount,
                    currency         = 'XAF',
                    description      = f"{raw_method or 'Mobile'} Money recharge",
                    payment_reference= internal_ref,
                    payment_method   = raw_method,
                    payment_phone    = raw_phone,
                )
        except Exception:
            pass

        serializer = DepositSerializer(data=request.data)
        if not serializer.is_valid():
            if pending_txn:
                pending_txn.status = Transaction.Status.FAILED
                pending_txn.save(update_fields=['status'])
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user           = request.user
        amount         = serializer.validated_data['amount']
        phone          = serializer.validated_data['phone']
        payment_method = serializer.validated_data['payment_method']

        # Use the pre-created record's reference, or generate a new one if
        # pre-recording was skipped due to a bad payload.
        internal_ref = pending_txn.payment_reference if pending_txn else \
                       f"ELITE-DEP-{uuid.uuid4().hex[:12].upper()}"

        # ── DEMO MODE ─────────────────────────────────────────────────────────
        if not getattr(settings, 'NOTCHPAY_PUBLIC_KEY', ''):
            with db_transaction.atomic():
                user_obj = user.__class__.objects.select_for_update().get(pk=user.pk)
                user_obj.balance_xaf += amount
                user_obj.save(update_fields=['balance_xaf'])

                if pending_txn:
                    pending_txn.amount      = amount
                    pending_txn.description = f"{payment_method.upper()} Money recharge"
                    pending_txn.status      = Transaction.Status.COMPLETED
                    pending_txn.save(update_fields=['amount', 'description', 'status'])
                    txn = pending_txn
                else:
                    txn = Transaction.objects.create(
                        recipient        = user_obj,
                        transaction_type = Transaction.TransactionType.DEPOSIT,
                        status           = Transaction.Status.COMPLETED,
                        amount           = amount,
                        currency         = 'XAF',
                        description      = f"{payment_method.upper()} Money recharge",
                        payment_reference= internal_ref,
                        payment_method   = payment_method.upper(),
                        payment_phone    = phone,
                    )

            _notify_deposit(txn, user_obj)
            return Response({
                'status':    'completed',
                'reference': internal_ref,
                'message':   f'XAF {amount:,.0f} credited to your account.',
                'transaction': TransactionSerializer(txn).data,
            }, status=status.HTTP_201_CREATED)

        # ── LIVE / SANDBOX MODE ───────────────────────────────────────────────
        from .services.notchpay import initiate_deposit

        # Ensure the pending record has the final validated values
        if pending_txn:
            pending_txn.amount         = amount
            pending_txn.payment_method = payment_method.upper()
            pending_txn.payment_phone  = phone
            pending_txn.save(update_fields=['amount', 'payment_method', 'payment_phone'])
            txn = pending_txn
        else:
            txn = Transaction.objects.create(
                recipient        = user,
                transaction_type = Transaction.TransactionType.DEPOSIT,
                status           = Transaction.Status.PENDING,
                amount           = amount,
                currency         = 'XAF',
                description      = f"{payment_method.upper()} Money recharge",
                payment_reference= internal_ref,
                payment_method   = payment_method.upper(),
                payment_phone    = phone,
            )

        try:
            resp = initiate_deposit(
                amount         = int(amount),
                phone          = phone,
                payment_method = payment_method,
                email          = user.email,
                reference      = internal_ref,
                description    = f"Elite Bank deposit — {user.full_name}",
            )
        except Exception as e:
            txn.status = Transaction.Status.FAILED
            txn.save(update_fields=['status'])
            return Response(
                {'detail': f'Payment gateway error: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        np_status = resp.get('status', '')
        if np_status not in ('Accepted', 'Pending', 'pending'):
            txn.status = Transaction.Status.FAILED
            txn.save(update_fields=['status'])
            detail = resp.get('message', 'Payment initialization failed.')
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        np_ref = resp.get('transaction', {}).get('reference', internal_ref)
        if np_ref != internal_ref:
            txn.payment_reference = np_ref
            txn.save(update_fields=['payment_reference'])

        # ── SANDBOX AUTO-COMPLETE ─────────────────────────────────────────────
        is_test_key = 'pk_test' in getattr(settings, 'NOTCHPAY_PUBLIC_KEY', '')
        if is_test_key and np_status == 'Accepted':
            with db_transaction.atomic():
                user_obj = user.__class__.objects.select_for_update().get(pk=user.pk)
                txn_obj  = Transaction.objects.select_for_update().get(pk=txn.pk)
                if txn_obj.status == Transaction.Status.PENDING:
                    user_obj.balance_xaf += txn_obj.amount
                    user_obj.save(update_fields=['balance_xaf'])
                    txn_obj.status = Transaction.Status.COMPLETED
                    txn_obj.save(update_fields=['status'])
                    txn = txn_obj

            _notify_deposit(txn, user_obj)
            return Response({
                'status':    'completed',
                'reference': np_ref,
                'message':   f'XAF {int(amount):,} credited to your account.',
                'transaction': TransactionSerializer(txn).data,
            }, status=status.HTTP_201_CREATED)

        return Response({
            'status':    'pending',
            'reference': np_ref,
            'message':   'Payment initiated. Please approve the prompt on your phone.',
            'transaction': TransactionSerializer(txn).data,
        }, status=status.HTTP_201_CREATED)


class DepositStatusView(APIView):
    """
    GET /api/transactions/deposit/status/<reference>/
    Polls the status of a pending deposit.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        try:
            txn = Transaction.objects.get(
                payment_reference=reference,
                recipient=request.user,
                transaction_type=Transaction.TransactionType.DEPOSIT,
            )
        except Transaction.DoesNotExist:
            return Response({'detail': 'Deposit not found.'}, status=status.HTTP_404_NOT_FOUND)

        if txn.status in (Transaction.Status.COMPLETED, Transaction.Status.FAILED,
                          Transaction.Status.CANCELLED):
            return Response({
                'status':      txn.status,
                'reference':   reference,
                'transaction': TransactionSerializer(txn).data,
            })

        is_test_key = 'pk_test' in getattr(settings, 'NOTCHPAY_PUBLIC_KEY', '')
        if is_test_key:
            credited = False
            with db_transaction.atomic():
                user_obj = request.user.__class__.objects.select_for_update().get(pk=request.user.pk)
                txn_obj  = Transaction.objects.select_for_update().get(pk=txn.pk)
                if txn_obj.status == Transaction.Status.PENDING:
                    user_obj.balance_xaf += txn_obj.amount
                    user_obj.save(update_fields=['balance_xaf'])
                    txn_obj.status = Transaction.Status.COMPLETED
                    txn_obj.save(update_fields=['status'])
                    txn = txn_obj
                    credited = True
            if credited:
                _notify_deposit(txn, user_obj)
            return Response({
                'status':      txn.status,
                'reference':   reference,
                'transaction': TransactionSerializer(txn).data,
            })

        if not getattr(settings, 'NOTCHPAY_PUBLIC_KEY', ''):
            return Response({'status': txn.status, 'reference': reference,
                             'transaction': TransactionSerializer(txn).data})

        from .services.notchpay import verify_payment
        try:
            resp = verify_payment(reference)
        except Exception:
            return Response({'status': txn.status, 'reference': reference,
                             'transaction': TransactionSerializer(txn).data})

        np_status = (resp.get('transaction', {}).get('status') or '').lower()

        if np_status in ('complete', 'completed'):
            credited = False
            with db_transaction.atomic():
                user_obj = request.user.__class__.objects.select_for_update().get(pk=request.user.pk)
                txn_obj  = Transaction.objects.select_for_update().get(pk=txn.pk)
                if txn_obj.status == Transaction.Status.PENDING:
                    user_obj.balance_xaf += txn_obj.amount
                    user_obj.save(update_fields=['balance_xaf'])
                    txn_obj.status = Transaction.Status.COMPLETED
                    txn_obj.save(update_fields=['status'])
                    txn = txn_obj
                    credited = True
            if credited:
                _notify_deposit(txn, user_obj)

        elif np_status in ('failed', 'cancelled', 'canceled'):
            txn.status = Transaction.Status.FAILED
            txn.save(update_fields=['status'])

        return Response({
            'status':      txn.status,
            'reference':   reference,
            'transaction': TransactionSerializer(txn).data,
        })


class DepositCallbackView(APIView):
    """
    POST /api/transactions/deposit/callback/
    Webhook called by NotchPay when a payment status changes.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data      = request.data
        reference = data.get('reference') or data.get('trxref')
        np_status = (data.get('status') or '').lower()

        if not reference:
            return Response({'detail': 'No reference provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            txn = Transaction.objects.get(
                payment_reference=reference,
                transaction_type=Transaction.TransactionType.DEPOSIT,
            )
        except Transaction.DoesNotExist:
            return Response({'detail': 'Transaction not found.'}, status=status.HTTP_404_NOT_FOUND)

        if txn.status != Transaction.Status.PENDING:
            return Response({'detail': 'Already processed.'})

        credited = False
        if np_status in ('complete', 'completed'):
            with db_transaction.atomic():
                user_obj = txn.recipient.__class__.objects.select_for_update().get(pk=txn.recipient.pk)
                txn_obj  = Transaction.objects.select_for_update().get(pk=txn.pk)
                if txn_obj.status == Transaction.Status.PENDING:
                    user_obj.balance_xaf += txn_obj.amount
                    user_obj.save(update_fields=['balance_xaf'])
                    txn_obj.status = Transaction.Status.COMPLETED
                    txn_obj.save(update_fields=['status'])
                    txn = txn_obj
                    credited = True
            if credited:
                _notify_deposit(txn, user_obj)
        elif np_status in ('failed', 'cancelled', 'canceled'):
            txn.status = Transaction.Status.FAILED
            txn.save(update_fields=['status'])

        return Response({'detail': 'Callback processed.'}, status=status.HTTP_200_OK)


# ── Bill Payment ──────────────────────────────────────────────────────────────

class BillPaymentView(APIView):
    """
    POST /api/transactions/bill-payment/
    Deduct balance and record a utility bill payment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BillPaymentSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            txn = serializer.save()
        except Exception as exc:
            logger.exception('Bill payment failed: %s', exc)
            return Response(
                {'detail': 'Payment could not be processed. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            TransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )


# ── Airtime Purchase ──────────────────────────────────────────────────────────

class AirtimeView(APIView):
    """
    POST /api/transactions/airtime/
    Deduct balance and record an airtime purchase.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AirtimeSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            txn = serializer.save()
        except Exception as exc:
            logger.exception('Airtime purchase failed: %s', exc)
            return Response(
                {'detail': 'Airtime purchase could not be processed. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            TransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )


# ── Withdrawal (mobile-money cash-out) ────────────────────────────────────────

class WithdrawalView(APIView):
    """
    POST /api/transactions/withdrawal/
    Pre-records a PENDING transaction so every attempt is audited; on success it
    becomes COMPLETED, on validation/race failure it becomes FAILED.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ── 1. Pre-record the attempt ────────────────────────────────────────
        pending_txn = None
        try:
            raw_amount = Decimal(str(request.data.get('amount', '0')))
            raw_phone  = str(request.data.get('phone', '')).strip()
            raw_method = str(request.data.get('payment_method', '')).upper()
            if raw_amount > 0 and raw_phone:
                pending_txn = Transaction.objects.create(
                    sender           = request.user,
                    transaction_type = Transaction.TransactionType.WITHDRAWAL,
                    status           = Transaction.Status.PENDING,
                    amount           = raw_amount,
                    currency         = 'XAF',
                    description      = f"{raw_method or 'Mobile'} Money withdrawal",
                    payment_method   = raw_method,
                    payment_phone    = raw_phone,
                )
        except Exception:
            pass

        # ── 2. Validate ──────────────────────────────────────────────────────
        serializer = WithdrawalSerializer(
            data=request.data,
            context={'request': request, 'pending_txn': pending_txn},
        )
        if not serializer.is_valid():
            if pending_txn:
                pending_txn.status = Transaction.Status.FAILED
                pending_txn.save(update_fields=['status'])
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ── 3. Execute ───────────────────────────────────────────────────────
        try:
            txn = serializer.save()
        except Exception as exc:
            if pending_txn and pending_txn.status == Transaction.Status.PENDING:
                pending_txn.status = Transaction.Status.FAILED
                pending_txn.save(update_fields=['status'])
            logger.exception('Withdrawal failed: %s', exc)
            return Response(
                {'detail': 'Withdrawal could not be completed. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'status':      'completed',
            'reference':   txn.reference,
            'message':     f'XAF {int(txn.amount):,} sent to {txn.payment_phone}.',
            'transaction': TransactionSerializer(txn).data,
        }, status=status.HTTP_201_CREATED)


# ── Statement (PDF / CSV) ─────────────────────────────────────────────────────

class StatementView(APIView):
    """
    GET /api/transactions/statement/?from=YYYY-MM-DD&to=YYYY-MM-DD&fmt=pdf|csv

    Both `from` and `to` are optional. Defaults:
      from = today - 30 days
      to   = today

    NOTE: the format parameter is named `fmt` (not `format`) because DRF reserves
    `?format=` for content-negotiation between renderers.

    Returns the statement as an attachment.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # NOTE: we use `fmt` (not `format`) because DRF reserves `?format=` for
        # renderer content-negotiation, which would 404 on unknown values.
        fmt = request.query_params.get('fmt', 'pdf').lower()
        if fmt not in ('pdf', 'csv'):
            return Response({'detail': 'fmt must be pdf or csv.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Parse date range
        today = timezone.localdate()
        try:
            date_from = self._parse_date(request.query_params.get('from')) or (today - timedelta(days=30))
            date_to   = self._parse_date(request.query_params.get('to'))   or today
        except ValueError:
            return Response({'detail': 'Dates must be YYYY-MM-DD.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if date_from > date_to:
            return Response({'detail': '`from` must be before `to`.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Build inclusive datetime range in the active timezone
        tz = timezone.get_current_timezone()
        dt_from = timezone.make_aware(datetime.combine(date_from, time.min), tz)
        dt_to   = timezone.make_aware(datetime.combine(date_to,   time.max), tz)

        user = request.user
        qs = (Transaction.objects
              .filter(Q(sender=user) | Q(recipient=user),
                      created_at__gte=dt_from,
                      created_at__lte=dt_to)
              .select_related('sender', 'recipient')
              .order_by('-created_at'))

        from .services.statement import render_csv, render_pdf
        filename_stub = f"elite-statement-{date_from.isoformat()}_{date_to.isoformat()}"

        if fmt == 'csv':
            content = render_csv(qs, user)
            response = HttpResponse(content, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename_stub}.csv"'
            return response

        content = render_pdf(qs, user, dt_from, dt_to)
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename_stub}.pdf"'
        return response

    @staticmethod
    def _parse_date(s):
        if not s:
            return None
        return datetime.strptime(s, '%Y-%m-%d').date()

from django.contrib import admin, messages
from django.db.models import Q, Sum, Count, DecimalField
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Transaction

# ── Filters ───────────────────────────────────────────────────────────────────

class HasPaymentReferenceFilter(admin.SimpleListFilter):
    title        = 'Payment reference'
    parameter_name = 'has_payment_ref'

    def lookups(self, request, model_admin):
        return [
            ('yes', 'Has external reference'),
            ('no',  'No external reference'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(payment_reference='')
        if self.value() == 'no':
            return queryset.filter(payment_reference='')
        return queryset


# ── Transaction admin ─────────────────────────────────────────────────────────

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):

    # ── List view ─────────────────────────────────────────────────────────────
    list_display = (
        'reference_display', 'type_badge', 'status_badge',
        'amount_display', 'sender_col', 'recipient_col',
        'method_col', 'created_at',
    )
    list_filter  = (
        'transaction_type', 'status',
        'payment_method', 'currency',
        HasPaymentReferenceFilter,
        'created_at',
    )
    search_fields = (
        'reference', 'payment_reference', 'description',
        'sender__email', 'sender__full_name',
        'recipient__email', 'recipient__full_name',
        'payment_phone',
    )
    ordering       = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page  = 30

    # ── Detail view ───────────────────────────────────────────────────────────
    readonly_fields = (
        'id', 'reference',
        'sender', 'recipient',
        'transaction_type', 'amount', 'currency', 'description',
        'payment_reference', 'payment_method', 'payment_phone',
        'created_at', 'updated_at',
        'parties_summary',
    )

    fieldsets = (
        (_('Reference'), {
            'fields': ('id', 'reference'),
        }),
        (_('Parties'), {
            'fields': ('parties_summary', 'sender', 'recipient'),
        }),
        (_('Transaction Details'), {
            'fields': ('transaction_type', 'status', 'amount', 'currency', 'description'),
        }),
        (_('Mobile Money'), {
            'fields':  ('payment_reference', 'payment_method', 'payment_phone'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    # Only status is editable (so admins can manually resolve stuck PENDING txns)
    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj:
            return ro      # 'status' is NOT in readonly_fields → stays editable
        return ro + ['status']

    # ── Bulk actions ──────────────────────────────────────────────────────────
    actions = ['action_mark_completed', 'action_mark_failed', 'action_mark_cancelled']

    # ── Custom columns ────────────────────────────────────────────────────────

    def reference_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;font-size:12px;">{}</span>',
            obj.reference,
        )
    reference_display.short_description = 'Reference'
    reference_display.admin_order_field = 'reference'

    def type_badge(self, obj):
        palette = {
            'TRANSFER':   ('#0d6efd', '#e7f1ff'),
            'DEPOSIT':    ('#198754', '#d1e7dd'),
            'WITHDRAWAL': ('#fd7e14', '#fff3cd'),
        }
        color, bg = palette.get(obj.transaction_type, ('#6c757d', '#f8f9fa'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
            'font-size:11px;font-weight:700;">{}</span>',
            bg, color, obj.get_transaction_type_display(),
        )
    type_badge.short_description = 'Type'
    type_badge.admin_order_field = 'transaction_type'

    def status_badge(self, obj):
        palette = {
            'COMPLETED': ('#155724', '#d4edda'),
            'PENDING':   ('#856404', '#fff3cd'),
            'FAILED':    ('#721c24', '#f8d7da'),
            'CANCELLED': ('#495057', '#e2e3e5'),
        }
        color, bg = palette.get(obj.status, ('#333', '#eee'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:10px;'
            'font-size:11px;font-weight:700;">{}</span>',
            bg, color, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def amount_display(self, obj):
        is_credit = obj.transaction_type == Transaction.TransactionType.DEPOSIT
        sign  = '+' if is_credit else ''
        color = '#198754' if is_credit else '#212529'
        return format_html(
            '<strong style="color:{};font-size:13px;">{}{:,.0f}&nbsp;{}</strong>',
            color, sign, obj.amount, obj.currency,
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def sender_col(self, obj):
        if not obj.sender:
            return format_html('<span style="color:#aaa;">—</span>')
        return format_html(
            '<span title="{}">{}</span>',
            obj.sender.email, obj.sender.full_name,
        )
    sender_col.short_description = 'Sender'

    def recipient_col(self, obj):
        if not obj.recipient:
            return format_html('<span style="color:#aaa;">—</span>')
        return format_html(
            '<span title="{}">{}</span>',
            obj.recipient.email, obj.recipient.full_name,
        )
    recipient_col.short_description = 'Recipient'

    def method_col(self, obj):
        if not obj.payment_method:
            return format_html('<span style="color:#aaa;">—</span>')
        colours = {'ORANGE': '#FF6B1A', 'MTN': '#FFC300'}
        color   = colours.get(obj.payment_method.upper(), '#555')
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>',
            color, obj.payment_method,
        )
    method_col.short_description = 'Method'

    def parties_summary(self, obj):
        sender_html = (
            format_html(
                '<strong>{}</strong><br/><small style="color:#888;">{}</small>',
                obj.sender.full_name, obj.sender.email,
            ) if obj.sender else format_html('<em>—</em>')
        )
        recipient_html = (
            format_html(
                '<strong>{}</strong><br/><small style="color:#888;">{}</small>',
                obj.recipient.full_name, obj.recipient.email,
            ) if obj.recipient else format_html('<em>—</em>')
        )
        return format_html(
            '<table style="border-collapse:collapse;min-width:360px;">'
            '<tr><td style="padding:6px 16px 6px 0;color:#888;font-size:12px;'
            'font-weight:600;text-transform:uppercase;letter-spacing:.05em;">From</td>'
            '<td>{}</td></tr>'
            '<tr><td style="padding:6px 16px 6px 0;color:#888;font-size:12px;'
            'font-weight:600;text-transform:uppercase;letter-spacing:.05em;">To</td>'
            '<td>{}</td></tr>'
            '</table>',
            sender_html, recipient_html,
        )
    parties_summary.short_description = 'Transfer Summary'

    # ── Actions ───────────────────────────────────────────────────────────────

    @admin.action(description='✓ Mark selected PENDING transactions as COMPLETED')
    def action_mark_completed(self, request, queryset):
        n = queryset.filter(status=Transaction.Status.PENDING).update(
            status=Transaction.Status.COMPLETED
        )
        self.message_user(request, f'{n} transaction(s) marked as COMPLETED.', messages.SUCCESS)

    @admin.action(description='✗ Mark selected PENDING transactions as FAILED')
    def action_mark_failed(self, request, queryset):
        n = queryset.filter(status=Transaction.Status.PENDING).update(
            status=Transaction.Status.FAILED
        )
        self.message_user(request, f'{n} transaction(s) marked as FAILED.', messages.WARNING)

    @admin.action(description='⊘ Mark selected PENDING transactions as CANCELLED')
    def action_mark_cancelled(self, request, queryset):
        n = queryset.filter(status=Transaction.Status.PENDING).update(
            status=Transaction.Status.CANCELLED
        )
        self.message_user(request, f'{n} transaction(s) marked as CANCELLED.', messages.WARNING)

    # ── Summary stats in changelist ───────────────────────────────────────────

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        # Apply any filters the user has set
        try:
            cl = self.get_changelist_instance(request)
            qs = cl.queryset
        except Exception:
            pass

        totals = qs.aggregate(
            count       = Count('id'),
            volume      = Coalesce(Sum('amount'), 0, output_field=DecimalField()),
            completed   = Count('id', filter=Q(status='COMPLETED')),
            pending     = Count('id', filter=Q(status='PENDING')),
            failed      = Count('id', filter=Q(status='FAILED')),
            deposits    = Count('id', filter=Q(transaction_type='DEPOSIT')),
            transfers   = Count('id', filter=Q(transaction_type='TRANSFER')),
        )

        extra_context = extra_context or {}
        extra_context['totals'] = totals
        return super().changelist_view(request, extra_context=extra_context)

"""
Generates account statements in CSV or PDF for a date range.
Used by `StatementView` to produce downloadable files.
"""
import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)


# Brand palette
GOLD       = colors.HexColor('#D4AF37')
GOLD_DIM   = colors.HexColor('#A8842B')
DARK       = colors.HexColor('#12110F')
TEXT_MUTED = colors.HexColor('#777777')

# Status palette — colored cell fills with matching text colors.
STATUS_COLORS = {
    'COMPLETED': (colors.HexColor('#E8F6F0'), colors.HexColor('#1F7A55')),
    'PENDING':   (colors.HexColor('#FBF1D6'), colors.HexColor('#A07E18')),
    'FAILED':    (colors.HexColor('#FCE8E8'), colors.HexColor('#B33A3A')),
    'CANCELLED': (colors.HexColor('#EEEEEE'), colors.HexColor('#666666')),
}

# Compact, human-readable type labels (the raw values are LIKE_THIS).
TYPE_LABELS = {
    'TRANSFER':     'Transfer',
    'DEPOSIT':      'Deposit',
    'WITHDRAWAL':   'Withdrawal',
    'BILL_PAYMENT': 'Bill',
    'AIRTIME':      'Airtime',
}

SUPPORT_EMAIL = 'promptforge237@gmail.com'


def _direction(txn, user) -> str:
    """Return 'IN' if the transaction credits the user, else 'OUT'."""
    if txn.transaction_type == 'DEPOSIT':
        return 'IN'
    if txn.transaction_type == 'TRANSFER' and txn.recipient_id == user.id:
        return 'IN'
    return 'OUT'


def _signed_amount(txn, user) -> Decimal:
    sign = Decimal('1') if _direction(txn, user) == 'IN' else Decimal('-1')
    return sign * (txn.amount or Decimal('0'))


# ── CSV ────────────────────────────────────────────────────────────────────────

def render_csv(transactions: Iterable, user) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Reference', 'Date', 'Type', 'Status',
        'Counterparty', 'Description', 'Direction', 'Amount (XAF)',
    ])
    for txn in transactions:
        counterparty = ''
        if txn.transaction_type == 'TRANSFER':
            if _direction(txn, user) == 'IN':
                counterparty = txn.sender.full_name if txn.sender else ''
            else:
                counterparty = txn.recipient.full_name if txn.recipient else ''
        elif txn.transaction_type in ('DEPOSIT', 'WITHDRAWAL'):
            counterparty = f"{txn.payment_method} {txn.payment_phone}".strip()
        elif txn.transaction_type == 'AIRTIME':
            counterparty = txn.payment_phone or ''

        writer.writerow([
            txn.reference,
            timezone.localtime(txn.created_at).strftime('%Y-%m-%d %H:%M'),
            txn.transaction_type,
            txn.status,
            counterparty,
            (txn.description or '')[:120],
            _direction(txn, user),
            f"{_signed_amount(txn, user):.2f}",
        ])
    return buf.getvalue().encode('utf-8')


# ── PDF ────────────────────────────────────────────────────────────────────────

def render_pdf(transactions, user, date_from: datetime, date_to: datetime) -> bytes:
    transactions = list(transactions)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
        title='Elite Bank Account Statement',
        author='Elite Bank',
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'],
        fontName='Helvetica-Bold', fontSize=22, textColor=GOLD, alignment=0,
        spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        'Sub', parent=styles['Normal'],
        fontSize=9, textColor=TEXT_MUTED, spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        'Meta', parent=styles['Normal'],
        fontSize=10, textColor=DARK, spaceAfter=2,
    )
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, textColor=TEXT_MUTED, alignment=1, leading=11,
    )
    desc_style = ParagraphStyle(
        'Desc', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, textColor=DARK, leading=10,
    )
    status_style = ParagraphStyle(
        'Status', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=7, alignment=1, leading=9,
    )

    elements = [
        Paragraph('ELITE BANK', title_style),
        Paragraph('Premium Account · Cameroon Digital Wealth', sub_style),
        Spacer(1, 6),
        Paragraph(f"<b>Account holder:</b> {user.full_name}", meta_style),
        Paragraph(f"<b>Email:</b> {user.email}", meta_style),
        Paragraph(f"<b>Phone:</b> {user.phone_number}", meta_style),
        Paragraph(
            f"<b>Statement period:</b> "
            f"{date_from.strftime('%d %b %Y')} → {date_to.strftime('%d %b %Y')}",
            meta_style,
        ),
        Paragraph(f"<b>Issued:</b> {timezone.localtime().strftime('%d %b %Y · %H:%M')}", meta_style),
        Spacer(1, 12),
    ]

    # ── Summary card ──────────────────────────────────────────────────────────
    inflow  = sum((t.amount for t in transactions if _direction(t, user) == 'IN'),  Decimal('0'))
    outflow = sum((t.amount for t in transactions if _direction(t, user) == 'OUT'), Decimal('0'))
    summary = Table([
        ['Total inflow',    f"+ {inflow:,.0f} XAF"],
        ['Total outflow',   f"− {outflow:,.0f} XAF"],
        ['Net movement',    f"{(inflow - outflow):+,.0f} XAF"],
        ['Closing balance', f"{user.balance_xaf:,.0f} XAF"],
    ], colWidths=[60*mm, 60*mm])
    summary.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 10),
        ('TEXTCOLOR',     (0, 0), (0, -1),  TEXT_MUTED),
        ('TEXTCOLOR',     (1, 0), (1, -1),  DARK),
        ('FONTNAME',      (1, -1), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR',     (1, -1), (1, -1), GOLD_DIM),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
    ]))
    elements += [summary, Spacer(1, 14)]

    # ── Transactions table ────────────────────────────────────────────────────
    # Column widths (A4 width 210mm − 30mm margins = 180mm usable):
    #   Date 24, Reference 34, Type 18, Description 56, Status 22, Amount 26 = 180
    header = ['Date', 'Reference', 'Type', 'Description', 'Status', 'Amount (XAF)']
    data = [header]
    status_cells = []  # Track (row_idx, status) for per-row coloring
    for i, txn in enumerate(transactions, start=1):
        signed = _signed_amount(txn, user)
        amount_str = f"{signed:+,.0f}"
        type_label = TYPE_LABELS.get(txn.transaction_type, txn.transaction_type.title())
        description = (txn.description or '').strip()
        status = txn.status

        data.append([
            timezone.localtime(txn.created_at).strftime('%d %b %Y\n%H:%M'),
            txn.reference,
            type_label,
            Paragraph(description, desc_style),
            Paragraph(f'<b>{status}</b>', status_style),
            amount_str,
        ])
        status_cells.append((i, status))

    if len(data) == 1:
        elements.append(Paragraph(
            '<i>No transactions in this period.</i>',
            ParagraphStyle('empty', fontSize=10, textColor=TEXT_MUTED, alignment=1),
        ))
    else:
        table = Table(
            data,
            colWidths=[24*mm, 34*mm, 18*mm, 56*mm, 22*mm, 26*mm],
            repeatRows=1,
        )
        style_cmds = [
            # Header
            ('BACKGROUND',    (0, 0), (-1, 0), DARK),
            ('TEXTCOLOR',     (0, 0), (-1, 0), GOLD),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('TOPPADDING',    (0, 0), (-1, 0), 7),
            ('ALIGN',         (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN',         (4, 0), (4, 0), 'CENTER'),
            ('ALIGN',         (5, 0), (5, 0), 'RIGHT'),
            # Body — uniform sizing & padding so colored status cells fit cleanly
            ('FONTSIZE',      (0, 1), (-1, -1), 8),
            ('FONTNAME',      (1, 1), (1, -1), 'Helvetica'),
            ('TEXTCOLOR',     (1, 1), (1, -1), GOLD_DIM),
            ('TOPPADDING',    (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 5),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',         (5, 1), (5, -1), 'RIGHT'),
            ('ALIGN',         (4, 1), (4, -1), 'CENTER'),
            ('FONTNAME',      (5, 1), (5, -1), 'Helvetica-Bold'),
            ('GRID',          (0, 0), (-1, -1), 0.25, colors.HexColor('#E5E5E5')),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')]),
            # Inset the colored status cell slightly so it reads as a pill
            ('TOPPADDING',    (4, 1), (4, -1), 4),
            ('BOTTOMPADDING', (4, 1), (4, -1), 4),
            ('LEFTPADDING',   (4, 1), (4, -1), 3),
            ('RIGHTPADDING',  (4, 1), (4, -1), 3),
        ]

        # Per-row status coloring (background + text inside the Paragraph).
        for row, status in status_cells:
            bg, fg = STATUS_COLORS.get(status, (colors.HexColor('#EEEEEE'), DARK))
            style_cmds.append(('BACKGROUND', (4, row), (4, row), bg))
            style_cmds.append(('TEXTCOLOR',  (4, row), (4, row), fg))
            # Amount color follows direction sign
            if str(data[row][5]).startswith('+'):
                style_cmds.append(('TEXTCOLOR', (5, row), (5, row), colors.HexColor('#1F7A55')))
            else:
                style_cmds.append(('TEXTCOLOR', (5, row), (5, row), colors.HexColor('#B33A3A')))

        table.setStyle(TableStyle(style_cmds))
        elements.append(table)

    elements += [
        Spacer(1, 18),
        Paragraph(
            f'This statement was generated electronically by Elite Bank. '
            f'Please contact {SUPPORT_EMAIL} for any discrepancies.<br/>'
            f'<b>Built by CORANTIN</b> · Yaoundé, Cameroon',
            footer_style,
        ),
    ]

    doc.build(elements)
    return buf.getvalue()

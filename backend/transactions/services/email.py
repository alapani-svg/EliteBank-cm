import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


# ── Async sender ─────────────────────────────────────────────────────────────

def _send_async(subject: str, text: str, html: str, to: str) -> None:
    def _task():
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to],
            )
            msg.attach_alternative(html, 'text/html')
            msg.send(fail_silently=False)
            logger.info('Email sent to %s — %s', to, subject)
        except Exception as exc:
            logger.warning('Email failed to %s: %s', to, exc)

    threading.Thread(target=_task, daemon=True).start()


# ── HTML building blocks ──────────────────────────────────────────────────────

def _row(label: str, value: str, bg: str = '#ffffff', val_color: str = '#111111') -> str:
    return (
        f'<tr style="background:{bg};">'
        f'<td style="padding:11px 16px;color:#888888;font-size:13px;'
        f'border-top:1px solid #eeeeee;width:42%;">{label}</td>'
        f'<td style="padding:11px 16px;color:{val_color};font-size:13px;'
        f'font-weight:600;border-top:1px solid #eeeeee;">{value}</td>'
        f'</tr>'
    )


def _wrap(amount_label: str, amount_value: str, amount_color: str, body_html: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Elite Bank Notification</title>
</head>
<body style="margin:0;padding:0;background:#f0ede8;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#f0ede8;padding:36px 12px;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:14px;overflow:hidden;
                  max-width:560px;width:100%;
                  box-shadow:0 4px 20px rgba(0,0,0,0.10);">

      <!-- Branding header -->
      <tr>
        <td style="background:#12110F;padding:22px 32px;text-align:center;">
          <span style="font-size:19px;font-weight:900;color:#D4AF37;
                       letter-spacing:4px;text-transform:uppercase;">
            ELITE BANK
          </span>
        </td>
      </tr>

      <!-- Amount banner -->
      <tr>
        <td style="background:#1E1C19;padding:30px 32px;text-align:center;">
          <p style="color:#c8bfaf;margin:0 0 6px;font-size:11px;
                    letter-spacing:1.5px;text-transform:uppercase;">
            {amount_label}
          </p>
          <p style="color:{amount_color};font-size:36px;font-weight:900;
                    margin:0;letter-spacing:-0.5px;">
            {amount_value}
          </p>
        </td>
      </tr>

      <!-- Main body -->
      <tr>
        <td style="padding:28px 32px;">
          {body_html}
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#12110F;padding:18px 32px;text-align:center;">
          <p style="color:#736b5a;font-size:11px;margin:0;">
            © 2026 Elite Bank &nbsp;·&nbsp; Yaoundé, Cameroon
          </p>
          <p style="color:#736b5a;font-size:11px;margin:4px 0 0;">
            Automated notification — please do not reply to this email.
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>'''


# ── Transfer notifications ────────────────────────────────────────────────────

def notify_transfer_received(txn, recipient, sender) -> None:
    """Email the recipient after an incoming transfer is confirmed."""
    if not getattr(recipient, 'email_notifications', True):
        return

    amount      = int(txn.amount)
    description = txn.description or '—'
    new_balance = int(recipient.balance_xaf)
    subject     = f"You received XAF {amount:,} from {sender.full_name} — Elite Bank"

    text = (
        f"Dear {recipient.full_name},\n\n"
        f"You have received a transfer to your Elite Bank account.\n\n"
        f"From:        {sender.full_name} ({sender.email})\n"
        f"Amount:      XAF {amount:,}\n"
        f"Reference:   {txn.reference}\n"
        f"Description: {description}\n"
        f"New Balance: XAF {new_balance:,}\n\n"
        f"Not expecting this transfer? Contact support immediately at "
        f"support@elite-bank.cm\n\n"
        f"— Elite Bank Team"
    )

    detail_table = (
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="border:1px solid #eeeeee;border-radius:8px;overflow:hidden;">'
        + _row('From',        f'{sender.full_name}<br><span style="color:#aaaaaa;font-weight:400;">'
                              f'{sender.email}</span>')
        + _row('Amount',      f'XAF {amount:,}', bg='#f9f9f9', val_color='#3DAA7A')
        + _row('Reference',   f'<span style="font-family:monospace;">{txn.reference}</span>')
        + _row('Description', description,       bg='#f9f9f9')
        + _row('New Balance', f'XAF {new_balance:,}')
        + '</table>'
    )

    warning = (
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:20px;background:#FFFBEB;border:1px solid #F59E0B;border-radius:8px;">'
        '<tr><td style="padding:12px 16px;color:#92400E;font-size:13px;line-height:1.5;">'
        '<strong>Not expecting this?</strong> If you did not authorise this transfer, '
        'please contact Elite Bank support immediately at '
        '<a href="mailto:support@elite-bank.cm" style="color:#92400E;">support@elite-bank.cm</a>.'
        '</td></tr></table>'
    )

    body = (
        f'<p style="color:#222222;font-size:15px;margin:0 0 18px;">'
        f'Dear <strong>{recipient.full_name}</strong>,</p>'
        f'<p style="color:#555555;font-size:14px;line-height:1.65;margin:0 0 20px;">'
        f'A transfer has just been credited to your Elite Bank account.</p>'
        + detail_table + warning
    )

    _send_async(
        subject, text,
        _wrap('Amount Received', f'+&nbsp;XAF&nbsp;{amount:,}', '#3DAA7A', body),
        recipient.email,
    )


def notify_transfer_sent(txn, sender, recipient) -> None:
    """Email the sender confirming their transfer was processed."""
    if not getattr(sender, 'email_notifications', True):
        return

    amount         = int(txn.amount)
    description    = txn.description or '—'
    remain_balance = int(sender.balance_xaf)
    subject        = f"Transfer of XAF {amount:,} to {recipient.full_name} confirmed — Elite Bank"

    text = (
        f"Dear {sender.full_name},\n\n"
        f"Your transfer has been processed successfully.\n\n"
        f"To:                {recipient.full_name} ({recipient.email})\n"
        f"Amount:            XAF {amount:,}\n"
        f"Reference:         {txn.reference}\n"
        f"Description:       {description}\n"
        f"Remaining Balance: XAF {remain_balance:,}\n\n"
        f"— Elite Bank Team"
    )

    detail_table = (
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="border:1px solid #eeeeee;border-radius:8px;overflow:hidden;">'
        + _row('To',               f'{recipient.full_name}<br><span style="color:#aaaaaa;font-weight:400;">'
                                   f'{recipient.email}</span>')
        + _row('Amount',           f'XAF {amount:,}',        bg='#f9f9f9', val_color='#B8922B')
        + _row('Reference',        f'<span style="font-family:monospace;">{txn.reference}</span>')
        + _row('Description',      description,              bg='#f9f9f9')
        + _row('Remaining Balance', f'XAF {remain_balance:,}')
        + '</table>'
    )

    body = (
        f'<p style="color:#222222;font-size:15px;margin:0 0 18px;">'
        f'Dear <strong>{sender.full_name}</strong>,</p>'
        f'<p style="color:#555555;font-size:14px;line-height:1.65;margin:0 0 20px;">'
        f'Your transfer has been processed successfully. Here are the details:</p>'
        + detail_table
    )

    _send_async(
        subject, text,
        _wrap('Transfer Confirmed', f'XAF&nbsp;{amount:,}', '#D4AF37', body),
        sender.email,
    )


# ── Deposit notification ──────────────────────────────────────────────────────

def notify_deposit_completed(txn, user) -> None:
    """Email the user when a mobile-money deposit is credited."""
    if not getattr(user, 'email_notifications', True):
        return

    amount      = int(txn.amount)
    method      = txn.payment_method or 'Mobile Money'
    new_balance = int(user.balance_xaf)
    subject     = f"XAF {amount:,} deposit credited to your account — Elite Bank"

    text = (
        f"Dear {user.full_name},\n\n"
        f"Your {method} deposit has been credited to your Elite Bank account.\n\n"
        f"Amount:      XAF {amount:,}\n"
        f"Method:      {method}\n"
        f"Reference:   {txn.payment_reference}\n"
        f"New Balance: XAF {new_balance:,}\n\n"
        f"— Elite Bank Team"
    )

    detail_table = (
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="border:1px solid #eeeeee;border-radius:8px;overflow:hidden;">'
        + _row('Amount',      f'XAF {amount:,}',        val_color='#3DAA7A')
        + _row('Method',      method,                   bg='#f9f9f9')
        + _row('Reference',   f'<span style="font-family:monospace;">{txn.payment_reference}</span>')
        + _row('New Balance', f'XAF {new_balance:,}',   bg='#f9f9f9')
        + '</table>'
    )

    body = (
        f'<p style="color:#222222;font-size:15px;margin:0 0 18px;">'
        f'Dear <strong>{user.full_name}</strong>,</p>'
        f'<p style="color:#555555;font-size:14px;line-height:1.65;margin:0 0 20px;">'
        f'Your {method} recharge has been credited to your Elite Bank account.</p>'
        + detail_table
    )

    _send_async(
        subject, text,
        _wrap('Deposit Credited', f'+&nbsp;XAF&nbsp;{amount:,}', '#3DAA7A', body),
        user.email,
    )

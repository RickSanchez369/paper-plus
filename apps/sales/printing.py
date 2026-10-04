"""
What the printed sales invoice shows beyond the invoice itself (D-088): brand and
contacts, the small print, how the invoice was (or will be) settled, and a thank-you
line. Read-only helpers for SalesPrintView; nothing here writes.
"""

from django.conf import settings

from apps.payments.models import BankAccount, Cheque

# A blank .env key must not blank the paper: these are the owner's own details.
_DEFAULTS = {
    "brand": "کاغذ پلاس",
    "phones": "خندانی:09145572511,حقگو:09145589832",
    "email": "kaghazplus1@gmail.com",
}

_DEFAULT_TERMS = (
    "لطفاً کالا را هنگام تحویل بررسی کنید؛ کسری یا آسیب را همان لحظه اطلاع دهید.",
    "مبلغ نسیه و چک‌ها در تاریخ‌های سررسید درج‌شده در همین برگه تسویه شود.",
    "این صورت‌حساب بدون مهر و امضای فروشنده اعتبار ندارد.",
)

# One is picked per invoice (stable, so a reprint carries the same line).
THANK_YOU_LINES = (
    "از اعتماد شما سپاسگزاریم؛ همیشه در کنارتان هستیم.",
    "خرید شما انگیزهٔ ما برای بهتر شدن است. سپاس!",
    "سپاس که ما را انتخاب کردید؛ منتظر دیدار دوباره‌تان هستیم.",
    "همکاری با شما برای ما مایهٔ افتخار است.",
    "هر برگ از این سفارش با احترام برای شما آماده شد.",
    "از معامله با شما خرسندیم؛ تا سفارش بعدی!",
    "اعتماد شما سرمایهٔ ماست؛ از همراهی‌تان ممنونیم.",
    "روزهایتان مثل کاغذ نو، سفید و پر از فرصت!",
    "امیدواریم این خرید آغاز همکاری‌های بیشتری باشد.",
    "رضایت شما بهترین کارنامهٔ ماست؛ سپاسگزاریم.",
    "ممنون از خریدتان؛ کاغذ پلاس همیشه آمادهٔ خدمت است.",
    "با سپاس از انتخاب شما؛ سفارش بعدی را با همین دقت آماده می‌کنیم.",
)


def company_print_info():
    """settings.COMPANY plus the print defaults, with the phone list split into (name, number)."""
    company = dict(settings.COMPANY)
    for key, default in _DEFAULTS.items():
        company[key] = company.get(key) or default
    phones = []
    for part in company["phones"].split(","):
        name, _, number = part.strip().rpartition(":")
        if number:
            phones.append({"name": name.strip(), "number": number.strip()})
    company["phone_list"] = phones
    terms = [t.strip() for t in (company.get("terms") or "").split("|") if t.strip()]
    company["term_list"] = terms or list(_DEFAULT_TERMS)
    return company


def thank_you_line(invoice):
    """A thank-you sentence chosen from the invoice id: varied across invoices, fixed for one."""
    return THANK_YOU_LINES[invoice.pk.int % len(THANK_YOU_LINES)]


def settlement_rows(invoice):
    """
    How the invoice was paid and what is still to come, for the "روش پرداخت" box:
    ``[{"label", "detail", "date", "amount", "state"}]``. Money already received comes
    first (oldest first), then pending cheques by due date, then the open credit
    (نسیه) with its due date. A refunded part (D-055) is left out; a payment booked
    before the invoice was confirmed is earlier credit used on it (D-087).
    """
    rows = []
    allocations = invoice.payment_allocations.select_related(
        "payment__bank_account", "payment__cheque",
    ).filter(reversal_payment__isnull=True).order_by("payment__payment_date", "created_at")
    for allocation in allocations:
        payment = allocation.payment
        cheque = getattr(payment, "cheque", None)
        if payment.is_credit_note:  # value of goods brought back (D-089)
            label, detail = "مرجوعی", payment.note.rsplit(" ", 1)[-1]
        elif cheque is not None:
            label, detail = "چک", " · ".join(x for x in (cheque.cheque_number, cheque.bank_name) if x)
        elif invoice.confirmed_at and payment.created_at < invoice.confirmed_at:
            label, detail = "از بستانکاری قبلی", ""
        elif payment.bank_account and payment.bank_account.account_type == BankAccount.AccountType.POS:
            label, detail = "کارت‌خوان", ""
        else:
            label, detail = "حواله بانکی", ""
        rows.append({"label": label, "detail": detail, "date": payment.payment_date,
                     "amount": allocation.amount, "state": "پرداخت شد"})

    pending = 0
    for cheque in invoice.cheques.filter(status=Cheque.Status.PENDING).order_by("due_date"):
        pending += cheque.amount
        rows.append({"label": "چک", "detail": " · ".join(x for x in (cheque.cheque_number, cheque.bank_name) if x),
                     "date": cheque.due_date, "amount": cheque.amount, "state": "سررسید"})

    if invoice.status == invoice.Status.CONFIRMED:
        credit = invoice.outstanding - pending
        if credit > 0:
            rows.append({"label": "نسیه", "detail": "", "date": invoice.credit_due_date,
                         "amount": credit, "state": "سررسید"})
    return rows

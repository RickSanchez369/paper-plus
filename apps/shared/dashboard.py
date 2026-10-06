# path: apps/shared/dashboard.py

"""
Read-only aggregates for the Dashboard. Everything here is computed live, same
as Financial Reports and User Activity: inventing numbers here would be
worse than showing none.
"""

import datetime

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.inventory.selectors import get_stock_map, get_total_inventory_value
from apps.payments.models import BankAccount, Cheque
from apps.payments.selectors import (
    get_bank_account_balance,
    get_total_payables_as_of,
    get_upcoming_payments,
    get_upcoming_receivables,
    get_total_receivables_as_of,
)
from apps.products.models import Product
from apps.sales.models import SalesInvoice
from apps.shared import dates, reports, user_activity


def out_of_stock_count():
    """Active products with nothing on the shelf (stock <= 0): the dashboard's "what needs action" stock alert (D-095).

    Same population and rule as the inventory list's «ناموجود» chip, so the number and the page it links to agree.
    """
    ids = list(Product.objects.filter(is_active=True).values_list("pk", flat=True))
    stock = get_stock_map(ids)
    return sum(1 for pk in ids if stock.get(pk, 0) <= 0)


def _prev_month_span(jalali_today):
    """Last Jalali month, from its first day to the same day-of-month (clamped to its length), so a
    half-finished month is compared like for like instead of against a full one.
    Returns (start, end, jalali month number, days covered)."""
    year, month = dates.clamp_month(jalali_today.year, jalali_today.month - 1)
    prev_start, prev_end = dates.month_bounds(year, month)
    span = min(jalali_today.day, (prev_end - prev_start).days + 1)
    return prev_start, prev_start + datetime.timedelta(days=span - 1), month, span


def _compare(current, previous, higher_is_better=True):
    """How `current` stands against `previous`: signed difference, % change (only against a positive
    base, so a prior loss never flips the sign), and the tone class. Purchases and expenses pass
    higher_is_better=False, the same colour logic reports.html uses."""
    diff = current - previous
    direction = (diff > 0) - (diff < 0)
    tone = ""
    if direction:
        tone = "up" if (direction > 0) == higher_is_better else "down"
    return {
        "prev": previous,
        "diff": diff,
        "direction": direction,
        "tone": tone,
        "change": reports.pct_change(current, previous) if previous > 0 else None,
    }


def kpi_cards():
    """Sales/purchases/expenses/net-profit, each today + this month -- reuses Financial Reports' own
    selectors so this card can never disagree with that page. Also carries the month-to-date
    comparison with the same days of last Jalali month."""
    today = timezone.localdate()
    jalali_today = dates.today()
    month_start, month_end = dates.month_bounds(jalali_today.year, jalali_today.month)

    def _figures(start, end):
        sales = reports.sales_total(start, end)
        purchases = reports.purchases_total(start, end)
        expenses = reports.expenses_total(start, end)
        gross = reports.gross_profit(start, end)
        # Same definition as reports.summary_cards: what the goods actually sold cost (FIFO).
        return {
            "sales": sales, "purchases": purchases, "expenses": expenses,
            "cogs": sales - gross, "net_profit": gross - expenses,
        }

    prev_start, prev_end, prev_month, span = _prev_month_span(jalali_today)
    so_far = _figures(month_start, min(today, month_end))
    before = _figures(prev_start, prev_end)
    compare = {
        key: _compare(so_far[key], before[key], higher_is_better=key not in ("purchases", "expenses"))
        for key in ("sales", "purchases", "expenses", "net_profit")
    }
    return {
        "today": _figures(today, today),
        "month": _figures(month_start, month_end),
        "compare": compare,
        # "۱۲ شهریور": where last month's comparable span ends.
        "compare_label": dates.to_persian_digits(f"{span} {dates.MONTH_NAMES[prev_month - 1]}"),
    }


def totals_now():
    """Open receivables, open payables, total bank balance (all active
    accounts summed), total inventory value, each linking to its own module."""
    today = timezone.localdate()
    bank_balance = sum(
        get_bank_account_balance(account) for account in BankAccount.objects.filter(is_active=True)
    )
    return {
        "receivables": {"value": get_total_receivables_as_of(today), "url": reverse("receivables:list")},
        "payables": {"value": get_total_payables_as_of(today), "url": reverse("payables:list")},
        "bank_balance": {"value": bank_balance, "url": reverse("bank_accounts:list")},
        "inventory_value": {"value": get_total_inventory_value(), "url": reverse("inventory:list")},
    }


def setup_progress():
    """First-run checklist: a step is done once real rows exist, so it ticks itself and can never
    drift from the data. The first open step is flagged `is_next` (the one to highlight)."""
    from apps.partners.models import Supplier
    from apps.products.models import Product

    steps = [
        ("ثبت کالاها", "اسم، تعداد بسته در کارتن و قیمت را وارد کنید. موجودی فعلی انبار را هم همان‌جا و فقط یک‌بار می‌توانید ثبت کنید.",
         reverse("inventory:product_new"), "ثبت کالا", Product.objects.exists()),
        ("یک حساب بانکی تعریف کنید", "برای دریافت با حواله یا کارت‌خوان و برای چک لازم می‌شود؛ اگر فعلاً نیاز ندارید رد شوید.",
         reverse("bank_accounts:new"), "ثبت حساب", BankAccount.objects.exists()),
        ("تأمین‌کننده را اضافه کنید", "فاکتور خرید موجودی انبار را بالا می‌برد؛ تأمین‌کننده و کالای تازه را از داخل خود فاکتور هم می‌شود ساخت.",
         reverse("purchasing:supplier_new"), "ثبت تأمین‌کننده", Supplier.objects.exists()),
        ("اولین فاکتور فروش را بزنید", "مشتری را همان‌جا با «+ مشتری جدید» اضافه کنید.",
         reverse("sales:new"), "فاکتور فروش", SalesInvoice.objects.exists()),
    ]
    rows = [
        {"title": title, "hint": hint, "url": url, "cta": cta, "done": done}
        for title, hint, url, cta, done in steps
    ]
    open_rows = [row for row in rows if not row["done"]]
    for row in rows:
        row["is_next"] = bool(open_rows) and row is open_rows[0]
    done_count = len(rows) - len(open_rows)
    return {
        "rows": rows,
        "done": done_count,
        "total": len(rows),
        "complete": done_count == len(rows),
    }


def cheques_needing_completion(limit=5):
    """Pending cheques entered incomplete from an invoice (no due date or no
    number yet). A missing due date can never fall inside a "due soon"
    window, so without this bucket such a cheque could sit forgotten."""
    qs = Cheque.objects.filter(status=Cheque.Status.PENDING).filter(
        Q(due_date__isnull=True) | Q(cheque_number="")
    ).select_related("customer", "supplier").order_by("created_at")
    return {"cheques": list(qs[:limit]), "total_count": qs.count()}


def overdue_credit_invoices(threshold_days=30, limit=5):
    """
    Confirmed sales invoices still owing money, older than `threshold_days`.
    Sales side only: this widget is about
    collection risk (money owed *to* the business); the payables mirror
    already has its own home on the Payables page.
    """
    today = timezone.localdate()
    cutoff = today - datetime.timedelta(days=threshold_days)
    invoices = list(
        SalesInvoice.objects.filter(status=SalesInvoice.Status.CONFIRMED, invoice_date__lte=cutoff)
        .select_related("customer")
        .prefetch_related("payment_allocations")
        .order_by("invoice_date")
    )
    overdue = [invoice for invoice in invoices if invoice.outstanding > 0]
    return {"invoices": overdue[:limit], "total_count": len(overdue)}


DUES_WINDOW_DAYS = 10


def _group(items):
    """One list of due rows with its own total and the part already overdue."""
    return {
        "items": items,
        "total": sum(i["amount"] for i in items),
        "overdue_total": sum(i["amount"] for i in items if i["overdue"]),
    }


def _side(cheques, credit):
    """A column of the dues card: cheques and credit groups plus the column totals."""
    return {
        "cheques": _group(cheques),
        "credit": _group(credit),
        "total": sum(i["amount"] for i in cheques + credit),
        "overdue_total": sum(i["amount"] for i in cheques + credit if i["overdue"]),
    }


def dues_overview(days=DUES_WINDOW_DAYS):
    """
    One card for money coming in and going out (D-079): what customers owe
    (cheques held, sale credit) and what the business owes (cheques issued,
    supplier credit, credit expenses, fixed costs), each due within ``days``
    days or already late, soonest first. Replaces the separate
    "next week's payments" and "needs attention" cards.
    """
    today = timezone.localdate()
    incoming = get_upcoming_receivables(today, days)
    outgoing = get_upcoming_payments(today, days)
    return {
        "days": days,
        "receivable": _side(
            [i for i in incoming if i["kind"] == "cheque"], [i for i in incoming if i["kind"] != "cheque"],
        ),
        "payable": _side(
            [i for i in outgoing if i["kind"] == "cheque"], [i for i in outgoing if i["kind"] != "cheque"],
        ),
    }


def recent_activity(limit=10):
    """The latest N events, all users."""
    return user_activity.get_recent_activity(limit=limit)

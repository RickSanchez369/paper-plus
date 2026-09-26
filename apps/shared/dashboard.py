# path: apps/shared/dashboard.py

"""
Read-only aggregates for the Dashboard (REDESIGN_VISION 4.10, Phase C
module 10, the last of the 11). Everything here is computed live, same
as Financial Reports and User Activity -- REDESIGN_VISION's own words:
"inventing numbers here would be worse than showing none".
"""

import datetime

from django.urls import reverse
from django.utils import timezone

from apps.inventory.selectors import get_negative_stock_products, get_total_inventory_value
from apps.payments.models import BankAccount, Cheque
from apps.payments.selectors import (
    get_bank_account_balance,
    get_total_payables_as_of,
    get_total_receivables_as_of,
)
from apps.sales.models import SalesInvoice
from apps.shared import dates, reports, user_activity


def kpi_cards():
    """Sales/purchases/expenses/net-profit, each today + this month
    (REDESIGN_VISION 4.10, row 1) -- reuses Financial Reports' own
    selectors so this card can never disagree with that page."""
    today = timezone.localdate()
    jalali_today = dates.today()
    month_start, month_end = dates.month_bounds(jalali_today.year, jalali_today.month)

    def _figures(start, end):
        sales = reports.sales_total(start, end)
        purchases = reports.purchases_total(start, end)
        expenses = reports.expenses_total(start, end)
        net = reports.gross_profit(start, end) - expenses
        return {"sales": sales, "purchases": purchases, "expenses": expenses, "net_profit": net}

    return {"today": _figures(today, today), "month": _figures(month_start, month_end)}


def totals_now():
    """Open receivables, open payables, total bank balance (all active
    accounts summed), total inventory value -- REDESIGN_VISION 4.10, row
    2, each linking to its own module."""
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


def cheques_due_soon(days=7, limit=5):
    """Pending cheques due within `days` (REDESIGN_VISION 4.10, row 3):
    a handful shown, plus the real total so "see all" doesn't undersell
    how many there are."""
    today = timezone.localdate()
    qs = Cheque.objects.filter(
        status=Cheque.Status.PENDING, due_date__isnull=False, due_date__gte=today, due_date__lte=today + datetime.timedelta(days=days),
    ).select_related("customer", "supplier").order_by("due_date")
    return {"cheques": list(qs[:limit]), "total_count": qs.count()}


def overdue_credit_invoices(threshold_days=30, limit=5):
    """
    Confirmed sales invoices still owing money, older than `threshold_days`
    (REDESIGN_VISION 4.10, row 3: "default 30-day threshold — a query
    parameter, not a new field"). Sales side only: this widget is about
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


def negative_stock():
    """Products whose stock has gone negative (defensive only, D-016 --
    an oversell is allowed for a superuser, this just surfaces it)."""
    return get_negative_stock_products()


def recent_activity(limit=10):
    """The latest N events, all users (REDESIGN_VISION 4.10, row 4)."""
    return user_activity.get_recent_activity(limit=limit)

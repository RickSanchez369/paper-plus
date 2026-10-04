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

from apps.inventory.selectors import get_total_inventory_value
from apps.payments.models import BankAccount, Cheque
from apps.payments.selectors import (
    get_bank_account_balance,
    get_total_payables_as_of,
    get_upcoming_payments,
    get_upcoming_receivables,
    get_total_receivables_as_of,
)
from apps.sales.models import SalesInvoice
from apps.shared import dates, reports, user_activity


def kpi_cards():
    """Sales/purchases/expenses/net-profit, each today + this month -- reuses Financial Reports' own
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

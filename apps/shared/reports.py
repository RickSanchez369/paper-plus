# path: apps/shared/reports.py

"""
Read-only aggregates for the Financial Reports page (REDESIGN_VISION 4.8,
Phase C module 8). A selector module like apps/*/selectors.py, just placed
here because it reads across every app (sales, purchasing, inventory,
payments, shared) rather than owning one of them.

Every number is computed live for the requested (start, end) range,
never stored (REDESIGN_VISION 2.8) -- a report for last month must show
last month's true numbers, not today's.
"""

import datetime

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum

from apps.inventory.selectors import get_inventory_as_of
from apps.payments.models import Cheque, Payment
from apps.payments.selectors import (
    get_bank_account_balance,
    get_total_payables_as_of,
    get_total_receivables_as_of,
)
from apps.payments.models import BankAccount, Expense
from apps.purchasing.models import PurchaseInvoice, PurchaseItem
from apps.sales.models import SaleItem, SalesInvoice
from apps.shared.models import AuditLog


def previous_period(start, end):
    """The equal-length period immediately before (start, end), inclusive
    of both ends -- so a 7-day range compares against the 7 days before it,
    not a Gregorian-calendar concept of "last week"."""
    length = (end - start).days + 1
    previous_end = start - datetime.timedelta(days=1)
    previous_start = previous_end - datetime.timedelta(days=length - 1)
    return previous_start, previous_end


def pct_change(current, previous):
    """% change vs. the prior period. None when there is nothing to compare
    against (a page showing "+inf%" would be worse than showing nothing)."""
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def sales_total(start, end):
    return sum(
        invoice.total for invoice in SalesInvoice.objects.filter(
            status=SalesInvoice.Status.CONFIRMED, invoice_date__gte=start, invoice_date__lte=end,
        )
    )


def purchases_total(start, end):
    return sum(
        invoice.total_amount for invoice in PurchaseInvoice.objects.filter(
            status=PurchaseInvoice.Status.CONFIRMED, invoice_date__gte=start, invoice_date__lte=end,
        )
    )


def expenses_total(start, end):
    return Expense.objects.filter(
        cancelled_at__isnull=True, expense_date__gte=start, expense_date__lte=end,
    ).aggregate(total=Sum("amount"))["total"] or 0


def gross_profit(start, end):
    return sum(
        invoice.profit for invoice in SalesInvoice.objects.filter(
            status=SalesInvoice.Status.CONFIRMED, invoice_date__gte=start, invoice_date__lte=end,
        ).prefetch_related("items__consumptions__layer")
    )


def summary_cards(start, end):
    """The five headline cards, each with its % change vs. the equal-length
    prior period -- everything computed live, twice (this period, the one
    before it)."""
    prev_start, prev_end = previous_period(start, end)

    sales = sales_total(start, end)
    purchases = purchases_total(start, end)
    expenses = expenses_total(start, end)
    gross = gross_profit(start, end)
    net = gross - expenses

    prev_sales = sales_total(prev_start, prev_end)
    prev_purchases = purchases_total(prev_start, prev_end)
    prev_expenses = expenses_total(prev_start, prev_end)
    prev_gross = gross_profit(prev_start, prev_end)
    prev_net = prev_gross - prev_expenses

    return {
        "sales": {"value": sales, "change": pct_change(sales, prev_sales)},
        "purchases": {"value": purchases, "change": pct_change(purchases, prev_purchases)},
        "expenses": {"value": expenses, "change": pct_change(expenses, prev_expenses)},
        "gross_profit": {"value": gross, "change": pct_change(gross, prev_gross)},
        "net_profit": {"value": net, "change": pct_change(net, prev_net)},
    }


def sales_by_product(start, end):
    """qty, amount, profit per product, across every confirmed sale in the
    range -- REDESIGN_VISION 4.8's own table, and the source "top sellers" is
    ranked from."""
    items = (
        SaleItem.objects.filter(
            invoice__status=SalesInvoice.Status.CONFIRMED,
            invoice__invoice_date__gte=start,
            invoice__invoice_date__lte=end,
        )
        .select_related("product")
        .prefetch_related("consumptions__layer")
    )
    rows = {}
    for item in items:
        row = rows.setdefault(item.product_id, {"product": item.product, "quantity": 0, "amount": 0, "profit": 0})
        row["quantity"] += item.quantity
        row["amount"] += item.line_total
        row["profit"] += item.profit
    return sorted(rows.values(), key=lambda row: -row["quantity"])


def purchases_by_product(start, end):
    """qty, amount per product -- no profit column, purchases have none."""
    items = (
        PurchaseItem.objects.filter(
            invoice__status=PurchaseInvoice.Status.CONFIRMED,
            invoice__invoice_date__gte=start,
            invoice__invoice_date__lte=end,
        )
        .select_related("product")
    )
    rows = {}
    for item in items:
        row = rows.setdefault(item.product_id, {"product": item.product, "quantity": 0, "amount": 0})
        row["quantity"] += item.quantity
        row["amount"] += item.line_total
    return sorted(rows.values(), key=lambda row: -row["quantity"])


def top_sellers(start, end, limit=10):
    """Ranked by quantity, linked (REDESIGN_VISION 4.8) -- the same rows
    `sales_by_product` already computed, just capped."""
    return sales_by_product(start, end)[:limit]


def inventory_snapshot(start, end):
    """Inventory **as of the end of the selected range**, not "right now"
    (REDESIGN_VISION 4.8) -- reconstructed from the movement/layer ledger."""
    rows = get_inventory_as_of(end)
    return {
        "total_value": sum(row["value"] for row in rows.values()),
        "product_count": len(rows),
    }


def bank_accounts_as_of(start, end):
    """Balance as of range end + this period's own in/out totals, per
    active account (REDESIGN_VISION 4.8)."""
    rows = []
    for account in BankAccount.objects.filter(is_active=True).order_by("name"):
        period = Payment.objects.filter(bank_account=account, payment_date__gte=start, payment_date__lte=end)
        period_in = period.filter(direction=Payment.Direction.IN).aggregate(total=Sum("amount"))["total"] or 0
        period_out = period.filter(direction=Payment.Direction.OUT).aggregate(total=Sum("amount"))["total"] or 0
        rows.append({
            "account": account,
            "balance": get_bank_account_balance(account, as_of=end),
            "period_in": period_in,
            "period_out": period_out,
        })
    return rows


def receivables_payables_as_of(end):
    """Open receivables/payables as of range end (REDESIGN_VISION 4.8) --
    the business-wide totals; the per-party breakdown already lives on
    Receivables/Payables."""
    return {
        "receivables": get_total_receivables_as_of(end),
        "payables": get_total_payables_as_of(end),
    }


def cheques_by_status(start, end):
    """Counts/amounts by status, for cheques due within the range
    (REDESIGN_VISION 4.8) -- due date is what a cheque's own timing means,
    not when it was entered."""
    rows = (
        Cheque.objects.filter(due_date__gte=start, due_date__lte=end)
        .values("status")
        .annotate(count=Count("id"), amount=Sum("amount"))
        .order_by("status")
    )
    labels = dict(Cheque.Status.choices)
    return [
        {"status": row["status"], "label": labels.get(row["status"], row["status"]), "count": row["count"], "amount": row["amount"] or 0}
        for row in rows
    ]


def user_activity(start, end):
    """Event counts grouped by actor, within the range (REDESIGN_VISION
    4.8) -- the full per-event breakdown is the separate User Activity
    module (4.9); this is just the report's own summary row per person."""
    User = get_user_model()
    rows = (
        AuditLog.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .values("actor_id")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    users = {user.pk: user for user in User.objects.filter(pk__in=[row["actor_id"] for row in rows])}
    return [
        {"actor": users.get(row["actor_id"]), "count": row["count"]}
        for row in rows
        if row["actor_id"] in users
    ]

# path: apps/shared/reports.py

"""
Read-only aggregates for the Financial Reports page. A selector module like
apps/*/selectors.py, just placed
here because it reads across every app (sales, purchasing, inventory,
payments, shared) rather than owning one of them.

Every number is computed live for the requested (start, end) range,
never stored -- a report for last month must show
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
from apps.sales.models import SalesInvoice
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


def sales_returns_total(start, end):
    """Value of goods customers brought back, by return date (D-089); the sales they came from stay as they were."""
    from apps.returns.models import SalesReturn

    return SalesReturn.objects.filter(return_date__gte=start, return_date__lte=end).aggregate(
        t=Sum("total_amount"))["t"] or 0


def returns_profit(start, end):
    """Profit the period's sales returns take back: their value minus the FIFO cost that came back to the shelf."""
    from apps.returns.models import SalesReturn

    returns = SalesReturn.objects.filter(return_date__gte=start, return_date__lte=end).prefetch_related("items")
    return sum(r.profit_given_back for r in returns)


def purchase_returns_total(start, end):
    """Goods price of what went back to suppliers, by return date (D-089)."""
    from apps.returns.models import PurchaseReturn

    return PurchaseReturn.objects.filter(return_date__gte=start, return_date__lte=end).aggregate(
        t=Sum("total_amount"))["t"] or 0


def summary_cards(start, end):
    """The five headline cards, each with its % change vs. the equal-length
    prior period -- everything computed live, twice (this period, the one
    before it)."""
    prev_start, prev_end = previous_period(start, end)

    sales = sales_total(start, end)
    purchases = purchases_total(start, end)
    expenses = expenses_total(start, end)
    gross = gross_profit(start, end)
    sales_back = sales_returns_total(start, end)
    profit_back = returns_profit(start, end)
    net = gross - profit_back - expenses

    prev_sales = sales_total(prev_start, prev_end)
    prev_purchases = purchases_total(prev_start, prev_end)
    prev_expenses = expenses_total(prev_start, prev_end)
    prev_gross = gross_profit(prev_start, prev_end)
    prev_net = prev_gross - returns_profit(prev_start, prev_end) - prev_expenses

    return {
        "sales": {"value": sales, "change": pct_change(sales, prev_sales)},
        "purchases": {"value": purchases, "change": pct_change(purchases, prev_purchases)},
        "expenses": {"value": expenses, "change": pct_change(expenses, prev_expenses)},
        "gross_profit": {"value": gross, "change": pct_change(gross, prev_gross)},
        "net_profit": {"value": net, "change": pct_change(net, prev_net)},
        # D-089: returns are booked on their own date and shown beside sales, never netted into them.
        "sales_returns": {"value": sales_back},
        "returns_profit": {"value": profit_back},
        "purchase_returns": {"value": purchase_returns_total(start, end)},
        # What the goods that were actually sold cost (FIFO). Not the
        # period's purchases: those only fill the shelf, and cost nothing
        # until the goods leave it.
        "cogs": sales - gross,
    }


def sales_by_product(start, end):
    """qty, amount, profit per product, across every confirmed sale in the
    range -- the Reports table, and the source "top sellers" is
    ranked from.

    Amount and profit are net of each invoice's discount, shared across its
    lines in proportion to their line totals (D-048) -- so the column totals
    equal `sales_total` and `gross_profit` exactly. Walked invoice by
    invoice, so every line reads its share from its own (prefetched)
    invoice instead of one query per line."""
    invoices = SalesInvoice.objects.filter(
        status=SalesInvoice.Status.CONFIRMED, invoice_date__gte=start, invoice_date__lte=end,
    ).prefetch_related("items__product", "items__consumptions__layer")
    rows = {}
    for invoice in invoices:
        for item in invoice.items.all():
            row = rows.setdefault(item.product_id, {"product": item.product, "quantity": 0, "amount": 0, "profit": 0})
            row["quantity"] += item.quantity
            row["amount"] += item.net_total
            row["profit"] += item.profit
    return sorted(rows.values(), key=lambda row: -row["quantity"])


def sales_by_tier(start, end):
    """
    Wholesale vs retail (D-075): invoices, net sales, discount given and
    profit per sale type over the range -- the answer to "which kind of sale
    makes money". Derived from the same invoices as `sales_total` and
    `gross_profit`, so the two rows add up to exactly those figures.
    """
    from apps.products.models import PriceTier

    rows = {
        tier: {"label": label, "invoices": 0, "sales": 0, "discount": 0, "profit": 0}
        for tier, label in PriceTier.choices
    }
    invoices = SalesInvoice.objects.filter(
        status=SalesInvoice.Status.CONFIRMED, invoice_date__gte=start, invoice_date__lte=end,
    ).prefetch_related("items__consumptions__layer")
    for invoice in invoices:
        row = rows[invoice.price_tier]
        row["invoices"] += 1
        row["sales"] += invoice.total
        row["discount"] += invoice.discount_amount
        row["profit"] += invoice.profit
    for row in rows.values():
        row["margin"] = (row["profit"] * 100 // row["sales"]) if row["sales"] else None
    return list(rows.values())


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
    """Ranked by quantity, linked -- the same rows
    `sales_by_product` already computed, just capped."""
    return sales_by_product(start, end)[:limit]


def inventory_snapshot(start, end):
    """Inventory **as of the end of the selected range**, not "right now" --
    reconstructed from the movement/layer ledger."""
    rows = get_inventory_as_of(end)
    return {
        "total_value": sum(row["value"] for row in rows.values()),
        "product_count": len(rows),
    }


def bank_accounts_as_of(start, end):
    """Balance as of range end + this period's own in/out totals, per
    active account."""
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
    """Open receivables/payables as of range end --
    the business-wide totals; the per-party breakdown already lives on
    Receivables/Payables."""
    return {
        "receivables": get_total_receivables_as_of(end),
        "payables": get_total_payables_as_of(end),
    }


def cheques_by_status(start, end):
    """Counts/amounts by status, for cheques due within the range -- due date
    is what a cheque's own timing means,
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
    """Event counts grouped by actor, within the range -- the full per-event
    breakdown is the separate User Activity
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

# path: apps/shared/user_activity.py

"""
Read-only aggregates and feed queries for User Activity. A selector module like
apps/shared/reports.py,
placed here because it reads AuditLog plus a handful of other apps' models
only to resolve a target link, not because it owns any of them.
"""

from django.urls import reverse

from apps.inventory.models import InventoryMovement
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared.models import AuditLog

EventType = AuditLog.EventType

# Which bucket each event type counts toward on the aggregate table. A
# cancellation counts only in its
# own bucket, never double-counted into "recorded" too.
_BUCKETS = {
    EventType.CONFIRM_SALE: "sales",
    EventType.CONFIRM_PURCHASE: "purchases",
    EventType.RECORD_EXPENSE: "expenses",
    EventType.RECORD_PAYMENT: "payments",
    EventType.ALLOCATE_PAYMENT: "payments",
    EventType.RECORD_CHEQUE: "cheques",
    EventType.CLEAR_CHEQUE: "cheques",
    EventType.CANCEL_SALE: "cancellations",
    EventType.CANCEL_PURCHASE: "cancellations",
    EventType.CANCEL_EXPENSE: "cancellations",
    EventType.CANCEL_CHEQUE: "cancellations",
    EventType.BOUNCE_CHEQUE: "cancellations",
}
BUCKET_LABELS = {
    "sales": "فروش ثبت‌شده",
    "purchases": "خرید ثبت‌شده",
    "expenses": "هزینهٔ ثبت‌شده",
    "payments": "پرداخت ثبت‌شده",
    "cheques": "چک ثبت‌شده",
    "cancellations": "لغو/برگشت",
}
BUCKET_ORDER = ("sales", "purchases", "expenses", "payments", "cheques", "cancellations")

# target_type ("app_label.model_name", from AuditLog.target_type) -> a
# function building that target's own detail URL. Built once, here,
# as a small routing table -- some targets (a bare Payment, an Expense, a PaymentAllocation)
# have no page of their own to link to, and are left unresolved on purpose.
_TARGET_URL_BUILDERS = {
    "sales.salesinvoice": lambda target_id: reverse("sales:detail", args=[target_id]),
    "purchasing.purchaseinvoice": lambda target_id: reverse("purchasing:detail", args=[target_id]),
    "payments.cheque": lambda target_id: reverse("cheques:detail", args=[target_id]),
    "products.product": lambda target_id: reverse("inventory:detail", args=[target_id]),
}


def _amount_for(entry):
    """This event's own monetary size -- from the logged payload when it
    carries one (every money event does), or the invoice's own total for
    confirm_sale/confirm_purchase, which never logged an amount."""
    if "amount" in entry.payload:
        return entry.payload["amount"]
    return None


def get_activity_summary(start, end, event_type=None):
    """
    One row per user: counts per bucket, and each bucket's own amount
    total, for events within (start, end).

    Deliberately per-bucket, not one blended total: `record_expense` and
    `cancel_expense` (and the cheque lifecycle) book their own money
    through `record_payment` internally, which logs *its own* separate
    AuditLog row -- so the same Toman amount legitimately appears once
    under "expenses" and once under "payments". Both statements are true
    on their own ("this much was recorded as an expense", "this much
    moved through a payment"); summing them into one number would silently
    double it. Never fixed by dropping the payment's own audit row either --
    that row is its own real, independently useful fact.
    """
    qs = AuditLog.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    if event_type:
        qs = qs.filter(event_type=event_type)

    entries = list(qs.select_related("actor"))

    # Money-bearing events carry their own amount in payload; confirm_sale/
    # confirm_purchase do not, so their invoices are fetched once, in bulk,
    # rather than one query per row.
    sale_ids = {e.target_id for e in entries if e.event_type == EventType.CONFIRM_SALE}
    purchase_ids = {e.target_id for e in entries if e.event_type == EventType.CONFIRM_PURCHASE}
    sale_totals = {
        invoice.pk: invoice.total for invoice in SalesInvoice.objects.filter(pk__in=sale_ids)
    }
    purchase_totals = {
        invoice.pk: invoice.total_amount for invoice in PurchaseInvoice.objects.filter(pk__in=purchase_ids)
    }

    rows = {}
    for entry in entries:
        row = rows.setdefault(entry.actor_id, {
            "actor": entry.actor,
            "counts": {bucket: 0 for bucket in BUCKET_ORDER},
            "amounts": {bucket: 0 for bucket in BUCKET_ORDER},
        })
        bucket = _BUCKETS.get(entry.event_type)
        if not bucket:
            continue
        row["counts"][bucket] += 1

        amount = _amount_for(entry)
        if amount is None:
            if entry.event_type == EventType.CONFIRM_SALE:
                amount = sale_totals.get(entry.target_id, 0)
            elif entry.event_type == EventType.CONFIRM_PURCHASE:
                amount = purchase_totals.get(entry.target_id, 0)
        if amount:
            row["amounts"][bucket] += amount

    return sorted(rows.values(), key=lambda row: str(row["actor"]))


def resolve_target_url(target_type, target_id):
    """This event's target's own page, or None when it has none. `inventory.inventorymovement`
    is resolved via its product, since a movement has no page of its own."""
    if target_type == "inventory.inventorymovement":
        product_id = (
            InventoryMovement.objects.filter(pk=target_id).values_list("product_id", flat=True).first()
        )
        if product_id:
            return reverse("inventory:detail", args=[product_id])
        return None
    builder = _TARGET_URL_BUILDERS.get(target_type)
    return builder(target_id) if builder else None


def get_recent_activity(limit=10):
    """The latest N events, any actor, no date range -- the Dashboard's
    own global activity feed, not scoped to
    a reporting period the way User Activity's own feed is."""
    entries = AuditLog.objects.select_related("actor").order_by("-created_at")[:limit]
    return [
        {"entry": entry, "target_url": resolve_target_url(entry.target_type, entry.target_id)}
        for entry in entries
    ]


def get_activity_feed(start, end, actor=None, event_type=None):
    """The raw AuditLog feed for the drill-down page: event type, linked
    target, timestamp -- newest first."""
    qs = (
        AuditLog.objects
        .filter(created_at__date__gte=start, created_at__date__lte=end)
        .select_related("actor")
        .order_by("-created_at")
    )
    if actor is not None:
        qs = qs.filter(actor=actor)
    if event_type:
        qs = qs.filter(event_type=event_type)

    rows = []
    for entry in qs:
        rows.append({
            "entry": entry,
            "target_url": resolve_target_url(entry.target_type, entry.target_id),
        })
    return rows

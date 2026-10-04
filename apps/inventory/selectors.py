# path: apps/inventory/selectors.py

"""
Read-only queries over the inventory ledger.

Selectors never write. Anything that writes belongs in a service.
"""

from django.db.models import Case, F, IntegerField, Sum, When

from .models import InventoryConsumption, InventoryLayer, InventoryMovement


def _signed_quantity_expression():
    """SQL CASE that turns a positive quantity into a signed one (D-012)."""
    return Case(
        When(movement_type__in=InventoryMovement.INFLOW_TYPES, then=F("quantity")),
        default=-F("quantity"),
        output_field=IntegerField(),
    )


def get_stock(product):
    """Current stock of one product, computed from the ledger."""
    result = InventoryMovement.objects.filter(product=product).aggregate(
        stock=Sum(_signed_quantity_expression())
    )
    return result["stock"] or 0


def get_stock_map(product_ids):
    """
    Stock for several products at once: {product_id: stock}.

    One query instead of N. Products with no movements are absent from the
    result, so callers should use `.get(pk, 0)`.
    """
    rows = (
        InventoryMovement.objects
        .filter(product_id__in=product_ids)
        .values("product_id")
        .annotate(stock=Sum(_signed_quantity_expression()))
    )
    return {row["product_id"]: row["stock"] or 0 for row in rows}


def get_active_layers(product):
    """
    This product's still-sellable layers, oldest first (FIFO order).

    Excludes cancelled layers (a cancelled purchase's stock is gone) and
    exhausted ones. `select_for_update()` belongs in the service that
    consumes them, not here -- a selector never locks.
    """
    return (
        InventoryLayer.objects
        .filter(product=product, cancelled_at__isnull=True, quantity_remaining__gt=0)
        .order_by("created_at", "id")
    )


def get_current_cost_map(product_ids):
    """
    Cost the *next* sale of each product will consume: {product_id: Toman}.

    That is the oldest active layer's own cost, which is what FIFO will
    draw from next -- not an average and not the latest purchase price
    (the old `get_cost_map`, which was never FIFO). Products with no
    active layer are absent; callers that need a display fallback use
    `get_last_known_cost_map`.
    """
    rows = (
        InventoryLayer.objects
        .filter(product_id__in=product_ids, cancelled_at__isnull=True, quantity_remaining__gt=0)
        .order_by("product_id", "created_at", "id")
        .values("product_id", "unit_cost")
    )
    cost_map = {}
    for row in rows:
        cost_map.setdefault(row["product_id"], row["unit_cost"])
    return cost_map


def get_average_cost_map(product_ids):
    """
    Average purchase price of the stock still on the shelf: {product_id: Toman per pack}.

    Σ(remaining × layer cost) ÷ Σ(remaining) over the active layers only, so
    units already sold never weigh in (D-081). It is for showing and judging
    stock, nothing else: cost of goods and profit keep drawing from the real
    FIFO layers (`consume_fifo`), and no calculation reads this figure.
    Rounded to the nearest Toman; products with no stock are absent.
    """
    rows = (
        InventoryLayer.objects
        .filter(product_id__in=product_ids, cancelled_at__isnull=True, quantity_remaining__gt=0)
        .values("product_id")
        .annotate(value=Sum(F("quantity_remaining") * F("unit_cost")), quantity=Sum("quantity_remaining"))
    )
    return {row["product_id"]: (2 * row["value"] + row["quantity"]) // (2 * row["quantity"]) for row in rows}


def get_last_known_cost_map(product_ids):
    """
    Most recent known cost per product, including exhausted layers.

    Display-only fallback for a product whose stock has hit zero, so its
    "قیمت خرید جاری" column shows the last cost it was bought at instead
    of a blank. Never feeds a calculation.
    """
    rows = (
        InventoryLayer.objects
        .filter(product_id__in=product_ids, cancelled_at__isnull=True)
        .order_by("product_id", "-created_at", "-id")
        .values("product_id", "unit_cost")
    )
    cost_map = {}
    for row in rows:
        cost_map.setdefault(row["product_id"], row["unit_cost"])
    return cost_map


def get_inventory_value_map(product_ids):
    """
    Toman value of each product's stock: {product_id: value}.

    Sum of every active layer's own remaining quantity times its own cost
    -- layers carry different costs, so a single "stock x latest cost"
    figure would be wrong.
    """
    rows = (
        InventoryLayer.objects
        .filter(product_id__in=product_ids, cancelled_at__isnull=True)
        .values("product_id")
        .annotate(value=Sum(F("quantity_remaining") * F("unit_cost")))
    )
    return {row["product_id"]: row["value"] or 0 for row in rows}


def get_total_inventory_value():
    """Toman value of all stock on hand, across every product."""
    result = InventoryLayer.objects.filter(cancelled_at__isnull=True).aggregate(
        value=Sum(F("quantity_remaining") * F("unit_cost"))
    )
    return result["value"] or 0


def get_inventory_as_of(as_of):
    """
    {product_id: {"stock": n, "value": v}} reconstructed from the layer/
    consumption ledger up to and including `as_of`.

    A layer counts only if it already existed by `as_of` and had not yet
    been cancelled by then; a consumption counts only if it happened by
    `as_of` -- both compared on `created_at`, the ledger's own timestamp,
    same as every other point-in-time selector in this app
    (`get_bank_account_balance`'s `as_of`).
    """
    layers = [
        layer for layer in InventoryLayer.objects.filter(created_at__date__lte=as_of)
        if not (layer.cancelled_at and layer.cancelled_at.date() <= as_of)
    ]
    consumed_map = dict(
        InventoryConsumption.objects
        .filter(layer_id__in=[layer.pk for layer in layers], created_at__date__lte=as_of)
        .values("layer_id")
        .annotate(total=Sum("quantity"))
        .values_list("layer_id", "total")
    )
    result = {}
    for layer in layers:
        remaining = layer.quantity - consumed_map.get(layer.pk, 0)
        if remaining <= 0:
            continue
        row = result.setdefault(layer.product_id, {"stock": 0, "value": 0})
        row["stock"] += remaining
        row["value"] += remaining * layer.unit_cost
    return result


def get_layer_balance(layer):
    """
    A layer's remaining quantity rebuilt from its consumption rows.

    `InventoryLayer.quantity_remaining` is a maintained running balance;
    this recomputes it from scratch so a verification script (or a future
    reconciliation page) can prove the two never drifted apart.
    """
    consumed = InventoryConsumption.objects.filter(layer=layer).aggregate(
        total=Sum("quantity")
    )["total"] or 0
    return layer.quantity - consumed

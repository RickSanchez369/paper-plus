# path: apps/inventory/selectors.py

"""
Read-only queries over the inventory ledger.

Selectors never write. Anything that writes belongs in a service.
"""

from django.db.models import Case, F, IntegerField, Sum, When

from .models import InventoryMovement


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
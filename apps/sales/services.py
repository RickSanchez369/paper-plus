# path: apps/sales/services.py

"""
Business logic for sales invoices.

Unlike a purchase, a sale removes stock, so it must serialise against other
sales of the same products (D-015).
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryMovement
from apps.inventory.selectors import get_stock_map
from apps.products.models import Product

from .models import SalesInvoice


@transaction.atomic
def confirm_sale(invoice, user):
    """
    Confirm a draft sales invoice and remove its items from stock.

    Stock may go negative (D-016); the sale is never blocked for that reason.
    Products that end up below zero are reported back to the caller and marked
    in the movement note so the shadow-phase reconciliation can count them.

    Args:
        invoice: the SalesInvoice to confirm.
        user: the user performing the action.

    Returns:
        (invoice, shortages) where shortages is a list of dicts:
        {"product": Product, "available": int, "requested": int, "resulting": int}

    Raises:
        ValidationError: invoice is not a draft, has no items, or references a
        product or customer belonging to another business.
    """
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)

    if locked_invoice.status != SalesInvoice.Status.DRAFT:
        raise ValidationError("این فاکتور قبلاً تأیید شده است.")

    items = list(locked_invoice.items.select_related("product").all())
    if not items:
        raise ValidationError("فاکتور بدون قلم قابل تأیید نیست.")

    foreign = [i for i in items if i.product.business_id != locked_invoice.business_id]
    if foreign:
        names = "، ".join(i.product.name for i in foreign)
        raise ValidationError(f"این کالاها متعلق به کسب‌وکار دیگری هستند: {names}")

    if locked_invoice.customer.business_id != locked_invoice.business_id:
        raise ValidationError("مشتری متعلق به کسب‌وکار دیگری است.")

    # Lock the product rows before reading stock. The rows are not modified;
    # they act as a mutex so a second concurrent sale of the same products
    # waits here and then reads a stock figure that already includes this sale.
    # Ordered by pk to give every transaction the same lock order (no deadlock).
    product_ids = sorted({i.product_id for i in items})
    list(Product.objects.select_for_update().filter(pk__in=product_ids).order_by("pk"))

    stock_map = get_stock_map(product_ids)

    shortages = []
    movements = []
    for item in items:
        available = stock_map.get(item.product_id, 0)
        resulting = available - item.quantity
        note = f"فاکتور فروش {locked_invoice.invoice_number}"

        if resulting < 0:
            # Marked so reconciliation can find these rows later (D-016).
            note += f" — موجودی منفی شد ({resulting})"
            shortages.append({
                "product": item.product,
                "available": available,
                "requested": item.quantity,
                "resulting": resulting,
            })

        movements.append(
            InventoryMovement(
                business=locked_invoice.business,
                product=item.product,
                movement_type=InventoryMovement.MovementType.SALE,
                quantity=item.quantity,
                created_by=user,
                note=note,
            )
        )

    InventoryMovement.objects.bulk_create(movements)

    locked_invoice.status = SalesInvoice.Status.CONFIRMED
    locked_invoice.confirmed_at = timezone.now()
    locked_invoice.save(update_fields=["status", "confirmed_at", "updated_at"])

    return locked_invoice, shortages
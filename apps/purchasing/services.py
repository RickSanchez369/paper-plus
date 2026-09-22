# path: apps/purchasing/services.py

"""
Business logic for purchase invoices.

Every write that touches stock lives here, never in a model, serializer or view.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryMovement
from apps.shared.audit import log_event

from .models import PurchaseInvoice


@transaction.atomic
def confirm_purchase(invoice, user):
    """
    Confirm a draft purchase invoice and push its items into stock.

    Creates one InventoryMovement per line, then freezes the invoice (D-014).
    All-or-nothing: if any step fails, no movement is written and the status
    stays draft.

    Args:
        invoice: the PurchaseInvoice to confirm.
        user: the user performing the action; recorded on every movement.

    Returns:
        The refreshed, confirmed PurchaseInvoice.

    Raises:
        ValidationError: invoice is not a draft, or has no items.
    """
    # Re-read the row with a database lock. A second concurrent confirmation
    # blocks here until this transaction ends, then sees status=confirmed
    # and fails on the check below instead of duplicating the movements.
    locked_invoice = (
        PurchaseInvoice.objects.select_for_update().get(pk=invoice.pk)
    )

    if locked_invoice.status != PurchaseInvoice.Status.DRAFT:
        raise ValidationError("این فاکتور قبلاً تأیید شده است.")

    items = list(locked_invoice.items.select_related("product").all())
    if not items:
        raise ValidationError("فاکتور بدون قلم قابل تأیید نیست.")
    # A line may only reference a product of the same business. Nothing in the
    # database prevents this (a CHECK cannot look at another table), so the
    # service is the gate.
    foreign = [i for i in items if i.product.business_id != locked_invoice.business_id]
    if foreign:
        names = "، ".join(i.product.name for i in foreign)
        raise ValidationError(f"این کالاها متعلق به کسب‌وکار دیگری هستند: {names}")

    # Same rule for the supplier.
    if locked_invoice.supplier.business_id != locked_invoice.business_id:
        raise ValidationError("تأمین‌کننده متعلق به کسب‌وکار دیگری است.")
    # One ledger row per line. quantity stays positive; the type carries
    # the direction (D-012).
    
    movements = [
        InventoryMovement(
            business=locked_invoice.business,
            product=item.product,
            movement_type=InventoryMovement.MovementType.PURCHASE,
            quantity=item.quantity,
            created_by=user,
            note=f"فاکتور خرید {locked_invoice.invoice_number}",
        )
        for item in items
    ]
    InventoryMovement.objects.bulk_create(movements)

    locked_invoice.status = PurchaseInvoice.Status.CONFIRMED
    locked_invoice.confirmed_at = timezone.now()
    locked_invoice.save(update_fields=["status", "confirmed_at", "updated_at"])

    log_event(
        business=locked_invoice.business,
        actor=user,
        event_type="confirm_purchase",
        target=locked_invoice,
        payload={"item_count": len(items)},
    )

    return locked_invoice
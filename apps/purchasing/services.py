# path: apps/purchasing/services.py

"""
Business logic for purchase invoices.

Every write that touches stock lives here, never in a model, serializer or view.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryMovement
from apps.payments.models import Cheque, Payment, PaymentAllocation
from apps.payments.services import allocate_payment, record_cheque, record_payment
from apps.shared.audit import log_event
from apps.shared.permissions import is_owner
from apps.shared.services import get_next_document_number

from .models import PurchaseInvoice, PurchasePaymentEntry


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

    # Number assigned only now, at confirmation (D-022) — never while draft.
    locked_invoice.invoice_number = get_next_document_number(
        locked_invoice.business, "purchase"
    )

    # One ledger row per line. quantity stays positive; the type carries
    # the direction (D-012).
    
    movements = [
        InventoryMovement(
            business=locked_invoice.business,
            product=item.product,
            movement_type=InventoryMovement.MovementType.PURCHASE,
            quantity=item.quantity,
            unit_price=item.unit_price,
            purchase_item=item,
            created_by=user,
            note=f"فاکتور خرید {locked_invoice.invoice_number}",
        )
        for item in items
    ]
    InventoryMovement.objects.bulk_create(movements)

    locked_invoice.status = PurchaseInvoice.Status.CONFIRMED
    locked_invoice.confirmed_at = timezone.now()
    locked_invoice.save(
        update_fields=["status", "confirmed_at", "invoice_number", "updated_at"]
    )

    # Payment entries drafted on the invoice (mirrors confirm_sale, 4.3b):
    # each becomes a real Payment, allocated to this invoice immediately,
    # or a pending Cheque tied to it (auto-allocated later when it clears
    # -- see clear_cheque). Whatever is left over than these rows is
    # simply the نسیه/credit portion; payment_status already shows it.
    entries = list(locked_invoice.payment_entries.all())
    if sum(entry.amount for entry in entries) > locked_invoice.total_amount:
        raise ValidationError("جمع ردیف‌های پرداخت از مبلغ کل فاکتور بیشتر است.")
    for entry in entries:
        if entry.method == PurchasePaymentEntry.Method.CHEQUE:
            record_cheque(
                Cheque(
                    business=locked_invoice.business,
                    direction=Payment.Direction.OUT,
                    supplier=locked_invoice.supplier,
                    bank_account=entry.bank_account,
                    cheque_number=entry.cheque_number,
                    bank_name=entry.bank_name,
                    due_date=entry.due_date,
                    amount=entry.amount,
                    purchase_invoice=locked_invoice,
                ),
                user,
            )
        else:
            new_payment = record_payment(
                Payment(
                    business=locked_invoice.business,
                    bank_account=entry.bank_account,
                    direction=Payment.Direction.OUT,
                    amount=entry.amount,
                    payment_date=locked_invoice.invoice_date,
                    note=f"فاکتور خرید {locked_invoice.invoice_number}",
                ),
                user,
            )
            allocate_payment(
                PaymentAllocation(payment=new_payment, purchase_invoice=locked_invoice, amount=entry.amount),
                user,
            )

    log_event(
        business=locked_invoice.business,
        actor=user,
        event_type="confirm_purchase",
        target=locked_invoice,
        payload={"item_count": len(items)},
    )

    return locked_invoice


@transaction.atomic
def cancel_purchase(invoice, user):
    """
    Cancel a confirmed purchase invoice: reverse its stock, freeze it (D-023).

    The invoice is never edited or reopened -- only Owner/superuser may
    cancel, and a mistaken purchase is corrected by a brand new invoice,
    never by editing this one (D-014 extended to cancelled invoices).

    One ADJUSTMENT_OUT movement per original line removes exactly the
    quantity that confirm_purchase added, so the ledger stays a full,
    auditable history rather than deleting or editing the original rows.

    Args:
        invoice: the PurchaseInvoice to cancel.
        user: the user performing the action; must be an Owner or superuser.

    Returns:
        The cancelled PurchaseInvoice.

    Raises:
        ValidationError: invoice is not confirmed (draft or already
        cancelled), or ``user`` is not an Owner/superuser (D-023).
    """
    locked_invoice = (
        PurchaseInvoice.objects.select_for_update().get(pk=invoice.pk)
    )

    if locked_invoice.status != PurchaseInvoice.Status.CONFIRMED:
        raise ValidationError("فقط فاکتور تأییدشده قابل لغو است.")

    if not is_owner(user, locked_invoice.business):
        raise ValidationError("فقط مالک یا ابرکاربر می‌تواند فاکتور را لغو کند.")

    items = list(locked_invoice.items.select_related("product").all())

    reversals = [
        InventoryMovement(
            business=locked_invoice.business,
            product=item.product,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT_OUT,
            quantity=item.quantity,
            unit_price=item.unit_price,
            created_by=user,
            note=f"لغو فاکتور خرید {locked_invoice.invoice_number}",
        )
        for item in items
    ]
    InventoryMovement.objects.bulk_create(reversals)

    locked_invoice.status = PurchaseInvoice.Status.CANCELLED
    locked_invoice.save(update_fields=["status", "updated_at"])

    log_event(
        business=locked_invoice.business,
        actor=user,
        event_type="cancel_purchase",
        target=locked_invoice,
        payload={"item_count": len(items)},
    )

    return locked_invoice
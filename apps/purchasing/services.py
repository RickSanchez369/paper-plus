# path: apps/purchasing/services.py

"""
Business logic for purchase invoices.

Every write that touches stock lives here, never in a model, serializer or view.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryLayer, InventoryMovement
from apps.inventory.services import cancel_layer
from apps.payments.models import Cheque, Payment, PaymentAllocation
from apps.payments.services import allocate_payment, record_cheque, record_payment, refund_invoice_payments
from apps.shared.audit import log_event
from apps.shared.permissions import is_privileged
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

    # Number assigned only now, at confirmation (D-022) — never while draft.
    locked_invoice.invoice_number = get_next_document_number("purchase")

    # One ledger row per line. quantity stays positive; the type carries
    # the direction (D-012).
    
    movements = [
        InventoryMovement(
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

    # One FIFO cost layer per line: this is the stock a later sale will
    # consume, at the price it was actually bought for.
    InventoryLayer.objects.bulk_create([
        InventoryLayer(
            product=item.product,
            source=InventoryLayer.Source.PURCHASE,
            purchase_item=item,
            quantity=item.quantity,
            quantity_remaining=item.quantity,
            unit_cost=item.unit_price,
            created_by=user,
        )
        for item in items
    ])

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
                    direction=Payment.Direction.OUT,
                    supplier=locked_invoice.supplier,
                    bank_account=entry.bank_account,
                    cheque_number=entry.cheque_number,
                    bank_name=entry.bank_name,
                    issuer=entry.issuer,
                    due_date=entry.due_date,
                    amount=entry.amount,
                    purchase_invoice=locked_invoice,
                ),
                user,
            )
        else:
            new_payment = record_payment(
                Payment(
                    bank_account=entry.bank_account,
                    direction=Payment.Direction.OUT,
                    supplier=locked_invoice.supplier,  # who got this money
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
        actor=user,
        event_type="confirm_purchase",
        target=locked_invoice,
        payload={"item_count": len(items)},
    )

    return locked_invoice


def plan_full_payment(invoice, bank_account):
    """
    The default settlement (mirrors sales, D-046/D-053): the whole invoice was
    paid to the supplier out of `bank_account` (None = cash, chosen explicitly
    on the form).

    Adds the one payment-entry row that says so, on a draft invoice whose
    items are already saved; confirm_purchase then books it like any typed
    row. The amount is the server's own `invoice.total_amount`, never a
    figure from the browser. Nothing is planned when the total is not
    positive. Must be called inside the caller's transaction, before
    confirm_purchase.
    """
    total = invoice.total_amount
    if total <= 0:
        return None
    return PurchasePaymentEntry.objects.create(
        invoice=invoice,
        method=PurchasePaymentEntry.Method.CASH if bank_account is None else PurchasePaymentEntry.Method.BANK_TRANSFER,
        amount=total,
        bank_account=bank_account,
    )


@transaction.atomic
def cancel_purchase(invoice, user):
    """
    Cancel a confirmed purchase invoice: reverse its stock, freeze it (D-023).

    The invoice is never edited or reopened -- only a superuser may
    cancel, and a mistaken purchase is corrected by a brand new invoice,
    never by editing this one (D-014 extended to cancelled invoices).

    One ADJUSTMENT_OUT movement per original line removes exactly the
    quantity that confirm_purchase added, so the ledger stays a full,
    auditable history rather than deleting or editing the original rows.

    Args:
        invoice: the PurchaseInvoice to cancel.
        user: the user performing the action; must be a superuser.

    Returns:
        The cancelled PurchaseInvoice.

    Raises:
        ValidationError: invoice is not confirmed (draft or already
        cancelled); ``user`` is not a superuser (D-023); or any of the stock this purchase brought
        in has already been sold.
    """
    locked_invoice = (
        PurchaseInvoice.objects.select_for_update().get(pk=invoice.pk)
    )

    if locked_invoice.status != PurchaseInvoice.Status.CONFIRMED:
        raise ValidationError("فقط فاکتور تأییدشده قابل لغو است.")

    if not is_privileged(user):
        raise ValidationError("فقط ابرکاربر می‌تواند فاکتور را لغو کند.")

    items = list(locked_invoice.items.select_related("product").all())

    # FIFO integrity guard, stricter than a sale's cancel rule: this stock
    # may only be withdrawn while none of it has been sold. Checked for
    # every line before anything is written, so a rejected cancellation
    # leaves the invoice exactly as it was.
    for layer in InventoryLayer.objects.select_related("product").filter(
        purchase_item__in=items
    ):
        cancel_layer(layer, user)

    reversals = [
        InventoryMovement(
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

    # What we paid the supplier comes back too (D-055): a refund Payment
    # (IN) per allocation, pending cheques we issued cancelled.
    refunded = refund_invoice_payments(locked_invoice, user)

    locked_invoice.status = PurchaseInvoice.Status.CANCELLED
    locked_invoice.save(update_fields=["status", "updated_at"])

    log_event(
        actor=user,
        event_type="cancel_purchase",
        target=locked_invoice,
        payload={"item_count": len(items), "refunded": refunded},
    )

    locked_invoice.refunded_amount = refunded
    return locked_invoice
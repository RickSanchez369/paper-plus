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
from apps.payments.models import Cheque, Payment, PaymentAllocation
from apps.payments.services import allocate_payment, record_cheque, record_payment
from apps.products.models import Product
from apps.shared.audit import log_event
from apps.shared.permissions import is_privileged
from apps.shared.services import get_next_document_number

from .models import SalesInvoice, SalesPaymentEntry


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
        ValidationError: invoice is not a draft, has no items, or has a
        discount exceeding its subtotal; or the sale would drive stock
        negative and ``user`` is not a superuser (D-021, §2.3).
    """
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)

    if locked_invoice.status != SalesInvoice.Status.DRAFT:
        raise ValidationError("این فاکتور قبلاً تأیید شده است.")

    items = list(locked_invoice.items.select_related("product").all())
    if not items:
        raise ValidationError("فاکتور بدون قلم قابل تأیید نیست.")

    subtotal = sum(i.line_total for i in items)
    if locked_invoice.discount_amount > subtotal:
        raise ValidationError(
            "تخفیف نمی‌تواند از جمع اقلام فاکتور بیشتر باشد."
        )

    # Number assigned only now, at confirmation (D-022) — never while draft.
    locked_invoice.invoice_number = get_next_document_number("sale")

    # Lock the product rows before reading stock.
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
                product=item.product,
                movement_type=InventoryMovement.MovementType.SALE,
                quantity=item.quantity,
                unit_price=item.unit_price,
                sale_item=item,
                created_by=user,
                note=note,
            )
        )

    if shortages and not is_privileged(user):
        # D-021, now §2.3: an ordinary user may not confirm a sale that
        # goes negative; a superuser may, and gets it back as a warning (D-016).
        names = "، ".join(s["product"].name for s in shortages)
        raise ValidationError(
            f"این فروش موجودی این کالاها را منفی می‌کند؛ فقط ابرکاربر "
            f"می‌تواند آن را تأیید کند: {names}"
        )

    InventoryMovement.objects.bulk_create(movements)

    locked_invoice.status = SalesInvoice.Status.CONFIRMED
    locked_invoice.confirmed_at = timezone.now()
    locked_invoice.save(
        update_fields=["status", "confirmed_at", "invoice_number", "updated_at"]
    )

    # Payment entries drafted on the invoice (Sina, 2026-09-24: "2M by
    # cheque, 1M cash, the rest نسیه"): each becomes a real Payment,
    # allocated to this invoice immediately, or a pending Cheque tied to
    # it (auto-allocated later when it clears -- see clear_cheque).
    # Whatever is left over than these rows is simply the نسیه/credit
    # portion; it needs no row of its own, payment_status already shows it.
    entries = list(locked_invoice.payment_entries.all())
    if sum(entry.amount for entry in entries) > locked_invoice.total:
        raise ValidationError("جمع ردیف‌های پرداخت از مبلغ کل فاکتور بیشتر است.")
    for entry in entries:
        if entry.method == SalesPaymentEntry.Method.CHEQUE:
            record_cheque(
                Cheque(
                    direction=Payment.Direction.IN,
                    customer=locked_invoice.customer,
                    bank_account=entry.bank_account,
                    cheque_number=entry.cheque_number,
                    bank_name=entry.bank_name,
                    due_date=entry.due_date,
                    amount=entry.amount,
                    sales_invoice=locked_invoice,
                ),
                user,
            )
        else:
            new_payment = record_payment(
                Payment(
                    bank_account=entry.bank_account,
                    direction=Payment.Direction.IN,
                    amount=entry.amount,
                    payment_date=locked_invoice.invoice_date,
                    note=f"فاکتور فروش {locked_invoice.invoice_number}",
                ),
                user,
            )
            allocate_payment(
                PaymentAllocation(payment=new_payment, sales_invoice=locked_invoice, amount=entry.amount),
                user,
            )

    log_event(
        actor=user,
        event_type="confirm_sale",
        target=locked_invoice,
        payload={"item_count": len(items), "shortage_count": len(shortages)},
    )

    return locked_invoice, shortages


@transaction.atomic
def cancel_sale(invoice, user):
    """
    Cancel a confirmed sales invoice: reverse its stock, freeze it (D-023).

    The invoice is never edited or reopened -- only a superuser may
    cancel, and a mistaken sale is corrected by a brand new invoice, never
    by editing this one (D-014 extended to cancelled invoices).

    One ADJUSTMENT_IN movement per original line restores exactly the
    quantity that confirm_sale removed, so the ledger stays a full,
    auditable history rather than deleting or editing the original rows.

    Args:
        invoice: the SalesInvoice to cancel.
        user: the user performing the action; must be a superuser.

    Returns:
        The cancelled SalesInvoice.

    Raises:
        ValidationError: invoice is not confirmed (draft or already
        cancelled), or ``user`` is not a superuser (D-023, §2.3).
    """
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)

    if locked_invoice.status != SalesInvoice.Status.CONFIRMED:
        raise ValidationError("فقط فاکتور تأییدشده قابل لغو است.")

    if not is_privileged(user):
        raise ValidationError("فقط ابرکاربر می‌تواند فاکتور را لغو کند.")

    items = list(locked_invoice.items.select_related("product").all())

    reversals = [
        InventoryMovement(
            product=item.product,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT_IN,
            quantity=item.quantity,
            unit_price=item.unit_price,
            created_by=user,
            note=f"لغو فاکتور فروش {locked_invoice.invoice_number}",
        )
        for item in items
    ]
    InventoryMovement.objects.bulk_create(reversals)

    locked_invoice.status = SalesInvoice.Status.CANCELLED
    locked_invoice.save(update_fields=["status", "updated_at"])

    log_event(
        actor=user,
        event_type="cancel_sale",
        target=locked_invoice,
        payload={"item_count": len(items)},
    )

    return locked_invoice
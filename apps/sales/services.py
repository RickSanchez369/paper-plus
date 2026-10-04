# path: apps/sales/services.py

"""
Business logic for sales invoices.

Unlike a purchase, a sale removes stock, so it must serialise against other
sales of the same products (D-015).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryMovement
from apps.inventory.selectors import get_stock_map
from apps.inventory.services import consume_fifo, restore_consumptions
from apps.payments.models import Cheque, Payment, PaymentAllocation
from apps.payments.selectors import get_party_credit
from apps.payments.services import (
    apply_party_credit,
    allocate_payment,
    record_cheque,
    record_payment,
    refund_invoice_payments,
    resolve_full_payment_amounts,
    validate_entry_account,
)
from apps.products.models import PriceTier, Product
from apps.products.units import split_units, units_phrase
from apps.shared.audit import log_event
from apps.shared.exchange import latest_valid_rate
from apps.shared.permissions import is_privileged
from apps.shared.services import get_next_document_number
from apps.shared.utils import format_toman

from .models import SalesInvoice, SalesPaymentEntry


def percent_to_amount(subtotal, percent):
    """
    Whole-Toman discount for ``percent`` % of ``subtotal`` (D-070).

    Rounded down, so the discount never exceeds what the percent says and
    never exceeds the subtotal. Only the Toman figure is ever stored; the
    percent was just a way of typing it.
    """
    return int(Decimal(subtotal) * Decimal(percent) / Decimal(100))


@transaction.atomic
def confirm_sale(invoice, user):
    """
    Confirm a draft sales invoice and remove its items from stock.

    A sale never takes stock below zero, for anyone (D-052): the missing goods
    have to be bought first.

    Args:
        invoice: the SalesInvoice to confirm.
        user: the user performing the action.

    Returns:
        (invoice, shortages). ``shortages`` is always empty now (a shortage
        raises instead); the tuple is kept so callers do not change.

    Raises:
        ValidationError: invoice is not a draft, has no items, or has a
        discount exceeding its subtotal; or a line asks for more than the
        stock on hand (D-052).
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

    # Number assigned only now, at confirmation (D-022) — never while draft;
    # built from the invoice's own date (D-086).
    locked_invoice.invoice_number = get_next_document_number("sale", on_date=locked_invoice.invoice_date)

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
        note = f"فاکتور فروش {locked_invoice.invoice_number}"

        if item.quantity > available:
            shortages.append({
                "product": item.product,
                "available": available,
                "requested": item.quantity,
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

    if shortages:
        raise ValidationError(
            "موجودی کافی نیست: "
            + "؛ ".join(
                f"«{s['product'].name}» (موجودی {units_phrase(*split_units(s['available'], s['product'].pack_per_carton))}، "
                f"درخواست {units_phrase(*split_units(s['requested'], s['product'].pack_per_carton))})"
                for s in shortages
            )
            + ". ابتدا خرید را ثبت کنید."
        )

    InventoryMovement.objects.bulk_create(movements)

    # FIFO: each line takes from the oldest layers still holding stock, and
    # what it took is recorded per layer, so the line's real cost is known
    # and a later cancellation can put back exactly those amounts. The product
    # rows are already locked above, which
    # is what keeps two concurrent sales from draining the same layer twice.
    for item in items:
        consume_fifo(
            item,
            item.quantity,
            user,
            note=f"فاکتور فروش {locked_invoice.invoice_number}",
        )

    # The sale type is picked on the invoice again and kept as chosen (D-090, replacing
    # D-081's "any carton = wholesale"); a value outside the two types is refused.
    if locked_invoice.price_tier not in PriceTier.values:
        raise ValidationError("نوع فروش (خرد/عمده) معتبر نیست.")
    locked_invoice.status = SalesInvoice.Status.CONFIRMED
    locked_invoice.confirmed_at = timezone.now()
    # Freeze today's USD rate on the invoice (D-080); None while no rate was ever read.
    locked_invoice.usd_rate = latest_valid_rate()
    locked_invoice.save(
        update_fields=["status", "confirmed_at", "invoice_number", "usd_rate", "price_tier", "updated_at"]
    )

    # Payment entries drafted on the invoice (Sina, 2026-09-24: "2M by
    # cheque, 1M cash, the rest نسیه"): each becomes a real Payment,
    # allocated to this invoice immediately, or a pending Cheque tied to
    # it (auto-allocated later when it clears -- see clear_cheque).
    # Whatever is left over than these rows is simply the نسیه/credit
    # portion; it needs no row of its own, payment_status already shows it.
    entries = list(locked_invoice.payment_entries.all())
    paid_by_rows = sum(entry.amount for entry in entries)
    # Money the customer already paid beyond earlier invoices pays this one first (D-087).
    credit_used = apply_party_credit(locked_invoice, user)
    due = locked_invoice.total - credit_used
    if paid_by_rows > due:
        if credit_used:
            raise ValidationError(
                f"جمع ردیف‌های پرداخت از مبلغ باقی‌ماندهٔ فاکتور بیشتر است "
                f"({format_toman(credit_used)} از بستانکاری قبلی کسر شد؛ باقی‌مانده {format_toman(due)})."
            )
        raise ValidationError("جمع ردیف‌های پرداخت از مبلغ کل فاکتور بیشتر است.")
    # What the rows leave unpaid is credit (نسیه) and needs a due date (D-069);
    # a due date on a fully covered invoice means nothing and is dropped.
    if paid_by_rows < due:
        if locked_invoice.credit_due_date is None:
            raise ValidationError("برای مبلغ نسیه، تاریخ سررسید را وارد کنید.")
    elif locked_invoice.credit_due_date is not None:
        locked_invoice.credit_due_date = None
        locked_invoice.save(update_fields=["credit_due_date", "updated_at"])
    for entry in entries:
        validate_entry_account(entry.method, entry.bank_account)
        if entry.method == SalesPaymentEntry.Method.CHEQUE:
            record_cheque(
                Cheque(
                    direction=Payment.Direction.IN,
                    customer=locked_invoice.customer,
                    bank_account=entry.bank_account,
                    cheque_number=entry.cheque_number,
                    bank_name=entry.bank_name,
                    issuer=entry.issuer,
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
                    customer=locked_invoice.customer,  # whose money this is
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


def plan_full_payment(invoice, parts):
    """
    The default settlement (D-046, D-069): the customer paid the whole
    invoice by card reader, by bank transfer, or by both.

    ``parts`` is ``[(method, account, amount_or_None)]`` as built by the
    form; `resolve_full_payment_amounts` settles it against the server's own
    ``invoice.total`` (never a figure from the browser) and raises if it does
    not add up. One payment-entry row per method is added on a draft invoice
    whose items are already saved -- confirm_sale then books them exactly like
    rows typed by hand (a real Payment, allocated to this invoice), so there is
    no second way money gets recorded. Nothing is planned when the total is
    not positive; confirm_sale rejects a discount above the subtotal on its own.

    Must be called inside the caller's transaction, before confirm_sale.
    """
    # What earlier credit will not cover (D-087): confirm applies the credit first.
    total = invoice.total - get_party_credit(customer=invoice.customer)
    if total <= 0:
        return []
    return [
        SalesPaymentEntry.objects.create(invoice=invoice, method=method, amount=amount, bank_account=account)
        for method, account, amount in resolve_full_payment_amounts(total, parts)
    ]


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
        cancelled), or ``user`` is not a superuser (D-023, D-034).
    """
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)

    if locked_invoice.status != SalesInvoice.Status.CONFIRMED:
        raise ValidationError("فقط فاکتور تأییدشده قابل لغو است.")

    if not is_privileged(user):
        raise ValidationError("فقط ابرکاربر می‌تواند فاکتور را لغو کند.")

    # A return already moved part of this invoice's goods and money (D-089); undoing
    # the whole invoice on top of it would count those twice.
    if locked_invoice.returns.exists():
        raise ValidationError("این فاکتور مرجوعی دارد و قابل لغو نیست.")

    items = list(locked_invoice.items.select_related("product").all())

    # Undo the FIFO draw first: every unit goes back to the exact layer it
    # came from, by recorded amount rather than by FIFO order, so a layer a
    # later sale has since drawn from still adds up.
    for item in items:
        restore_consumptions(
            item,
            user,
            note=f"لغو فاکتور فروش {locked_invoice.invoice_number}",
        )

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

    # The customer's money goes back with the goods (D-055): a refund
    # Payment per allocation, pending cheques cancelled.
    refunded = refund_invoice_payments(locked_invoice, user)

    locked_invoice.status = SalesInvoice.Status.CANCELLED
    locked_invoice.save(update_fields=["status", "updated_at"])

    log_event(
        actor=user,
        event_type="cancel_sale",
        target=locked_invoice,
        payload={"item_count": len(items), "refunded": refunded},
    )

    locked_invoice.refunded_amount = refunded
    return locked_invoice
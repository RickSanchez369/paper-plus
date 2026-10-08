# path: apps/returns/services.py

"""
The only writers of returns (D-089). Each call books the whole return in one
transaction: the document and its lines, the stock (FIFO), and the money.

Value of a returned line: its share of what the line really brought in (sales:
net of the invoice discount, D-048; purchases: the goods price, without freight).
A piece takes its share of what is still unreturned on the line and the last piece
takes the whole rest, so returning a line in several goes always adds up to exactly
the whole line, even after an earlier return was cancelled (D-101).

D-101 adds, on sales returns, a condition per line (resalable goods go back on the
shelf, damaged goods never enter stock and their cost is a loss), a damage deduction
that lowers what the customer is credited, and the cancellation of a return.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import InventoryConsumption, InventoryLayer, InventoryMovement
from apps.inventory.services import cancel_layer
from apps.payments.models import BankAccount, Cheque, Payment, PaymentAllocation
from apps.payments.services import allocate_payment, record_payment
from apps.shared.permissions import is_privileged
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice, PurchaseItem
from apps.sales.models import SaleItem, SalesInvoice
from apps.shared.audit import log_event
from apps.shared.services import get_next_document_number

from .models import (
    ItemCondition, PurchaseReturn, PurchaseReturnItem, ReturnStatus, SalesReturn, SalesReturnItem, SettleMode,
)


def _piece(rest, now, left):
    """The part of ``rest`` (value still unreturned) that ``now`` of the ``left`` units take; the last piece takes it all."""
    return rest if now == left else rest * now // left


def _open_credit(invoice, invoice_field, total):
    """What is still owed on the invoice outside pending cheques: a return may only take this off.
    A pending cheque's part must stay open, or clearing that cheque would over-pay the invoice."""
    pending = Cheque.objects.filter(**{invoice_field: invoice}, status=Cheque.Status.PENDING).aggregate(
        t=Sum("amount"))["t"] or 0
    return max(total - invoice.paid_amount - pending, 0)


def _active_items(item, returned_field, doc_field):
    """The return lines of ``item`` that still count: those of cancelled returns gave their units back (D-101)."""
    return getattr(item, returned_field).exclude(**{f"{doc_field}__status": ReturnStatus.CANCELLED})


def _clean_lines(lines, invoice, returned_field, doc_field):
    """
    ``lines`` = ``[(item, cartons, packs, condition, deduction)]`` as typed (the last two are optional);
    returns ``[(item, cartons, quantity, already, condition, deduction)]`` for the lines that return something,
    after checking each against what is left to return (cancelled returns do not count as returned).
    """
    out = []
    for line in lines:
        item, cartons, packs = line[:3]
        condition = line[3] if len(line) > 3 and line[3] else ItemCondition.RESALABLE
        deduction = int(line[4] or 0) if len(line) > 4 else 0
        if condition not in ItemCondition.values:
            raise ValidationError("وضعیت کالا معتبر نیست.")
        if deduction < 0:
            raise ValidationError("کسر خسارت نمی‌تواند منفی باشد.")
        cartons, packs = int(cartons or 0), int(packs or 0)
        if cartons < 0 or packs < 0:
            raise ValidationError("مقدار مرجوعی نمی‌تواند منفی باشد.")
        quantity = cartons * item.pack_per_carton + packs
        if quantity == 0:
            continue
        if item.invoice_id != invoice.pk:
            raise ValidationError("ردیف انتخاب‌شده متعلق به این فاکتور نیست.")
        already = _active_items(item, returned_field, doc_field).aggregate(t=Sum("quantity"))["t"] or 0
        left = item.quantity - already
        if quantity > left:
            raise ValidationError(
                f"«{item.product.name}»: حداکثر {left} بسته قابل مرجوع است ({quantity} بسته وارد شده)."
            )
        out.append((item, cartons, quantity, already, condition, deduction))
    if not out:
        raise ValidationError("حداقل یک ردیف با مقدار مرجوعی وارد کنید.")
    return out


def _settle_money(doc, invoice, invoice_field, total, party, direction, refund_direction, user, label):
    """
    Book the money side: a credit note for what comes off the invoice (and, when the
    surplus stays as credit, for that too), plus a bank refund for a refunded surplus.
    """
    applied = min(doc.total_amount, _open_credit(invoice, invoice_field, total))
    surplus = doc.total_amount - applied
    if surplus and doc.settle_mode == SettleMode.REFUND:
        account = doc.bank_account
        if account is None:
            raise ValidationError("برای برگشت وجه، حساب بانکی را انتخاب کنید.")
        if account.account_type != BankAccount.AccountType.CURRENT:
            raise ValidationError("برگشت وجه فقط از/به حساب جاری ممکن است (کارت‌خوان فقط دریافت می‌کند).")
    elif doc.settle_mode == SettleMode.CREDIT or not surplus:
        doc.bank_account = None

    credit_note_amount = doc.total_amount if doc.settle_mode == SettleMode.CREDIT else applied
    if credit_note_amount:
        note = record_payment(
            Payment(
                direction=direction,
                amount=credit_note_amount,
                payment_date=doc.return_date,
                note=f"{label} {doc.return_number}",
                is_credit_note=True,
                **party,
            ),
            user,
        )
        if applied:
            allocate_payment(PaymentAllocation(payment=note, amount=applied, **{invoice_field: invoice}), user)
        doc.credit_note = note
    if surplus and doc.settle_mode == SettleMode.REFUND:
        doc.refund_payment = record_payment(
            Payment(
                direction=refund_direction,
                amount=surplus,
                bank_account=doc.bank_account,
                payment_date=doc.return_date,
                note=f"برگشت وجه {label} {doc.return_number}",
                is_reversal=True,  # money back against the party's usual direction (D-055)
                **party,
            ),
            user,
        )
        doc.refund_amount = surplus
    else:
        doc.credit_amount = surplus
    doc.applied_amount = applied
    doc.save()


@transaction.atomic
def record_sales_return(invoice, lines, return_date, settle_mode, user, bank_account=None, note=""):
    """
    A customer brings goods back from a confirmed sales invoice (D-089).

    Stock comes back as a new FIFO layer per line, at that line's own FIFO cost per
    pack (its proportional share, floored to whole Toman per pack), so the shelf value
    and every later sale's cost stay real. The original sale, its consumptions and its
    profit are never edited (D-014): the return is its own document, and reports book
    its value and profit on the return date.

    Args:
        lines: ``[(SaleItem, cartons, packs, condition, deduction)]``; rows with nothing typed are skipped.
            ``condition`` is ``ItemCondition`` (resalable goods go back on the shelf, damaged goods never enter
            stock and their cost is a loss); ``deduction`` is the damage deduction in Toman, at most the
            line's value, and lowers what the customer is credited (D-101). The last two are optional.
        settle_mode: SettleMode -- what happens to the part the invoice's open debt
            does not absorb (credit for the customer, or a refund from a current account).

    Returns:
        The SalesReturn.
    """
    invoice = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != SalesInvoice.Status.CONFIRMED:
        raise ValidationError("فقط از فاکتور تأییدشده می‌توان مرجوعی ثبت کرد.")
    if return_date < invoice.invoice_date:
        raise ValidationError("تاریخ مرجوعی نمی‌تواند پیش از تاریخ فاکتور باشد.")
    item_ids = sorted(line[0].pk for line in lines)
    locked = {i.pk: i for i in SaleItem.objects.select_for_update().filter(pk__in=item_ids).select_related("product")}
    cleaned = _clean_lines([(locked[line[0].pk], *line[1:]) for line in lines], invoice, "return_items", "sales_return")
    # Same lock order as confirm_sale, so a return and a sale of the same product never deadlock.
    list(Product.objects.select_for_update().filter(pk__in=sorted({i.product_id for i, *_ in cleaned})).order_by("pk"))

    doc = SalesReturn(
        invoice=invoice,
        return_number=get_next_document_number("sales_return"),
        return_date=return_date,
        settle_mode=settle_mode,
        bank_account=bank_account,
        note=note,
        total_amount=0,
        created_by=user,
    )
    doc.save()
    total = 0
    for item, cartons, quantity, already, condition, deduction in cleaned:
        left = item.quantity - already
        active = _active_items(item, "return_items", "sales_return").aggregate(a=Sum("amount"), c=Sum("cost"))
        amount = _piece(item.net_total - (active["a"] or 0), quantity, left)
        cost = _piece(item.cost_of_goods - (active["c"] or 0), quantity, left)
        if deduction > amount:
            raise ValidationError(
                f"«{item.product.name}»: کسر خسارت ({deduction}) از ارزش این ردیف ({amount}) بیشتر است."
            )
        unit_cost = cost // quantity  # the layer's per-pack cost; the line's cost is what the layer holds
        ret_item = SalesReturnItem.objects.create(
            sales_return=doc, sale_item=item, quantity=quantity, cartons=cartons,
            pack_per_carton=item.pack_per_carton, amount=amount, cost=unit_cost * quantity,
            condition=condition, deduction=deduction,
        )
        if condition == ItemCondition.RESALABLE:
            layer = InventoryLayer.objects.create(
                product=item.product, source=InventoryLayer.Source.SALES_RETURN, sales_return_item=ret_item,
                quantity=quantity, quantity_remaining=quantity, unit_cost=unit_cost, created_by=user,
            )
            InventoryMovement.objects.create(
                product=item.product, movement_type=InventoryMovement.MovementType.SALES_RETURN, quantity=quantity,
                unit_price=unit_cost, sale_item=item, layer=layer, created_by=user,
                note=f"مرجوعی فروش {doc.return_number} از فاکتور {invoice.invoice_number}",
            )
        total += amount - deduction
    doc.total_amount = total
    _settle_money(doc, invoice, "sales_invoice", invoice.total, {"customer": invoice.customer},
                  Payment.Direction.IN, Payment.Direction.OUT, user, "مرجوعی فروش")
    log_event(actor=user, event_type="sales_return", target=doc,
              payload={"invoice": invoice.invoice_number, "amount": total, "settle": settle_mode,
                       "damaged": sum(1 for row in cleaned if row[4] == ItemCondition.DAMAGED)})
    return doc


@transaction.atomic
def record_purchase_return(invoice, lines, return_date, settle_mode, user, bank_account=None, note=""):
    """
    Goods go back to the supplier from a confirmed purchase invoice (D-089).

    The packs leave that purchase line's own FIFO layer (a consumption row, like a
    sale's), so only what is still on the shelf from that purchase can go back. The
    supplier owes the goods price of the packs; freight (D-082) is not refunded, so the
    shelf value removed (layer cost, freight included) can exceed the money.
    """
    invoice = PurchaseInvoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != PurchaseInvoice.Status.CONFIRMED:
        raise ValidationError("فقط از فاکتور تأییدشده می‌توان مرجوعی ثبت کرد.")
    if return_date < invoice.invoice_date:
        raise ValidationError("تاریخ مرجوعی نمی‌تواند پیش از تاریخ فاکتور باشد.")
    item_ids = sorted(line[0].pk for line in lines)
    locked = {i.pk: i for i in PurchaseItem.objects.select_for_update().filter(pk__in=item_ids).select_related("product")}
    cleaned = _clean_lines([(locked[line[0].pk], *line[1:3]) for line in lines], invoice, "return_items", "purchase_return")
    list(Product.objects.select_for_update().filter(pk__in=sorted({i.product_id for i, *_ in cleaned})).order_by("pk"))

    doc = PurchaseReturn(
        invoice=invoice,
        return_number=get_next_document_number("purchase_return"),
        return_date=return_date,
        settle_mode=settle_mode,
        bank_account=bank_account,
        note=note,
        total_amount=0,
        created_by=user,
    )
    doc.save()
    total = 0
    for item, cartons, quantity, already, _condition, _deduction in cleaned:
        left = item.quantity - already
        layer = InventoryLayer.objects.select_for_update().get(purchase_item=item)
        if quantity > layer.quantity_remaining:
            raise ValidationError(
                f"«{item.product.name}»: از این خرید فقط {layer.quantity_remaining} بسته در انبار مانده است؛ "
                f"بقیه فروخته شده و قابل مرجوع به تأمین‌کننده نیست."
            )
        active = _active_items(item, "return_items", "purchase_return").aggregate(a=Sum("amount"))["a"] or 0
        amount = _piece(item.line_total - active, quantity, left)
        ret_item = PurchaseReturnItem.objects.create(
            purchase_return=doc, purchase_item=item, quantity=quantity, cartons=cartons,
            pack_per_carton=item.pack_per_carton, amount=amount, cost=quantity * layer.unit_cost,
        )
        InventoryConsumption.objects.create(
            purchase_return_item=ret_item, layer=layer, quantity=quantity, created_by=user,
            note=f"مرجوعی خرید {doc.return_number}",
        )
        layer.quantity_remaining -= quantity
        layer.save(update_fields=["quantity_remaining", "updated_at"])
        InventoryMovement.objects.create(
            product=item.product, movement_type=InventoryMovement.MovementType.PURCHASE_RETURN, quantity=quantity,
            unit_price=layer.unit_cost, purchase_item=item, created_by=user,
            note=f"مرجوعی خرید {doc.return_number} از فاکتور {invoice.invoice_number}",
        )
        total += amount
    doc.total_amount = total
    _settle_money(doc, invoice, "purchase_invoice", invoice.total_amount, {"supplier": invoice.supplier},
                  Payment.Direction.OUT, Payment.Direction.IN, user, "مرجوعی خرید")
    log_event(actor=user, event_type="purchase_return", target=doc,
              payload={"invoice": invoice.invoice_number, "amount": total, "settle": settle_mode})
    return doc


def returnable_lines(invoice):
    """Per invoice line: what was sold/bought, what already came back, what is left (and, for purchases, still on the shelf)."""
    rows = []
    doc_field = "purchase_return" if isinstance(invoice, PurchaseInvoice) else "sales_return"
    for item in invoice.items.select_related("product"):
        returned = _active_items(item, "return_items", doc_field).aggregate(t=Sum("quantity"))["t"] or 0
        left = item.quantity - returned
        shelf = None
        if isinstance(item, PurchaseItem):
            layer = getattr(item, "layer", None)
            shelf = layer.quantity_remaining if layer else 0
            left = min(left, shelf)
        rows.append({"item": item, "returned": returned, "left": max(left, 0), "shelf": shelf})
    return rows


# ---------------------------------------------------------------------------------------------- cancel (D-101)

def _opposite(direction):
    return Payment.Direction.OUT if direction == Payment.Direction.IN else Payment.Direction.IN


def _check_cancellable(doc, user):
    """The common gate: only a superuser, only an active return."""
    if doc.status != ReturnStatus.ACTIVE:
        raise ValidationError("این مرجوعی قبلاً لغو شده است.")
    if not is_privileged(user):
        raise ValidationError("فقط ابرکاربر می‌تواند مرجوعی را لغو کند.")


def _undo_money(doc, invoice_field, party, user):
    """
    Take the return's money effects back (D-101): the credit note leaves the party's account (its share on the
    invoice is released, so the invoice owes it again; the rest of the credit is voided) and a refund that was
    paid out is booked back in the opposite direction. Refused when a later invoice already used the credit.
    """
    today = timezone.localdate()
    note = doc.credit_note
    if note is not None:
        note = Payment.objects.select_for_update().get(pk=note.pk)
        allocations = list(PaymentAllocation.objects.select_for_update().filter(payment=note))
        mine = [a for a in allocations if getattr(a, f"{invoice_field}_id") == doc.invoice_id and a.reversal_payment_id is None]
        if len(mine) != len(allocations):
            raise ValidationError("اعتبار ساخته‌شده از این مرجوعی در فاکتور دیگری مصرف شده است؛ لغو ممکن نیست.")
        for allocation in mine:
            reversal = Payment.objects.create(
                direction=_opposite(note.direction), amount=allocation.amount, payment_date=today,
                note=f"لغو مرجوعی {doc.return_number}", is_reversal=True, is_credit_note=True, created_by=user, **party,
            )
            allocation.reversal_payment = reversal
            allocation.save(update_fields=["reversal_payment", "updated_at"])
        note.voided_at = timezone.now()
        note.save(update_fields=["voided_at", "updated_at"])
    refund = doc.refund_payment
    if refund is not None:
        record_payment(
            Payment(
                direction=_opposite(refund.direction), amount=refund.amount, bank_account=refund.bank_account,
                payment_date=today, note=f"برگشت وجه بابت لغو مرجوعی {doc.return_number}", is_reversal=True, **party,
            ),
            user,
        )


@transaction.atomic
def cancel_sales_return(doc, user):
    """
    Cancel a sales return (superuser only, D-101): the return was recorded by mistake, so everything it did is
    undone and it is marked cancelled (never deleted, never edited otherwise).

    Allowed only while every effect can still be undone: the goods it put back on the shelf have not been sold
    again, and the credit it made has not been used by another invoice. A refund already paid out is booked
    back as money returning from the customer (the page warns the owner to collect it).
    """
    doc = SalesReturn.objects.select_for_update().get(pk=doc.pk)
    _check_cancellable(doc, user)
    items = list(doc.items.select_related("sale_item__product"))
    layers = []
    for ret_item in items:
        if ret_item.condition != ItemCondition.RESALABLE:
            continue  # damaged goods never entered stock
        layer = InventoryLayer.objects.select_for_update().get(sales_return_item=ret_item)
        if layer.quantity_remaining != layer.quantity:
            sold = layer.quantity - layer.quantity_remaining
            raise ValidationError(
                f"«{ret_item.sale_item.product.name}»: {sold} بسته از کالای برگشتی دوباره فروخته شده است؛ لغو مرجوعی ممکن نیست."
            )
        layers.append((ret_item, layer))
    _undo_money(doc, "sales_invoice", {"customer": doc.invoice.customer}, user)
    for ret_item, layer in layers:
        cancel_layer(layer, user)
        InventoryMovement.objects.create(
            product=ret_item.sale_item.product, movement_type=InventoryMovement.MovementType.ADJUSTMENT_OUT,
            quantity=ret_item.quantity, unit_price=layer.unit_cost, created_by=user,
            note=f"لغو مرجوعی فروش {doc.return_number}",
        )
    doc.status = ReturnStatus.CANCELLED
    doc.cancelled_at = timezone.now()
    doc.cancelled_by = user
    doc.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
    log_event(actor=user, event_type="cancel_sales_return", target=doc,
              payload={"invoice": doc.invoice.invoice_number, "amount": doc.total_amount})
    return doc


@transaction.atomic
def cancel_purchase_return(doc, user):
    """
    Cancel a purchase return (superuser only, D-101): the packs go back into the purchase line's own layer, the
    supplier's refund or prepayment is reversed, and the return is marked cancelled.

    Refused when a later invoice already used the prepayment this return created.
    """
    doc = PurchaseReturn.objects.select_for_update().get(pk=doc.pk)
    _check_cancellable(doc, user)
    items = list(doc.items.select_related("purchase_item__product"))
    restores = []
    for ret_item in items:
        layer = InventoryLayer.objects.select_for_update().get(purchase_item=ret_item.purchase_item)
        if layer.cancelled_at is not None:
            raise ValidationError(f"«{ret_item.purchase_item.product.name}»: لایهٔ این خرید لغو شده است؛ لغو مرجوعی ممکن نیست.")
        restores.append((ret_item, layer))
    _undo_money(doc, "purchase_invoice", {"supplier": doc.invoice.supplier}, user)
    for ret_item, layer in restores:
        InventoryConsumption.objects.create(
            purchase_return_item=ret_item, layer=layer, quantity=-ret_item.quantity, created_by=user,
            note=f"لغو مرجوعی خرید {doc.return_number}",
        )
        layer.quantity_remaining += ret_item.quantity
        layer.save(update_fields=["quantity_remaining", "updated_at"])
        InventoryMovement.objects.create(
            product=ret_item.purchase_item.product, movement_type=InventoryMovement.MovementType.ADJUSTMENT_IN,
            quantity=ret_item.quantity, unit_price=layer.unit_cost, created_by=user,
            note=f"لغو مرجوعی خرید {doc.return_number}",
        )
    doc.status = ReturnStatus.CANCELLED
    doc.cancelled_at = timezone.now()
    doc.cancelled_by = user
    doc.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
    log_event(actor=user, event_type="cancel_purchase_return", target=doc,
              payload={"invoice": doc.invoice.invoice_number, "amount": doc.total_amount})
    return doc

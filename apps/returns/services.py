# path: apps/returns/services.py

"""
The only writers of returns (D-089). Each call books the whole return in one
transaction: the document and its lines, the stock (FIFO), and the money.

Value of a returned line: its share of what the line really brought in (sales:
net of the invoice discount, D-048; purchases: the goods price, without freight).
Shares are taken on the running total ("floor of what has been returned so far"),
so returning a line in several goes always adds up to exactly the whole line.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.inventory.models import InventoryConsumption, InventoryLayer, InventoryMovement
from apps.payments.models import BankAccount, Cheque, Payment, PaymentAllocation
from apps.payments.services import allocate_payment, record_payment
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice, PurchaseItem
from apps.sales.models import SaleItem, SalesInvoice
from apps.shared.audit import log_event
from apps.shared.services import get_next_document_number

from .models import PurchaseReturn, PurchaseReturnItem, SalesReturn, SalesReturnItem, SettleMode


def _share(total, done, now, whole):
    """The part of ``total`` that ``now`` more units out of ``whole`` take, after ``done`` (exact over all goes)."""
    return total * (done + now) // whole - total * done // whole


def _open_credit(invoice, invoice_field, total):
    """What is still owed on the invoice outside pending cheques: a return may only take this off.
    A pending cheque's part must stay open, or clearing that cheque would over-pay the invoice."""
    pending = Cheque.objects.filter(**{invoice_field: invoice}, status=Cheque.Status.PENDING).aggregate(
        t=Sum("amount"))["t"] or 0
    return max(total - invoice.paid_amount - pending, 0)


def _clean_lines(lines, invoice, returned_field):
    """
    ``lines`` = ``[(item, cartons, packs)]`` as typed; returns ``[(item, cartons, quantity)]``
    for the lines that return something, after checking each against what is left to return.
    """
    out = []
    for item, cartons, packs in lines:
        cartons, packs = int(cartons or 0), int(packs or 0)
        if cartons < 0 or packs < 0:
            raise ValidationError("مقدار مرجوعی نمی‌تواند منفی باشد.")
        quantity = cartons * item.pack_per_carton + packs
        if quantity == 0:
            continue
        if item.invoice_id != invoice.pk:
            raise ValidationError("ردیف انتخاب‌شده متعلق به این فاکتور نیست.")
        already = getattr(item, returned_field).aggregate(t=Sum("quantity"))["t"] or 0
        left = item.quantity - already
        if quantity > left:
            raise ValidationError(
                f"«{item.product.name}»: حداکثر {left} بسته قابل مرجوع است ({quantity} بسته وارد شده)."
            )
        out.append((item, cartons, quantity, already))
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
        lines: ``[(SaleItem, cartons, packs)]``; rows with nothing typed are skipped.
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
    item_ids = sorted(item.pk for item, _, _ in lines)
    locked = {i.pk: i for i in SaleItem.objects.select_for_update().filter(pk__in=item_ids).select_related("product")}
    cleaned = _clean_lines([(locked[i.pk], c, p) for i, c, p in lines], invoice, "return_items")
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
    for item, cartons, quantity, already in cleaned:
        amount = _share(item.net_total, already, quantity, item.quantity)
        cost = _share(item.cost_of_goods, already, quantity, item.quantity)
        unit_cost = cost // quantity  # the layer's per-pack cost; the line's cost is what the layer holds
        ret_item = SalesReturnItem.objects.create(
            sales_return=doc, sale_item=item, quantity=quantity, cartons=cartons,
            pack_per_carton=item.pack_per_carton, amount=amount, cost=unit_cost * quantity,
        )
        layer = InventoryLayer.objects.create(
            product=item.product, source=InventoryLayer.Source.SALES_RETURN, sales_return_item=ret_item,
            quantity=quantity, quantity_remaining=quantity, unit_cost=unit_cost, created_by=user,
        )
        InventoryMovement.objects.create(
            product=item.product, movement_type=InventoryMovement.MovementType.SALES_RETURN, quantity=quantity,
            unit_price=unit_cost, sale_item=item, layer=layer, created_by=user,
            note=f"مرجوعی فروش {doc.return_number} از فاکتور {invoice.invoice_number}",
        )
        total += amount
    doc.total_amount = total
    _settle_money(doc, invoice, "sales_invoice", invoice.total, {"customer": invoice.customer},
                  Payment.Direction.IN, Payment.Direction.OUT, user, "مرجوعی فروش")
    log_event(actor=user, event_type="sales_return", target=doc,
              payload={"invoice": invoice.invoice_number, "amount": total, "settle": settle_mode})
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
    item_ids = sorted(item.pk for item, _, _ in lines)
    locked = {i.pk: i for i in PurchaseItem.objects.select_for_update().filter(pk__in=item_ids).select_related("product")}
    cleaned = _clean_lines([(locked[i.pk], c, p) for i, c, p in lines], invoice, "return_items")
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
    for item, cartons, quantity, already in cleaned:
        layer = InventoryLayer.objects.select_for_update().get(purchase_item=item)
        if quantity > layer.quantity_remaining:
            raise ValidationError(
                f"«{item.product.name}»: از این خرید فقط {layer.quantity_remaining} بسته در انبار مانده است؛ "
                f"بقیه فروخته شده و قابل مرجوع به تأمین‌کننده نیست."
            )
        amount = _share(item.line_total, already, quantity, item.quantity)
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
    for item in invoice.items.select_related("product").prefetch_related("return_items"):
        returned = sum(r.quantity for r in item.return_items.all())
        left = item.quantity - returned
        shelf = None
        if isinstance(item, PurchaseItem):
            layer = getattr(item, "layer", None)
            shelf = layer.quantity_remaining if layer else 0
            left = min(left, shelf)
        rows.append({"item": item, "returned": returned, "left": max(left, 0), "shelf": shelf})
    return rows


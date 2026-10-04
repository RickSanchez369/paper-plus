# path: apps/inventory/unit_conversion.py

"""
One-time conversion from "pack products and carton products" to one product
counted in packs (D-081).

Before D-081 a product was counted in ONE unit; the same goods sold by the
pack and by the carton were two products. Now there is one product, the base
unit is the pack, and a carton is `pack_per_carton` packs. Products already
counted in packs need nothing but the wholesale price (handled by migration
`products.0009`). Products counted in cartons have to be rewritten into packs:
their stock, FIFO layers, movements, consumptions and invoice lines, and
optionally merged into the pack product that sells the same goods.

Nothing here decides which products are the same goods: a human lists the
merges in a map file (`merge_units`, never guessed). Everything runs inside one
transaction and is checked against the figures it started from; a dry run
does all of it and rolls back. This module is deleted once the conversion has
been run on every database.

Ledger rows are append-only for the application (D-012); this one-off rewrite
uses queryset `.update()` on purpose and is the only thing allowed to.
"""

from django.db import transaction
from django.db.models import F, Sum

from apps.inventory.models import InventoryConsumption, InventoryLayer, InventoryMovement
from apps.inventory.selectors import get_stock_map
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice, PurchaseItem
from apps.sales.models import SaleItem, SalesInvoice


class ConversionError(Exception):
    """The conversion cannot be done as asked; nothing was changed."""


def _round_div(value, divisor):
    """Integer division rounded to the nearest whole number (half up)."""
    return (2 * value + divisor) // (2 * divisor)


def snapshot():
    """The figures a conversion must keep: stock per product, money, and every invoice total."""
    products = list(Product.objects.all())
    stock = get_stock_map([p.pk for p in products])
    layer_value = InventoryLayer.objects.filter(cancelled_at__isnull=True).aggregate(
        v=Sum(F("quantity_remaining") * F("unit_cost"))
    )["v"] or 0
    consumed_cost = InventoryConsumption.objects.aggregate(v=Sum(F("quantity") * F("layer__unit_cost")))["v"] or 0
    return {
        "stock": {p.pk: stock.get(p.pk, 0) for p in products},
        "inventory_value": layer_value,
        "cost_of_goods": consumed_cost,
        "sales": {i.pk: i.total for i in SalesInvoice.objects.all()},
        "purchases": {i.pk: i.total_amount for i in PurchaseInvoice.objects.all()},
    }


def report():
    """
    Read-only picture for deciding the map: every product with its unit, stock,
    layers and prices, which carton products could be the same goods as a pack
    product (same name apart from spacing/case), whether their costs divide
    evenly, and invoices that carry both products of a pair (those block a merge).
    """
    products = list(Product.objects.order_by("name"))
    stock = get_stock_map([p.pk for p in products])
    rows = []
    for p in products:
        layers = list(InventoryLayer.objects.filter(product=p, cancelled_at__isnull=True))
        rows.append({
            "sku": p.sku, "name": p.name, "unit": p.unit, "active": p.is_active, "pack_per_carton": p.pack_per_carton,
            "stock": stock.get(p.pk, 0), "layers": [(l.quantity_remaining, l.unit_cost) for l in layers],
            "uneven_costs": [l.unit_cost for l in layers if p.unit == Product.Unit.CARTON and l.unit_cost % p.pack_per_carton],
            "retail": p.default_selling_price, "wholesale": p.wholesale_selling_price,
        })

    def key(name):
        return "".join(name.split()).casefold()

    packs = [p for p in products if p.unit == Product.Unit.PACK]
    pairs = []
    for c in (p for p in products if p.unit == Product.Unit.CARTON):
        for q in packs:
            if key(c.name) == key(q.name):
                both = SalesInvoice.objects.filter(items__product=c).filter(items__product=q).distinct().count()
                both += PurchaseInvoice.objects.filter(items__product=c).filter(items__product=q).distinct().count()
                pairs.append({"carton": c.sku, "pack": q.sku, "name": c.name, "invoices_with_both": both})
    return {"products": rows, "candidate_pairs": pairs}


@transaction.atomic
def convert(merge=None, pack_per_carton=None, dry_run=False):
    """
    Rewrite every carton-counted product into packs.

    ``merge``: ``{carton_sku: pack_sku}`` -- fold that carton product into that
    pack product (its ratio is used). ``pack_per_carton``: ``{sku: ratio}``
    overrides the default 5 for a product. Returns the before/after figures;
    raises `ConversionError` (changing nothing) on anything that does not add up.
    With ``dry_run`` everything is done and then rolled back.
    """
    merge = merge or {}
    ratios = pack_per_carton or {}
    by_sku = {p.sku: p for p in Product.objects.select_for_update().all()}
    for carton_sku, pack_sku in merge.items():
        if carton_sku not in by_sku or pack_sku not in by_sku:
            raise ConversionError(f"کالای نقشه پیدا نشد: {carton_sku} / {pack_sku}")
        if by_sku[carton_sku].unit != Product.Unit.CARTON or by_sku[pack_sku].unit != Product.Unit.PACK:
            raise ConversionError(f"ادغام باید از یک کالای کارتنی به یک کالای بسته‌ای باشد: {carton_sku} -> {pack_sku}")
    for sku, ratio in ratios.items():
        if sku not in by_sku or int(ratio) < 1:
            raise ConversionError(f"نسبت نامعتبر برای {sku}")
        Product.objects.filter(pk=by_sku[sku].pk).update(pack_per_carton=int(ratio))

    before = snapshot()
    cartons = list(Product.objects.filter(unit=Product.Unit.CARTON))
    uneven = []
    ratio_of = {}
    for c in cartons:
        target = by_sku[merge[c.sku]] if c.sku in merge else None
        ratio = Product.objects.get(pk=(target or c).pk).pack_per_carton
        ratio_of[c.pk] = ratio
        if target is not None:
            clash = (
                SalesInvoice.objects.filter(items__product=c).filter(items__product=target).exists()
                or PurchaseInvoice.objects.filter(items__product=c).filter(items__product=target).exists()
            )
            if clash:
                raise ConversionError(f"یک فاکتور هر دو کالای {c.sku} و {target.sku} را دارد؛ ادغام ممکن نیست.")
        # Collected before the layers move, while they still belong to the carton product.
        consumptions = list(InventoryConsumption.objects.filter(layer__product=c).values_list("pk", "quantity"))
        for layer in InventoryLayer.objects.filter(product=c):
            if layer.unit_cost % ratio:
                uneven.append((c.sku, layer.unit_cost))
            InventoryLayer.objects.filter(pk=layer.pk).update(
                product=target or c,
                quantity=layer.quantity * ratio,
                quantity_remaining=layer.quantity_remaining * ratio,
                unit_cost=_round_div(layer.unit_cost, ratio),
            )
        for pk, quantity in consumptions:
            InventoryConsumption.objects.filter(pk=pk).update(quantity=quantity * ratio)
        for move in InventoryMovement.objects.filter(product=c):
            InventoryMovement.objects.filter(pk=move.pk).update(
                product=target or c,
                quantity=move.quantity * ratio,
                unit_price=None if move.unit_price is None else _round_div(move.unit_price, ratio),
            )
        for model in (SaleItem, PurchaseItem):
            for item in model.objects.filter(product=c):
                model.objects.filter(pk=item.pk).update(
                    product=target or c,
                    cartons=item.quantity,
                    pack_per_carton=ratio,
                    carton_price=item.unit_price,
                    quantity=item.quantity * ratio,
                    unit_price=_round_div(item.unit_price, ratio),
                )
        # A carton product's "retail" price was the price of a carton; its wholesale (when really set) too.
        carton_price = c.wholesale_selling_price if c.wholesale_selling_price > 0 else c.default_selling_price
        if target is None:
            really_set = c.wholesale_selling_price > 0 and c.wholesale_selling_price != c.default_selling_price
            Product.objects.filter(pk=c.pk).update(
                unit=Product.Unit.PACK, pack_per_carton=ratio,
                default_selling_price=_round_div(c.default_selling_price, ratio),
                wholesale_selling_price=c.wholesale_selling_price if really_set else 0,
            )
        else:
            if target.wholesale_selling_price == 0:
                Product.objects.filter(pk=target.pk).update(wholesale_selling_price=carton_price)
            Product.objects.filter(pk=c.pk).update(is_active=False)

    after = snapshot()
    problems = []
    if before["sales"] != after["sales"] or before["purchases"] != after["purchases"]:
        problems.append("جمع بعضی فاکتورها تغییر کرد")
    expected = dict(before["stock"])
    for c in cartons:
        moved = before["stock"][c.pk] * ratio_of[c.pk]
        if c.sku in merge:
            expected[c.pk] = 0
            expected[by_sku[merge[c.sku]].pk] += moved
        else:
            expected[c.pk] = moved
    names = {p.pk: p.sku for p in Product.objects.all()}
    for pk, want in expected.items():
        if after["stock"].get(pk, 0) != want:
            problems.append(f"موجودی {names[pk]}: انتظار {want}، پس از تبدیل {after['stock'].get(pk, 0)}")
    if InventoryLayer.objects.filter(quantity_remaining__gt=F("quantity")).exists():
        problems.append("مانده‌ی یک لایه از مقدار اولیه‌اش بیشتر شد")
    if problems:
        raise ConversionError("؛ ".join(problems))
    result = {
        "before": before, "after": after, "uneven_costs": uneven,
        "value_drift": after["inventory_value"] - before["inventory_value"],
        "cost_of_goods_drift": after["cost_of_goods"] - before["cost_of_goods"],
    }
    if dry_run:
        transaction.set_rollback(True)
    return result

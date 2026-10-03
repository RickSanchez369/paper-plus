"""D-081: the one-time conversion of carton products into packs (report, dry run, merge, reconciliation)."""
from tools.qa.qa_lib import *
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.inventory.models import InventoryLayer
from apps.inventory.selectors import get_stock
from apps.inventory.unit_conversion import ConversionError, convert, report
from apps.products.models import Product
from apps.sales.models import SaleItem, SalesInvoice


def legacy_carton_product(h, name, stock, cost, price):
    """A product counted in cartons the way it was before D-081 (unit carton, quantities in cartons)."""
    p = h.product(name=name, stock=stock, cost=cost, price=price)
    Product.objects.filter(pk=p.pk).update(unit="کارتن")
    p.refresh_from_db()
    return p


def scenarios(h):
    acct = h.account()
    cust = h.customer()
    # Park every other carton product of the dev database: the conversion looks at all of them.
    Product.objects.exclude(sku__startswith="QA").filter(unit="کارتن").update(unit="بسته")

    name = "QA-same-" + rnd()
    pack = h.product(name=name, stock=7, cost=300, price=400)
    carton = legacy_carton_product(h, name.upper(), stock=6, cost=1500, price=2400)
    Product.objects.filter(pk=carton.pk).update(wholesale_selling_price=2300)
    # A sale in the legacy shape: 2 cartons at 2500 each, typed as plain quantity.
    h.post_sale(cust, [h.item_row(carton, 2, 2500)], account=acct)
    old = SalesInvoice.objects.filter(customer=cust).latest("created_at")
    old_total, old_cogs = old.total, old.cost_of_goods

    rep = report()
    check("CV01 report lists both products and sees the pair", any(r["sku"] == carton.sku and r["unit"] == "کارتن" for r in rep["products"])
          and any(p_["carton"] == carton.sku and p_["pack"] == pack.sku for p_ in rep["candidate_pairs"]))
    out = StringIO()
    call_command("inventory_unit_report", stdout=out)
    check("CV02 the report command prints and writes nothing", carton.sku in out.getvalue() and get_stock(carton) == 4)

    # ---- dry run changes nothing
    res = convert(merge={carton.sku: pack.sku}, dry_run=True)
    check("CV03 a dry run reports no drift and rolls back", res["value_drift"] == 0 and res["cost_of_goods_drift"] == 0
          and get_stock(carton) == 4 and get_stock(pack) == 7 and Product.objects.get(pk=carton.pk).is_active)

    # ---- bad maps
    for label, mapping in (("unknown sku", {"NOPE": pack.sku}), ("pack as the source", {pack.sku: carton.sku})):
        try:
            convert(merge=mapping, dry_run=True)
            ok = False
        except ConversionError:
            ok = True
        check(f"CV04 map with {label} is refused", ok)

    # ---- the real thing
    res = convert(merge={carton.sku: pack.sku})
    pack.refresh_from_db()
    carton.refresh_from_db()
    check("CV10 merged stock = 7 own + 4 cartons x 5 = 27 packs", get_stock(pack) == 27 and get_stock(carton) == 0, (get_stock(pack), get_stock(carton)))
    check("CV11 the carton product is parked (inactive), not deleted", carton.is_active is False)
    lay = InventoryLayer.objects.filter(product=pack).order_by("created_at")
    check("CV12 its layer became 30 packs at 300 each", any(l.quantity == 30 and l.unit_cost == 300 for l in lay), [(l.quantity, l.unit_cost) for l in lay])
    old = SalesInvoice.objects.get(pk=old.pk)
    line = old.items.get()
    check("CV13 the old sale line reads 2 cartons = 10 packs on the pack product", line.product_id == pack.pk and (line.cartons, line.quantity, line.pack_per_carton) == (2, 10, 5))
    check("CV14 the invoice total is exactly what it was (2 x 2500)", old.total == old_total == 5000)
    check("CV15 the FIFO cost of that sale is unchanged (10 x 300 = 2 x 1500)", old.cost_of_goods == old_cogs == 3000, old.cost_of_goods)
    check("CV16 pack product's carton price is taken from the carton product's wholesale price", pack.wholesale_selling_price == 2300)
    page = h.c.get(f"/sales/{old.pk}/")
    check("CV17 the invoice page shows it as cartons + packs", has(page, "۲ کارتن"))

    # ---- not merged: a carton product alone is rewritten into packs
    solo = legacy_carton_product(h, "QA-solo-" + rnd(), stock=3, cost=1000, price=5000)
    Product.objects.filter(pk=solo.pk).update(wholesale_selling_price=4500)
    res = convert()
    solo.refresh_from_db()
    check("CV20 a lone carton product: 3 cartons -> 15 packs at 200, pack price 1000, carton price 4500",
          get_stock(solo) == 15 and solo.unit == "بسته" and solo.default_selling_price == 1000 and solo.wholesale_selling_price == 4500
          and InventoryLayer.objects.get(product=solo).unit_cost == 200)

    # ---- costs that do not divide
    odd = legacy_carton_product(h, "QA-odd-" + rnd(), stock=2, cost=1503, price=100)
    res = convert(dry_run=True)
    check("CV30 a cost of 1503 per carton is flagged and the drift reported", (odd.sku, 1503) in res["uneven_costs"] and res["value_drift"] != 0, res["uneven_costs"])
    try:
        call_command("convert_units", "--dry-run", stdout=StringIO())
        refused = False
    except CommandError:
        refused = True
    check("CV31 the command refuses uneven costs without --allow-rounding", refused)
    call_command("convert_units", "--dry-run", "--allow-rounding", stdout=StringIO())
    check("CV32 --allow-rounding with --dry-run still changes nothing", get_stock(odd) == 2)
    call_command("convert_units", "--allow-rounding", stdout=StringIO())
    check("CV33 the real run converts it: 10 packs at 301", get_stock(odd) == 10 and InventoryLayer.objects.get(product=odd).unit_cost == 301)

    # ---- an invoice carrying both products blocks a merge
    n1 = "QA-blk-" + rnd()
    pk_ = h.product(name=n1, stock=10, cost=100, price=300)
    ck_ = legacy_carton_product(h, n1 + " ", stock=10, cost=500, price=900)
    h.post_sale(cust, [h.item_row(pk_, 1, 300), h.item_row(ck_, 1, 900)], account=acct)
    try:
        convert(merge={ck_.sku: pk_.sku}, dry_run=True)
        blocked = False
    except ConversionError:
        blocked = True
    check("CV40 two lines of the same invoice cannot be merged into one", blocked)


run("convert_units", scenarios)

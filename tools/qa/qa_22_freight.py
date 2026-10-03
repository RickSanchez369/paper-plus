"""D-082: freight on a purchase invoice is part of what is owed and of every line's landed cost."""
from tools.qa.qa_lib import *
from apps.inventory.models import InventoryLayer, InventoryMovement
from apps.inventory.selectors import get_average_cost_map, get_stock
from apps.payments.selectors import get_supplier_outstanding
from apps.purchasing.models import PurchaseInvoice
from apps.purchasing.services import allocate_freight
from apps.shared import reports


def last_purchase(s):
    return PurchaseInvoice.objects.filter(supplier=s).latest("created_at")


class Fake:
    """A stand-in line for the pure allocation function."""

    def __init__(self, pk, quantity):
        self.pk, self.quantity = pk, quantity


def scenarios(h):
    acct = h.account()
    sup = h.supplier()

    # ---------------------------------------------------- the allocation rule
    shares = allocate_freight(1000, [Fake("a", 10), Fake("b", 30)])
    check("FR01 freight splits by packs: 250 / 750", shares == {"a": 250, "b": 750}, shares)
    shares = allocate_freight(100, [Fake("a", 1), Fake("b", 1), Fake("c", 1)])
    check("FR02 the leftover Toman go to the biggest remainders and the sum is exact", sum(shares.values()) == 100 and sorted(shares.values()) == [33, 33, 34], shares)
    check("FR03 no freight, no share", allocate_freight(0, [Fake("a", 5)]) == {"a": 0})
    check("FR04 the same invoice always splits the same way", allocate_freight(100, [Fake("a", 1), Fake("b", 1), Fake("c", 1)]) == shares)

    # ---------------------------------------------------- a purchase with freight: 10M on 20 cartons of goods
    p = h.product(stock=0, price=100000)
    r = h.post_purchase(sup, [h.carton_row(p, 3, packs=2, carton_price=1_000_000, unit_price=200_000)], account=acct,
                        extra={"has_freight": "on", "freight_amount": "1000000"})
    inv = last_purchase(sup)
    goods = 3 * 1_000_000 + 2 * 200_000
    check("FR10 the invoice is created with freight", r.status_code == 302 and inv.freight_amount == 1_000_000, r.status_code)
    check("FR11 total owed = goods + freight", inv.items_total == goods and inv.total_amount == goods + 1_000_000, (inv.items_total, inv.total_amount))
    item = inv.items.get()
    check("FR12 the line carries all the freight (one line)", item.freight_share == 1_000_000 and item.cost_total == goods + 1_000_000)
    lay = InventoryLayer.objects.get(purchase_item=item)
    check("FR13 the FIFO layer cost per pack = (goods + freight) / 17 packs, rounded",
          lay.quantity == 17 and lay.unit_cost == (2 * (goods + 1_000_000) + 17) // 34, lay.unit_cost)
    check("FR14 the purchase movement and the average price use that cost", InventoryMovement.objects.get(purchase_item=item).unit_price == lay.unit_cost
          and get_average_cost_map([p.pk])[p.pk] == lay.unit_cost)
    check("FR15 cost per carton = cost per pack x 5", item.carton_cost == (2 * item.cost_total * 5 + 17) // 34)
    check("FR16 paid in full: the transfer covers goods + freight, nothing is outstanding",
          inv.payment_status == "paid" and get_supplier_outstanding(sup) == 0, (inv.payment_status, get_supplier_outstanding(sup)))

    # ---------------------------------------------------- several lines: by packs
    a = h.product(stock=0, price=1000)
    b = h.product(stock=0, price=1000)
    h.post_purchase(sup, [h.item_row(a, 10, 100), h.item_row(b, 30, 100)], account=acct, extra={"has_freight": "on", "freight_amount": "400"})
    inv = last_purchase(sup)
    ia, ib = inv.items.get(product=a), inv.items.get(product=b)
    check("FR20 freight 400 over 10 and 30 packs: 100 and 300", (ia.freight_share, ib.freight_share) == (100, 300), (ia.freight_share, ib.freight_share))
    check("FR21 shares add up to the freight", ia.freight_share + ib.freight_share == inv.freight_amount)
    la = InventoryLayer.objects.get(purchase_item=ia)
    lb = InventoryLayer.objects.get(purchase_item=ib)
    check("FR22 landed pack cost: a = (1000 + 100) / 10 = 110, b = (3000 + 300) / 30 = 110", (la.unit_cost, lb.unit_cost) == (110, 110), (la.unit_cost, lb.unit_cost))

    # ---------------------------------------------------- credit: the freight is part of the debt
    c = h.product(stock=0, price=1000)
    h.post_purchase(sup, [h.item_row(c, 10, 100)], mode="split", payments=[], credit_due="1405/12/29",
                    extra={"has_freight": "on", "freight_amount": "250"})
    inv = last_purchase(sup)
    check("FR30 on credit the supplier is owed goods + freight", inv.outstanding == 1250 and get_supplier_outstanding(sup) == 1250, (inv.outstanding, get_supplier_outstanding(sup)))
    from apps.payments.selectors import get_total_payables_as_of
    import datetime
    check("FR31 the payables total includes it", get_total_payables_as_of(datetime.date.today()) >= 1250)

    # ---------------------------------------------------- form rules
    n = PurchaseInvoice.objects.filter(supplier=sup).count()
    r = h.post_purchase(sup, [h.item_row(c, 1, 100)], account=acct, extra={"has_freight": "on", "freight_amount": ""})
    check("FR40 freight ticked without an amount is refused", r.status_code == 200 and PurchaseInvoice.objects.filter(supplier=sup).count() == n)
    r = h.post_purchase(sup, [h.item_row(c, 1, 100)], account=acct, extra={"has_freight": "on", "freight_amount": "-5"})
    check("FR41 a negative freight is refused", r.status_code == 200 and PurchaseInvoice.objects.filter(supplier=sup).count() == n)
    r = h.post_purchase(sup, [h.item_row(c, 1, 100)], account=acct, extra={"freight_amount": "777"})
    inv = last_purchase(sup)
    check("FR42 an amount without the tick is ignored", r.status_code == 302 and inv.freight_amount == 0 and inv.total_amount == 100, inv.freight_amount)
    r = h.post_purchase(sup, [h.item_row(c, 1, 100)], account=acct, extra={"has_freight": "on", "freight_amount": "99999999999999999999999"})
    check("FR43 an absurdly large freight does not crash", r.status_code in (200, 302))

    # ---------------------------------------------------- cancelling
    d = h.product(stock=0, price=1000)
    h.post_purchase(sup, [h.item_row(d, 10, 100)], account=acct, extra={"has_freight": "on", "freight_amount": "100"})
    inv = last_purchase(sup)
    rc = h.c.post(f"/purchasing/{inv.pk}/cancel/")
    check("FR50 cancelling takes the stock off again", get_stock(d) == 0 and PurchaseInvoice.objects.get(pk=inv.pk).status == "cancelled", rc.status_code)
    out = InventoryMovement.objects.filter(product=d, movement_type="adjustment_out").first()
    check("FR51 the reversal movement carries the landed cost (110)", out is not None and out.unit_price == 110, out and out.unit_price)

    # ---------------------------------------------------- pages
    inv = last_purchase(sup)
    d2 = h.product(stock=0, price=1000)
    h.post_purchase(sup, [h.carton_row(d2, 2, packs=0, carton_price=500)], account=acct, extra={"has_freight": "on", "freight_amount": "50"})
    inv = last_purchase(sup)
    page = h.c.get(f"/purchasing/{inv.pk}/")
    check("FR60 detail shows items total, freight and total", page.status_code == 200 and has(page, "کرایه بار") and shown(page, 1050) and shown(page, 1000), page.status_code)
    check("FR61 detail shows the landed cost per pack and per carton", has(page, "بهای تمام‌شده") and has(page, "کارتن:") and shown(page, 525))
    page = h.c.get(f"/purchasing/{inv.pk}/print/")
    check("FR62 the printed invoice shows the freight line", has(page, "کرایه بار") and shown(page, 1050))
    page = h.c.get("/purchasing/new/")
    check("FR63 the new purchase page has the freight tick and amount", has(page, 'name="has_freight"') and has(page, 'name="freight_amount"') and has(page, 'id="sale-subtotal"'))
    page = h.c.get("/purchasing/")
    check("FR64 the list shows the total with freight", page.status_code == 200 and shown(page, 1050))
    check("FR65 reports count the purchase total with freight", reports.purchases_total(h.today, h.today) >= 1050)


run("freight", scenarios)

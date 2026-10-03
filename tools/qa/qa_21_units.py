"""D-081: one product, two trade units (carton = packs per carton, default 5), stock in packs,
average purchase price of the stock still held kept apart from FIFO profit."""
from tools.qa.qa_lib import *
from apps.inventory.models import InventoryLayer
from apps.inventory.selectors import get_average_cost_map, get_current_cost_map, get_stock
from apps.products.models import Product
from apps.products.units import split_units, to_packs, units_phrase
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared.templatetags import paper


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def last_purchase(s):
    return PurchaseInvoice.objects.filter(supplier=s).latest("created_at")


def scenarios(h):
    acct = h.account()
    cust, sup = h.customer(), h.supplier()

    # ---------------------------------------------------- arithmetic helpers
    check("UQ01 split 34 packs at 5 per carton = 6 cartons + 4 packs", split_units(34, 5) == (6, 4))
    check("UQ02 to_packs 6 cartons + 4 packs = 34", to_packs(6, 4, 5) == 34)
    check("UQ03 phrase leaves zero parts out", units_phrase(6, 0) == "6 کارتن" and units_phrase(0, 4) == "4 بسته" and units_phrase(0, 0) == "0 بسته")
    check("UQ04 the filter prints cartons + packs with the pack total", paper.units(34, 5) == "۶ کارتن + ۴ بسته (۳۴ بسته)", paper.units(34, 5))
    check("UQ05 a quantity under one carton has no total in brackets", paper.units(4, 5) == "۴ بسته")

    # ---------------------------------------------------- selling
    p = h.product(stock=10, cost=100, price=1000)
    h.post_sale(cust, [h.item_row(p, 3, 1000)], account=acct)
    check("UQ10 10 packs, sell 3 packs -> 7", get_stock(p) == 7, get_stock(p))
    p = h.product(stock=10, cost=100, price=1000)
    h.post_sale(cust, [h.carton_row(p, 1)], account=acct)
    check("UQ11 10 packs, sell 1 carton -> 5", get_stock(p) == 5, get_stock(p))
    p = h.product(stock=17, cost=100, price=1000)
    r = h.post_sale(cust, [h.carton_row(p, 2, packs=3)], account=acct)
    check("UQ12 17 packs, sell 2 cartons + 3 packs -> 4", r.status_code == 302 and get_stock(p) == 4, (r.status_code, get_stock(p)))
    line = last_sale(cust).items.get()
    check("UQ13 the line keeps what was typed: 2 cartons, 3 loose packs, 13 packs, ratio 5",
          (line.cartons, line.loose_packs, line.quantity, line.pack_per_carton) == (2, 3, 13, 5), (line.cartons, line.loose_packs, line.quantity))
    r = h.post_sale(cust, [h.carton_row(p, 1, packs=0)], account=acct)
    check("UQ14 selling 1 carton (5 packs) of 4 packs is refused and nothing moves", r.status_code == 200 and get_stock(p) == 4 and has(r, "موجودی"))

    # ---------------------------------------------------- purchasing
    p = h.product(stock=0, price=1000)
    r = h.post_purchase(sup, [h.carton_row(p, 3, packs=2, carton_price=500, unit_price=100)], account=acct)
    pi = last_purchase(sup)
    lay = InventoryLayer.objects.get(purchase_item__invoice=pi)
    check("UQ20 buy 3 cartons + 2 packs -> stock +17", r.status_code == 302 and get_stock(p) == 17 and lay.quantity == 17, (r.status_code, get_stock(p)))
    check("UQ21 invoice total = 3 x 500 + 2 x 100 = 1700, layer value matches within rounding",
          pi.total_amount == 1700 and abs(lay.quantity * lay.unit_cost - 1700) <= lay.quantity, (pi.total_amount, lay.unit_cost))
    r = h.post_purchase(sup, [h.carton_row(p, 1, carton_price=""), ], account=acct)
    check("UQ22 a purchase with cartons but no carton price is refused", r.status_code == 200)
    r = h.post_purchase(sup, [h.carton_row(p, 0, packs=2, unit_price="")], account=acct)
    check("UQ23 a purchase with packs but no pack price is refused", r.status_code == 200)
    q = h.product(stock=0, price=1000)
    h.post_purchase(sup, [h.carton_row(q, 1, carton_price=1003)], account=acct)
    lay = InventoryLayer.objects.get(purchase_item__invoice=last_purchase(sup))
    check("UQ24 a carton of 1003 over 5 packs: pack cost rounds to nearest (201)", lay.unit_cost == 201 and lay.quantity == 5, lay.unit_cost)
    check("UQ25 the invoice total stays exact (1003)", last_purchase(sup).total_amount == 1003)

    # ---------------------------------------------------- mixed invoice
    a = h.product(stock=40, cost=100, price=1000)
    b = h.product(stock=40, cost=300, price=2000)
    r = h.post_sale(cust, [h.carton_row(a, 1, packs=2), h.item_row(b, 4, 2000)], account=acct)
    inv = last_sale(cust)
    check("UQ30 one invoice with several products, cartons and packs mixed",
          r.status_code == 302 and get_stock(a) == 33 and get_stock(b) == 36 and inv.items.count() == 2)
    ia = inv.items.get(product=a)
    check("UQ31 line totals: carton at its price + packs at pack price", ia.line_total == 1 * ia.carton_price + 2 * 1000 and inv.subtotal == ia.line_total + 4 * 2000)
    r = h.post_sale(cust, [h.carton_row(a, 1), h.carton_row(a, 0, packs=1)], account=acct)
    check("UQ32 the same product twice is still refused (one row per product)", r.status_code == 200)

    # ---------------------------------------------------- FIFO stays FIFO, average is separate
    f = h.product(stock=10, cost=100, price=1000)                     # layer 1: 10 @ 100
    h.post_purchase(sup, [h.item_row(f, 50, 300)], account=acct)      # layer 2: 50 @ 300
    h.post_purchase(sup, [h.item_row(f, 20, 600)], account=acct)      # layer 3: 20 @ 600
    h.post_sale(cust, [h.item_row(f, 40, 1000)], account=acct)        # takes 10 @ 100 + 30 @ 300
    s = last_sale(cust).items.get()
    check("UQ40 FIFO cost of the sale = 10 x 100 + 30 x 300 = 10000", s.cost_of_goods == 10 * 100 + 30 * 300, s.cost_of_goods)
    check("UQ41 FIFO profit = 40 x 1000 - 10000", s.profit == 40 * 1000 - 10_000, s.profit)
    avg = get_average_cost_map([f.pk])[f.pk]
    expected = (20 * 300 + 20 * 600 + 0) // 40 if False else (2 * (20 * 300 + 20 * 600) + 40) // (2 * 40)
    check("UQ42 average price counts only what is left: 20 @ 300 + 20 @ 600 -> 450", avg == 450 == expected, avg)
    check("UQ43 FIFO's next layer is a different number from the average", get_current_cost_map([f.pk])[f.pk] == 300 and avg != 300)
    check("UQ44 the sale's cost did not move with the average", last_sale(cust).items.get().cost_of_goods == 10_000)
    h.post_sale(cust, [h.item_row(f, 20, 1000)], account=acct)        # drains layer 2
    check("UQ45 after selling the 300 layer out the average becomes 600", get_average_cost_map([f.pk])[f.pk] == 600)
    h.post_sale(cust, [h.item_row(f, 20, 1000)], account=acct)
    check("UQ46 no stock left: no average", f.pk not in get_average_cost_map([f.pk]))

    # ---------------------------------------------------- ratio per product, snapshot on lines
    g = h.product(stock=0, price=100, pack_per_carton=12)
    h.post_purchase(sup, [h.carton_row(g, 2, packs=5, carton_price=1200, unit_price=100)], account=acct)
    check("UQ50 a product with 12 per carton: 2 cartons + 5 packs = 29", get_stock(g) == 29)
    line = last_purchase(sup).items.get()
    Product.objects.filter(pk=g.pk).update(pack_per_carton=6)
    line.refresh_from_db()
    check("UQ51 changing the ratio later does not rewrite an old line", line.pack_per_carton == 12 and line.cartons == 2 and line.loose_packs == 5 and line.quantity == 29)
    check("UQ52 the old line still prints with its own ratio", paper.line_units(line) == "۲ کارتن + ۵ بسته (۲۹ بسته)", paper.line_units(line))

    # ---------------------------------------------------- pages
    page = h.c.get(f"/sales/{inv.pk}/print/")
    check("UQ60 printed sale shows the quantity as entered, not only in packs",
          page.status_code == 200 and has(page, "۱ کارتن + ۲ بسته") and not has(page, "<th>واحد</th>"), page.status_code)
    page = h.c.get(f"/sales/{inv.pk}/")
    check("UQ61 sale detail shows it too", has(page, "۱ کارتن + ۲ بسته"))
    page = h.c.get(f"/purchasing/{last_purchase(sup).pk}/")
    check("UQ62 purchase detail shows cartons + packs", has(page, "۲ کارتن + ۵ بسته"))
    page = h.c.get(f"/purchasing/{last_purchase(sup).pk}/print/")
    check("UQ63 printed purchase shows cartons + packs", has(page, "۲ کارتن + ۵ بسته"))
    h.product(stock=34, cost=100, price=1000, name="QA-show-34")
    page = h.c.get("/inventory/")
    check("UQ70 inventory shows stock as cartons + packs and the average column",
          page.status_code == 200 and has(page, "۶ کارتن + ۴ بسته (۳۴ بسته)") and has(page, "میانگین قیمت خرید"))
    check("UQ71 the negative-stock card and the FIFO-cost column are gone from the list",
          not has(page, "موجودی منفی") and not has(page, "بهای خرید جاری (FIFO)"))
    check("UQ72 there is no longer a pack section and a carton section", not has(page, "کالاهای بسته") and not has(page, "کالاهای کارتن"))
    page = h.c.get(f"/inventory/{f.pk}/")
    check("UQ73 product page tells average price and FIFO layer cost apart", has(page, "میانگین قیمت خرید") and has(page, "بهای لایهٔ بعدی (FIFO)"))
    page = h.c.get("/sales/new/")
    check("UQ74 the sale row has carton and pack boxes and a price for each",
          has(page, "-cartons") and has(page, "-packs") and has(page, "-carton_price") and has(page, "-unit_price"))
    page = h.c.get("/purchasing/new/")
    check("UQ75 the purchase row too", has(page, "-cartons") and has(page, "-packs") and has(page, "-carton_price"))
    from django.urls import reverse
    page = h.c.get(reverse("purchasing:product_search"), {"q": a.name})
    check("UQ76 purchase search result gives the stock in cartons + packs and the ratio", has(page, 'data-ratio="5"') and has(page, "کارتن"))

    # ---------------------------------------------------- opening stock typed in cartons + packs
    name = "QA-open-" + rnd()
    r = h.c.post("/inventory/products/new/", {"name": name, "sku": "QO" + rnd(6), "pack_per_carton": "5", "default_selling_price": "100",
                                              "opening_cartons": "2", "opening_packs": "3", "opening_unit_cost": "40"})
    made = Product.objects.get(name=name)
    check("UQ80 opening stock 2 cartons + 3 packs = 13 packs at 40", r.status_code == 302 and get_stock(made) == 13 and get_current_cost_map([made.pk])[made.pk] == 40)

    # ---------------------------------------------------- cancelling gives exactly the packs back
    c0 = h.product(stock=20, cost=100, price=1000)
    h.post_sale(cust, [h.carton_row(c0, 2, packs=1)], account=acct)
    inv = last_sale(cust)
    h.c.post(f"/sales/{inv.pk}/cancel/")
    check("UQ90 cancelling a 2 cartons + 1 pack sale restores 11 packs", get_stock(c0) == 20, get_stock(c0))
    h.post_purchase(sup, [h.carton_row(c0, 1, packs=1, carton_price=500, unit_price=100)], account=acct)
    pinv = last_purchase(sup)
    h.c.post(f"/purchasing/{pinv.pk}/cancel/")
    check("UQ91 cancelling a 1 carton + 1 pack purchase takes the 6 packs off", get_stock(c0) == 20, get_stock(c0))


run("units", scenarios)

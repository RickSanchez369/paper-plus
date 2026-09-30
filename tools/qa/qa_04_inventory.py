from tools.qa.qa_lib import *
from apps.inventory.models import InventoryLayer, InventoryMovement
from apps.inventory.selectors import get_total_inventory_value
from apps.products.models import Product
from apps.shared.models import AuditLog


def scenarios(h):
    acct = h.account()
    sup, cust = h.supplier(), h.customer()

    r = h.c.get("/inventory/")
    check("I01 list renders", r.status_code == 200)
    r = h.c.get("/inventory/products/new/")
    check("I02 new-product page renders", r.status_code == 200 and has(r, "opening_quantity"))

    def new(**kw):
        d = {"name": "QA-N-" + rnd(), "sku": "QS" + str(random.randint(10**6, 10**7)), "unit": "بسته",
             "default_selling_price": "1000", "opening_quantity": "", "opening_unit_cost": ""}
        d.update(kw)
        return h.c.post("/inventory/products/new/", d)

    n0 = Product.objects.count()
    r = new()
    check("I03 product without stock created → redirects to its detail", r.status_code == 302 and "/inventory/" in r["Location"] and Product.objects.count() == n0 + 1)
    p = Product.objects.latest("created_at")
    check("I03 stock 0, no layer, no movement", h.stock(p) == 0 and not InventoryLayer.objects.filter(product=p).exists())
    r = new(opening_quantity="12", opening_unit_cost="450")
    p = Product.objects.latest("created_at")
    lay = InventoryLayer.objects.get(product=p)
    check("I04 opening stock creates a layer at the given cost", r.status_code == 302 and h.stock(p) == 12 and lay.unit_cost == 450 and lay.source == "opening_stock")
    check("I04 opening movement recorded", InventoryMovement.objects.filter(product=p, movement_type="opening", quantity=12).exists())
    check("I04 inventory value includes it (12×450 = 5400)", get_total_inventory_value() >= 5400)
    check("I04 audit log row", AuditLog.objects.filter(event_type="opening_stock", actor=h.su, payload__quantity=12).exists())

    n1 = Product.objects.count()
    bad = {
        "qty without cost": dict(opening_quantity="5"),
        "cost without qty": dict(opening_unit_cost="100"),
        "negative qty": dict(opening_quantity="-3", opening_unit_cost="10"),
        "zero qty": dict(opening_quantity="0", opening_unit_cost="10"),
        "negative cost": dict(opening_quantity="3", opening_unit_cost="-10"),
        "text qty": dict(opening_quantity="abc", opening_unit_cost="10"),
        "decimal qty": dict(opening_quantity="1.5", opening_unit_cost="10"),
        "blank name": dict(name=""),
        "blank sku": dict(sku=""),
        "blank price": dict(default_selling_price=""),
        "negative price": dict(default_selling_price="-1"),
        "text price": dict(default_selling_price="x"),
    }
    for label, kw in bad.items():
        r = new(**kw)
        check(f"I05 {label} rejected, no product left behind", r.status_code == 200 and Product.objects.count() == n1, (r.status_code, Product.objects.count() - n1))
    sku = p.sku
    r = new(sku=sku)
    check("I06 duplicate SKU rejected with a message", r.status_code == 200 and Product.objects.count() == n1)
    r = new(sku=sku.lower() + "x", name=p.name)
    check("I06 a duplicate NAME is allowed (only SKU is unique)", r.status_code == 302)
    r = new(default_selling_price=str(10**19))
    check("I06 absurd price does not crash", r.status_code in (200, 302) and r.status_code != 500, r.status_code)
    r = new(sku="  " + "S" + rnd() + "  ", name="  " + "QA-sp-" + rnd() + "  ")
    check("I06 surrounding spaces in SKU/name do not crash", r.status_code in (200, 302))
    r = new(name="کالای فارسی " + rnd(), sku="فا" + str(random.randint(1000, 9999)))
    check("I06 Persian name and SKU work", r.status_code == 302)
    r = new(default_selling_price=digits_fa("2500"))
    check("I06 Persian digits in price", r.status_code == 302)

    # selling price
    p = h.product(price=1000, stock=5, cost=200)
    lay_before = list(InventoryLayer.objects.filter(product=p).values_list("unit_cost", "quantity_remaining"))
    r = h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": "1500"})
    p.refresh_from_db()
    check("I07 selling price updated", r.status_code == 302 and p.default_selling_price == 1500)
    check("I07 costs/layers untouched", list(InventoryLayer.objects.filter(product=p).values_list("unit_cost", "quantity_remaining")) == lay_before)
    check("I07 history row written for the user", p.history.filter(history_user=h.su).exists())
    check("I07 audit row", AuditLog.objects.filter(event_type="change_selling_price", target_id=p.pk).exists())
    n_hist = p.history.count()
    h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": "1500"})
    check("I07 setting the same price again adds no history row", p.history.count() == n_hist)
    for label, v in (("negative", "-5"), ("text", "abc"), ("blank", ""), ("decimal", "1.5")):
        h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": v})
        p.refresh_from_db()
        check(f"I07 {label} price rejected (price unchanged)", p.default_selling_price == 1500)
    r = h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": "0"})
    p.refresh_from_db()
    check("I07 price 0 is allowed", p.default_selling_price == 0)
    check("I07 GET on the price URL = 405", h.c.get(f"/inventory/{p.pk}/selling-price/").status_code == 405)
    check("I07 unknown product 404", h.c.post("/inventory/00000000-0000-0000-0000-000000000003/selling-price/", {"default_selling_price": "5"}).status_code == 404)
    # a price change never rewrites past invoices
    p2 = h.product(price=100, stock=10, cost=10)
    h.post_sale(cust, [(p2, 2, 100)], account=acct)
    h.c.post(f"/inventory/{p2.pk}/selling-price/", {"default_selling_price": "999"})
    from apps.sales.models import SaleItem
    check("I07 an existing sale line keeps its own price", SaleItem.objects.get(product=p2).unit_price == 100)

    # detail page across every movement type
    d = h.product(stock=10, cost=100, price=500)
    h.post_purchase(sup, [(d, 5, 200)], account=acct)
    h.post_sale(cust, [(d, 12, 500)], account=acct)
    from apps.sales.models import SalesInvoice
    from apps.purchasing.models import PurchaseInvoice
    si = SalesInvoice.objects.filter(customer=cust).latest("created_at")
    h.c.post(f"/sales/{si.pk}/cancel/")
    pi = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    h.c.post(f"/purchasing/{pi.pk}/cancel/")
    r = h.c.get(f"/inventory/{d.pk}/")
    check("I08 detail renders with opening+purchase+sale+reversal rows", r.status_code == 200 and has(r, "لغو فاکتور"))
    check("I08 links from movements to their invoices", has(r, f"/sales/{si.pk}/") and has(r, f"/purchasing/{pi.pk}/"))
    check("I08 price history section present", has(r, "تاریخچه"))
    check("I08 stock after everything = 10 (opening only)", h.stock(d) == 10)
    check("I08 unknown product = 404, malformed = 404", h.c.get("/inventory/00000000-0000-0000-0000-000000000004/").status_code == 404 and h.c.get("/inventory/xx/").status_code == 404)
    # last known cost once stock hits zero
    z = h.product(stock=2, cost=77, price=100)
    h.post_sale(cust, [(z, 2, 100)], account=acct)
    r = h.c.get("/inventory/")
    check("I09 a sold-out product shows its last known cost", r.status_code == 200 and has(r, z.name) and has(r, "آخرین"))
    r = h.c.get(f"/inventory/{z.pk}/")
    check("I09 sold-out detail renders", r.status_code == 200)
    ev = h.product(name="<b onmouseover=alert(1)>QA</b>", stock=1, cost=1)
    for url in ("/inventory/", f"/inventory/{ev.pk}/", "/sales/new/", "/purchasing/new/"):
        r = h.c.get(url)
        check(f"I10 HTML in a product name escaped on {url}", "<b onmouseover=alert(1)>" not in text(r))
    r = h.c.get("/sales/product-search/?q=onmouseover")
    check("I10 …and in the live search results", "<b onmouseover=alert(1)>" not in text(r))
    for url in ("/inventory/", "/inventory/products/new/", f"/inventory/{d.pk}/"):
        check(f"I11 anonymous redirected: {url}", h.anon.get(url).status_code == 302)
    check("I11 anonymous POST redirected", h.anon.post("/inventory/products/new/", {}).status_code == 302)


run("inventory", scenarios)

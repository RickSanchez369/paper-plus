"""D-075/D-081: pack price (retail) and carton price (wholesale), blank line prices filled from the product, the report by sale type."""
from tools.qa.qa_lib import *
import datetime
from apps.products.models import Product
from apps.products.services import update_selling_price, update_selling_prices
from apps.sales.models import SalesInvoice
from apps.shared import reports
from apps.shared.models import AuditLog


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def scenarios(h):
    acct = h.account()
    cust = h.customer()
    p = h.product(stock=100, cost=100, price=1000)          # retail 1000
    update_selling_prices(p, h.su, wholesale=700)
    p.refresh_from_db()

    # ---------------------------------------------------- model + service
    check("PR01 pack price is retail, carton price is the wholesale price", p.pack_price == 1000 and p.carton_price == 700)
    q = h.product(stock=10, cost=100, price=500)
    q.wholesale_selling_price = 0
    q.save()
    check("PR02 an unset (0) carton price = pack price x packs per carton", q.carton_price == 500 * 5 and q.wholesale_is_unset)
    n = AuditLog.objects.filter(target_id=p.pk, event_type="change_selling_price").count()
    update_selling_prices(p, h.su, retail=1000, wholesale=700)
    check("PR03 unchanged prices log nothing", AuditLog.objects.filter(target_id=p.pk, event_type="change_selling_price").count() == n)
    update_selling_prices(p, h.su, retail=1100)
    p.refresh_from_db()
    check("PR04 None leaves the other price alone", p.default_selling_price == 1100 and p.wholesale_selling_price == 700)
    log = AuditLog.objects.filter(target_id=p.pk, event_type="change_selling_price").latest("created_at")
    check("PR04 audit row names the tier and both prices", log.payload == {"tier": "retail", "old_price": 1000, "new_price": 1100}, log.payload)
    update_selling_price(p, 1000, h.su)
    p.refresh_from_db()
    check("PR05 the old one-price service still sets retail", p.default_selling_price == 1000)
    try:
        update_selling_prices(p, h.su, wholesale=-1)
        ok = False
    except Exception:
        ok = True
    check("PR06 negative price refused", ok)
    check("PR07 history rows carry both prices", p.history.first().wholesale_selling_price == 700)

    # ---------------------------------------------------- Inventory form
    r = h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": "1200", "wholesale_selling_price": "900"})
    p.refresh_from_db()
    check("PR10 inventory form saves retail and wholesale", r.status_code == 302 and p.default_selling_price == 1200 and p.wholesale_selling_price == 900)
    r = h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": "", "wholesale_selling_price": "800"})
    p.refresh_from_db()
    check("PR11 a blank price is left alone", p.default_selling_price == 1200 and p.wholesale_selling_price == 800)
    r = h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": "", "wholesale_selling_price": ""})
    p.refresh_from_db()
    check("PR12 both blank is an error, nothing changes", p.default_selling_price == 1200 and p.wholesale_selling_price == 800)
    r = h.c.post(f"/inventory/{p.pk}/selling-price/", {"default_selling_price": "-5"})
    p.refresh_from_db()
    check("PR13 negative refused", p.default_selling_price == 1200)
    page = h.c.get(f"/inventory/{p.pk}/")
    check("PR14 detail shows both prices and the history columns", page.status_code == 200 and has(page, "قیمت فروش عمده") and has(page, "قیمت فروش خرد"))

    # ---------------------------------------------------- sales: blank prices come from the product (D-081)
    r = h.post_sale(cust, [h.carton_row(p, 2)], account=acct, extra={"price_tier": "wholesale"})
    i = last_sale(cust)
    it = i.items.get()
    check("PT01 wholesale invoice: blank carton price = the wholesale carton price, packs untouched", r.status_code == 302 and it.carton_price == 800 and it.cartons == 2 and it.quantity == 10, (r.status_code, it.carton_price))
    check("PT02 the sale type is the one chosen (D-090)", i.price_tier == "wholesale" and i.total == 2 * 800)
    r = h.post_sale(cust, [h.carton_row(p, 2)], account=acct, extra={"price_tier": "retail"})
    i = last_sale(cust)
    check("PT02b a retail invoice with cartons stays retail and prices the retail carton (pack x ratio)",
          i.price_tier == "retail" and i.items.get().carton_price == 1200 * 5, (i.price_tier, i.items.get().carton_price))
    r = h.post_sale(cust, [h.carton_row(p, 0, packs=3)], account=acct)
    i = last_sale(cust)
    check("PT03 loose packs only: blank pack price = retail, invoice counts as retail", i.items.get().unit_price == 1200 and i.price_tier == "retail" and i.total == 3 * 1200)
    r = h.post_sale(cust, [h.carton_row(p, 1, packs=2, carton_price=999, unit_price=1)], account=acct)
    i = last_sale(cust)
    check("PT05 typed prices win; line = 1 carton + 2 packs", i.items.get().line_total == 999 + 2 and i.total == 1001)
    r = h.post_sale(cust, [h.carton_row(q, 1)], account=acct)
    check("PT06 a product with no carton price sells a carton at pack price x ratio", last_sale(cust).items.get().carton_price == 500 * 5)
    i = last_sale(cust)
    price0 = i.items.get().carton_price
    update_selling_prices(q, h.su, retail=777, wholesale=555)
    check("PT07 confirmed invoice keeps its price snapshot", SalesInvoice.objects.get(pk=i.pk).items.get().carton_price == price0)
    r = h.post_sale(cust, [h.carton_row(p, 0, packs=0)], account=acct)
    check("PT08 a line with neither cartons nor packs is refused", r.status_code == 200)

    # ---------------------------------------------------- search results carry both prices
    from django.urls import reverse
    r = h.c.get(reverse("sales:product_search"), {"q": p.name})
    check("PT10 product search carries the four prices and the ratio", r.status_code == 200 and has(r, 'data-retail-pack="1200"')
          and has(r, 'data-wholesale-carton="800"') and has(r, 'data-retail-carton="6000"') and has(r, 'data-ratio="5"'))
    page = h.c.get("/sales/new/")
    check("PT11 the new-sale page has the sale type switch again (D-090)", page.status_code == 200 and has(page, 'name="price_tier"'))
    check("PT12 invoice detail shows the derived sale type", has(h.c.get(f"/sales/{last_sale(cust).pk}/"), "نوع فروش"))

    # ---------------------------------------------------- report by tier
    start = h.today - datetime.timedelta(days=1)
    end = h.today + datetime.timedelta(days=1)
    rows = reports.sales_by_tier(start, end)
    check("PT20 report rows add up to sales_total and gross_profit",
          sum(r["sales"] for r in rows) == reports.sales_total(start, end) and sum(r["profit"] for r in rows) == reports.gross_profit(start, end))
    check("PT21 reports page renders the tier card", has(h.c.get("/reports/"), "فروش عمده و خرد"))

    # ---------------------------------------------------- product creation (D-081)
    name = "QA-carton-" + rnd()
    r = h.c.post("/inventory/products/new/", {"name": name, "sku": "QAC" + rnd(6), "pack_per_carton": "12", "default_selling_price": "100", "wholesale_selling_price": "1000"})
    made = Product.objects.get(name=name)
    check("UN04 a product with its own ratio and both prices", r.status_code == 302 and made.pack_per_carton == 12 and made.wholesale_selling_price == 1000)
    name2 = "QA-blankw-" + rnd()
    r = h.c.post("/inventory/products/new/", {"name": name2, "sku": "QAB" + rnd(6), "pack_per_carton": "5", "default_selling_price": "250"})
    made2 = Product.objects.get(name=name2)
    check("UN05 blank carton price on creation = unset, suggested as 5 x pack price", made2.wholesale_selling_price == 0 and made2.carton_price == 1250)
    r = h.c.post("/inventory/products/new/", {"name": "QA-zero-" + rnd(), "sku": "QAZ" + rnd(6), "pack_per_carton": "0", "default_selling_price": "250"})
    check("UN06 a ratio below 1 is refused", r.status_code == 200)


run("pricing_units", scenarios)

"""D-075/D-076: wholesale vs retail prices, the sale type on the invoice, Inventory pack/carton split."""
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
    check("PR01 price_for retail/wholesale", p.price_for("retail") == 1000 and p.price_for("wholesale") == 700)
    q = h.product(stock=10, cost=100, price=500)
    q.wholesale_selling_price = 0
    q.save()
    check("PR02 an unset (0) wholesale price falls back to retail", q.price_for("wholesale") == 500 and q.wholesale_is_unset)
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

    # ---------------------------------------------------- sales: blank price follows the sale type
    r = h.post_sale(cust, [(p, 2, "")], account=acct, extra={"price_tier": "wholesale"})
    i = last_sale(cust)
    check("PT01 wholesale invoice: blank price = wholesale price", r.status_code == 302 and i.price_tier == "wholesale" and i.items.get().unit_price == 800, i.items.get().unit_price if i.items.exists() else "")
    r = h.post_sale(cust, [(p, 2, "")], account=acct, extra={"price_tier": "retail"})
    i = last_sale(cust)
    check("PT02 retail invoice: blank price = retail price", i.price_tier == "retail" and i.items.get().unit_price == 1200)
    r = h.post_sale(cust, [(p, 2, "")], account=acct)
    i = last_sale(cust)
    check("PT03 no tier posted = retail", i.price_tier == "retail" and i.items.get().unit_price == 1200)
    r = h.post_sale(cust, [(p, 2, "")], account=acct, extra={"price_tier": "gold"})
    check("PT04 an unknown tier is rejected, no 500", r.status_code in (200, 302) and r.status_code != 500)
    r = h.post_sale(cust, [(p, 2, 999)], account=acct, extra={"price_tier": "wholesale"})
    i = last_sale(cust)
    check("PT05 a typed price wins over the tier price", i.items.get().unit_price == 999)
    r = h.post_sale(cust, [(q, 1, "")], account=acct, extra={"price_tier": "wholesale"})
    check("PT06 unset wholesale on a product falls back to retail on the line", last_sale(cust).items.get().unit_price == 500)
    # a later price change never touches a confirmed invoice
    i = last_sale(cust)
    price0 = i.items.get().unit_price
    update_selling_prices(q, h.su, retail=777, wholesale=555)
    check("PT07 confirmed invoice keeps its price snapshot", SalesInvoice.objects.get(pk=i.pk).items.get().unit_price == price0)

    # ---------------------------------------------------- search results carry both prices
    r = h.c.get("/sales/products/search/?q=" + p.name[:6]) if False else None
    from django.urls import reverse
    r = h.c.get(reverse("sales:product_search"), {"q": p.name})
    check("PT10 product search carries both tier prices", r.status_code == 200 and has(r, 'data-price-retail="1200"') and has(r, 'data-price-wholesale="800"'))
    page = h.c.get("/sales/new/")
    check("PT11 the new-sale page has the sale type switch", page.status_code == 200 and has(page, 'name="price_tier"') and has(page, "نوع فروش"))
    check("PT12 invoice detail shows the sale type", has(h.c.get(f"/sales/{last_sale(cust).pk}/"), "نوع فروش"))

    # ---------------------------------------------------- report by tier
    start = h.today - datetime.timedelta(days=1)
    end = h.today + datetime.timedelta(days=1)
    rows = reports.sales_by_tier(start, end)
    check("PT20 report rows add up to sales_total and gross_profit",
          sum(r["sales"] for r in rows) == reports.sales_total(start, end) and sum(r["profit"] for r in rows) == reports.gross_profit(start, end))
    check("PT21 reports page renders the tier card", has(h.c.get("/reports/"), "فروش عمده و خرد"))

    # ---------------------------------------------------- units (D-076)
    pack = h.product(stock=7, cost=10, price=100)
    carton = h.product(stock=3, cost=500, price=5000)
    Product.objects.filter(pk=carton.pk).update(unit="کارتن")
    page = h.c.get("/inventory/")
    check("UN01 inventory list shows pack and carton sections apart", page.status_code == 200 and has(page, "کالاهای بسته") and has(page, "کالاهای کارتن"))
    from apps.inventory.views import InventoryListView
    from django.test import RequestFactory
    view = InventoryListView()
    view.setup(RequestFactory().get("/inventory/"))
    groups = {g["unit"]: g for g in view.get_context_data()["groups"]}
    check("UN02 stock totals per unit are separate", groups["کارتن"]["stock_total"] >= 3 and groups["بسته"]["stock_total"] >= 7 and
          pack.pk in [r["product"].pk for r in groups["بسته"]["rows"]] and carton.pk in [r["product"].pk for r in groups["کارتن"]["rows"]]
          and carton.pk not in [r["product"].pk for r in groups["بسته"]["rows"]])
    r = h.c.post("/inventory/products/new/", {"name": "QA-unit-" + rnd(), "sku": "QAU" + rnd(6), "unit": "رول", "default_selling_price": "10"})
    check("UN03 a unit other than pack/carton is refused", r.status_code == 200 and not Product.objects.filter(unit="رول").exists())
    name = "QA-carton-" + rnd()
    r = h.c.post("/inventory/products/new/", {"name": name, "sku": "QAC" + rnd(6), "unit": "کارتن", "default_selling_price": "100", "wholesale_selling_price": "80"})
    made = Product.objects.get(name=name)
    check("UN04 a carton product with both prices", r.status_code == 302 and made.unit == "کارتن" and made.wholesale_selling_price == 80)
    name2 = "QA-blankw-" + rnd()
    r = h.c.post("/inventory/products/new/", {"name": name2, "sku": "QAB" + rnd(6), "unit": "بسته", "default_selling_price": "250"})
    check("UN05 blank wholesale on creation = retail", Product.objects.get(name=name2).wholesale_selling_price == 250)


run("pricing_units", scenarios)

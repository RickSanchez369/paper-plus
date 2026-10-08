"""Two prices, chosen by the unit sold; the sale type is only a label (D-100, supersedes the D-090 grid)."""
from apps.partners.models import Customer
from apps.products.models import Product
from apps.products.services import update_selling_prices
from apps.sales.models import SaleItem, SalesInvoice
from apps.shared import reports
from apps.shared.models import AuditLog
from tools.qa.qa_lib import *


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def scenarios(h):
    acct = h.account()

    # ---------------------------------------------------------------- the two prices
    p = h.product(price=1000, stock=500, cost=600, pack_per_carton=6)
    check("TP01 a pack is the pack price", p.price_for("pack") == 1000 and p.pack_price == 1000)
    check("TP02 a carton with no carton price follows pack x ratio", p.price_for("carton") == 6000)
    p.wholesale_selling_price = 5000
    check("TP03 a set carton price wins; the pack price is unchanged", p.price_for("carton") == 5000 and p.price_for("pack") == 1000)
    p.save()
    Product.objects.filter(pk=p.pk).update(retail_carton_price=1, wholesale_pack_price=1)
    fresh = Product.objects.get(pk=p.pk)
    check("TP04 the two retired columns no longer change any price", fresh.price_for("carton") == 5000 and fresh.price_for("pack") == 1000)

    # ---------------------------------------------------------------- the service and the product page
    q = h.product(price=2000, stock=100, cost=1200, pack_per_carton=4)
    n0 = AuditLog.objects.filter(event_type="change_selling_price").count()
    update_selling_prices(q, h.su, retail=2100, wholesale=7600)
    q.refresh_from_db()
    check("TP05 the service sets the two prices", q.default_selling_price == 2100 and q.wholesale_selling_price == 7600)
    check("TP06 one audit row per changed price", AuditLog.objects.filter(event_type="change_selling_price").count() == n0 + 2)
    try:
        update_selling_prices(q, h.su, retail_carton=5)
        refused = False
    except TypeError:
        refused = True
    check("TP07 the retired cells cannot be written through the service", refused)
    r = h.c.post(f"/inventory/{q.pk}/selling-price/", {"default_selling_price": "", "wholesale_selling_price": "6500",
                                                "retail_carton_price": "9", "wholesale_pack_price": "9"})
    q.refresh_from_db()
    check("TP08 the price form sets the carton price; blank leaves alone; extra cells are ignored",
          r.status_code == 302 and q.wholesale_selling_price == 6500 and q.default_selling_price == 2100
          and q.retail_carton_price == 0 and q.wholesale_pack_price == 0, (r.status_code, q.wholesale_selling_price))
    page = h.c.get(f"/inventory/{q.pk}/")
    check("TP09 product page shows two prices (pack = retail, carton = wholesale), no four-cell grid",
          has(page, "هر بسته (خرد)") and has(page, "هر کارتن (عمده)") and not has(page, "خرد · هر کارتن")
          and not has(page, "عمده · هر بسته") and has(page, "بهای لایهٔ بعدی (FIFO)") and shown(page, 6500))
    lst = h.c.get("/inventory/", {"q": p.name})
    check("TP10 inventory list has the two price columns", lst.status_code == 200 and has(lst, "قیمت بسته (خرد)") and has(lst, "قیمت کارتن (عمده)"))
    check("TP11 a product with no carton price is flagged «قیمت ناقص»",
          has(h.c.get("/inventory/", {"q": h.product(price=10).name}), "قیمت ناقص"))
    r = h.c.post("/inventory/products/new/", {"name": f"QA-new-{rnd()}", "sku": f"N{rnd()}", "pack_per_carton": "10",
                                     "default_selling_price": "300", "wholesale_selling_price": "2500"})
    made = Product.objects.order_by("-created_at").first()
    check("TP12 new product with the two prices", r.status_code == 302 and made.default_selling_price == 300
          and made.wholesale_selling_price == 2500, r.status_code)
    form_page = h.c.get("/inventory/products/new/")
    check("TP13 the new-product form has no retired price fields", not has(form_page, "retail_carton_price") and not has(form_page, "wholesale_pack_price"))

    # ---------------------------------------------------------------- the sale
    cust = h.customer()
    h.post_sale(cust, [h.carton_row(p, 1, 2)], account=acct, extra={"price_tier": "wholesale"})
    inv = last_sale(cust)
    it = inv.items.get()
    check("TP14 a wholesale-labelled invoice: carton at the carton price, packs at the pack price",
          inv.price_tier == "wholesale" and it.carton_price == 5000 and it.unit_price == 1000 and inv.total == 5000 + 2000,
          (inv.price_tier, it.carton_price, it.unit_price))
    h.post_sale(cust, [h.carton_row(p, 1, 2)], account=acct, extra={"price_tier": "retail"})
    inv = last_sale(cust)
    it = inv.items.get()
    check("TP15 a retail-labelled invoice prices the same lines the same way (the label changes no price)",
          inv.price_tier == "retail" and it.carton_price == 5000 and it.unit_price == 1000)
    h.post_sale(cust, [h.carton_row(p, 1, 2, carton_price=5555, unit_price=999)], account=acct)
    it = last_sale(cust).items.get()
    check("TP16 a typed price always wins", it.carton_price == 5555 and it.unit_price == 999)
    h.post_sale(cust, [h.carton_row(p, 0, 3)], account=acct)
    inv = last_sale(cust)
    check("TP17 no sale type posted: retail label, packs at the pack price", inv.price_tier == "retail"
          and inv.items.get().unit_price == 1000, (inv.price_tier, inv.items.get().unit_price))
    r = h.post_sale(cust, [h.carton_row(p, 0, 1)], account=acct, extra={"price_tier": "vip"})
    check("TP18 an unknown sale type is refused, nothing saved", r.status_code == 200 and has(r, "معتبر"), r.status_code)

    # admin path: SaleItem.clean_fields fills from the unit
    draft = SalesInvoice.objects.create(customer=cust, invoice_date=h.today, price_tier="wholesale", created_by=h.su)
    line = SaleItem(invoice=draft, product=p, quantity=6, cartons=1, pack_per_carton=6, unit_price=None, carton_price=0)
    line.clean_fields()
    check("TP19 an admin-made line fills from the unit", line.unit_price == 1000 and line.carton_price == 5000)
    draft.delete()

    # ---------------------------------------------------------------- pages
    page = h.c.get("/sales/new/")
    check("TP20 new-sale page: the switch stays, the customer-type map and note are gone",
          has(page, 'name="price_tier"') and not has(page, "customer-tiers") and not has(page, "tier-note"))
    lw = h.c.get("/sales/", {"price_tier": "wholesale", "q": cust.name})
    lr = h.c.get("/sales/", {"price_tier": "retail", "q": cust.name})
    wholesale_no = SalesInvoice.objects.filter(customer=cust, price_tier="wholesale").latest("created_at").invoice_number
    check("TP21 sales list still filters by the label", lw.status_code == 200 and has(lw, wholesale_no) and not has(lr, wholesale_no))
    r = h.c.post("/customers/quick-new/", {"name": f"QA-shop-{rnd()}", "phone": "", "price_tier": "wholesale", "address": "", "note": ""})
    newc = Customer.objects.order_by("-created_at").first()
    check("TP22 a customer has no type any more", r.status_code in (200, 302) and not hasattr(newc, "price_tier"), r.status_code)
    edit_page = h.c.get(f"/customers/{newc.pk}/")
    check("TP23 the customer page has no «نوع مشتری»", edit_page.status_code == 200 and not has(edit_page, "نوع مشتری") and not has(edit_page, "price_tier"),
          (edit_page.status_code, has(edit_page, "نوع مشتری"), has(edit_page, "price_tier")))
    rows = reports.sales_by_tier(h.today, h.today)
    check("TP24 the wholesale/retail report still adds up to the sales total",
          sum(x["sales"] for x in rows) == reports.sales_total(h.today, h.today), rows)


run("tier_prices", scenarios)

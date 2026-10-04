"""Four prices (retail/wholesale x pack/carton) and the sale type chosen on the invoice (D-090)."""
from apps.partners.models import Customer
from apps.products.models import PriceTier, Product
from apps.products.services import update_selling_prices
from apps.sales.models import SaleItem, SalesInvoice
from apps.shared import reports
from apps.shared.models import AuditLog
from tools.qa.qa_lib import *

R, W = PriceTier.RETAIL, PriceTier.WHOLESALE


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def scenarios(h):
    acct = h.account()

    # ---------------------------------------------------------------- the price grid
    p = h.product(price=1000, stock=500, cost=600, pack_per_carton=6)
    check("TP01 only retail pack set: retail carton = pack x ratio", p.price_for(R, "carton") == 6000)
    check("TP02 …wholesale pack falls back to retail pack (never a guessed discount)", p.price_for(W, "pack") == 1000)
    check("TP03 …wholesale carton falls back to the retail carton", p.price_for(W, "carton") == 6000)
    check("TP04 three cells derived -> prices_incomplete", p.prices_incomplete)
    p.wholesale_selling_price = 5000
    check("TP05 wholesale carton set: wholesale pack = carton / ratio rounded UP (5000/6 -> 834)", p.price_for(W, "pack") == 834)
    p.wholesale_pack_price = 800
    check("TP06 wholesale pack set wins", p.price_for(W, "pack") == 800 and p.price_for(W, "carton") == 5000)
    p.wholesale_selling_price = 0
    check("TP07 wholesale carton unset, pack set: carton = pack x ratio", p.price_for(W, "carton") == 4800)
    p.retail_carton_price = 5800
    check("TP08 retail carton set wins", p.price_for(R, "carton") == 5800)
    p.wholesale_selling_price = 4500
    check("TP09 all four set -> complete", not p.prices_incomplete and p.price_grid["wholesale_carton"]["price"] == 4500)
    p.save()

    # ---------------------------------------------------------------- the service and the product page
    q = h.product(price=2000, stock=100, cost=1200, pack_per_carton=4)
    n0 = AuditLog.objects.filter(event_type="change_selling_price").count()
    update_selling_prices(q, h.su, retail_carton=7600, wholesale_pack=1700)
    q.refresh_from_db()
    check("TP10 the service sets the two new cells", q.retail_carton_price == 7600 and q.wholesale_pack_price == 1700)
    check("TP11 one audit row per changed cell", AuditLog.objects.filter(event_type="change_selling_price").count() == n0 + 2)
    r = h.c.post(f"/inventory/{q.pk}/selling-price/", {"default_selling_price": "", "wholesale_selling_price": "6500",
                                                "retail_carton_price": "", "wholesale_pack_price": "1650"})
    q.refresh_from_db()
    check("TP12 the price form sets any cell; blank leaves alone", r.status_code == 302 and q.wholesale_selling_price == 6500
          and q.wholesale_pack_price == 1650 and q.retail_carton_price == 7600 and q.default_selling_price == 2000,
          (r.status_code, q.wholesale_selling_price, q.wholesale_pack_price))
    page = h.c.get(f"/inventory/{q.pk}/")
    check("TP13 product page shows the four cells and the cost block", has(page, "خرد · هر کارتن") and has(page, "عمده · هر بسته")
          and has(page, "بهای لایهٔ بعدی (FIFO)") and shown(page, 7600))
    lst = h.c.get("/inventory/", {"q": p.name})
    check("TP14 inventory list shows both tiers", lst.status_code == 200 and has(lst, "کارتن:"))
    check("TP15 a product with derived cells is flagged «قیمت ناقص»",
          has(h.c.get("/inventory/", {"q": h.product(price=10).name}), "قیمت ناقص"))
    r = h.c.post("/inventory/products/new/", {"name": f"QA-new-{rnd()}", "sku": f"N{rnd()}", "pack_per_carton": "10",
                                     "default_selling_price": "300", "retail_carton_price": "2900",
                                     "wholesale_pack_price": "", "wholesale_selling_price": "2500"})
    made = Product.objects.order_by("-created_at").first()
    check("TP16 new product with the grid; blank cell = unset", r.status_code == 302 and made.retail_carton_price == 2900
          and made.wholesale_pack_price == 0 and made.wholesale_selling_price == 2500, r.status_code)

    # ---------------------------------------------------------------- the sale
    cust = h.customer()
    h.post_sale(cust, [h.carton_row(p, 1, 2)], account=acct, extra={"price_tier": "wholesale"})
    inv = last_sale(cust)
    it = inv.items.get()
    check("TP17 wholesale invoice: blank prices = wholesale carton (4500) and wholesale pack (800)",
          inv.price_tier == "wholesale" and it.carton_price == 4500 and it.unit_price == 800 and inv.total == 4500 + 1600,
          (inv.price_tier, it.carton_price, it.unit_price))
    h.post_sale(cust, [h.carton_row(p, 1, 2)], account=acct, extra={"price_tier": "retail"})
    inv = last_sale(cust)
    it = inv.items.get()
    check("TP18 retail invoice with a whole carton stays retail: retail carton (5800) + retail packs (1000)",
          inv.price_tier == "retail" and it.carton_price == 5800 and it.unit_price == 1000)
    h.post_sale(cust, [h.carton_row(p, 1, 2, carton_price=5555, unit_price=999)], account=acct, extra={"price_tier": "wholesale"})
    it = last_sale(cust).items.get()
    check("TP19 a typed price always wins", it.carton_price == 5555 and it.unit_price == 999)

    shop = h.customer(price_tier="wholesale")
    h.post_sale(shop, [h.carton_row(p, 0, 3)], account=acct)
    inv = last_sale(shop)
    check("TP20 no sale type posted: the customer's type decides (wholesale)", inv.price_tier == "wholesale"
          and inv.items.get().unit_price == 800, (inv.price_tier, inv.items.get().unit_price))
    r = h.post_sale(cust, [h.carton_row(p, 0, 1)], account=acct, extra={"price_tier": "vip"})
    check("TP21 an unknown sale type is refused, nothing saved", r.status_code == 200 and has(r, "معتبر"), r.status_code)

    # admin path: SaleItem.clean_fields fills from the invoice's tier
    draft = SalesInvoice.objects.create(customer=cust, invoice_date=h.today, price_tier="wholesale", created_by=h.su)
    line = SaleItem(invoice=draft, product=p, quantity=6, cartons=1, pack_per_carton=6, unit_price=None, carton_price=0)
    line.clean_fields()
    check("TP22 an admin-made line fills from the invoice's tier", line.unit_price == 800 and line.carton_price == 4500)
    draft.delete()

    # ---------------------------------------------------------------- pages
    page = h.c.get(f"/sales/new/?customer={shop.pk}")
    check("TP23 new-sale page: the switch and the customer-type map", has(page, 'name="price_tier"') and has(page, "customer-tiers")
          and has(page, str(shop.pk)))
    lw = h.c.get("/sales/", {"price_tier": "wholesale", "q": shop.name})
    lr = h.c.get("/sales/", {"price_tier": "retail", "q": shop.name})
    shop_no = last_sale(shop).invoice_number  # the name alone also echoes in the search box
    check("TP24 sales list filters by sale type", lw.status_code == 200 and has(lw, shop_no) and not has(lr, shop_no))
    r = h.c.post("/customers/quick-new/", {"name": f"QA-shop-{rnd()}", "phone": "", "price_tier": "wholesale", "address": "", "note": ""})
    newc = Customer.objects.order_by("-created_at").first()
    check("TP25 quick-create stores the customer's type", newc.price_tier == "wholesale", r.status_code)
    r = h.c.post(f"/customers/{newc.pk}/edit/", {"name": newc.name, "phone": "", "address": "", "note": "", "is_active": "on"})
    newc.refresh_from_db()
    check("TP26 an edit that does not send the type keeps it", newc.price_tier == "wholesale", r.status_code)
    rows = reports.sales_by_tier(h.today, h.today)
    check("TP27 the wholesale/retail report still adds up to the sales total",
          sum(x["sales"] for x in rows) == reports.sales_total(h.today, h.today), rows)


run("tier_prices", scenarios)

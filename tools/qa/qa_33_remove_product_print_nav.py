"""D-102: product removal (delete vs archive), one-sheet print with colour choice, folded sidebar groups."""
from tools.qa.qa_lib import *  # noqa: F401,F403

from apps.products.models import Product


def scenarios(h):
    cust, acct = h.customer(), h.account()

    # ---- remove product
    fresh = Product.objects.create(name=f"QA-بی‌سابقه-{rnd()}", sku=f"RM{rnd()}", default_selling_price=1000)
    r = h.cu.post(f"/inventory/{fresh.pk}/remove/")
    check("RM01 an ordinary user cannot remove a product", Product.objects.filter(pk=fresh.pk).exists(), r.status_code)
    r = h.c.post(f"/inventory/{fresh.pk}/remove/")
    check("RM02 a never-used product is really deleted", r.status_code == 302 and not Product.objects.filter(pk=fresh.pk).exists(), r.status_code)

    stocked = h.product(price=1000, stock=5, cost=400)
    r = h.c.post(f"/inventory/{stocked.pk}/remove/")
    stocked.refresh_from_db()
    check("RM03 a product with stock is refused", stocked.is_active, r.status_code)

    gone = h.product(price=1000, stock=5, cost=400)
    h.post_sale(cust, [(gone, 5, 900)], account=acct)
    check("RM04 setup: stock sold down to zero", h.stock(gone) == 0, h.stock(gone))
    r = h.c.post(f"/inventory/{gone.pk}/remove/")
    gone.refresh_from_db()
    check("RM05 a product with history and zero stock is archived, not deleted", r.status_code == 302 and not gone.is_active)
    r = h.c.get("/inventory/")
    check("RM06 an archived product leaves the inventory list", gone.name not in text(r))
    check("RM07 its detail page still opens (history kept)", h.c.get(f"/inventory/{gone.pk}/").status_code == 200)
    check("RM08 the detail page shows the remove button to a superuser", "حذف کالا" in text(h.c.get(f"/inventory/{stocked.pk}/")))
    check("RM09 and hides it from an ordinary user", f"/inventory/{stocked.pk}/remove/" not in text(h.cu.get(f"/inventory/{stocked.pk}/")))

    # ---- print: colour choice, one sheet
    inv = h.post_sale(cust, [(stocked, 1, 900)], account=acct)
    from apps.sales.models import SalesInvoice
    invoice = SalesInvoice.objects.filter(customer=cust).order_by("-created_at").first()
    body = text(h.c.get(f"/sales/{invoice.pk}/print/"))
    check("PN01 print page offers colour and black-and-white", 'id="mode-color"' in body and 'id="mode-mono"' in body)
    check("PN02 last-resort scale-to-fit exists", "--inv-fit" in body)
    check("PN03 list print link opens the print page (no hidden-iframe print)", "printInline" not in open("apps/sales/static/sales/js/sales_pages.js", encoding="utf-8").read())

    # ---- sidebar
    body = text(h.c.get("/receivables/"))
    check("NV01 receivables group is one folded entry, open on its own pages", 'class="nav-group nav-fold" open' in body and "مطالبات و بدهی" in body)
    body = text(h.c.get("/sales/"))
    check("NV02 folded groups are closed elsewhere", "nav-fold\">" in body or 'nav-group nav-fold"' in body and 'nav-fold" open' not in body)
    check("NV03 expenses group is folded too", body.count("nav-fold__summary") == 2, body.count("nav-fold__summary"))


run("remove_product_print_nav", scenarios)

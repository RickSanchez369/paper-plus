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

    # ---- brand (D-103)
    cust2 = h.customer("مشتری فقط نام", phone="09121112233", address="نشانی آزمون برند")
    h.post_sale(cust2, [(stocked, 1, 900)], account=acct)
    inv2 = SalesInvoice.objects.filter(customer=cust2).order_by("-created_at").first()
    body = text(h.c.get(f"/sales/{inv2.pk}/print/"))
    check("BR01 the invoice shows the customer name", "مشتری فقط نام" in body)
    check("BR02 but not the customer's phone or address", "09121112233" not in body and "۰۹۱۲۱۱۱۲۲۳۳" not in body and "نشانی آزمون برند" not in body)
    check("BR03 the invoice carries the real logo", "shared/img/logo.png" in body and "inv__logo-sheet" not in body)
    dash = text(h.c.get("/"))
    check("BR04 the app says کاغذ پلاس and never پیپر پلاس", "کاغذ پلاس" in dash and "پیپر" not in dash and "logo.png" in dash)
    check("BR05 the sign-in page too", "پیپر" not in text(h.anon.get("/login/")))

    # ---- print layout and payment details (D-104)
    import datetime, jdatetime
    from apps.payments.models import BankAccount
    pos = h.account("کارت‌خوان آزمون", kind="pos")
    cur = h.account("حساب جاری آزمون")
    c3 = h.customer("مشتری روش‌ها")
    due = jdatetime.date.fromgregorian(date=datetime.date.today() + datetime.timedelta(days=9)).strftime("%Y/%m/%d")
    prods = [h.product(price=100000, stock=10, cost=1000) for _ in range(3)]
    h.post_sale(c3, [(p, 1, 100000) for p in prods], extra={"pos_account": str(pos.pk), "transfer_account": str(cur.pk), "pos_amount": "100000"})
    inv3 = SalesInvoice.objects.filter(customer=c3).order_by("-created_at").first()
    body = text(h.c.get(f"/sales/{inv3.pk}/print/"))
    check("PL01 a card-reader row names its account number", pos.account_number in body or digits_fa(pos.account_number) in body)
    check("PL02 a transfer row names the account it went to", cur.account_number in body or digits_fa(cur.account_number) in body)
    check("PL03 few lines print roomy rows", "inv inv--roomy" in body)
    c4 = h.customer("مشتری چک و نسیه")
    h.post_sale(c4, [(prods[0], 2, 100000)], mode="split",
                payments=[{"method": "cheque", "amount": "50000", "cheque_number": "778899", "due_date": due}], credit_due=due)
    inv4 = SalesInvoice.objects.filter(customer=c4).order_by("-created_at").first()
    body = text(h.c.get(f"/sales/{inv4.pk}/print/"))
    check("PL04 a pending cheque shows its number", "778899" in body or digits_fa("778899") in body)
    check("PL05 the credit part shows its due date", digits_fa(due) in body or due in body)
    html = body
    check("PL06 payment and totals come right before the signatures (below the table)", html.index("inv__middle") < html.index("inv__bottom") and html.index("inv__lines") < html.index("inv__middle"))


run("remove_product_print_nav", scenarios)

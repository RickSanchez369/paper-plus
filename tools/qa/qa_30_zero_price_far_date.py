"""D-097: a price of 0 and a date far ahead are refused; the purchase cancel dialog lists its effects like the sale one."""
import datetime

import jdatetime

from tools.qa.qa_lib import *  # noqa: F401,F403

from apps.payments.models import Expense
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice


def jalali_in(days):
    return jdatetime.date.fromgregorian(date=datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y/%m/%d")


def scenarios(h):
    cust, sup, acct = h.customer(), h.supplier(), h.account()
    p = h.product(price=1000, stock=50, cost=400)

    # ---- zero price
    n = SalesInvoice.objects.count()
    r = h.post_sale(cust, [(p, 2, 0)], account=acct)
    check("ZP01 sale line at price 0 is refused with a message", r.status_code == 200 and SalesInvoice.objects.count() == n and has(r, "نمی‌تواند صفر باشد"), r.status_code)
    r = h.post_sale(cust, [(p, 2, 1)], account=acct)
    check("ZP02 a gift at 1 Toman is accepted", r.status_code == 302 and SalesInvoice.objects.count() == n + 1, r.status_code)
    r = h.post_sale(cust, [h.carton_row(p, 1, carton_price=0)], account=acct)
    check("ZP03 sale line with a typed carton price 0 is refused", r.status_code == 200 and SalesInvoice.objects.count() == n + 1, r.status_code)
    unpriced = h.product(price=0, stock=10, cost=100)
    r = h.post_sale(cust, [h.carton_row(unpriced, 0, packs=2)], account=acct)
    check("ZP04 an unpriced product left blank (price falls back to 0) is refused", r.status_code == 200 and SalesInvoice.objects.count() == n + 1, r.status_code)

    m = PurchaseInvoice.objects.count()
    r = h.post_purchase(sup, [(p, 3, 0)], account=acct)
    check("ZP10 purchase line at price 0 is refused with a message", r.status_code == 200 and PurchaseInvoice.objects.count() == m and has(r, "نمی‌تواند صفر باشد"), r.status_code)
    r = h.post_purchase(sup, [(p, 3, 1)], account=acct)
    check("ZP11 a purchase at 1 Toman is accepted", r.status_code == 302 and PurchaseInvoice.objects.count() == m + 1, r.status_code)

    base = {"name": "کالای آزمون صفر", "pack_per_carton": "6", "default_selling_price": "1000", "opening_packs": "10"}
    k = Product.objects.count()
    r = h.c.post("/inventory/products/new/", dict(base, sku=f"ZP{rnd()}", opening_unit_cost="0"))
    check("ZP20 opening stock at cost 0 is refused", r.status_code == 200 and Product.objects.count() == k and has(r, "نمی‌تواند صفر باشد"), r.status_code)
    r = h.c.post("/inventory/products/new/", dict(base, sku=f"ZP{rnd()}", opening_unit_cost="1"))
    check("ZP21 opening stock at cost 1 is accepted", r.status_code == 302 and Product.objects.count() == k + 1, r.status_code)

    # ---- date far ahead
    n = SalesInvoice.objects.count()
    for label, days, ok in (("today", 0, True), ("29 days ahead", 29, True), ("45 days ahead", 45, False), ("11 years ahead", 4000, False)):
        r = h.post_sale(cust, [(p, 1, 900)], account=acct, date=jalali_in(days))
        check(f"FD sale dated {label}: {'saved' if ok else 'refused with a message'}",
              (r.status_code == 302) if ok else (r.status_code == 200 and has(r, "روز بعد از امروز")), r.status_code)
    check("FD sale: only the near dates were stored", SalesInvoice.objects.count() == n + 2, SalesInvoice.objects.count() - n)
    m = PurchaseInvoice.objects.count()
    for label, days, ok in (("29 days ahead", 29, True), ("45 days ahead", 45, False), ("11 years ahead", 4000, False)):
        r = h.post_purchase(sup, [(p, 1, 900)], account=acct, date=jalali_in(days))
        check(f"FD purchase dated {label}: {'saved' if ok else 'refused with a message'}",
              (r.status_code == 302) if ok else (r.status_code == 200 and has(r, "روز بعد از امروز")), r.status_code)
    check("FD purchase: only the near date was stored", PurchaseInvoice.objects.count() == m + 1)
    e = Expense.objects.count()
    for label, days, ok in (("29 days ahead", 29, True), ("45 days ahead", 45, False)):
        r = h.c.post("/expenses/new/", {"expense_date": jalali_in(days), "reason": f"QA-{label}", "amount": "500", "bank_account": str(acct.pk)})
        check(f"FD expense dated {label}: {'saved' if ok else 'refused'}", (r.status_code == 302) if ok else (r.status_code == 200), r.status_code)
    check("FD expense: only the near date was stored", Expense.objects.count() == e + 1, Expense.objects.count() - e)
    past = h.post_sale(cust, [(p, 1, 900)], account=acct, date=jalali_in(-400))
    check("FD a date in the past is still fine", past.status_code == 302, past.status_code)

    # ---- purchase cancel dialog
    inv = PurchaseInvoice.objects.filter(supplier=sup).order_by("-created_at").first()
    r = h.c.get(f"/purchasing/{inv.pk}/")
    body = text(r)
    check("PC01 the purchase detail has the cancel dialog, not a confirm() form", 'id="cancel-dialog"' in body and 'data-sp-dialog-open="cancel-dialog"' in body and "onsubmit" not in body, r.status_code)
    check("PC02 the dialog lists the stock effect with the product name", "از موجودی کم می‌شود" in body and p.name in body)
    check("PC03 the dialog loads the script that opens it", "sales_pages.js" in body)
    check("PC04 an ordinary user does not get the dialog", 'id="cancel-dialog"' not in text(h.cu.get(f"/purchasing/{inv.pk}/")))
    r = h.c.post(f"/purchasing/{inv.pk}/cancel/")
    inv.refresh_from_db()
    check("PC05 posting the dialog form cancels the purchase", r.status_code == 302 and inv.status == "cancelled", (r.status_code, inv.status))


run("zero_price_far_date", scenarios)

from tools.qa.qa_lib import *
from django.db.models import Sum
from apps.inventory.models import InventoryConsumption, InventoryLayer, InventoryMovement
from apps.payments.models import Cheque, Payment, PaymentAllocation
from apps.payments.selectors import get_customer_outstanding
from apps.sales.models import SaleItem, SalesInvoice
from apps.shared.models import DocumentSequence


def seq():
    from apps.shared import dates
    t = dates.today()  # sales count per invoice day (D-086)
    row = DocumentSequence.objects.filter(doc_type="sale", year=t.year, day=t.month * 100 + t.day).first()
    return row.next_number if row else 1


def n_inv():
    return SalesInvoice.objects.count()


def last(cust):
    return SalesInvoice.objects.filter(customer=cust).latest("created_at")


def scenarios(h):
    cust, cust2 = h.customer(), h.customer()
    acct = h.account()
    pos = h.account(kind="pos")
    a = h.product(stock=50, cost=100, price=1000)
    b = h.product(stock=20, cost=300, price=2000)
    zero = h.product(stock=0)

    # ------------------------------------------------ settlement
    s0 = seq()
    r = h.post_sale(cust, [(a, 10, 1000)], account=acct)
    check("S01 full settlement to a bank account redirects", r.status_code == 302, r.status_code)
    i = last(cust)
    check("S01 confirmed with a number, sequence +1", i.status == "confirmed" and i.invoice_number and seq() == s0 + 1)
    check("S01 stock -10", h.stock(a) == 40)
    check("S01 paid in full: Payment IN for the total into that account",
          i.payment_status == "paid" and Payment.objects.filter(customer=cust, direction="in", amount=10000, bank_account=acct).exists())
    it = i.items.get()
    check("S01 COGS 10×100 = 1000 and profit 9000", it.cost_of_goods == 1000 and it.profit == 9000, (it.cost_of_goods, it.profit))
    check("S01 customer owes nothing", get_customer_outstanding(cust) == 0)

    r = h.post_sale(cust, [(a, 1, 1000)], account=pos)
    check("S02 full settlement by card reader: payment into the card-reader account", r.status_code == 302 and
          Payment.objects.filter(customer=cust, amount=1000, bank_account=pos).exists())
    n1, s1 = n_inv(), seq()
    r = h.post_sale(cust, [(a, 1, 1000)], account=None)
    check("S03 full settlement without an account rejected, nothing consumed", r.status_code == 200 and n_inv() == n1 and seq() == s1 and h.stock(a) == 39)

    r = h.post_sale(cust2, [(a, 2, 1000)], mode="split")
    check("S04 split with no rows = fully on credit", r.status_code == 302 and last(cust2).payment_status == "unpaid" and get_customer_outstanding(cust2) == 2000)
    r = h.post_sale(cust2, [(a, 2, 1000)], mode="split", payments=[{"method": "bank_transfer", "amount": "500", "bank_account": str(acct.pk)}])
    check("S05 partial transfer row → partial", r.status_code == 302 and last(cust2).payment_status == "partial" and get_customer_outstanding(cust2) == 3500)
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "card", "amount": "1000", "bank_account": str(pos.pk)}])
    check("S06 card row paying everything → paid", r.status_code == 302 and last(cust2).payment_status == "paid")
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "bank_transfer", "amount": "400", "bank_account": str(acct.pk)}, {"method": "card", "amount": "600", "bank_account": str(pos.pk)}])
    check("S07 two rows summing to the total → paid", r.status_code == 302 and last(cust2).payment_status == "paid")
    r = h.post_sale(cust2, [(a, 2, 1000)], mode="split", payments=[
        {"method": "cheque", "amount": "1500", "bank_account": str(acct.pk), "cheque_number": "C9", "bank_name": "Mellat", "due_date": "1405/08/10"},
        {"method": "bank_transfer", "amount": "500", "bank_account": str(acct.pk)}])
    ic = last(cust2)
    chq = Cheque.objects.get(sales_invoice=ic)
    check("S08 cheque row → PENDING IN cheque, not counted as paid", chq.status == "pending" and chq.direction == "in" and ic.paid_amount == 500 and ic.payment_status == "partial")
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "cheque", "amount": "1000"}])
    check("S09 incomplete cheque accepted", r.status_code == 302 and Cheque.objects.filter(customer=cust2, amount=1000, cheque_number="").exists())
    n2, s2, st = n_inv(), seq(), h.stock(a)
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "cash", "amount": "1001"}])
    check("S10 rows above the total rejected, stock untouched", r.status_code == 200 and n_inv() == n2 and h.stock(a) == st and seq() == s2)
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "cash", "amount": "0"}])
    check("S10 a zero-amount payment row is rejected", r.status_code == 200 and n_inv() == n2)
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "cash", "amount": "-5"}])
    check("S10 a negative payment row is rejected", r.status_code == 200 and n_inv() == n2)
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "gold", "amount": "5"}])
    check("S10 an unknown method is rejected (no 500)", r.status_code == 200 and n_inv() == n2, r.status_code)
    r = h.post_sale(cust2, [(a, 1, 1000)], mode="split", payments=[{"method": "cash", "amount": "5", "bank_account": "00000000-0000-0000-0000-000000000000"}])
    check("S10 an unknown bank account is rejected (no 500)", r.status_code == 200 and n_inv() == n2, r.status_code)

    # ------------------------------------------------ stock rules (D-052)
    st = h.stock(b)
    r = h.post_sale(cust, [(b, st + 1, 100)], account=acct)
    check("S11 quantity above stock rejected", r.status_code == 200 and h.stock(b) == st and has(r, "موجودی"))
    r = h.post_sale(cust, [(b, st, 100)], account=acct)
    check("S12 exactly the stock on hand is allowed", r.status_code == 302 and h.stock(b) == 0)
    r = h.post_sale(cust, [(b, 1, 100)], account=acct)
    check("S12 …and then one more is refused (stock 0)", r.status_code == 200 and h.stock(b) == 0)
    r = h.post_sale(cust, [(zero, 1, 100)], account=acct)
    check("S13 a product that never had stock cannot be sold", r.status_code == 200)
    n3 = n_inv()
    r = h.post_sale(cust, [(a, 1, 100), (a, 2, 100)], account=acct)
    check("S14 same product twice rejected", r.status_code == 200 and n_inv() == n3)
    r = h.post_sale(cust, [(a, 1, 100), (zero, 1, 100)], account=acct)
    check("S15 one bad line rejects the whole invoice (no partial sale)", r.status_code == 200 and n_inv() == n3)
    r = h.post_sale(cust, [], account=acct)
    check("S16 no items rejected", r.status_code == 200 and n_inv() == n3)
    su_r = h.post_sale(cust, [(a, h.stock(a) + 1, 100)], account=acct, client=h.c)
    check("S17 a superuser cannot oversell either", su_r.status_code == 200)
    ord_r = h.post_sale(cust, [(a, 1, 1000)], account=acct, client=h.cu)
    check("S18 an ordinary user can sell normally", ord_r.status_code == 302)

    # ------------------------------------------------ field validation
    for q in ("0", "-2", "abc", "1.5", ""):
        c0 = n_inv()
        r = h.post_sale(cust, [(a, q, 100)], account=acct)
        check(f"S19 quantity '{q}' rejected", r.status_code == 200 and n_inv() == c0, r.status_code)
    for pr in ("-1", "abc", "1.5", str(10**19)):
        c0 = n_inv()
        r = h.post_sale(cust, [(a, 1, pr)], account=acct)
        check(f"S20 price '{pr[:8]}' does not crash", r.status_code in (200, 302) and r.status_code != 500 and (r.status_code == 200 or pr == "1.5" and False or True), r.status_code)
        if pr in ("-1", "abc", "1.5"):
            check(f"S20 price '{pr}' rejected", n_inv() == c0)
    # blank price falls back to the product default (2.4)
    d = {"customer": str(cust.pk), "invoice_date": TODAY_J, "discount_amount": "", "payment_mode": "full", "transfer_account": str(acct.pk), "use_transfer": "on"}
    d.update(h._rows("items", [{"product": str(a.pk), "packs": "1", "unit_price": ""}]))
    d.update(h._rows("payments", []))
    r = h.c.post("/sales/new/", d)
    check("S21 a blank price falls back to the product's selling price", r.status_code == 302 and last(cust).items.get().unit_price == 1000, r.status_code)
    r = h.post_sale(cust, [(a, 1, 0)], account=acct)
    check("S22 a zero price is allowed (free item)", r.status_code == 302)

    c0 = n_inv()
    inactive = h.customer(is_active=False)
    for label, cu in (("missing", None), ("inactive", inactive)):
        r = h.post_sale(cu, [(a, 1, 10)], account=acct)
        check(f"S23 {label} customer rejected", r.status_code == 200 and n_inv() == c0)
    for label, dt in (("garbage", "x"), ("empty", ""), ("Feb-30-like", "1405/13/40"), ("Gregorian", "2026-09-30"), ("year 1300", "1300/01/01"), ("year 1500", "1500/01/01")):
        r = h.post_sale(cust, [(a, 1, 10)], account=acct, date=dt)
        check(f"S24 date '{label}' rejected", r.status_code == 200 and n_inv() == c0, (r.status_code, n_inv() - c0))
    r = h.post_sale(cust, [(a, 1, 10)], account=acct, date="۱۴۰۵/۰۷/۰۸")
    check("S24 Persian-digit date accepted", r.status_code == 302)
    ghost = Product(pk="00000000-0000-0000-0000-0000000000bb", name="g")
    r = h.post_sale(cust, [(ghost, 1, 10)], account=acct)
    check("S25 unknown product id rejected", r.status_code == 200)
    r = h.post_sale(cust, [(h.product(is_active=False, stock=5), 1, 10)], account=acct)
    check("S25 inactive product rejected", r.status_code == 200)

    # ------------------------------------------------ discount (D-032/D-048)
    p1, p2 = h.product(stock=100, cost=1000, price=1), h.product(stock=100, cost=2000, price=1)
    c1 = h.customer()
    r = h.post_sale(c1, [(p1, 6, 100), (p2, 4, 100)], account=acct, discount="100")
    inv = last(c1)
    items = {x.product_id: x for x in inv.items.all()}
    check("S26 discount 100 over 600+400 → total 900", r.status_code == 302 and inv.total == 900)
    check("S26 pro-rata shares 60 and 40 (sum = 100)", items[p1.pk].discount_share == 60 and items[p2.pk].discount_share == 40)
    check("S26 line profits sum to invoice profit", sum(i.profit for i in items.values()) == inv.profit)
    c2 = h.customer()
    r = h.post_sale(c2, [(p1, 1, 1), (p1.__class__.objects.get(pk=p2.pk), 1, 1), ], account=acct, discount="1")
    inv2 = last(c2)
    check("S27 discount 1 over two equal lines: shares sum exactly to 1", sum(i.discount_share for i in inv2.items.all()) == 1)
    c3 = h.customer()
    n4 = n_inv()
    r = h.post_sale(c3, [(p1, 1, 100)], account=acct, discount="101")
    check("S28 discount above the subtotal rejected", r.status_code == 200 and n_inv() == n4)
    r = h.post_sale(c3, [(p1, 1, 100)], account=acct, discount="-5")
    check("S28 negative discount rejected", r.status_code == 200 and n_inv() == n4)
    r = h.post_sale(c3, [(p1, 1, 100)], account=acct, discount="abc")
    check("S28 text discount rejected", r.status_code == 200 and n_inv() == n4)
    r = h.post_sale(c3, [(p1, 1, 100)], account=acct, discount="100")
    check("S29 discount equal to the subtotal → total 0, no payment planned", r.status_code == 302 and last(c3).total == 0 and not Payment.objects.filter(customer=c3).exists(), r.status_code)
    check("S29 zero-total invoice reads as paid or unpaid without crashing", last(c3).payment_status in ("paid", "unpaid"))
    r = h.post_sale(c3, [(p1, 1, 100)], account=acct, discount=digits_fa(10))
    check("S30 Persian digits in the discount", r.status_code == 302)

    # ------------------------------------------------ FIFO / cancel
    f = h.product(stock=10, cost=100, price=500)
    h.post_purchase(h.supplier(), [(f, 10, 300)], account=acct)
    c4 = h.customer()
    h.post_sale(c4, [(f, 15, 500)], account=acct)
    inv = last(c4)
    it = inv.items.get()
    check("S31 15 units cost 10×100 + 5×300 = 2500", it.cost_of_goods == 2500, it.cost_of_goods)
    layers = list(InventoryLayer.objects.filter(product=f).order_by("created_at"))
    check("S31 layers drained oldest first: 0 and 5 left", [l.quantity_remaining for l in layers] == [0, 5])
    r = h.cu.post(f"/sales/{inv.pk}/cancel/")
    inv.refresh_from_db()
    check("S32 an ordinary user cannot cancel", inv.status == "confirmed")
    r = h.c.get(f"/sales/{inv.pk}/cancel/")
    check("S32 GET on cancel = 405", r.status_code == 405)
    r = h.c.post(f"/sales/{inv.pk}/cancel/")
    inv.refresh_from_db()
    layers = list(InventoryLayer.objects.filter(product=f).order_by("created_at"))
    check("S33 superuser cancels: status, stock back, layers restored exactly", inv.status == "cancelled" and h.stock(f) == 20 and [l.quantity_remaining for l in layers] == [10, 10])
    check("S33 cancelled invoice profit is 0 and cost is netted to 0", inv.profit == 0 and inv.items.get().cost_of_goods == 0)
    h.c.post(f"/sales/{inv.pk}/cancel/")
    check("S33 second cancel changes nothing", h.stock(f) == 20)
    refund = Payment.objects.filter(customer=c4, is_reversal=True).aggregate(t=Sum("amount"))["t"]
    check("S33 the money received for the cancelled sale (7500) was refunded (D-055)", refund == 7500 and inv.paid_amount == 0, refund)
    inv3 = last(cust)
    r = h.c.get(f"/sales/{inv3.pk}/")
    check("S34 detail renders", r.status_code == 200 and has(r, inv3.invoice_number))
    r = h.c.get(f"/sales/{inv3.pk}/print/")
    check("S34 print renders", r.status_code == 200)
    check("S34 unknown/malformed ids = 404", h.c.get("/sales/00000000-0000-0000-0000-000000000009/").status_code == 404 and h.c.get("/sales/xyz/").status_code == 404)

    # ------------------------------------------------ list & filters
    for qs, label in (("", "default"), ("?q=" + cust.name, "search customer"), ("?q=" + inv3.invoice_number, "search number"),
                      ("?payment_status=paid", "paid"), ("?payment_status=unpaid", "unpaid"), ("?payment_status=partial", "partial"), ("?payment_status=zz", "bad status"),
                      ("?amount_min=1000&amount_max=1", "min>max"), ("?amount_min=x", "text amount"), ("?page=abc", "bad page"), ("?page=99999", "huge page"),
                      ("?preset=custom&start=1405/07/01&end=1405/07/30", "range"), ("?preset=custom&start=1405/07/30&end=1405/07/01", "reversed"),
                      ("?preset=custom&start=x&end=y", "garbage range"), ("?preset=foo", "unknown preset"), ("?product=" + str(a.pk), "product"),
                      ("?q=%25", "wildcard"), ("?q=" + "z" * 3000, "very long q")):
        r = h.c.get("/sales/" + qs)
        check(f"S35 list {label or 'default'} → 200", r.status_code == 200, r.status_code)
    r = h.c.get("/sales/?q=" + cust.name)
    check("S35 search by customer name finds the invoice", has(r, inv3.invoice_number))
    r = h.c.get("/sales/?q=" + cust.name + "&payment_status=unpaid")
    check("S35 filter + search combine", r.status_code == 200)
    r = h.c.get("/sales/product-search/?q=" + a.name)
    check("S36 product search shows stock and price data", has(r, str(a.pk)) and has(r, "data-pack-price"))
    r = h.c.get(f"/sales/product-search/?q={a.name}&exclude={a.pk}")
    check("S36 exclude hides a chosen product", not has(r, str(a.pk)))
    r = h.c.get("/sales/product-search/?q=" + zero.name)
    check("S36 zero-stock product is listed but disabled", has(r, str(zero.pk)) and has(r, "disabled") and has(r, "ناموجود"))

    # ------------------------------------------------ misc / tamper
    for total in ("-1", "abc", "100000", ""):
        d = {"customer": str(cust.pk), "invoice_date": TODAY_J, "payment_mode": "full", "transfer_account": str(acct.pk), "use_transfer": "on",
             "items-TOTAL_FORMS": total, "items-INITIAL_FORMS": 0, "payments-TOTAL_FORMS": 0, "payments-INITIAL_FORMS": 0}
        r = h.c.post("/sales/new/", d)
        check(f"S37 tampered TOTAL_FORMS '{total}' no crash", r.status_code in (200, 400), r.status_code)
    r = h.c.post("/sales/new/", {})
    check("S37 empty POST no crash", r.status_code in (200, 400))
    r = h.post_sale(cust, [(a, 1, 10)], account=acct, mode="zzz")
    check("S37 unknown payment mode rejected", r.status_code == 200)
    # tamper: payment rows posted in FULL mode are ignored (never validated)
    r = h.post_sale(cust, [(a, 1, 10)], account=acct, mode="full", payments=[{"method": "cash", "amount": "-999"}])
    check("S38 payment rows sent in full mode are ignored", r.status_code == 302)
    # stale-form protection: the stock check happens on the server at POST time
    lim = h.product(stock=3)
    r1 = h.post_sale(cust, [(lim, 3, 1)], account=acct)
    r2 = h.post_sale(cust, [(lim, 3, 1)], account=acct)
    check("S39 two sales racing for the same stock: the second is refused", r1.status_code == 302 and r2.status_code == 200 and h.stock(lim) == 0)
    # unauthenticated
    for url in ("/sales/", "/sales/new/", f"/sales/{inv3.pk}/", f"/sales/{inv3.pk}/print/", "/sales/product-search/"):
        r = h.anon.get(url)
        check(f"S40 anonymous redirected for {url}", r.status_code == 302 and "/login/" in r["Location"])
    evil = h.customer(name="<img src=x onerror=alert(1)>QA")
    h.post_sale(evil, [(a, 1, 10)], account=acct)
    ev = last(evil)
    for url in ("/sales/", f"/sales/{ev.pk}/", f"/sales/{ev.pk}/print/", "/customers/", f"/customers/{evil.pk}/", "/sales/new/", "/receivables/"):
        r = h.c.get(url)
        check(f"S41 HTML in a customer name is escaped on {url}", "<img src=x onerror=alert(1)>" not in text(r), r.status_code)
    # quick customer
    r = h.c.post("/customers/quick-new/", {"name": "QA-qc-" + rnd(), "phone": "0912"})
    check("S42 quick customer created (+oob select with the sale form's form attr)", r.status_code == 200 and has(r, 'form="sale-form"'))
    nm = "QA-dupc-" + rnd(); h.customer(name=nm)
    r = h.c.post("/customers/quick-new/", {"name": nm})
    check("S42 quick customer duplicate → 422", r.status_code == 422)
    r = h.c.post("/customers/quick-new/", {"name": ""})
    check("S42 quick customer blank → 422", r.status_code == 422)


run("sales", scenarios)

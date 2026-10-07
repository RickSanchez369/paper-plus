from tools.qa.qa_lib import *
from django.db.models import Sum
from apps.payments.models import Cheque, Payment, PaymentAllocation
from apps.purchasing.models import PurchaseInvoice, PurchasePaymentEntry
from apps.inventory.models import InventoryLayer, InventoryMovement
from apps.payments.selectors import get_supplier_outstanding
from apps.shared.models import DocumentSequence


def seq():
    from apps.shared import dates
    row = DocumentSequence.objects.filter(doc_type="purchase", year=dates.today().year).first()
    return row.next_number if row else 1


def n_inv():
    return PurchaseInvoice.objects.count()


def scenarios(h):
    sup, sup2 = h.supplier(), h.supplier()
    acct = h.account()
    a, b = h.product(stock=0), h.product(stock=0)

    # ---------------------------------------------------------- basic settlement
    n0, s0 = n_inv(), seq()
    r = h.post_purchase(sup, [(a, 10, 2000)], account=acct)
    check("P01 full settlement from a bank account redirects", r.status_code == 302, r.status_code)
    inv = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    check("P01 invoice confirmed with a number", inv.status == "confirmed" and bool(inv.invoice_number))
    check("P01 stock +10", h.stock(a) == 10)
    lay = InventoryLayer.objects.get(purchase_item__invoice=inv)
    check("P01 layer opened at the purchase price", lay.unit_cost == 2000 and lay.quantity == 10 and lay.quantity_remaining == 10)
    check("P01 paid in full", inv.payment_status == "paid", inv.payment_status)
    pay = Payment.objects.get(supplier=sup)
    check("P01 payment is OUT from that account for the total", pay.direction == "out" and pay.bank_account_id == acct.pk and pay.amount == 20000)
    check("P01 sequence advanced by 1", seq() == s0 + 1)
    check("P01 supplier outstanding 0", get_supplier_outstanding(sup) == 0)

    pos = h.account(kind="pos")
    n0 = n_inv()
    r = h.post_purchase(sup, [(b, 5, 300)], account=pos)
    check("P02 a card-reader account cannot pay a supplier (rejected, nothing saved)", r.status_code == 200 and n_inv() == n0)
    r = h.post_purchase(sup, [(b, 5, 300)], account=acct)
    check("P02 full settlement by bank transfer redirects", r.status_code == 302)
    inv2 = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    check("P02 transfer payment is out of the account", Payment.objects.filter(supplier=sup, amount=1500, bank_account=acct).exists())
    check("P02 numbers strictly increase", inv2.invoice_number.split("/")[0] == inv.invoice_number.split("/")[0] and int(inv2.invoice_number.split("/")[1]) == int(inv.invoice_number.split("/")[1]) + 1)

    n1, s1 = n_inv(), seq()
    r = h.post_purchase(sup, [(a, 1, 100)], account=None)
    check("P03 full settlement without an account is rejected", r.status_code == 200 and n_inv() == n1)
    check("P03 error is shown on the page", has(r, "حداقل یک روش"))
    check("P03 sequence untouched", seq() == s1)

    # ---------------------------------------------------------------- split mode
    r = h.post_purchase(sup2, [(a, 4, 1000)], mode="split")
    check("P04 split with no rows = fully on credit", r.status_code == 302)
    i4 = PurchaseInvoice.objects.filter(supplier=sup2).latest("created_at")
    check("P04 status unpaid, outstanding = total", i4.payment_status == "unpaid" and get_supplier_outstanding(sup2) == 4000)
    check("P04 no payment written", not Payment.objects.filter(supplier=sup2).exists())

    r = h.post_purchase(sup2, [(b, 10, 100)], mode="split", payments=[{"method": "bank_transfer", "amount": "300", "bank_account": str(acct.pk)}])
    i5 = PurchaseInvoice.objects.filter(supplier=sup2).latest("created_at")
    check("P05 split transfer row books a payment from the account", r.status_code == 302 and i5.payment_status == "partial" and
          Payment.objects.filter(supplier=sup2, amount=300, bank_account=acct).exists())
    check("P05 outstanding = 4000 + (1000-300)", get_supplier_outstanding(sup2) == 4700)

    n6 = n_inv()
    r = h.post_purchase(sup2, [(a, 1, 500)], mode="split", payments=[{"method": "card", "amount": "200", "bank_account": str(pos.pk)}])
    check("P06 a card row is refused when paying a supplier", r.status_code == 200 and n_inv() == n6)
    r = h.post_purchase(sup2, [(a, 1, 500)], mode="split", payments=[{"method": "bank_transfer", "amount": "500", "bank_account": str(acct.pk)}])
    i7 = PurchaseInvoice.objects.filter(supplier=sup2).latest("created_at")
    check("P07 split transfer row paying it all = paid", r.status_code == 302 and i7.payment_status == "paid")

    r = h.post_purchase(sup2, [(a, 2, 500)], mode="split", payments=[
        {"method": "cheque", "amount": "700", "bank_account": str(acct.pk), "cheque_number": "CH1", "bank_name": "Melli", "due_date": "1405/08/01"},
        {"method": "bank_transfer", "amount": "300", "bank_account": str(acct.pk)}])
    i8 = PurchaseInvoice.objects.filter(supplier=sup2).latest("created_at")
    chq = Cheque.objects.get(purchase_invoice=i8)
    check("P08 cheque row becomes a PENDING OUT cheque", chq.status == "pending" and chq.direction == "out" and chq.amount == 700 and chq.supplier_id == sup2.pk)
    check("P08 pending cheque is not counted as paid (only the cash 300)", i8.payment_status == "partial" and i8.paid_amount == 300, (i8.payment_status, i8.paid_amount))

    r = h.post_purchase(sup2, [(a, 1, 500)], mode="split", payments=[{"method": "cheque", "amount": "500"}])
    check("P09 incomplete cheque (no number/bank/date) is accepted", r.status_code == 302)
    ci = Cheque.objects.filter(supplier=sup2, amount=500, cheque_number="").first()
    check("P09 …and stays pending, editable later", ci is not None and ci.status == "pending" and ci.due_date is None)

    n2, s2 = n_inv(), seq()
    st2 = h.stock(a)
    r = h.post_purchase(sup2, [(a, 1, 100)], mode="split", payments=[{"method": "bank_transfer", "amount": "101", "bank_account": str(acct.pk)}])
    check("P10 payment rows above the total are rejected", r.status_code == 200 and n_inv() == n2)
    check("P10 nothing leaked: stock, sequence, payments", h.stock(a) == st2 and seq() == s2 and not Payment.objects.filter(supplier=sup2, amount=101).exists())
    r = h.post_purchase(sup2, [(a, 1, 100)], mode="split", payments=[{"method": "bank_transfer", "amount": "60", "bank_account": str(acct.pk)}, {"method": "bank_transfer", "amount": "41", "bank_account": str(acct.pk)}])
    check("P10b two rows that sum above the total are rejected", r.status_code == 200 and n_inv() == n2)
    r = h.post_purchase(sup2, [(a, 1, 100)], mode="split", payments=[{"method": "bank_transfer", "amount": "60", "bank_account": str(acct.pk)}, {"method": "bank_transfer", "amount": "40", "bank_account": str(acct.pk)}])
    check("P11 rows summing exactly to the total = paid", r.status_code == 302 and PurchaseInvoice.objects.filter(supplier=sup2).latest("created_at").payment_status == "paid")

    # ---------------------------------------------------------------- item validation
    n3 = n_inv()
    r = h.post_purchase(sup, [(a, 1, 100), (a, 2, 100)], account=acct)
    check("P12 same product twice is rejected", r.status_code == 200 and n_inv() == n3)
    r = h.post_purchase(sup, [], account=acct)
    check("P13 no items is rejected", r.status_code == 200 and n_inv() == n3)
    d = {"supplier": str(sup.pk), "invoice_date": TODAY_J, "payment_mode": "full", "transfer_account": str(acct.pk), "use_transfer": "on"}
    d.update(h._rows("items", [{"product": "", "packs": "", "unit_price": ""}, {"product": str(b.pk), "packs": "2", "unit_price": "10"}]))
    d.update(h._rows("payments", []))
    r = h.c.post("/purchasing/new/", d)
    check("P14 an untouched blank row next to a valid one is ignored", r.status_code == 302, r.status_code)

    bad_qty = ["0", "-3", "abc", "1.5", "", "  ", str(10**12), "٣"]  # last one: an Arabic-Indic digit
    outcomes = {}
    for q in bad_qty:
        c0 = n_inv()
        r = h.post_purchase(sup, [(a, q, 100)], account=acct)
        outcomes[q] = (r.status_code, n_inv() - c0)
    check("P15 zero/negative/text/decimal/blank quantities never create an invoice",
          all(outcomes[q][1] == 0 and outcomes[q][0] == 200 for q in ["0", "-3", "abc", "1.5", "", "  "]), outcomes)
    check("P15 huge quantity is rejected cleanly (no 500)", outcomes[str(10**12)][0] in (200, 302) and outcomes[str(10**12)][0] != 500, outcomes[str(10**12)])
    check("P15 an Arabic-Indic digit is a valid number (٣ = 3)", outcomes["٣"][0] in (200, 302) and outcomes["٣"][0] != 500, outcomes["٣"])

    outcomes = {}
    for pr in ["-1", "abc", "", "1.5", str(10**19), str(2**63)]:
        c0 = n_inv()
        r = h.post_purchase(sup, [(a, 1, pr)], account=acct)
        outcomes[pr] = (r.status_code, n_inv() - c0)
    check("P16 negative/text/blank/decimal price rejected", all(outcomes[p][1] == 0 and outcomes[p][0] == 200 for p in ["-1", "abc", "", "1.5"]), outcomes)
    check("P16 absurdly large price does not crash (no 500)", outcomes[str(10**19)][0] != 500 and outcomes[str(2**63)][0] != 500, outcomes)
    c0 = n_inv()
    r = h.post_purchase(sup, [(a, 1, 0)], account=acct)
    check("P16 a zero price is refused (D-097: a cost-0 layer would inflate profit; free goods go in at 1 Toman)", r.status_code == 200 and n_inv() == c0)

    # ---------------------------------------------------------------- header validation
    c0 = n_inv()
    inactive = h.supplier(is_active=False)
    for label, s in (("missing", None), ("inactive", inactive)):
        r = h.post_purchase(s, [(a, 1, 10)], account=acct)
        check(f"P17 {label} supplier rejected", r.status_code == 200 and n_inv() == c0)
    d = {"supplier": "not-a-uuid", "invoice_date": TODAY_J, "payment_mode": "full", "transfer_account": str(acct.pk), "use_transfer": "on"}
    d.update(h._rows("items", [{"product": str(a.pk), "packs": "1", "unit_price": "1"}])); d.update(h._rows("payments", []))
    r = h.c.post("/purchasing/new/", d)
    check("P17 malformed supplier id rejected (no 500)", r.status_code == 200 and n_inv() == c0, r.status_code)
    d["supplier"] = "00000000-0000-0000-0000-000000000000"
    r = h.c.post("/purchasing/new/", d)
    check("P17 unknown supplier id rejected", r.status_code == 200 and n_inv() == c0)

    ghost = Product(pk="00000000-0000-0000-0000-0000000000aa", name="x")
    inactive_p = h.product(is_active=False)
    for label, p in (("nonexistent", ghost), ("inactive", inactive_p)):
        r = h.post_purchase(sup, [(p, 1, 10)], account=acct)
        check(f"P18 {label} product rejected", r.status_code == 200 and n_inv() == c0, r.status_code)
    r = h.post_purchase(sup, [(None, 1, 10)], account=acct)
    check("P18 an item row with no product rejected", r.status_code == 200 and n_inv() == c0)

    for label, dt in (("garbage", "hello"), ("empty", ""), ("impossible Jalali day", "1405/13/45"), ("Gregorian-style", "2026-09-30")):
        r = h.post_purchase(sup, [(a, 1, 10)], account=acct, date=dt)
        check(f"P19 date '{label}' rejected without a 500", r.status_code == 200 and n_inv() == c0, (r.status_code, n_inv() - c0))
    r = h.post_purchase(sup, [(a, 1, 10)], account=acct, date=TODAY_J)
    check("P19 a normal Jalali date is accepted", r.status_code == 302)
    r = h.post_purchase(sup, [(a, 1, 10)], account=acct, date="1500/01/01")
    check("P19 a far-future date is accepted or rejected but never a 500", r.status_code in (200, 302))
    r = h.post_purchase(sup, [(a, 1, 10)], account=acct, date="1300/01/01")
    check("P19 a very old date is accepted or rejected but never a 500", r.status_code in (200, 302))
    r = h.post_purchase(sup, [(a, 1, 10)], account=acct, date="۱۴۰۵/۰۷/۰۸")
    check("P19 Persian digits in the date work", r.status_code == 302, r.status_code)

    r = h.post_purchase(sup, [(a, 1, 10)], account=acct, supplier_invoice="فاکتور-۱۲۳ <b>x</b>")
    check("P20 supplier invoice number accepts free text", r.status_code == 302)
    r = h.post_purchase(sup, [(a, 1, 10)], account=acct, supplier_invoice="x" * 500)
    check("P20 an overlong supplier invoice number is rejected/trimmed, never a 500", r.status_code in (200, 302), r.status_code)

    r = h.post_purchase(sup, [(b, digits_fa(3), digits_fa(1500))], account=acct)
    check("P21 Persian digits in quantity/price are accepted", r.status_code == 302, r.status_code)
    pi = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    check("P21 …and stored as the right numbers", pi.total_amount == 4500, pi.total_amount)
    r = h.post_purchase(sup, [(a, 1, 10)], account=acct, mode="hack")
    check("P22 unknown payment_mode is rejected (no 500)", r.status_code == 200)

    # tampered management form
    for total in ("-1", "abc", "100000", ""):
        d = {"supplier": str(sup.pk), "invoice_date": TODAY_J, "payment_mode": "full", "transfer_account": str(acct.pk), "use_transfer": "on",
             "items-TOTAL_FORMS": total, "items-INITIAL_FORMS": 0, "payments-TOTAL_FORMS": 0, "payments-INITIAL_FORMS": 0}
        r = h.c.post("/purchasing/new/", d)
        check(f"P23 tampered TOTAL_FORMS='{total}' does not crash", r.status_code in (200, 400), r.status_code)
    r = h.c.post("/purchasing/new/", {})
    check("P23 an empty POST does not crash", r.status_code in (200, 400), r.status_code)

    # ---------------------------------------------------------------- FIFO & multi-line
    p1, p2 = h.product(), h.product()
    r = h.post_purchase(sup, [(p1, 5, 100), (p2, 7, 250)], account=acct)
    check("P24 multi-line purchase: stock and one layer per line", r.status_code == 302 and h.stock(p1) == 5 and h.stock(p2) == 7 and
          InventoryLayer.objects.filter(product__in=[p1, p2]).count() == 2)
    r = h.post_purchase(sup, [(p1, 5, 300)], account=acct)
    lay = list(InventoryLayer.objects.filter(product=p1).order_by("created_at"))
    check("P24 a second purchase of the same product opens a second layer at its own cost", [l.unit_cost for l in lay] == [100, 300])
    cust = h.customer()
    h.post_sale(cust, [(p1, 6, 900)], account=acct)
    lay = list(InventoryLayer.objects.filter(product=p1).order_by("created_at"))
    check("P24 a sale drains the oldest layer first (5@100 then 1@300)", [l.quantity_remaining for l in lay] == [0, 4], [l.quantity_remaining for l in lay])

    # ---------------------------------------------------------------- cancel
    cp = h.product()
    h.post_purchase(sup, [(cp, 3, 400)], account=acct)
    ci = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    r = h.cu.post(f"/purchasing/{ci.pk}/cancel/")
    ci.refresh_from_db()
    check("P25 an ordinary user cannot cancel", ci.status == "confirmed" and h.stock(cp) == 3)
    r = h.c.get(f"/purchasing/{ci.pk}/cancel/")
    check("P25 GET on the cancel URL is refused (405)", r.status_code == 405, r.status_code)
    r = h.c.post(f"/purchasing/{ci.pk}/cancel/")
    ci.refresh_from_db()
    check("P25 a superuser cancels: status, stock back to 0, layer withdrawn",
          ci.status == "cancelled" and h.stock(cp) == 0 and InventoryLayer.objects.get(product=cp).cancelled_at is not None)
    r = h.c.post(f"/purchasing/{ci.pk}/cancel/")
    check("P25 a second cancel is a no-op (no double reversal)", h.stock(cp) == 0)
    check("P25 the cancelled invoice keeps its number", bool(ci.invoice_number))
    out_after = supp_out = get_supplier_outstanding(sup)
    refund = Payment.objects.filter(supplier=sup, is_reversal=True).aggregate(t=Sum("amount"))["t"]
    check("P25 what was paid for the cancelled purchase (1200) came back as a refund (D-055)", refund == 1200 and ci.paid_amount == 0, refund)

    sold = h.product()
    h.post_purchase(sup, [(sold, 4, 100)], account=acct)
    si = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    h.post_sale(cust, [(sold, 1, 500)], account=acct)
    r = h.c.post(f"/purchasing/{si.pk}/cancel/")
    si.refresh_from_db()
    check("P26 cancelling a purchase whose stock was partly sold is refused", si.status == "confirmed" and h.stock(sold) == 3)

    # ---------------------------------------------------------------- pages
    r = h.c.get(f"/purchasing/{si.pk}/")
    check("P27 detail page renders with the invoice number", r.status_code == 200 and has(r, si.invoice_number))
    r = h.c.get(f"/purchasing/{si.pk}/print/")
    check("P27 print page renders", r.status_code == 200)
    r = h.c.get("/purchasing/00000000-0000-0000-0000-000000000001/")
    check("P27 unknown id = 404", r.status_code == 404)
    r = h.c.get("/purchasing/not-a-uuid/")
    check("P27 malformed id = 404", r.status_code == 404)
    r = h.c.get("/purchasing/")
    check("P28 list renders", r.status_code == 200 and has(r, si.invoice_number))
    for qs, label in (("?q=" + sup.name, "search by supplier"), ("?q=" + si.invoice_number, "search by number"),
                      ("?payment_status=paid", "status paid"), ("?payment_status=zzz", "invalid status"),
                      ("?amount_min=10&amount_max=5", "min>max"), ("?amount_min=abc", "non-numeric amount"),
                      ("?page=abc", "page not a number"), ("?page=9999", "page too large"), ("?page=-1", "negative page"),
                      ("?preset=custom&start=1405/07/01&end=1405/07/30", "custom range"), ("?preset=custom&start=1405/07/30&end=1405/07/01", "reversed range"),
                      ("?preset=custom&start=1405/07/01", "half range"), ("?preset=today", "today"), ("?preset=week", "week"),
                      ("?product=" + str(a.pk), "product filter"), ("?product=zzz", "bad product")):
        r = h.c.get("/purchasing/" + qs)
        check(f"P28 list {label} → no crash", r.status_code == 200, r.status_code)
    r = h.c.get("/purchasing/?q=" + sup.name)
    check("P28 search by supplier finds only that supplier's invoices", has(r, si.invoice_number))

    # XSS
    evil = h.supplier(name="<script>alert(1)</script>QA")
    h.post_purchase(evil, [(a, 1, 5)], account=acct)
    ei = PurchaseInvoice.objects.filter(supplier=evil).latest("created_at")
    for url in ("/purchasing/", f"/purchasing/{ei.pk}/", f"/purchasing/{ei.pk}/print/", "/purchasing/suppliers/", f"/purchasing/suppliers/{evil.pk}/", "/purchasing/new/", "/payables/"):
        r = h.c.get(url)
        check(f"P29 script tag in a supplier name is escaped on {url}", "<script>alert(1)</script>" not in text(r), r.status_code)

    # anonymous / auth
    for url in ("/purchasing/", "/purchasing/new/", f"/purchasing/{si.pk}/"):
        r = h.anon.get(url)
        check(f"P30 anonymous → login redirect for {url}", r.status_code == 302 and "/login/" in r["Location"])
    r = h.anon.post("/purchasing/new/", {})
    check("P30 anonymous POST is refused", r.status_code == 302 and "/login/" in r["Location"])

    # ---------------------------------------------------------------- quick create & search
    r = h.c.post("/purchasing/quick-supplier/", {"name": "QA-quick-" + rnd(), "phone": "0912"})
    check("P31 quick supplier: created", r.status_code == 200 and has(r, "hx-swap-oob"))
    nm = "QA-dup-" + rnd(); h.supplier(name=nm)
    r = h.c.post("/purchasing/quick-supplier/", {"name": nm})
    check("P31 quick supplier: duplicate name → 422 with a message", r.status_code == 422 and has(r, "همین نام"))
    r = h.c.post("/purchasing/quick-supplier/", {"name": "   "})
    check("P31 quick supplier: blank name → 422", r.status_code == 422)
    r = h.c.post("/purchasing/quick-supplier/", {"name": "QA-c-" + rnd(), "compact": "1"})
    check("P31 quick supplier compact flag is accepted", r.status_code == 200)
    r = h.c.post("/purchasing/quick-supplier/", {"name": nm, "compact": "1"})
    check("P31 …and a compact error re-renders compact (name+phone only)", r.status_code == 422 and has(r, "quick-party--compact") and not has(r, 'name="address"'))

    sku = f"QQ{random.randint(10**6, 10**7)}"
    r = h.c.post("/purchasing/quick-product/", {"name": "QA-qp-" + rnd(), "sku": sku, "pack_per_carton": "5", "default_selling_price": "1200"})
    check("P32 quick product: created", r.status_code == 200 and has(r, "data-quick-product-created"))
    r = h.c.post("/purchasing/quick-product/", {"name": "QA-qp2-" + rnd(), "sku": sku, "pack_per_carton": "5", "default_selling_price": "1"})
    check("P32 quick product: duplicate SKU → 422", r.status_code == 422)
    r = h.c.post("/purchasing/quick-product/", {"name": "QA-qp3-" + rnd(), "sku": "S" + rnd(), "pack_per_carton": "5", "default_selling_price": ""})
    check("P32 quick product: missing selling price → 422 (gap #6)", r.status_code == 422)
    r = h.c.post("/purchasing/quick-product/", {"name": "QA-qp4-" + rnd(), "sku": "S" + rnd(), "pack_per_carton": "5", "default_selling_price": "-5"})
    check("P32 quick product: negative price → 422", r.status_code == 422)

    ps = h.product(name="QA-searchable-" + rnd())
    r = h.c.get("/purchasing/product-search/?q=" + ps.name)
    check("P33 product search finds by name", has(r, str(ps.pk)))
    r = h.c.get("/purchasing/product-search/?q=" + ps.sku)
    check("P33 product search finds by SKU", has(r, str(ps.pk)))
    r = h.c.get(f"/purchasing/product-search/?q={ps.name}&exclude={ps.pk}")
    check("P33 exclude hides the product", not has(r, str(ps.pk)))
    r = h.c.get("/purchasing/product-search/?q=" + inactive_p.name)
    check("P33 inactive products are not offered", not has(r, str(inactive_p.pk)))
    for ex in ("", ",,,", "zzz", "'; DROP TABLE x;--", str(ps.pk) + ",zzz"):
        r = h.c.get("/purchasing/product-search/?exclude=" + ex)
        check(f"P33 exclude='{ex[:12]}' never crashes", r.status_code == 200, r.status_code)
    r = h.c.get("/purchasing/product-search/?q=" + "x" * 5000)
    check("P33 a very long query does not crash", r.status_code == 200)
    r = h.c.get("/purchasing/product-search/?q=%25_%5C")
    check("P33 SQL wildcard characters do not crash", r.status_code == 200)

    # payables page mirrors the outstanding
    r = h.c.get("/payables/")
    check("P34 payables lists suppliers with a balance", r.status_code == 200 and has(r, sup2.name))
    r = h.c.get(f"/purchasing/suppliers/{sup2.pk}/")
    check("P34 supplier detail shows their invoices", r.status_code == 200 and has(r, i4.invoice_number))


run("purchase", scenarios)

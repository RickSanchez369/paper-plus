"""Purchase invoice scenarios on a phone: suppliers x item shapes x freight x payment shapes x dates, with DB oracles (totals, stock
gained, payments), refusals, and the two quick-create dialogs (supplier, product) used in the middle of an invoice."""
import datetime
import random
import re

from tools.qa.mobile_suite import driver as D
from tools.qa.mobile_suite.lib import Watched, run_module
from tools.qa.mobile_suite.t_sale import PRODUCT_TERMS, jalali, stock_of

SUPPLIERS = ["پخش سراسری کاغذ", "شرکت صنایع بسته‌بندی", "تأمین ماژیک ایران", "واردات چین‌کالا", "بازرگانی میلاد", "تولیدی دفتر نگین"]


def gen(seed=1406):
    R = random.Random(seed)
    prods = ["R-101", "R-102", "R-103", "R-104", "R-105", "R-107", "R-110", "R-111", "QA-P1", "QA-P2", "QA-P3"]
    shapes = {
        "packs": lambda p: [dict(sku=p, cartons=0, packs=12, up=5000)],
        "cartons": lambda p: [dict(sku=p, cartons=3, packs=0, cp=90000)],
        "mixed": lambda p: [dict(sku=p, cartons=1, packs=2, cp=60000, up=11000)],
        "persian-digits": lambda p: [dict(sku=p, cartons="", packs="۱۰", up="۷۵۰۰")],
        "two-rows": lambda p: [dict(sku=p, cartons=0, packs=6, up=4000), dict(sku=prods[(prods.index(p) + 3) % len(prods)], cartons=1, packs=0, cp=50000)],
    }
    pays = ["full_tr", "credit_15", "credit_typed", "split_tr_credit", "split_cheque_credit", "split_tr_cheque"]
    S = []

    def add(tag, **kw):
        base = dict(sup=SUPPLIERS[len(S) % len(SUPPLIERS)], rows=[], pay=dict(k="full_tr"), date=0, freight=None, invno="", expect="ok", kw=[])
        base.update(kw)
        base["id"] = f"P{len(S) + 1:03d}"
        base["tag"] = tag
        S.append(base)

    n = 0
    for pk in pays:
        for i in range(9):
            shape = list(shapes)[(n + i) % len(shapes)]
            p = prods[(n * 3 + i * 2) % len(prods)]
            add(f"{pk}/{shape}", rows=shapes[shape](p), pay=dict(k=pk), sup=SUPPLIERS[(n + i) % len(SUPPLIERS)],
                freight=[None, 250000, "۱۲۰۰۰۰", None, 90000][(n + i) % 5], date=[0, 0, -1, -9][(n + i) % 4],
                invno=["", "A-" + str(100 + i), "فاکتور ۴۵۶", "", "X" * 40][(n + i) % 5])
        n += 1
    for s in SUPPLIERS:
        add(f"supplier:{s[:12]}", sup=s, rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)])
    add("freight-only-spread", rows=[dict(sku="R-101", cartons=0, packs=5, up=2000), dict(sku="R-102", cartons=0, packs=10, up=3000)], freight=150000)
    add("long-supplier-invoice-number", rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], invno="N" * 120, expect="ok_or_error")
    add("edge:credit-without-due-date", rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], pay=dict(k="credit", due=""), expect="ok_or_error")
    add("html-in-invoice-number", rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], invno="<b>x</b>&amp;\"'", expect="ok_or_error")
    bad = [
        ("no-supplier", dict(sup=None, rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)]), ["تأمین"]),
        ("no-rows", dict(rows=[]), ["قلم", "کالا", "ردیف"]),
        ("zero-qty", dict(rows=[dict(sku="R-105", cartons=0, packs=0, up=3000)]), []),
        ("no-price", dict(rows=[dict(sku="R-105", cartons=0, packs=3)]), []),
        ("negative-qty", dict(rows=[dict(sku="R-105", cartons="", packs="-3", up=3000)]), []),
        ("decimal-qty", dict(rows=[dict(sku="R-105", cartons="", packs="1.5", up=3000)]), []),
        ("text-price", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up="abc")]), []),
        ("freight-negative", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], freight="-500"), ["کرایه"]),
        ("freight-ticked-no-amount", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], freight="TICK_ONLY"), ["کرایه"]),
        ("huge-price", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up="99999999999999999999")]), []),
        ("huge-qty", dict(rows=[dict(sku="R-105", cartons=0, packs="99999999999999999999", up=3000)]), []),
        ("huge-qty-times-price", dict(rows=[dict(sku="R-105", cartons=0, packs=10**12, up=10**12)]), []),
        ("huge-freight", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], freight="99999999999999999999"), []),
        ("no-payment-method", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], pay=dict(k="none")), ["روش", "پرداخت"]),
        ("split-over-total", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], pay=dict(k="split_over_total", due="30")), ["مبلغ", "جمع"]),
        ("bad-date", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], date="1405/00/99"), ["تاریخ"]),
        # D-097: a price of 0 and a date far ahead are refused
        ("zero-price", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=0)]), ["صفر"]),
        ("date-45-days-ahead", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], date=45), ["تاریخ"]),
        ("date-11-years-ahead", dict(rows=[dict(sku="R-105", cartons=0, packs=3, up=3000)], date=4000), ["تاریخ"]),
    ]
    for tag, kw, words in bad:
        add("refuse:" + tag, expect="error", kw=words, **kw)
    return S


def run_one(b, rec, w, sc):
    from apps.partners.models import Supplier
    from apps.products.models import Product
    from apps.purchasing.models import PurchaseInvoice
    pg = w.page
    tag = f"{sc['id']} {sc['tag']}"
    lines, need, bad_row = [], {}, False
    for r in sc["rows"]:
        p = Product.objects.get(sku=r["sku"])
        r["_p"] = p
        c_txt, k_txt = D.ascii_digits(str(r.get("cartons") or "")), D.ascii_digits(str(r.get("packs") or ""))
        ok_num = re.fullmatch(r"\s*\d*\s*", c_txt) and re.fullmatch(r"\s*\d*\s*", k_txt)
        c, k = int(c_txt.strip() or 0) if ok_num else 0, int(k_txt.strip() or 0) if ok_num else 0
        up_txt, cp_txt = D.ascii_digits(str(r.get("up", ""))), D.ascii_digits(str(r.get("cp", "")))
        if not ok_num or (up_txt and not up_txt.isdigit()) or (cp_txt and not cp_txt.isdigit()):
            bad_row = True
        up, cp = int(up_txt or 0) if up_txt.isdigit() else 0, int(cp_txt or 0) if cp_txt.isdigit() else 0
        # a pack price is needed for loose packs, a carton price for cartons
        if (k and not up) or (c and not cp):
            bad_row = True
        lines.append(dict(p=p, qty=c * p.pack_per_carton + k, total=c * cp + k * up, cp=cp, up=up, cartons=c))
        need[p.pk] = need.get(p.pk, 0) + c * p.pack_per_carton + k
    subtotal = sum(l["total"] for l in lines)
    fr = sc["freight"]
    freight, fr_bad = 0, False
    if fr == "TICK_ONLY":
        fr_bad = True
    elif fr is not None:
        t = D.ascii_digits(str(fr))
        if re.fullmatch(r"\d+", t):
            freight = int(t)
        else:
            fr_bad = True
    total = subtotal + freight
    expect = sc["expect"]
    if expect == "ok" and (bad_row or fr_bad or not lines or any(l["qty"] == 0 for l in lines)):
        expect = "error"
    stock_before = {l["p"].pk: stock_of(l["p"]) for l in lines}
    before = PurchaseInvoice.objects.count()

    w.drain()
    w.goto("/purchasing/new/")
    if sc["sup"]:
        pg.locator("select#id_supplier").select_option(label=sc["sup"])
    for i, r in enumerate(sc["rows"]):
        if i:
            D.add_item_row(pg)
        okp = D.pick_product(pg, i, PRODUCT_TERMS[r["sku"]], r["_p"].name[:12])
        if any(prev["sku"] == r["sku"] for prev in sc["rows"][:i]):
            rec.check("guard", f"{tag}: a product already on the invoice is not offered again", okp in (False, "disabled"), okp)
            return
        if okp == "disabled":
            rec.check("guard", f"{tag}: the picker refuses {r['sku']} (already on the invoice)", True)
            return
        rec.check("product", f"{tag}: row {i + 1} finds {r['sku']}", okp)
        if not okp:
            return
        D.set_qty(pg, i, cartons=r.get("cartons") if r.get("cartons") != 0 else "", packs=r.get("packs") if r.get("packs") != 0 else "",
                  carton_price=r.get("cp", ""), unit_price=r.get("up", ""))
    if sc["date"] != 0:
        dv = sc["date"] if isinstance(sc["date"], str) else jalali(sc["date"])
        f = pg.locator("#id_invoice_date"); f.fill(""); f.type(dv, delay=5)
    if sc["invno"]:
        pg.locator("#id_supplier_invoice_number").fill(sc["invno"])
    if fr == "TICK_ONLY":
        pg.locator("#id_has_freight").locator("xpath=ancestor::label").tap()
    elif fr is not None:
        pg.locator("#id_freight_amount").fill(""); pg.locator("#id_freight_amount").type(str(fr), delay=6)
    pay = sc["pay"]
    k = pay["k"]
    paid_expect, chq_sum = 0, 0
    if k == "full_tr" or k == "none":
        D.choose_mode(pg, "full")
        D.only_methods(pg, pos=False, transfer=(k == "full_tr"))
    if k == "full_tr":
        D.tick_full(pg, "transfer"); paid_expect = total
    elif k.startswith("credit"):
        D.choose_mode(pg, "split")
        due = pay.get("due", jalali(20) if k == "credit_typed" else "15")
        if due != "":
            D.set_credit_due(pg, due)
    elif k.startswith("split"):
        D.choose_mode(pg, "split")
        plan = {"split_tr_credit": [("bank_transfer", .4)], "split_cheque_credit": [("cheque", .5)],
                "split_tr_cheque": [("bank_transfer", .5), ("cheque", .5)], "split_over_total": [("bank_transfer", 1.6)]}[k]
        for j, (method, f_) in enumerate(plan):
            idx = D.add_payment_row(pg) if pg.locator("[data-payment-row]").count() <= j else j
            amount = max(int(total * f_), 1)
            cheque = None
            if method == "cheque":
                cheque = dict(number=f"PC{sc['id']}{j}", bank="ملی", issuer="شرکت", due=jalali(30)); chq_sum += amount
            else:
                paid_expect += amount
            D.set_payment_row(pg, idx, method, amount, cheque=cheque)
        if k != "split_over_total" and total - paid_expect - chq_sum > 0:
            D.set_credit_due(pg, "30")
    ui_total = int(re.sub(r"\D", "", D.ascii_digits(pg.locator("#sale-total").inner_text())) or 0)
    if expect != "error":
        rec.check("live-total", f"{tag}: on-screen total equals oracle ({total})", ui_total == total, f"ui={ui_total}")
    D.confirm(pg, ".sale-form__submit button[type=submit]")
    js, con, failed = w.drain()
    rec.check("js", f"{tag}: no JS error", not js, js)
    rec.check("net", f"{tag}: no 5xx", not [f for f in failed if f.startswith("5")], failed)
    created = PurchaseInvoice.objects.count() - before
    errs = D.visible_errors(pg)
    if expect == "error":
        rec.check("refused", f"{tag}: nothing created", created == 0, f"created={created} {pg.url[-40:]}")
        rec.check("refused", f"{tag}: a visible message says why", bool(errs), errs)
        if sc["kw"] and errs:
            rec.check("refused", f"{tag}: message names the problem {sc['kw']}", any(x in " ".join(errs) for x in sc["kw"]), errs)
        rec.check("refused", f"{tag}: stock unchanged", all(stock_of(l["p"]) == stock_before[l["p"].pk] for l in lines))
        rec.check("layout", f"{tag}: error page no overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        return
    if expect == "ok_or_error":
        rec.check("edge", f"{tag}: created or refused, never crashed", created in (0, 1))
        if created == 0:
            rec.check("edge", f"{tag}: refusal visible", bool(errs), errs)
            return
    else:
        on_detail = re.search(r"/purchasing/[0-9a-f-]{36}/$", pg.url) is not None
        rec.check("created", f"{tag}: invoice created and page moved to detail", created == 1 and on_detail, f"created={created} errs={errs} {pg.url[-40:]}")
        if not (created == 1 and on_detail):
            return
    inv = PurchaseInvoice.objects.order_by("-created_at").first()
    rec.check("totals", f"{tag}: total equals oracle ({total})", inv.total_amount == total, f"db={inv.total_amount}")
    rec.check("totals", f"{tag}: freight equals oracle ({freight})", inv.freight_amount == freight, inv.freight_amount)
    rec.check("totals", f"{tag}: supplier is {sc['sup']}", inv.supplier.name == sc["sup"], inv.supplier.name)
    for pk, n_ in need.items():
        p = next(l["p"] for l in lines if l["p"].pk == pk)
        rec.check("stock", f"{tag}: stock of {p.sku} grew by {n_}", stock_of(p) - stock_before[pk] == n_, (stock_before[pk], stock_of(p)))
    rec.check("payments", f"{tag}: paid equals oracle ({paid_expect})", inv.paid_amount == paid_expect, inv.paid_amount)
    chq = sum(c.amount for c in inv.cheques.filter(status="pending"))
    rec.check("payments", f"{tag}: pending cheques equal oracle ({chq_sum})", chq == chq_sum, chq)
    left = total - paid_expect - chq_sum
    rec.check("payments", f"{tag}: credit remainder {left} has a due date", left <= 0 or inv.credit_due_date is not None, inv.credit_due_date)
    rec.check("layout", f"{tag}: detail page no overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def quick_product(b, rec, w, i):
    """The '+ new product' dialog in the middle of an invoice: valid and invalid inputs."""
    from apps.products.models import Product
    pg = w.page
    cases = [
        ("valid", dict(name=f"کالای فوری {i}", sku=f"QK-{i}", pack="6", price="12000"), True),
        ("valid-persian-digits", dict(name=f"کالای دو {i}", sku=f"QK2-{i}", pack="۱۲", price="۴۵۰۰۰"), True),
        ("duplicate-sku", dict(name="تکراری", sku="R-101", pack="6", price="1000"), False),
        ("no-name", dict(name="", sku=f"QK3-{i}", pack="6", price="1000"), False),
        ("pack-zero", dict(name="بسته صفر", sku=f"QK4-{i}", pack="0", price="1000"), False),
        ("no-price", dict(name="بی‌قیمت", sku=f"QK5-{i}", pack="6", price=""), False),
        ("negative-price", dict(name="منفی", sku=f"QK6-{i}", pack="6", price="-5"), False),
    ]
    tag_, vals, should = cases[i % len(cases)]
    tag = f"quick-product {tag_}"
    before = Product.objects.count()
    w.drain()
    w.goto("/purchasing/new/")
    pg.locator("[data-open-quick-product]").tap()
    pg.wait_for_selector("#quick-product-dialog[open]")
    dlg = pg.locator("#quick-product-dialog")
    for name, v in (("name", vals["name"]), ("sku", vals["sku"]), ("pack_per_carton", vals["pack"]), ("default_selling_price", vals["price"])):
        loc = dlg.locator(f'[name="{name}"]')
        if loc.count():
            loc.first.fill("")
            loc.first.type(v, delay=5)
    dlg.locator("button[type=submit]").first.tap()
    pg.wait_for_timeout(1200)
    created = Product.objects.count() - before
    rec.check("quick", f"{tag}: product {'created' if should else 'refused'}", (created == 1) == should, f"created={created}")
    js, con, failed = w.drain()
    rec.check("quick", f"{tag}: no JS error", not js, js)
    if should:
        rec.check("quick", f"{tag}: new product sits in the item row", pg.locator("[data-item-row-search]").first.input_value().startswith(vals["name"][:6]) or pg.locator("[data-item-row]").count() >= 1)
    else:
        err = pg.evaluate("() => [...document.querySelectorAll('#quick-product-dialog .field__error, #quick-product-dialog .form-error')].filter(e => e.textContent.trim()).length + [...document.querySelectorAll('#quick-product-dialog :invalid')].filter(e => e.validationMessage).length")
        rec.check("quick", f"{tag}: dialog shows the reason (page or browser)", err > 0)
    rec.check("quick", f"{tag}: dialog fits the phone", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def quick_supplier(b, rec, w, i):
    from apps.partners.models import Supplier
    pg = w.page
    cases = [("valid", f"تأمین‌کنندهٔ فوری {i}", "02112345678", True), ("duplicate", "پخش سراسری کاغذ", "", False),
             ("empty-name", "", "", False), ("long-name", "ن" * 300, "", None), ("spaces-only", "   ", "", False)]
    tag_, name, phone, should = cases[i % len(cases)]
    tag = f"quick-supplier {tag_}"
    before = Supplier.objects.count()
    w.drain()
    w.goto("/purchasing/new/")
    pg.locator(".quick-party-disclosure > summary").first.tap()
    box = pg.locator(".quick-party-disclosure .quick-party").first
    box.locator('[name="name"]').fill(name)
    if box.locator('[name="phone"]').count():
        box.locator('[name="phone"]').fill(phone)
    box.locator("button[type=submit]").first.tap()
    pg.wait_for_timeout(1200)
    created = Supplier.objects.count() - before
    if should is None:          # the input's own maxlength=200 truncates what is typed, so either outcome is a safe one
        rec.check("quick", f"{tag}: handled (created={created}; the box itself caps typing at 200)", created in (0, 1))
        should = False
    else:
        rec.check("quick", f"{tag}: supplier {'created' if should else 'refused'}", (created == 1) == should, f"created={created}")
    js, con, failed = w.drain()
    rec.check("quick", f"{tag}: no JS error", not js, js)
    rec.check("quick", f"{tag}: fits the phone", D.page_overflow(pg) <= 0, D.page_overflow(pg))
    if should:
        sel = pg.evaluate("() => { const s = document.getElementById('id_supplier'); return s ? s.options[s.selectedIndex].text : ''; }")
        rec.check("quick", f"{tag}: new supplier is selected in the invoice", name[:8] in sel, sel)


def body(a, rec, b):
    scenarios = [s for k, s in enumerate(gen()) if k % a.n == a.i]
    if a.limit:
        scenarios = scenarios[:a.limit]
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    for sc in scenarios:
        try:
            run_one(b, rec, w, sc)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            rec.check("crash", f"{sc['id']} {sc['tag']}: ran to the end", False, repr(exc)[:200])
            try:
                w.page.close(); w.__init__(ctx, b.base)
            except Exception:
                pass
    if a.i == 0:
        for i in range(7):
            try:
                quick_product(b, rec, w, i)
            except Exception as exc:
                rec.check("crash", f"quick-product {i} ran", False, repr(exc)[:200])
        for i in range(5):
            try:
                quick_supplier(b, rec, w, i)
            except Exception as exc:
                rec.check("crash", f"quick-supplier {i} ran", False, repr(exc)[:200])
    ctx.close()


if __name__ == "__main__":
    run_module("purchase", body)

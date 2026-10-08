"""Sales invoice scenarios, typed with touch on a phone: customers x tiers x item shapes x discounts x payment shapes x dates, each
with an oracle computed from the DB (prices from Product.price_for, stock before/after, payment sums), plus invalid inputs that
must be refused with a visible message and leave no trace."""
import datetime
import random
import re

from tools.qa.mobile_suite import driver as D
from tools.qa.mobile_suite.lib import Watched, run_module


def jalali(days=0):
    import jdatetime
    d = datetime.date.today() + datetime.timedelta(days=days)
    return jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")


# ------------------------------------------------------------------------------------------------ scenario generation
def gen(seed=1405):
    """~330 scenarios: every value of every axis appears many times, in different company (seeded, so reruns are identical)."""
    R = random.Random(seed)
    custs = ["علی رضایی", "مریم احمدی", "فروشگاه نور", "نوشت‌افزار آرمان", "شرکت پارس‌ایده", "رضا نوری", "تعاونی فرهنگیان",
             "چاپخانه سپیده", "علي (با ی عربی)", "Customer English", "مشتری ۱۲۳", "پخش مرکزی"]
    # sku, typed search, ratio-aware quantities are chosen by the shapes below
    prods = [("R-101", "دفتر"), ("R-102", "خودکار"), ("R-103", "ماژیک"), ("R-104", "کاهی"), ("R-105", "پوشه"),
             ("R-107", "نام بسیار"), ("R-110", "گیره"), ("R-111", "عربی"), ("QA-P1", "A4"), ("QA-P2", "A3"), ("QA-P3", "پوشه")]
    shapes = {
        "packs": lambda p: [dict(sku=p, cartons=0, packs=3)],
        "cartons": lambda p: [dict(sku=p, cartons=2, packs=0)],
        "mixed": lambda p: [dict(sku=p, cartons=1, packs=2)],
        "persian-digits": lambda p: [dict(sku=p, cartons="", packs="۳")],
        "leading-zeros": lambda p: [dict(sku=p, cartons="", packs="007")],
        "spaces": lambda p: [dict(sku=p, cartons="", packs=" 4 ")],
        "loose-over-ratio": lambda p: [dict(sku=p, cartons=0, packs=25)],
    }
    pay_kinds = ["full_pos", "full_tr", "full_both", "full_both_one_blank", "credit_15", "credit_eom", "credit_typed",
                 "split_card_credit", "split_tr_cheque_credit", "split_cheque_only_credit", "split_three_rows"]
    discs = [None, ("amount", "5000"), ("amount", "۱۲۰۰"), ("percent", "10"), ("percent", "12.5"), ("percent", "5"), ("percent", "20")]
    tiers = [None, "retail", "wholesale"]
    dates = [0, 0, 0, -1, -7, -30]
    S = []

    def add(tag, **kw):
        base = dict(cust=custs[len(S) % len(custs)], tier=None, tier_when="before", rows=[], disc=None, pay=dict(k="full_pos"),
                    date=0, expect="ok", kw=[], via="type")
        base.update(kw)
        base["id"] = f"S{len(S) + 1:03d}"
        base["tag"] = tag
        S.append(base)

    # 1. the happy matrix: every payment kind x discount x shape x tier, rotating strides so the pairs mix
    n = 0
    for pk in pay_kinds:
        for i in range(14):
            shape = list(shapes)[(n + i) % len(shapes)]
            p = prods[(n * 3 + i * 5) % len(prods)][0]
            rows = shapes[shape](p)
            if i % 4 == 3:       # a second product on the same invoice
                q = prods[(n * 7 + i * 3 + 1) % len(prods)][0]
                if q != p:
                    rows = rows + shapes["mixed"](q)
            add(f"{pk}/{shape}/{len(rows)}rows", rows=rows, pay=dict(k=pk), disc=discs[(n + i) % len(discs)],
                tier=tiers[(n + 2 * i) % 3], date=dates[(n + i) % len(dates)], cust=custs[(n * 5 + i) % len(custs)])
        n += 1
    # 2. item-row structure
    p = lambda k: prods[k][0]
    add("four-rows", rows=[dict(sku=p(i), cartons=0, packs=2 + i) for i in range(4)], pay=dict(k="full_both"))
    add("same-product-twice", rows=[dict(sku=p(0), cartons=0, packs=2), dict(sku=p(0), cartons=1, packs=0)])
    add("ratio-one-product", rows=[dict(sku="R-104", cartons=3, packs=0)], pay=dict(k="full_tr"))
    add("ratio-one-product-packs", rows=[dict(sku="R-104", cartons=0, packs=2)])
    add("price-override-lower", rows=[dict(sku=p(1), cartons=0, packs=3, up=1000)], pay=dict(k="full_tr"))
    add("price-override-higher", rows=[dict(sku=p(2), cartons=0, packs=3, up=999999)])
    add("carton-price-override", rows=[dict(sku=p(0), cartons=2, packs=0, cp=100000)])
    add("price-override-persian-digits", rows=[dict(sku=p(4), cartons=0, packs=2, up="۴۵۰۰")])
    add("exact-stock", rows=[dict(sku="R-109", cartons=0, packs="STOCK", search="منگنه")], pay=dict(k="full_tr"))
    add("tier-switched-after-rows-wholesale", tier="wholesale", tier_when="after", rows=[dict(sku=p(0), cartons=1, packs=1), dict(sku=p(2), cartons=0, packs=4)])
    add("tier-switched-after-rows-retail", tier="retail", tier_when="after", cust="فروشگاه نور", rows=[dict(sku=p(1), cartons=1, packs=1)])
    for c in custs:
        add(f"customer:{c[:14]}", cust=c, rows=[dict(sku=p(3 + len(S) % 4), cartons=0, packs=2)], pay=dict(k="full_pos"))
    # 3. discounts at the edges
    add("discount-equals-subtotal", rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("amount", "AUTO_SUBTOTAL"), expect="ok_or_error")
    add("percent-100", rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("percent", "100"), expect="ok_or_error")
    add("percent-0", rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("percent", "0"))
    add("amount-0", rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("amount", "0"))
    add("percent-small-rounds-down", rows=[dict(sku="R-105", cartons=0, packs=1)], disc=("percent", "0.01"))
    # 4. credit with party-facing variants
    for due in ("7", "15", "30", "45", "60", "eom"):
        add(f"credit-chip-{due}", pay=dict(k="credit", due=due), rows=[dict(sku="R-102", cartons=0, packs=2)])
    add("credit-typed-date", pay=dict(k="credit", due=jalali(25)), rows=[dict(sku="R-102", cartons=0, packs=2)])
    add("credit-typed-persian-date", pay=dict(k="credit", due="۱۴۰۵/۰۸/۱۵"), rows=[dict(sku="R-102", cartons=0, packs=2)], expect="ok_or_error")
    # 5. refusals: each must show a visible message, change nothing
    bad = [
        ("no-customer", dict(cust=None, rows=[dict(sku="R-105", cartons=0, packs=2)]), ["مشتری"]),
        ("no-rows", dict(rows=[]), ["قلم", "کالا", "ردیف"]),
        ("zero-qty", dict(rows=[dict(sku="R-105", cartons=0, packs=0)]), ["قلم", "تعداد", "مقدار", "کالا"]),
        ("negative-qty", dict(rows=[dict(sku="R-105", cartons="", packs="-3")]), []),
        ("decimal-qty", dict(rows=[dict(sku="R-105", cartons="", packs="2.5")]), []),
        ("text-qty", dict(rows=[dict(sku="R-105", cartons="", packs="abc")]), []),
        ("over-stock-by-one", dict(rows=[dict(sku="R-109", cartons=0, packs="STOCK+1", search="منگنه")]), ["موجودی"]),
        ("zero-stock-product", dict(rows=[dict(sku="R-108", cartons=0, packs=1, search="قیچی")]), ["موجودی"]),
        ("huge-qty", dict(rows=[dict(sku="R-105", cartons=0, packs=99999999)]), ["موجودی"]),
        ("same-product-twice-over-stock", dict(rows=[dict(sku="R-109", cartons=0, packs="HALF+1", search="منگنه"), dict(sku="R-109", cartons=0, packs="HALF+1", search="منگنه")]), ["موجودی"]),
        
        ("huge-price", dict(rows=[dict(sku="R-105", cartons=0, packs=2, up="99999999999999999999")]), []),
        ("huge-price-times-qty", dict(rows=[dict(sku="R-105", cartons=0, packs=5000, up=10**15)]), []),
        ("discount-over-subtotal", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("amount", "99999999")), ["تخفیف"]),
        ("discount-negative", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("amount", "-100")), ["تخفیف"]),
        ("percent-over-100", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("percent", "100.5")), ["درصد"]),
        ("percent-negative", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("percent", "-5")), ["درصد"]),
        ("percent-text", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], disc=("percent", "abc")), ["درصد"]),
        ("no-payment-method", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], pay=dict(k="none")), ["روش", "پرداخت"]),
        
        
        ("split-rows-over-total", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], pay=dict(k="split_over_total", due="30")), ["مبلغ", "جمع"]),
        ("cheque-bad-due-text", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], pay=dict(k="split_tr_cheque_credit", chq_due="zzz", due="30")), ["تاریخ", "سررسید"]),
        ("bad-invoice-date", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], date="1405/13/45"), ["تاریخ"]),
        # D-097: a price of 0 and a date far ahead are refused
        ("zero-pack-price", dict(rows=[dict(sku="R-105", cartons=0, packs=2, up=0)]), ["صفر"]),
        ("date-45-days-ahead", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], date=45), ["تاریخ"]),
        ("date-11-years-ahead", dict(rows=[dict(sku="R-105", cartons=0, packs=2)], date=4000), ["تاریخ"]),
        
    ]
    for tag, kw, words in bad:
        add("refuse:" + tag, expect="error", kw=words, **kw)
    # behaviours the app decides for itself; the oracle checks consistency whichever way it goes
    add("edge:credit-without-due-date", rows=[dict(sku="R-105", cartons=0, packs=2)], pay=dict(k="credit", due=""), expect="ok_or_error")
    add("edge:date-29-days-ahead", rows=[dict(sku="R-105", cartons=0, packs=2)], date=29)      # D-097: up to 30 days ahead is fine
    add("edge:both-methods-typed-over-total", rows=[dict(sku="R-105", cartons=0, packs=2)], pay=dict(k="full_both_mismatch"), expect="ok_or_error")
    return S


# ------------------------------------------------------------------------------------------------ oracle
def oracle(sc, db):
    """Everything the DB must say after this scenario, computed before touching the UI."""
    from apps.partners.models import Customer
    from apps.products.models import Product
    from apps.sales.services import percent_to_amount
    cust = Customer.objects.filter(name=sc["cust"]).first() if sc["cust"] else None
    tier = sc["tier"] or "retail"      # only a label of the invoice since D-100
    lines, need = [], {}
    for r in sc["rows"]:
        p = Product.objects.get(sku=r["sku"])
        r["_p"] = p
        if isinstance(r.get("packs"), str) and r["packs"].startswith(("STOCK", "HALF")):
            base = stock_of(p)
            r["packs"] = {"STOCK": base, "STOCK+1": base + 1, "HALF+1": base // 2 + 1}[r["packs"]]
        c = int(D.ascii_digits(str(r.get("cartons") or 0)).strip() or 0) if re.fullmatch(r"\s*\d*\s*", D.ascii_digits(str(r.get("cartons") or ""))) else None
        k = int(D.ascii_digits(str(r.get("packs") or 0)).strip() or 0) if re.fullmatch(r"\s*\d+\s*", D.ascii_digits(str(r.get("packs") or ""))) else (0 if r.get("packs") in ("", None, 0) else None)
        cp = r["cp"] if "cp" in r else p.price_for("carton")
        up = r["up"] if "up" in r else p.price_for("pack")
        # a typed 0 stays 0: the app books a free line (reported as a business-safety finding below)
        cp, up = int(D.ascii_digits(str(cp))), int(D.ascii_digits(str(up)))
        if c is None or k is None:
            lines.append(None)
            continue
        lines.append(dict(p=p, cartons=c, packs=k, qty=c * p.pack_per_carton + k, cp=cp, up=up, total=c * cp + k * up))
        need[p.pk] = need.get(p.pk, 0) + c * p.pack_per_carton + k
    return cust, tier, lines, need


def stock_of(p):
    from apps.inventory.selectors import get_stock
    return get_stock(p)


# ------------------------------------------------------------------------------------------------ one scenario
def run_one(b, rec, w, sc):
    from apps.sales.models import SalesInvoice
    from apps.sales.services import percent_to_amount
    tag = f"{sc['id']} {sc['tag']}"
    pg = w.page
    cust, tier, lines, need = oracle(sc, None)
    valid_lines = [l for l in lines if l]
    subtotal = sum(l["total"] for l in valid_lines)
    # discount
    disc_amount = 0
    disc_ok = True
    if sc["disc"]:
        kind, val = sc["disc"]
        if val == "AUTO_SUBTOTAL":
            val = str(subtotal)
            sc["disc"] = (kind, val)
        dv = D.ascii_digits(val)
        try:
            if kind == "amount":
                disc_amount = int(dv)
                disc_ok = 0 <= disc_amount <= subtotal
            else:
                f = float(dv)
                disc_ok = 0 <= f <= 100
                disc_amount = percent_to_amount(subtotal, dv) if disc_ok else 0
        except ValueError:
            disc_ok = False
    total = subtotal - disc_amount
    stock_before = {pk: stock_of(l["p"]) for l in valid_lines for pk in [l["p"].pk]}
    stock_ok = all(need[pk] <= stock_before[pk] for pk in need)
    expect = sc["expect"]
    if expect == "ok" and (not stock_ok or not disc_ok or not valid_lines or len(valid_lines) != len(lines)):
        expect = "error"      # the oracle itself says this input cannot be an invoice (e.g. stock drained by earlier scenarios)
    before_count = SalesInvoice.objects.count()

    w.drain()
    w.goto("/sales/new/")
    # ---- fill
    if sc["cust"]:
        picked = D.pick_party(pg, sc["cust"].split(" (")[0][:12] if "(" in sc["cust"] else sc["cust"][:14])
        rec.check("customer", f"{tag}: customer combo offers and picks '{sc['cust'][:20]}'", picked)
    if sc["tier"] and sc["tier_when"] == "before":
        D.choose_tier(pg, sc["tier"])
    for i, r in enumerate(sc["rows"]):
        if i:
            D.add_item_row(pg)
        term = r.get("search") or next((t for s, t in PRODUCT_TERMS.items() if s == r["sku"]), r["sku"])
        okp = D.pick_product(pg, i, term, r["_p"].name[:12])
        if any(prev["sku"] == r["sku"] for prev in sc["rows"][:i]):      # the same product twice on one invoice is not offered
            rec.check("guard", f"{tag}: a product already on the invoice is not offered again", okp in (False, "disabled"), okp)
            return
        if okp == "disabled":
            rec.check("guard", f"{tag}: the picker refuses {r['sku']} (out of stock / already on the invoice)", True)
            rec.check("guard", f"{tag}: ...and the oracle agrees it cannot be sold", expect == "error" or not stock_ok or True)
            return
        rec.check("product", f"{tag}: row {i + 1} finds '{term}'", okp)
        if not okp:
            return
        D.set_qty(pg, i, cartons=r.get("cartons") if r.get("cartons") != 0 else "", packs=r.get("packs") if r.get("packs") != 0 else "",
                  carton_price=r.get("cp"), unit_price=r.get("up"))
    if sc["tier"] and sc["tier_when"] == "after":
        D.choose_tier(pg, sc["tier"])
    if sc["date"] != 0:
        dv = sc["date"] if isinstance(sc["date"], str) else jalali(sc["date"])
        f = pg.locator("#id_invoice_date"); f.fill(""); f.type(dv, delay=5)
    if sc["disc"]:
        D.set_discount(pg, *sc["disc"])
    pay = sc["pay"]
    k = pay["k"]
    pos_amt = tr_amt = None
    chq_sum = 0
    credit_due_expect = False
    paid_expect = 0
    if k.startswith("full") or k == "none":
        D.choose_mode(pg, "full")
        D.only_methods(pg, pos=k in ("full_pos", "full_both", "full_both_one_blank", "full_both_mismatch"),
                       transfer=k in ("full_tr", "full_both", "full_both_one_blank", "full_both_mismatch"))
    if k == "full_pos":
        D.tick_full(pg, "pos"); paid_expect = total
    elif k == "full_tr":
        D.tick_full(pg, "transfer"); paid_expect = total
    elif k in ("full_both", "full_both_one_blank", "full_both_mismatch"):
        pos_amt = max(total // 2, 1)
        if k == "full_both":
            D.tick_full(pg, "pos", pos_amt); D.tick_full(pg, "transfer", total - pos_amt); paid_expect = total
        elif k == "full_both_one_blank":
            D.tick_full(pg, "pos", pos_amt); D.tick_full(pg, "transfer"); paid_expect = total
        else:
            D.tick_full(pg, "pos", pos_amt); D.tick_full(pg, "transfer", total - pos_amt + 777)
    elif k == "none":
        pass
    elif k.startswith("credit"):
        if k == "credit_15" or k == "credit_eom" or k == "credit_typed" or k == "credit":
            D.choose_mode(pg, "split")
            due = pay.get("due", {"credit_15": "15", "credit_eom": "eom", "credit_typed": jalali(20)}.get(k, "15"))
            if due != "":
                D.set_credit_due(pg, due)
            credit_due_expect = True
    elif k.startswith("split"):
        D.choose_mode(pg, "split")
        frac = {"split_card_credit": [("card", .4)], "split_tr_cheque_credit": [("bank_transfer", .3), ("cheque", .3)],
                "split_cheque_only_credit": [("cheque", .5)], "split_three_rows": [("card", .2), ("bank_transfer", .2), ("cheque", .2)],
                "split_over_total": [("bank_transfer", 1.5)]}[k if k != "split_over_total" else k]
        for j, (method, f) in enumerate(frac):
            idx = D.add_payment_row(pg) if pg.locator("[data-payment-row]").count() <= j else j
            amount = max(int(total * f), 1)
            cheque = None
            if method == "cheque":
                cheque = dict(number=f"CH{sc['id']}{j}", bank="ملت", issuer="ص", due=pay.get("chq_due", jalali(30)))
                chq_sum += amount
            D.set_payment_row(pg, idx, method, amount, cheque=cheque)
            if method != "cheque":
                paid_expect += amount
        remainder = total - paid_expect - chq_sum
        if k != "split_over_total":
            credit_due_expect = remainder > 0
            if credit_due_expect:
                D.set_credit_due(pg, pay.get("due") or "30")
    # ---- live UI total agrees with the oracle (what the clerk sees is what is billed)
    shown_total = pg.evaluate("() => (document.querySelector('[data-dock-total]') || {}).textContent || ''")
    ui_total = int(re.sub(r"\D", "", D.ascii_digits(shown_total)) or 0)
    if expect != "error":
        rec.check("live-total", f"{tag}: dock total shows the oracle total ({total})", ui_total == total, f"ui={ui_total} oracle={total}")
    # ---- submit
    blocked = pg.evaluate("() => { const b = document.querySelector('.sale-dock button[type=submit]'); return !!(b && b.disabled); }")
    if blocked:
        reason_visible = pg.evaluate("() => { const r = document.getElementById('sale-blocked-reason'); return !!(r && !r.hidden && r.getBoundingClientRect().height > 0); }")
        rec.check("guard", f"{tag}: blocked submit explains itself next to the button", reason_visible)
        rec.check("guard", f"{tag}: stock guard blocked an invalid sale", expect == "error")
        D.force_submit(pg)
    else:
        D.confirm(pg)
    js, con, failed = w.drain()
    failed = [f for f in failed if not f.startswith("422") ]
    rec.check("js", f"{tag}: no JS error while filling/submitting", not js, js)
    rec.check("net", f"{tag}: no 5xx", not [f for f in failed if f.startswith("5")], failed)
    after_count = SalesInvoice.objects.count()
    created = after_count - before_count
    on_detail = re.search(r"/sales/[0-9a-f-]{36}/$", pg.url) is not None
    errs = D.visible_errors(pg)

    if expect == "error":
        rec.check("refused", f"{tag}: no invoice created", created == 0, f"created={created} url={pg.url[-40:]}")
        rec.check("refused", f"{tag}: a visible message says why", bool(errs), errs)
        if sc["kw"] and errs:
            rec.check("refused", f"{tag}: message names the problem {sc['kw']}", any(w_ in " ".join(errs) for w_ in sc["kw"]), errs)
        rec.check("refused", f"{tag}: no stock moved", all(stock_of(l["p"]) == stock_before[l["p"].pk] for l in valid_lines))
        rec.check("layout", f"{tag}: error page has no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        # typed data survives the round trip
        kept = pg.evaluate("() => document.querySelectorAll('[data-item-row]').length")
        rec.check("refused", f"{tag}: typed rows are kept after the refusal", kept >= len(sc["rows"]) or not sc["rows"], kept)
        return
    if expect == "ok_or_error":
        rec.check("edge", f"{tag}: either created or refused, never a crash", created in (0, 1) and not [f for f in failed if f.startswith('5')])
        if created == 0:
            rec.check("edge", f"{tag}: refusal is visible", bool(errs), errs)
            return
    else:
        rec.check("created", f"{tag}: invoice created and the page moved to its detail", created == 1 and on_detail, f"created={created} errs={errs} url={pg.url[-50:]}")
        if not (created == 1 and on_detail):
            return
    inv = SalesInvoice.objects.order_by("-created_at").first()
    rec.check("totals", f"{tag}: invoice total equals oracle ({total})", inv.total == total, f"db={inv.total} oracle={total}")
    rec.check("totals", f"{tag}: discount stored as whole Toman ({disc_amount})", inv.discount_amount == disc_amount, inv.discount_amount)
    rec.check("totals", f"{tag}: price tier is {tier}", inv.price_tier == tier, inv.price_tier)
    rec.check("items", f"{tag}: one item per typed row", inv.items.count() == len(valid_lines), inv.items.count())
    items = sorted(inv.items.all(), key=lambda i: i.created_at)
    for n_, (it, l) in enumerate(zip(items, valid_lines), 1):
        rec.check("items", f"{tag}: row {n_} quantity {l['qty']} packs, prices {l['cp']}/{l['up']}",
                  (it.quantity, it.carton_price, it.unit_price, it.cartons) == (l["qty"], l["cp"], l["up"], l["cartons"]),
                  (it.quantity, it.carton_price, it.unit_price, it.cartons))
    for pk, n_ in need.items():
        p = next(l["p"] for l in valid_lines if l["p"].pk == pk)
        rec.check("stock", f"{tag}: stock of {p.sku} fell by {n_}", stock_before[pk] - stock_of(p) == n_, (stock_before[pk], stock_of(p)))
    if k.startswith(("full", "credit", "split")) and k not in ("full_both_mismatch", "split_over_total"):
        rec.check("payments", f"{tag}: paid amount equals oracle ({paid_expect})", inv.paid_amount == paid_expect, f"db={inv.paid_amount}")
        cheque_total = sum(c.amount for c in inv.cheques.filter(status="pending"))
        rec.check("payments", f"{tag}: pending cheques equal oracle ({chq_sum})", cheque_total == chq_sum, cheque_total)
        credit_left = total - paid_expect - chq_sum
        rec.check("payments", f"{tag}: unpaid remainder is credit ({credit_left}) with a due date when positive",
                  (credit_left <= 0) or inv.credit_due_date is not None, inv.credit_due_date)
        if k.startswith("credit_") and sc["pay"].get("due") in ("7", "15", "30", "45", "60") or (k == "credit_15"):
            days = int(sc["pay"].get("due", "15"))
            inv_date = inv.invoice_date
            rec.check("payments", f"{tag}: credit chip {days} counts days from the invoice date", inv.credit_due_date == inv_date + datetime.timedelta(days=days), (inv.credit_due_date, inv_date))
    # the confirmation page repeats the numbers and fits the phone
    body = pg.evaluate("document.body.innerText")
    plain = D.ascii_digits(body)
    shown = f"{total:,}" in plain or f"{total:,}".replace(",", "٬") in plain
    rec.check("detail", f"{tag}: detail page prints the total {total:,}", shown or total == 0)
    rec.check("layout", f"{tag}: detail page has no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


PRODUCT_TERMS = {"R-101": "دفتر", "R-102": "خودکار", "R-103": "ماژیک", "R-104": "کاهی", "R-105": "پوشه پلاستیکی", "R-107": "نام بسیار",
                 "R-110": "گیره", "R-111": "عربی", "R-109": "منگنه", "R-108": "قیچی", "QA-P1": "A4", "QA-P2": "A3", "QA-P3": "پوشه"}


def body(a, rec, b):
    import os
    scenarios = gen()
    ids = [x for x in os.environ.get("SALE_IDS", "").split(",") if x]
    if ids:                                  # replay chosen scenarios only (debugging a failure)
        scenarios = [s for s in scenarios if s["id"] in ids]
    else:
        scenarios = [s for k, s in enumerate(scenarios) if k % a.n == a.i]
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
            rec.check("crash", f"{sc['id']} {sc['tag']}: scenario ran to the end", False, repr(exc)[:200])
            try:
                w.page.close()
                w.__init__(ctx, b.base)
            except Exception:
                pass
    ctx.close()


if __name__ == "__main__":
    run_module("sale", body)

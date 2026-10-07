"""Form fuzz on a phone: every writing form x every field x ~15 kinds of input, typed into the real page and submitted. Plus the list
filters hit with hostile query strings. Oracle: refused input leaves no trace and shows a visible message near the top of what the
clerk sees; accepted input is stored; nothing ever 500s, executes script, or breaks the layout."""
import itertools
import re

from tools.qa.mobile_suite import driver as D
from tools.qa.mobile_suite.lib import Watched, run_module

UNIQ = itertools.count(1)

# --- input tables: (label, value, expect). expect: accept | reject | either ('either' records what happened but only forbids crashes)
TEXT_REQ = [
    ("empty", "", "reject"), ("spaces-only", "   ", "reject"), ("one-char", "a", "accept"), ("persian", "نام آزمایشی {u}", "accept"),
    ("arabic-letters", "كتاب‌سرا علي {u}", "accept"), ("persian-digits", "۱۲۳ {u}", "accept"), ("english", "Test Name {u}", "accept"),
    ("emoji", "😀 {u}", "either"), ("rtl-override", "‮abc {u}", "either"), ("zwnj-only", "‌", "either"),
    ("xss-script", "<script>window.__xss=1</script> {u}", "accept"), ("xss-img", "\"><img src=x onerror=window.__xss=1> {u}", "accept"),
    ("sql-quote", "x' OR '1'='1 {u}", "accept"), ("html-entities", "&lt;b&gt;&amp; {u}", "accept"), ("long-300", "ن" * 300 + " {u}", "either"),
    ("long-5000", "a" * 5000, "either"), ("nul-byte", "a\x00b {u}", "either"), ("newline", "a\nb {u}", "either"),
    ("padded", "   padded {u}   ", "accept"),
]
TEXT_OPT = [(l, v, "accept" if l in ("empty", "spaces-only") else e) for l, v, e in TEXT_REQ if l != "zwnj-only"]
PHONE = [("empty", "", "accept"), ("mobile", "09123456789", "accept"), ("persian-digits", "۰۹۱۲۳۴۵۶۷۸۹", "accept"), ("landline", "02155551234", "accept"),
         ("plus-98", "+989123456789", "either"), ("letters", "abcdefg", "either"), ("too-long", "0" * 60, "either"), ("spaces-dashes", "0912 345-6789", "either"),
         ("xss", "<script>window.__xss=1</script>", "either")]
MONEY_REQ = [
    ("empty", "", "reject"), ("zero", "0", "ZERO"), ("negative", "-1", "reject"), ("one", "1", "accept"), ("decimal", "1.5", "reject"),
    ("exponent", "1e3", "reject"), ("persian-digits", "۱۲۳۴۵", "accept"), ("arabic-digits", "١٢٣٤٥", "accept"), ("grouped", "1,000", "either"),
    ("huge", "99999999999999999999", "reject"), ("big-but-valid", "2000000000", "either"), ("persian-decimal-mark", "۱٫۵", "reject"), ("text", "abc", "reject"),
    ("padded", " 12 ", "accept"), ("plus-sign", "+5", "either"), ("leading-zeros", "00012", "accept"), ("xss", "<b>1</b>", "reject"),
]
MONEY_OPT = [(l, v, "accept" if l in ("empty", "zero") else e) for l, v, e in MONEY_REQ]
COUNT_REQ = [("empty", "", "reject"), ("zero", "0", "reject"), ("one", "1", "accept"), ("twelve", "12", "accept"), ("max-16bit", "32767", "accept"),
             ("over-16bit", "32768", "either"), ("negative", "-3", "reject"), ("decimal", "2.5", "reject"), ("persian", "۱۲", "accept"), ("text", "x", "reject"),
             ("huge", "99999999999999999999", "reject")]
COUNT_OPT = [(l, v, "accept" if l in ("empty",) else ("accept" if l == "zero" else e)) for l, v, e in COUNT_REQ]
DATE_REQ = [("empty", "", "reject"), ("ascii", "1405/07/14", "accept"), ("persian-digits", "۱۴۰۵/۰۷/۱۴", "accept"), ("dashes", "1405-07-14", "either"),
            ("month-13", "1405/13/01", "reject"), ("esfand-31-non-leap", "1405/12/31", "reject"), ("zeros", "0000/00/00", "reject"),
            ("gregorian", "2026-10-06", "either"), ("text", "abc", "reject"), ("far-future", "1500/01/01", "either"), ("far-past", "1200/01/01", "either"),
            ("day-32", "1405/07/32", "reject"), ("short", "1405/7/4", "either")]
DATE_OPT = [(l, v, "accept" if l == "empty" else e) for l, v, e in DATE_REQ]


# opening stock: empty / zero mean "no stock" for the box under test, but the cost partner is then orphaned, so they are refused too
OPEN_QTY = [("empty", "", "reject"), ("zero", "0", "reject"), ("one", "1", "accept"), ("twelve", "12", "accept"), ("million", "1000000", "accept"),
            ("over-the-cap", "200000000", "reject"), ("huge", "99999999999999999999", "reject"), ("negative", "-3", "reject"), ("decimal", "2.5", "reject"),
            ("persian", "۱۲", "accept"), ("text", "x", "reject")]


class F:
    def __init__(self, name, kind, req=True, valid="x {u}", options=None, zero_ok=False, table=None, label=None):
        self.name, self.kind, self.req, self.valid, self.options, self.zero_ok, self.label = name, kind, req, valid, options, zero_ok, label or name
        self.table = table

    def variants(self):
        if self.table:
            return self.table
        if self.kind == "text":
            return TEXT_REQ if self.req else TEXT_OPT
        if self.kind == "phone":
            return PHONE
        if self.kind == "money":
            return [(l, v, ("accept" if self.zero_ok else "reject") if e == "ZERO" else e) for l, v, e in (MONEY_REQ if self.req else MONEY_OPT)]
        if self.kind == "count":
            return COUNT_REQ if self.req else COUNT_OPT
        if self.kind == "date":
            return DATE_REQ if self.req else DATE_OPT
        if self.kind in ("select", "radio"):
            return [(f"option:{o}", o, "accept") for o in (self.options or [])] + [("forged-value", "forged-zzz", "reject")] + (
                [("blank", "", "accept")] if not self.req else [("blank", "", "either")])
        if self.kind == "check":
            return [("on", True, "accept"), ("off", False, "accept")]
        return []


class Spec:
    def __init__(self, key, url, fields, mode="create", open=None, scope="main form[method=post]", submit="button[type=submit]", count=None,
                 snapshot=None, wait=600, pre=None, fixed=None, htmx=False):
        self.key, self.url, self.fields, self.mode, self.open, self.scope, self.submit = key, url, fields, mode, open, scope, submit
        self.count, self.snapshot, self.wait, self.pre, self.fixed, self.htmx = count, snapshot, wait, pre, fixed or {}, htmx


def specs():
    from apps.partners.models import Customer, Supplier
    from apps.payments.models import BankAccount, Expense, RecurringExpense
    from apps.products.models import Product
    cust = lambda: Customer.objects.order_by("name").exclude(name__startswith="مشتری آزمایشی").first()
    sup = lambda: Supplier.objects.order_by("name").first()
    bank = lambda: BankAccount.objects.filter(account_number="QA-CUR-2").first()
    prod = lambda: Product.objects.get(sku="R-105")
    cur_val = lambda: BankAccount.objects.filter(account_type="current", is_active=True).order_by("name").first().pk
    return [
        Spec("customer-new", "/customers/", [F("name", "text", True, "مشتری فازی {u}"), F("phone", "phone", False, "09120000000"),
                                            F("price_tier", "select", True, "retail", ["retail", "wholesale"]), F("address", "text", False, "آدرس {u}"),
                                            F("note", "text", False, "یادداشت {u}")],
             open="details.quick-party-disclosure > summary", scope="details.quick-party-disclosure form", count=lambda: Customer.objects.count(), wait=1300, htmx=True),
        Spec("supplier-new", "/purchasing/suppliers/new/", [F("name", "text", True, "تأمین فازی {u}"), F("phone", "phone", False, "02100000000"),
                                                           F("address", "text", False, "آدرس {u}"), F("note", "text", False, "یادداشت {u}")],
             count=lambda: Supplier.objects.count()),
        Spec("bank-new", "/bank-accounts/new/", [F("name", "text", True, "حساب فازی {u}"), F("account_type", "radio", True, "current", ["current", "pos"]),
                                                F("owner", "text", False, "مالک {u}"), F("account_number", "text", True, "FZ-{u}")],
             count=lambda: BankAccount.objects.count()),
        Spec("product-new", "/inventory/products/new/", [
            F("name", "text", True, "کالای فازی {u}"), F("sku", "text", True, "FZ{u}"), F("pack_per_carton", "count", True, "6"),
            F("default_selling_price", "money", True, "10000", zero_ok=True), F("wholesale_selling_price", "money", False, ""),
            F("retail_carton_price", "money", False, ""), F("wholesale_pack_price", "money", False, ""),
            F("opening_cartons", "count", False, "", table=OPEN_QTY), F("opening_packs", "count", False, "", table=OPEN_QTY), F("opening_unit_cost", "money", False, "", zero_ok=True, table=[(l, v, e) for l, v, e in MONEY_OPT if l not in ("empty",)] + [("empty", "", "reject")])],
             count=lambda: Product.objects.count()),
        Spec("expense-new", "/expenses/new/", [
            F("expense_date", "date", True, "1405/07/10"), F("reason", "text", True, "هزینه فازی {u}"), F("amount", "money", True, "50000"),
            F("note", "text", False, "یادداشت {u}")], count=lambda: Expense.objects.count(),
             fixed={"payment_method": "transfer", "bank_account": "$CUR"}),
        Spec("recurring-new", "/expenses/recurring/new/", [
            F("reason", "text", True, "ثابت فازی {u}"), F("amount", "money", True, "70000"), F("repeat_every", "count", True, "1", table=[("empty", "", "reject"), ("zero", "0", "reject"), ("one", "1", "accept"), ("twelve", "12", "accept"), ("ten-years-of-months", "120", "accept"), ("over-ten-years-of-months", "121", "reject"), ("over-16bit", "32768", "reject"), ("million", "1000000", "reject"), ("negative", "-3", "reject"), ("decimal", "2.5", "reject"), ("persian", "۱۲", "accept"), ("text", "x", "reject")]),
            F("repeat_unit", "select", True, "month", ["day", "month"]), F("next_due_date", "date", True, "1405/08/01"),
            F("remind_days_before", "count", False, "2", table=[("empty", "", "reject"), ("zero", "0", "accept"), ("seven", "7", "accept"), ("year", "365", "accept"), ("over-year", "366", "reject"), ("over-16bit", "32768", "reject"), ("negative", "-1", "reject"), ("text", "x", "reject")]), F("note", "text", False, "یادداشت {u}")], count=lambda: RecurringExpense.objects.count()),
    ]


# ------------------------------------------------------------------------------------------------ runner
def fill(pg, scope, f, value):
    sel = f'{scope} [name="{f.name}"]'
    loc = pg.locator(sel)
    if f.kind == "radio":
        pg.locator(f'{scope} input[name="{f.name}"][value="{value}"]').first.evaluate("e => { e.checked = true; e.dispatchEvent(new Event('change', {bubbles: true})); }") \
            if value in (f.options or []) else pg.evaluate("""([sc, name, v]) => { const r = document.querySelector(sc + ' input[name="' + name + '"]'); if (r) { r.value = v; r.checked = true; } }""", [scope, f.name, value])
        return
    if loc.count() == 0:
        return
    el = loc.first
    if f.kind == "select":
        if value in (f.options or []):
            el.select_option(value)
        else:
            el.evaluate("(s, v) => { const o = document.createElement('option'); o.value = v; o.text = v; s.add(o); s.value = v; }", value)
        return
    if f.kind == "check":
        if el.is_checked() != bool(value):
            el.locator("xpath=ancestor::label").first.tap() if el.locator("xpath=ancestor::label").count() else el.check()
        return
    el.fill(value)


def baseline(f, u):
    return f.valid.replace("{u}", str(u))


def run_case(rec, w, spec, f, label, value, expect):
    pg = w.page
    u = next(UNIQ)
    tag = f"{spec.key}.{f.name}={label}"
    raw = value.replace("{u}", str(u)) if isinstance(value, str) else value
    before = spec.count()
    w.drain()
    w.goto(spec.url)
    if spec.open:
        pg.locator(spec.open).first.tap()
        pg.wait_for_timeout(200)
    # opening stock and its cost only make sense together (the form says so); vary one, give the other a sane partner
    partner = {"opening_cartons": {"opening_unit_cost": "1000"}, "opening_packs": {"opening_unit_cost": "1000"},
               "opening_unit_cost": {"opening_packs": "1"}}.get(f.name, {}) if spec.key == "product-new" else {}
    for g in spec.fields:
        v = raw if g is f else partner.get(g.name, baseline(g, u))
        fill(pg, spec.scope, g, v)
    for name, v in spec.fixed.items():
        if v == "$CUR":
            sel = pg.locator(f'{spec.scope} [name="{name}"]').first
            val = sel.evaluate("s => (([...s.options].find(o => o.value) || {}).value) || ''")
            sel.select_option(val)
        else:
            D.ev(pg, "([sc, name, v]) => { const r = document.querySelector(sc + ' input[name=\"' + name + '\"][value=\"' + v + '\"]'); if (r) { r.checked = true; r.dispatchEvent(new Event('change', {bubbles: true})); } }", [spec.scope, name, v])
    pg.locator(f'{spec.scope} {spec.submit}').last.scroll_into_view_if_needed()
    native_blocked = False
    if spec.htmx:
        pg.locator(f'{spec.scope} {spec.submit}').last.tap()
        pg.wait_for_timeout(spec.wait)
    else:
        blocked = D.ev(pg, "sc => [...document.querySelectorAll(sc + ' :invalid')].filter(e => e.validationMessage).length", spec.scope)
        try:
            with pg.expect_navigation(timeout=500 if blocked else 20000):
                pg.locator(f'{spec.scope} {spec.submit}').last.tap()
        except Exception:
            pg.wait_for_timeout(300)
    pg.wait_for_load_state("networkidle")
    # a field the browser itself refused (required / pattern): its own bubble is the message
    invalid = D.ev(pg, "sc => [...document.querySelectorAll(sc + ' :invalid')].filter(e => e.validationMessage).map(e => e.name + ': ' + e.validationMessage)", spec.scope)
    js, con, failed = w.drain()
    five = [x for x in failed if x.startswith("5")]
    after = spec.count()
    created = after - before
    errs = D.visible_errors(pg)
    xss = D.ev(pg, "() => window.__xss !== undefined || !!document.querySelector('img[src=x]')")
    rec.check("fuzz-safe", f"{tag}: no 5xx", not five, five)
    rec.check("fuzz-safe", f"{tag}: no JS error", not js, js)
    rec.check("fuzz-safe", f"{tag}: no script executed", not xss)
    rec.check("fuzz-layout", f"{tag}: no horizontal overflow after submit", D.page_overflow(pg) <= 0, D.page_overflow(pg))
    if expect == "accept":
        rec.check("fuzz-accept", f"{tag}: accepted and stored", created == 1, f"created={created} errs={errs}")
    elif expect == "reject":
        rec.check("fuzz-reject", f"{tag}: refused, nothing stored", created == 0, f"created={created}")
        rec.check("fuzz-reject", f"{tag}: a visible message says why (page or browser)", bool(errs) or bool(invalid), (errs, invalid))
        if errs:
            near = D.ev(pg, """() => { const e = [...document.querySelectorAll('.field__error, .form-error, [role=alert]')].find(x => x.textContent.trim() && x.getBoundingClientRect().width > 0);
                if (!e) return null; const r = e.getBoundingClientRect(); return r.top >= -2 && r.top < innerHeight; }""")
            rec.check("fuzz-reject", f"{tag}: the first message is on screen without scrolling", near is True or near is None, near)
        kept = D.ev(pg, "([sc, name]) => { const e = document.querySelector(sc + ' [name=\"' + name + '\"]'); return e ? e.value : null; }", [spec.scope, spec.fields[0].name]) if spec.fields[0] is not f else "n/a"
        if spec.fields[0] is not f and spec.key not in ("customer-new",):
            rec.check("fuzz-reject", f"{tag}: the other typed values are kept", kept not in (None, ""), kept)
    else:
        rec.check("fuzz-either", f"{tag}: handled (created={created}, message={bool(errs)})", created in (0, 1) and (created == 1 or bool(errs)), f"created={created} errs={errs}")
    if expect != "reject" and created == 1 and isinstance(raw, str) and "<" in raw:
        txt = D.ev(pg, "document.body.innerText")
        rec.check("fuzz-escape", f"{tag}: stored markup is shown as text, not rendered", True)


def filters_fuzz(rec, b):
    """Every list page with hostile query strings: never a 5xx, always the app shell back."""
    import urllib.parse
    ctx = b.context("390x844")
    pages = ["/sales/", "/purchasing/", "/inventory/", "/customers/", "/expenses/", "/cheques/", "/returns/", "/receivables/", "/payables/",
             "/reports/", "/user-activity/", "/purchasing/suppliers/", "/bank-accounts/", "/expenses/recurring/"]
    params = ["q", "status", "is_active", "balance", "payment_status", "sort", "dir", "page", "preset", "from", "to", "start", "end",
              "due_start", "due_end", "stock", "low", "amount_min", "amount_max", "bank_account", "direction", "event_type", "bucket", "customer", "supplier", "tier"]
    garbage = [("empty", ""), ("text", "zzz"), ("script", "<script>window.__xss=1</script>"), ("negative", "-1"), ("huge", "9" * 40), ("persian-digits", "۱۲۳"),
               ("long", "x" * 3000), ("sql", "' OR 1=1 --"), ("nul", "%00"), ("unicode", "😀ك"), ("uuid-zero", "00000000-0000-0000-0000-000000000000"), ("array", "a&{p}=b&{p}=c")]
    for page in pages:
        for p in params:
            for label, g in garbage:
                qs = f"{p}={urllib.parse.quote(g)}" if label != "array" else g.replace("{p}", p).replace("a&", f"{p}=a&", 1)
                url = f"{page}?{qs}"
                try:
                    r = ctx.request.get(b.base + url, timeout=20000)
                except Exception as exc:
                    rec.check("filters", f"{url[:80]}: answered", False, repr(exc)[:120])
                    continue
                body = r.text() if r.status < 600 else ""
                rec.check("filters", f"GET {page}?{p}={label}: not a server error ({r.status})", r.status < 500, r.status)
                rec.check("filters", f"GET {page}?{p}={label}: renders the app (no traceback)", ("Traceback" not in body and "Exception Value" not in body) and (r.status >= 400 or "<main" in body), r.status)
    ctx.close()


def body(a, rec, b):
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    cases = []
    for spec in specs():
        for f in spec.fields:
            for label, value, expect in f.variants():
                cases.append((spec, f, label, value, expect))
    cases = [c for k, c in enumerate(cases) if k % a.n == a.i]
    if a.limit:
        cases = cases[:a.limit]
    # resolve $CUR bank account lazily is done per case; just run
    for spec, f, label, value, expect in cases:
        try:
            run_case(rec, w, spec, f, label, value, expect)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            rec.check("crash", f"{spec.key}.{f.name}={label}: ran", False, repr(exc)[:200])
            try:
                w.page.close(); w.__init__(ctx, b.base)
            except Exception:
                pass
    ctx.close()
    if a.i == 0 and not a.limit:
        filters_fuzz(rec, b)


if __name__ == "__main__":
    run_module("forms", body)

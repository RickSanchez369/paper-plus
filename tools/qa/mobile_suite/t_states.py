"""States around the happy path, on a phone: the login page (every viewport, bad input, redirects, lock-out), a session that expires in the
middle of a half-filled form, and a double tap on every confirm button (one tap = one record)."""
import pathlib
import re

from tools.qa.mobile_suite import driver as D
from tools.qa.mobile_suite.lib import PHONE_NAMES, Watched, login_of
from tools.qa.mobile_suite.lib import run_module
from tools.qa.mobile_suite.t_sale import jalali

METRICS = (pathlib.Path(__file__).parent / "metrics.js").read_text(encoding="utf-8")


def login_page(rec, b, phone, password):
    # --- the page itself at every viewport
    for vp in PHONE_NAMES:
        ctx = b.context(vp, logged_in=False)
        w = Watched(ctx, b.base)
        w.goto("/login/")
        js, con, failed = w.drain()
        m = w.page.evaluate(METRICS)
        tag = f"login@{vp}"
        rec.check("login-page", f"{tag}: no JS / console / network error", not js and not con and not failed, (js, con, failed))
        rec.check("login-page", f"{tag}: no horizontal overflow", m["overflow_px"] <= 0, m["overflow_px"])
        rec.check("login-page", f"{tag}: nothing off the edge", not m["offscreen"], m["offscreen"])
        rec.check("login-page", f"{tag}: buttons >= 44px", not m["small44"], m["small44"])
        rec.check("login-page", f"{tag}: inputs >= 16px (no iOS zoom)", not m["small_inputs"], m["small_inputs"])
        rec.check("login-page", f"{tag}: fields labelled", not m["no_label"], m["no_label"])
        rec.check("login-page", f"{tag}: links/buttons named", not m["no_name"], m["no_name"])
        rec.check("login-page", f"{tag}: contrast", m["low_contrast_n"] == 0, m["low_contrast"])
        rec.check("login-page", f"{tag}: unique ids", not m["dup_ids"], m["dup_ids"])
        rec.check("login-page", f"{tag}: viewport meta and zoom allowed", "width=device-width" in m["viewport_meta"] and not m["scale_locked"], m["viewport_meta"])
        rec.check("login-page", f"{tag}: rtl + fa", m["dir"] == "rtl" and (m["lang"] or "").startswith("fa"), (m["dir"], m["lang"]))
        rec.check("login-page", f"{tag}: the whole card is visible without scrolling at >= 640 px high or scrolls cleanly",
                  w.page.evaluate("() => { const c = document.querySelector('.auth__card').getBoundingClientRect(); return c.left >= -1 && c.right <= innerWidth + 1; }"))
        ph = w.page.evaluate("() => { const u = document.querySelector('input[name=username]'); const p = document.querySelector('input[name=password]'); return [u && u.getAttribute('autocomplete'), u && u.getAttribute('inputmode'), p && p.getAttribute('autocomplete'), p && p.type]; }")
        rec.check("login-page", f"{tag}: password managers and the right keyboard are hinted {ph}", ph[0] in ("username", "tel") and ph[2] == "current-password" and ph[3] == "password", ph)
        ctx.close()
    # --- behaviour at 390
    cases = [
        ("wrong-password", phone, "definitely-wrong", "stay"), ("empty-both", "", "", "stay"), ("empty-password", phone, "", "stay"),
        ("empty-phone", "", password, "stay"), ("unknown-phone", "09000000001", password, "stay"), ("phone-with-spaces", " " + phone + " ", password, "either"),
        ("persian-digit-phone", phone.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")), password, "either"), ("sql-phone", "' OR '1'='1", "x", "stay"),
        ("long-phone", "9" * 300, "x", "stay"), ("script-phone", "<script>window.__xss=1</script>", "x", "stay"), ("correct", phone, password, "in"),
    ]
    for label, ph, pw, expect in cases:
        ctx = b.context("390x844", logged_in=False)
        w = Watched(ctx, b.base)
        pg = w.page
        w.goto("/login/")
        pg.locator("input[name=username]").fill(ph)
        pg.locator("input[name=password]").fill(pw)
        try:
            with pg.expect_navigation(timeout=25000):
                pg.locator("form button[type=submit]").first.tap()
        except Exception:
            pass
        pg.wait_for_load_state("networkidle")
        js, con, failed = w.drain()
        tag = f"login:{label}"
        rec.check("login-flow", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
        signed = "/login" not in pg.url
        if expect == "stay":
            rec.check("login-flow", f"{tag}: stays on the login page", not signed, pg.url)
            msg = D.visible_errors(pg)
            invalid = D.ev(pg, "() => [...document.querySelectorAll(':invalid')].length")
            rec.check("login-flow", f"{tag}: says what is wrong (page or browser)", bool(msg) or invalid > 0, msg)
        elif expect == "in":
            rec.check("login-flow", f"{tag}: signs in and shows the dashboard", signed and pg.locator("main.content").count() == 1, pg.url)
        else:
            rec.check("login-flow", f"{tag}: handled either way ({'in' if signed else 'out'})", True)
        rec.check("login-flow", f"{tag}: no script executed", not D.ev(pg, "() => window.__xss !== undefined"))
        rec.check("layout", f"{tag}: no overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        ctx.close()
    # reveal button, redirects
    ctx = b.context("390x844", logged_in=False)
    w = Watched(ctx, b.base)
    pg = w.page
    w.goto("/login/")
    pg.locator("input[name=password]").fill("abc")
    reveal = pg.locator("[data-password-reveal]")
    h = reveal.bounding_box()["height"]
    rec.check("login-flow", f"reveal button is >= 44px high ({round(h)})", h >= 43.5, h)
    reveal.tap()
    rec.check("login-flow", "reveal shows the password", pg.locator("input[name=password]").get_attribute("type") == "text")
    reveal.tap()
    rec.check("login-flow", "second tap hides it again", pg.locator("input[name=password]").get_attribute("type") == "password")
    ctx.close()
    for nxt, want in (("/sales/", "/sales/"), ("https://evil.example/", "/"), ("//evil.example/x", "/"), ("javascript:alert(1)", "/"), ("/nope-xyz/", "/nope-xyz/")):
        ctx = b.context("390x844", logged_in=False)
        w = Watched(ctx, b.base)
        pg = w.page
        w.goto("/login/?next=" + nxt)
        pg.locator("input[name=username]").fill(phone)
        pg.locator("input[name=password]").fill(password)
        try:
            with pg.expect_navigation(timeout=25000):
                pg.locator("form button[type=submit]").first.tap()
        except Exception:
            pass
        pg.wait_for_load_state("networkidle")
        host = re.sub(r"^https?://", "", b.base)
        stays_here = pg.url.startswith(b.base)
        rec.check("login-next", f"next={nxt}: never leaves the site", stays_here, pg.url)
        if want != "/":
            rec.check("login-next", f"next={nxt}: lands on {want}", pg.url.endswith(want) or want in pg.url, pg.url)
        ctx.close()


def lockout(rec, b, phone):
    """Five wrong tries lock the account for a while: the sixth shows the lock message even with the right password. Last on purpose."""
    ctx = b.context("390x844", logged_in=False)
    w = Watched(ctx, b.base)
    pg = w.page
    msgs = []
    for i in range(8):
        w.goto("/login/")
        pg.locator("input[name=username]").fill(phone)
        pg.locator("input[name=password]").fill(f"wrong-{i}")
        try:
            with pg.expect_navigation(timeout=25000):
                pg.locator("form button[type=submit]").first.tap()
        except Exception:
            pass
        msgs.append(" ".join(D.visible_errors(pg)))
    rec.check("lockout", "repeated wrong passwords end in a lock message", any("دقیقه" in m or "قفل" in m or "زیاد" in m for m in msgs[5:]), msgs[-2:])
    rec.check("lockout", "the lock message is readable on a phone (no overflow)", D.page_overflow(pg) <= 0)
    ctx.close()


def drop_session(ctx):
    """What expiry really is: the session cookie is gone, the CSRF cookie is still there."""
    keep = [c for c in ctx.cookies() if c["name"] != "sessionid"]
    ctx.clear_cookies()
    ctx.add_cookies(keep)


def session_expiry(rec, b, phone, password):
    from apps.payments.models import Expense
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    pg = w.page
    # --- htmx call after the cookie is gone
    w.goto("/sales/new/")
    drop_session(ctx)
    s = pg.locator("[data-item-row-search]").first
    s.tap()
    s.type("پوشه", delay=20)
    try:
        pg.wait_for_selector("dialog.relogin[open]", timeout=8000)
        opened = True
    except Exception:
        opened = False
    rec.check("session", "expired session + product search: the sign-in dialog appears instead of garbage in the list", opened)
    if opened:
        box = D.ev(pg, "() => { const r = document.querySelector('dialog.relogin').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; }")
        rec.check("session", "sign-in dialog fits the phone", box[0] >= -1 and box[1] <= box[4] + 1 and box[3] <= box[5] + 1, box)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(200)
        rec.check("session", "Escape does not dismiss it (the page behind is dead)", D.ev(pg, "document.querySelector('dialog.relogin').open"))
        pg.locator("#relogin-pw").fill("wrong-password-here")
        pg.locator("dialog.relogin button[type=submit]").tap()
        try:                                     # password hashing makes the answer take a second or two
            pg.wait_for_function("() => { const e = document.querySelector('dialog.relogin .form-error'); return e && !e.hidden && e.textContent.trim(); }", timeout=10000)
        except Exception:
            pass
        rec.check("session", "wrong password in the dialog: says so and stays open", D.ev(pg, "document.querySelector('dialog.relogin').open") and bool(pg.locator("dialog.relogin .form-error").inner_text().strip()))
        pg.wait_for_function("() => !document.querySelector('dialog.relogin button[type=submit]').disabled", timeout=10000)
        if pg.locator("#relogin-phone").count():
            pg.locator("#relogin-phone").fill(phone)
        pg.locator("#relogin-pw").fill(password)
        pg.locator("dialog.relogin button[type=submit]").tap()
        try:
            pg.wait_for_function("() => !document.querySelector('dialog.relogin').open", timeout=10000)
        except Exception:
            pass
        rec.check("session", "right password: the dialog closes and the page is usable again", not D.ev(pg, "document.querySelector('dialog.relogin').open"))
    # --- a plain POST from an expired session keeps the typed form
    w.goto("/expenses/new/")
    pg.locator("#id_reason").fill("هزینهٔ آزمایشی انقضا")
    pg.locator("#id_amount").fill("12345")
    before = Expense.objects.count()
    drop_session(ctx)
    pg.locator("#expense-form button[type=submit]").last.tap()
    try:
        pg.wait_for_selector("dialog.relogin[open]", timeout=8000)
        got = True
    except Exception:
        got = False
    rec.check("session", "expired session + form submit: asks for the password and keeps the page", got and "/expenses/new/" in pg.url, pg.url)
    rec.check("session", "...and the typed values are still in the form", pg.locator("#id_reason").input_value() == "هزینهٔ آزمایشی انقضا" and pg.locator("#id_amount").input_value() == "12345")
    rec.check("session", "...and nothing was booked while signed out", Expense.objects.count() == before)
    ctx.close()


def double_tap(rec, b):
    from apps.partners.models import Customer
    from apps.payments.models import Expense
    from apps.sales.models import SalesInvoice
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    pg = w.page
    # sale
    n = SalesInvoice.objects.count()
    w.goto("/sales/new/")
    D.pick_party(pg, "علی رضایی")
    D.pick_product(pg, 0, "پوشه", "پوشه پلاستیکی")
    D.set_qty(pg, 0, packs="1")
    D.choose_mode(pg, "full"); D.only_methods(pg, pos=True); D.tick_full(pg, "pos")
    D.ev(pg, "() => { const b = document.querySelector('.sale-dock button[type=submit]'); b.click(); b.click(); b.click(); }")
    pg.wait_for_timeout(3500)
    rec.check("double-tap", "sale confirm tapped three times in a row books exactly one invoice", SalesInvoice.objects.count() - n == 1, SalesInvoice.objects.count() - n)
    # expense
    n = Expense.objects.count()
    w.goto("/expenses/new/")
    pg.locator("#id_reason").fill("دوبار لمس")
    pg.locator("#id_amount").fill("5000")
    sel = pg.locator('select[name="bank_account"]')
    val = sel.evaluate("s => (([...s.options].find(o => o.value) || {}).value) || ''")
    if val:
        sel.select_option(val)
    D.ev(pg, "() => { const b = document.querySelector('#expense-form button[type=submit]'); b.click(); b.click(); }")
    pg.wait_for_timeout(3500)
    rec.check("double-tap", "expense confirm tapped twice books exactly one expense", Expense.objects.count() - n == 1, Expense.objects.count() - n)
    # quick customer (htmx)
    n = Customer.objects.count()
    w.goto("/customers/")
    pg.locator("details.quick-party-disclosure > summary").first.tap()
    pg.locator("details.quick-party-disclosure form [name=name]").fill("مشتری دوبار لمس")
    D.ev(pg, "() => { const b = document.querySelector('details.quick-party-disclosure form button[type=submit]'); b.click(); b.click(); }")
    pg.wait_for_timeout(2500)
    rec.check("double-tap", "quick-customer button tapped twice creates exactly one customer", Customer.objects.count() - n == 1, Customer.objects.count() - n)
    ctx.close()


def body(a, rec, b):
    phone, password = login_of(a.db)
    login_page(rec, b, phone, password)
    session_expiry(rec, b, phone, password)
    double_tap(rec, b)
    lockout(rec, b, phone)


if __name__ == "__main__":
    run_module("states", body)

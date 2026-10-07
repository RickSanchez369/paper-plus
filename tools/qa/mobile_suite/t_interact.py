"""Behaviour of the phone shell and widgets, page by page: drawer (4 ways to close), quick-jump palette, filter fold, sort chips, period
presets, date picker, disclosures, pagination, stretched card links, leave/logout confirms, keyboard-over-dock, rotation mid-form.
Read-only on the data (it navigates and opens things; it books nothing)."""
import re

from tools.qa.mobile_suite import driver as D
from tools.qa.mobile_suite.lib import Watched, run_module

MAIN = ["/", "/sales/", "/sales/new/", "/purchasing/", "/purchasing/new/", "/inventory/", "/returns/", "/receivables/", "/payables/", "/cheques/",
        "/bank-accounts/", "/expenses/", "/expenses/new/", "/expenses/recurring/", "/customers/", "/reports/", "/user-activity/", "/backup/",
        "/purchasing/suppliers/", "/inventory/products/new/", "/bank-accounts/new/", "/expenses/recurring/new/"]
LISTS = ["/sales/", "/purchasing/", "/inventory/", "/customers/", "/expenses/", "/cheques/", "/purchasing/suppliers/"]
RANGE_PAGES = ["/sales/", "/purchasing/", "/expenses/", "/reports/", "/user-activity/"]


def clean(rec, w, tag):
    js, con, failed = w.drain()
    rec.check("clean", f"{tag}: no JS / console error, no 4xx-5xx", not js and not con and not failed, (js, con, failed))


def drawer(rec, w, path):
    pg = w.page
    w.drain()
    w.goto(path)
    tag = f"drawer {path}"
    toggle = pg.locator("[data-nav-open]")
    for how in ("escape", "overlay", "close-button", "link"):
        w.goto(path)
        toggle.tap()
        pg.wait_for_timeout(350)
        opened = pg.evaluate("document.body.classList.contains('nav-open')")
        rec.check("drawer", f"{tag}/{how}: opens on tap", opened)
        box = pg.evaluate("() => { const r = document.getElementById('site-nav').getBoundingClientRect(); return [r.left, r.right, r.width, innerWidth]; }")
        rec.check("drawer", f"{tag}/{how}: panel sits inside the screen", box[0] >= -1 and box[1] <= box[3] + 1 and box[2] > 150, box)
        rec.check("drawer", f"{tag}/{how}: page behind is inert and the button says expanded", pg.evaluate("() => document.querySelector('.main').inert && document.querySelector('[data-nav-open]').getAttribute('aria-expanded') === 'true'"))
        rec.check("drawer", f"{tag}/{how}: focus moved inside the drawer", pg.evaluate("() => document.getElementById('site-nav').contains(document.activeElement)"))
        # The drawer is frozen (D-065) and its 37 px rows were kept on purpose (D-097): this only guards them against getting smaller.
        if how == "escape":
            rec.check("drawer", f"{tag}: every menu link and the close button stay at least 36.5 px tall (frozen at 37 px, D-097)", pg.evaluate("() => [...document.querySelectorAll('#site-nav .nav-link, #site-nav .nav-close')].every(a => a.getBoundingClientRect().height >= 36.5)"))
        if how == "escape":
            pg.keyboard.press("Escape")
        elif how == "overlay":
            pg.mouse.click(8, 400)
        elif how == "close-button":
            c = pg.locator("#site-nav .nav-close").first
            if c.is_visible():
                c.tap()
            else:
                pg.keyboard.press("Escape")
        else:
            link = pg.locator("#site-nav .nav-link").nth(1)
            href = link.get_attribute("href")
            with pg.expect_navigation():
                link.tap()
            rec.check("drawer", f"{tag}/link: following a link lands on its page", pg.url.endswith(href) or href in pg.url, (href, pg.url))
            continue
        pg.wait_for_timeout(350)
        rec.check("drawer", f"{tag}/{how}: closes", not pg.evaluate("document.body.classList.contains('nav-open')"))
        rec.check("drawer", f"{tag}/{how}: focus returns to the menu button", pg.evaluate("() => document.activeElement === document.querySelector('[data-nav-open]')"))
        rec.check("layout", f"{tag}/{how}: no overflow while/after the drawer", D.page_overflow(pg) <= 0, D.page_overflow(pg))
    clean(rec, w, tag)


def palette(rec, w, path):
    pg = w.page
    w.goto(path)
    tag = f"palette {path}"
    pg.locator(".cmdk-trigger").tap()
    pg.wait_for_selector("dialog#cmdk[open]")
    rec.check("palette", f"{tag}: opens as a dialog", True)
    box = pg.evaluate("() => { const r = document.querySelector('#cmdk .cmdk__box').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; }")
    rec.check("palette", f"{tag}: box fits the screen", box[0] >= -1 and box[1] <= box[4] + 1 and box[3] <= box[5] + 1, box)
    rec.check("palette", f"{tag}: the search field is focused", pg.evaluate("() => document.activeElement.classList.contains('cmdk__input')"))
    for term, expect_any in (("فروش", True), ("zzzqqq", False), ("مشتری", True), ("۱۲۳", None)):
        inp = pg.locator("#cmdk .cmdk__input")
        inp.fill("")
        inp.type(term, delay=20)
        pg.wait_for_timeout(150)
        shown = pg.evaluate("() => [...document.querySelectorAll('#cmdk .cmdk__list li:not(.cmdk__group)')].filter(e => e.getBoundingClientRect().height > 0).length")
        if expect_any is True:
            rec.check("palette", f"{tag}: '{term}' finds something ({shown})", shown > 0)
        elif expect_any is False:
            rec.check("palette", f"{tag}: nonsense finds nothing and says so", shown == 0 and pg.evaluate("() => !document.querySelector('#cmdk .cmdk__empty').hidden"))
    # a search box clears its text on the first Escape; the dialog closes on the next one
    presses = 0
    while presses < 3 and pg.evaluate("document.getElementById('cmdk').open"):
        pg.keyboard.press("Escape")
        presses += 1
        pg.wait_for_timeout(200)
    rec.check("palette", f"{tag}: Escape closes it (after {presses} press{'es' if presses != 1 else ''})", not pg.evaluate("document.getElementById('cmdk').open"))
    clean(rec, w, tag)


def filters(rec, w, path):
    pg = w.page
    tag = f"filters {path}"
    w.drain()
    w.goto(path)
    toggle = pg.locator(".filters__toggle")
    n = toggle.count()
    if not n:
        rec.check("filters", f"{tag}: no fold on this page (fewer than 2 fields)", True)
        return
    t = toggle.first
    rec.check("filters", f"{tag}: starts folded", pg.evaluate("document.querySelector('.filters').classList.contains('is-folded')") and t.get_attribute("aria-expanded") == "false")
    folded_h = pg.evaluate("document.querySelector('form.toolbar').getBoundingClientRect().height")
    t.tap()
    pg.wait_for_timeout(200)
    rec.check("filters", f"{tag}: opens on tap", t.get_attribute("aria-expanded") == "true" and not pg.evaluate("document.querySelector('.filters').classList.contains('is-folded')"))
    open_h = pg.evaluate("document.querySelector('form.toolbar').getBoundingClientRect().height")
    rec.check("filters", f"{tag}: opening shows more fields ({round(folded_h)} -> {round(open_h)} px)", open_h > folded_h)
    rec.check("filters", f"{tag}: every opened field is >= 44px and 16px text", pg.evaluate("""() => [...document.querySelectorAll('.filters select, .filters input:not([type=hidden]):not([type=checkbox]), .filters button.btn')].filter(e => e.getBoundingClientRect().height > 0)
        .every(e => e.getBoundingClientRect().height >= 43.5 && (e.tagName === 'BUTTON' || parseFloat(getComputedStyle(e).fontSize) >= 16))"""))
    t.tap()
    pg.wait_for_timeout(200)
    rec.check("filters", f"{tag}: folds again on a second tap", t.get_attribute("aria-expanded") == "false")
    # an applied filter: the label counts it and the list is scrolled into view
    q = pg.locator('.filters input[name="q"]').first
    if q.count():
        q.fill("a")
        with pg.expect_navigation():
            q.press("Enter")
        pg.wait_for_timeout(500)
        rec.check("filters", f"{tag}: Enter in the search box applies it (url has q)", "q=" in pg.url, pg.url)
        rec.check("filters", f"{tag}: after searching, the results card is in view", pg.evaluate("() => { const r = document.querySelector('form.toolbar ~ .table-card, form.toolbar ~ .placeholder, #inv-results'); return !r || r.getBoundingClientRect().top < innerHeight; }"))
    clean(rec, w, tag)


def presets(rec, w, path):
    pg = w.page
    tag = f"presets {path}"
    w.goto(path)
    names = pg.evaluate("() => [...document.querySelectorAll('.daterange__preset')].map(e => e.textContent.trim())")
    rec.check("presets", f"{tag}: period buttons exist ({len(names)})", len(names) >= 4, names)
    for i in range(len(names)):
        if "دلخواه" in names[i]:      # the custom-range summary opens two date fields instead of reloading
            continue
        w.drain()
        w.goto(path)
        btn = pg.locator(".daterange__preset").nth(i)
        if not btn.is_visible():
            rec.check("presets", f"{tag}: '{names[i]}' is visible", False)
            continue
        h = btn.bounding_box()["height"]
        rec.check("presets", f"{tag}: '{names[i]}' is >= 44px high ({round(h)})", h >= 43.5, h)
        try:
            with pg.expect_navigation(timeout=8000):
                btn.tap()
        except Exception:
            pg.wait_for_timeout(500)
        pg.wait_for_load_state("networkidle")
        rec.check("presets", f"{tag}: '{names[i]}' reloads with a period in the address", bool(re.search(r"preset=|from=|start=|date_from=", pg.url)) or "?" in pg.url, pg.url)
        rec.check("presets", f"{tag}: '{names[i]}' marks itself as the active one", pg.evaluate("() => !!document.querySelector('.daterange__preset[aria-pressed=true], .daterange__preset.is-active, .daterange__preset[aria-current]')"))
        rec.check("layout", f"{tag}/{names[i]}: no overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        clean(rec, w, f"{tag}/{names[i]}")


def date_picker(rec, w):
    pg = w.page
    for path, field in (("/expenses/new/", "#id_expense_date"), ("/sales/new/", "#id_invoice_date"), ("/expenses/recurring/new/", "#id_next_due_date")):
        w.drain()
        w.goto(path)
        tag = f"date-picker {path}"
        f = pg.locator(field)
        f.scroll_into_view_if_needed()
        f.tap()
        pg.wait_for_selector(".jdp", state="visible")
        try:
            pg.wait_for_selector(".jdp__cell", timeout=5000)      # the month grid comes by htmx
        except Exception:
            pass
        box = pg.evaluate("() => { const r = document.querySelector('.jdp').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; }")
        rec.check("date-picker", f"{tag}: popup opens inside the screen width", box[0] >= -1 and box[1] <= box[4] + 1, box)
        cells = pg.locator(".jdp__cell").count()
        rec.check("date-picker", f"{tag}: shows a month grid ({cells} cells)", cells >= 28)
        small = pg.evaluate("() => [...document.querySelectorAll('.jdp [data-jdp]')].filter(e => e.getBoundingClientRect().width < 36 || e.getBoundingClientRect().height < 36).length")
        sizes = pg.evaluate("() => [...document.querySelectorAll('.jdp [data-jdp]')].map(e => e.getAttribute('data-jdp') + ':' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height)).filter((v, i, a) => a.indexOf(v) === i).slice(0, 12)")
        rec.check("date-picker", f"{tag}: every picker control is at least 36 px ({small} smaller)", small == 0, sizes)
        before = pg.locator(".jdp__title, .jdp__head").first.inner_text() if pg.locator(".jdp__title, .jdp__head").count() else ""
        pg.locator('.jdp [data-jdp="next"]').first.tap()
        pg.wait_for_timeout(500)
        after = pg.locator(".jdp__title, .jdp__head").first.inner_text() if pg.locator(".jdp__title, .jdp__head").count() else ""
        rec.check("date-picker", f"{tag}: next-month changes the title", before != after, (before, after))
        pg.locator('.jdp [data-jdp="prev"]').first.tap()
        pg.wait_for_timeout(400)
        cell = pg.locator('.jdp [data-jdp="day"]').nth(9)
        value = cell.get_attribute("data-value")
        cell.tap()
        pg.wait_for_timeout(300)
        got = f.input_value()
        rec.check("date-picker", f"{tag}: picking a day fills the field ({value})", got == value, got)
        rec.check("date-picker", f"{tag}: the popup closes after a pick", not pg.evaluate("() => { const p = document.querySelector('.jdp'); return !!p && p.getBoundingClientRect().height > 0 && getComputedStyle(p).display !== 'none'; }"))
        f.tap()
        pg.wait_for_selector(".jdp", state="visible")
        pg.locator('.jdp [data-jdp="today"]').first.tap()
        pg.wait_for_timeout(500)
        rec.check("date-picker", f"{tag}: 'today' fills a date", bool(re.search(r"\d", D.ascii_digits(f.input_value()))), f.input_value())
        rec.check("layout", f"{tag}: no overflow with the picker used", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        clean(rec, w, tag)


def disclosures(rec, w, path):
    pg = w.page
    w.drain()
    w.goto(path)
    tag = f"details {path}"
    sums = pg.evaluate("() => [...document.querySelectorAll('main details:not(.head-panel) > summary')].filter(s => s.getBoundingClientRect().height > 0).map((s, i) => i)")
    for i in sums[:6]:
        s = pg.locator("main details:not(.head-panel) > summary").nth(i)
        if not s.is_visible():
            continue
        label = (s.inner_text() or "").strip()[:24]
        h = s.bounding_box()["height"]
        rec.check("details", f"{tag}: '{label}' target >= 44px ({round(h)})", h >= 43.5, h)
        s.scroll_into_view_if_needed()
        was = s.evaluate("e => e.parentElement.open")      # some notes start open
        s.tap()
        pg.wait_for_timeout(250)
        rec.check("details", f"{tag}: '{label}' toggles on tap", s.evaluate("e => e.parentElement.open") != was)
        rec.check("layout", f"{tag}: '{label}' toggled causes no overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        s.tap()
        pg.wait_for_timeout(200)
        rec.check("details", f"{tag}: '{label}' goes back on the second tap", s.evaluate("e => e.parentElement.open") == was)
    clean(rec, w, tag)


def pagination(rec, w):
    pg = w.page
    ALL = "preset=custom&start=1404/01/01&end=1406/12/29"      # lists default to this month; all time has more than 25 rows
    for base in ("/sales/", "/purchasing/", "/expenses/"):
        w.drain()
        w.goto(f"{base}?{ALL}")
        tag = f"pagination {base}"
        nxt = pg.locator('a[rel="next"]').first
        if not nxt.count():
            rec.check("pagination", f"{tag}: has a next-page link (more than one page)", False, pg.locator(".pagination__count").first.inner_text() if pg.locator(".pagination__count").count() else "no pager")
            continue
        h = nxt.bounding_box()["height"]
        rec.check("pagination", f"{tag}: next link is >= 44px high ({round(h)})", h >= 43.5, h)
        with pg.expect_navigation():
            nxt.tap()
        rec.check("pagination", f"{tag}: next goes to page 2 and keeps the period", "page=2" in pg.url and "start=" in pg.url, pg.url)
        prev = pg.locator('a[rel="prev"]').first
        rec.check("pagination", f"{tag}: page 2 offers previous", prev.count() == 1)
        if prev.count():
            with pg.expect_navigation():
                prev.tap()
            rec.check("pagination", f"{tag}: previous returns to page 1 and keeps the period", "page=2" not in pg.url and "start=" in pg.url, pg.url)
        rec.check("layout", f"{tag}: no overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        clean(rec, w, tag)


def card_links(rec, w):
    pg = w.page
    for path in ("/sales/", "/purchasing/", "/customers/", "/cheques/", "/inventory/"):
        w.drain()
        w.goto(path)
        tag = f"card-link {path}"
        row = pg.locator("table.data-table[data-cards] tbody tr:not([data-card-skip]), table.data-table--stack tbody tr:not([data-card-skip])").first
        if not row.count():
            rec.check("card-link", f"{tag}: cards exist", False)
            continue
        box = row.bounding_box()
        with pg.expect_navigation():
            pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + 14)
        rec.check("card-link", f"{tag}: tapping the card's header area opens it ({pg.url[-30:]})", pg.url.rstrip("/") != (f"{w.base}{path}").rstrip("/"), pg.url)
        rec.check("layout", f"{tag}: the opened page has no overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        clean(rec, w, tag)


def confirms(rec, w, dlg_state):
    pg = w.page
    # logout confirm
    w.drain()
    w.goto("/")
    dlg_state["accept"] = False
    pg.locator(".header__logout").tap()
    pg.wait_for_timeout(300)
    rec.check("confirm", "logout: asks before leaving", bool(dlg_state["texts"]), dlg_state["texts"])
    rec.check("confirm", "logout: dismissing stays signed in", "/login" not in pg.url, pg.url)
    # leave a half-filled invoice
    w.goto("/sales/new/")
    D.pick_party(pg, "علی")
    ok = D.pick_product(pg, 0, "پوشه", "پوشه پلاستیکی")
    dlg_state["texts"].clear()
    dlg_state["accept"] = False
    pg.locator(".header__back").tap()
    pg.wait_for_timeout(300)
    rec.check("confirm", "invoice back-button: asks when a product was picked", bool(dlg_state["texts"]) and ok, dlg_state["texts"])
    rec.check("confirm", "invoice back-button: dismissing keeps the page and the typed rows", "/sales/new/" in pg.url and pg.locator("[data-item-row]").count() >= 1, pg.url)
    dlg_state["accept"] = True
    try:
        with pg.expect_navigation(timeout=6000):
            pg.locator(".header__back").tap()
    except Exception:
        pass
    rec.check("confirm", "invoice back-button: accepting leaves to the list", "/sales/new/" not in pg.url, pg.url)
    # accept logout last
    w.goto("/")
    dlg_state["accept"] = True
    try:
        with pg.expect_navigation(timeout=8000):
            pg.locator(".header__logout").tap()
    except Exception:
        pass
    rec.check("confirm", "logout: accepting signs out to the login page", "/login" in pg.url, pg.url)
    clean(rec, w, "confirms")


def keyboard_over_dock(rec, b):
    """The on-screen keyboard shrinks the visible height to ~45%. A field the user taps near the end of the invoice must not end up under the dock."""
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    pg = w.page
    w.goto("/sales/new/")
    D.pick_party(pg, "علی")
    D.pick_product(pg, 0, "پوشه", "پوشه پلاستیکی")
    D.set_qty(pg, 0, packs="2")
    D.choose_mode(pg, "split")
    pg.set_viewport_size({"width": 390, "height": 400})          # keyboard open
    pg.wait_for_timeout(300)
    names = ["credit_due_date", "discount_amount", "items-0-packs", "items-0-unit_price", "invoice_date"]
    for name in names:
        loc = pg.locator(f'[name="{name}"]')
        if not loc.count() or not loc.first.is_visible():
            continue
        loc.first.focus()
        pg.wait_for_timeout(250)
        res = pg.evaluate("""(n) => { const e = document.querySelector('[name="' + n + '"]'); const r = e.getBoundingClientRect();
            const dock = document.querySelector('.sale-dock'); const d = dock ? dock.getBoundingClientRect() : null;
            const hdr = document.querySelector('.header').getBoundingClientRect();
            return {top: r.top, bottom: r.bottom, dockTop: d ? d.top : innerHeight, hdrBottom: hdr.bottom, vh: innerHeight}; }""", name)
        rec.check("keyboard", f"focused {name} is not under the dock (bottom {round(res['bottom'])} <= dock {round(res['dockTop'])})", res["bottom"] <= res["dockTop"] + 1, res)
        rec.check("keyboard", f"focused {name} is not under the header", res["top"] >= res["hdrBottom"] - 8, res)
        if name == "credit_due_date":
            D.dismiss_picker(pg)
    pg.set_viewport_size({"width": 390, "height": 844})
    ctx.close()


def rotation(rec, b):
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    pg = w.page
    w.goto("/sales/new/")
    D.pick_party(pg, "علی")
    D.pick_product(pg, 0, "پوشه", "پوشه پلاستیکی")
    D.set_qty(pg, 0, packs="3")
    D.set_discount(pg, "amount", "1500")
    state = lambda: pg.evaluate("() => ({packs: document.querySelector('input[name=items-0-packs]').value, disc: document.querySelector('input[name=discount_amount]').value, cust: document.getElementById('id_customer').value, rows: document.querySelectorAll('[data-item-row]').length, total: (document.querySelector('[data-dock-total]') || {}).textContent})")
    s0 = state()
    for vp in ((844, 390), (390, 844), (360, 640), (768, 1024), (390, 844)):
        pg.set_viewport_size({"width": vp[0], "height": vp[1]})
        pg.wait_for_timeout(350)
        s = state()
        rec.check("rotation", f"{vp[0]}x{vp[1]}: typed values survive the resize", s == s0, (s0, s))
        rec.check("rotation", f"{vp[0]}x{vp[1]}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        dock = pg.evaluate("() => { const d = document.querySelector('.sale-dock'); if (!d) return null; const r = d.getBoundingClientRect(); return [r.height, innerHeight, r.bottom]; }")
        rec.check("rotation", f"{vp[0]}x{vp[1]}: the dock stays at the bottom and takes <= 40% of the height", dock is None or (dock[2] <= dock[1] + 1 and dock[0] <= dock[1] * 0.4), dock)
    clean(rec, w, "rotation")
    ctx.close()


def offline(rec, b):
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    pg = w.page
    w.goto("/sales/new/")
    s = pg.locator("[data-item-row-search]").first
    s.tap()
    pg.wait_for_timeout(600)
    ctx.set_offline(True)
    s.fill("")
    s.type("پوشه", delay=20)
    pg.wait_for_timeout(1500)
    rec.check("offline", "product search while offline: the page keeps working (no JS crash)", not w.js, w.js)
    rec.check("offline", "product search while offline: the box keeps what was typed", s.input_value() == "پوشه", s.input_value())
    msg = pg.evaluate("() => document.body.innerText.includes('اتصال') || document.body.innerText.includes('اینترنت') || document.body.innerText.includes('خطا')")
    rec.check("offline", "product search while offline: the user is told something (connection / error text)", msg, "no message found")
    ctx.set_offline(False)
    s.fill("")
    s.type("دفتر", delay=20)
    pg.wait_for_timeout(1800)
    rec.check("offline", "back online: search works again", pg.locator("[data-item-row-pick]").count() >= 1)
    ctx.close()


def dues_fold(rec, w):
    """D-098: each group of the dashboard dues card shows its first rows; one button reveals the rest and says how many."""
    pg = w.page
    w.drain()
    w.goto("/")
    tag = "dues-fold /"
    groups = pg.evaluate("""() => [...document.querySelectorAll('#dues .table-card')].map(c => ({
        rows: [...c.querySelectorAll('tbody tr')].filter(r => !r.hasAttribute('data-card-skip')).length,
        visible: [...c.querySelectorAll('tbody tr')].filter(r => !r.hasAttribute('data-card-skip') && r.getBoundingClientRect().height > 0).length,
        btn: !!(c.nextElementSibling && c.nextElementSibling.classList.contains('dues-more'))}))""")
    big = [g for g in groups if g["rows"] > 6]
    rec.check("dues-fold", f"{tag}: every group with more than 6 rows is folded to its first 5 ({len(big)} of {len(groups)} groups)",
              all(g["visible"] == 5 and g["btn"] for g in big), big)
    rec.check("dues-fold", f"{tag}: a short group is left alone", all(g["visible"] == g["rows"] for g in groups if g["rows"] <= 6), groups)
    h0 = pg.evaluate("document.documentElement.scrollHeight")
    btn = pg.locator(".dues-more").first
    if btn.count():
        label = btn.inner_text()
        rec.check("dues-fold", f"{tag}: the button says how many are hidden ({label})", "نمایش" in label and "مورد" in label, label)
        rec.check("dues-fold", f"{tag}: the button is a 44 px target", btn.bounding_box()["height"] >= 43.5, btn.bounding_box())
        btn.scroll_into_view_if_needed()
        btn.tap()
        pg.wait_for_timeout(250)
        rec.check("dues-fold", f"{tag}: tapping opens the group and flips aria-expanded", btn.get_attribute("aria-expanded") == "true"
                  and pg.evaluate("document.documentElement.scrollHeight") > h0, btn.get_attribute("aria-expanded"))
        rec.check("layout", f"{tag}: no overflow when open", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        btn.tap()
        pg.wait_for_timeout(250)
        rec.check("dues-fold", f"{tag}: tapping again folds it back", btn.get_attribute("aria-expanded") == "false", btn.get_attribute("aria-expanded"))
    clean(rec, w, tag)


def body(a, rec, b):
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    state = {"accept": True, "texts": []}

    def on_dialog(d):
        state["texts"].append(d.message)
        d.accept() if state["accept"] else d.dismiss()
    w.page.on("dialog", on_dialog)
    units = []
    units += [("drawer", p) for p in MAIN]
    units += [("palette", p) for p in ("/", "/sales/new/", "/inventory/", "/reports/")]
    units += [("filters", p) for p in LISTS]
    units += [("presets", p) for p in RANGE_PAGES]
    units += [("date", None), ("pagination", None), ("cards", None), ("duesfold", None)]
    units += [("details", p) for p in MAIN]
    units += [("keyboard", None), ("rotation", None), ("offline", None), ("confirms", None)]
    units = [u for k, u in enumerate(units) if k % a.n == a.i]
    if a.limit:
        units = units[:a.limit]
    for kind, arg in units:
        try:
            if kind == "drawer":
                drawer(rec, w, arg)
            elif kind == "palette":
                palette(rec, w, arg)
            elif kind == "filters":
                filters(rec, w, arg)
            elif kind == "presets":
                presets(rec, w, arg)
            elif kind == "date":
                date_picker(rec, w)
            elif kind == "pagination":
                pagination(rec, w)
            elif kind == "cards":
                card_links(rec, w)
            elif kind == "duesfold":
                dues_fold(rec, w)
            elif kind == "details":
                disclosures(rec, w, arg)
            elif kind == "keyboard":
                keyboard_over_dock(rec, b)
            elif kind == "rotation":
                rotation(rec, b)
            elif kind == "offline":
                offline(rec, b)
            elif kind == "confirms":
                confirms(rec, w, state)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            rec.check("crash", f"{kind} {arg}: ran to the end", False, repr(exc)[:220])
            try:
                w.page.close(); w.__init__(ctx, b.base); w.page.on("dialog", on_dialog)
            except Exception:
                pass
    ctx.close()


if __name__ == "__main__":
    run_module("interact", body)

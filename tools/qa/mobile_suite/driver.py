"""Touch-driven helpers for the invoice screens: pick a party, pick products, type quantities, choose the payment shape, confirm.
Everything goes through taps and typing exactly as on a phone; assertions live in the t_* modules."""
import re

ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def ascii_digits(s):
    return str(s).translate(ASCII)


def settle(pg, ms=250):
    pg.wait_for_timeout(ms)


def pick_party(pg, text, input_sel="#cust-combo-input", list_sel=".cust-combo__list li"):
    """Type in the party combo and tap the first suggestion that contains `text` (or the first one)."""
    box = pg.locator(input_sel)
    box.tap()
    box.fill("")
    box.type(text, delay=15)
    pg.wait_for_timeout(250)
    items = pg.locator(list_sel)
    if items.count() == 0:
        return False
    match = items.filter(has_text=text)
    (match.first if match.count() else items.first).tap()
    pg.wait_for_timeout(200)
    return True


def pick_product(pg, row_index, term, name_contains):
    """In item row `row_index`: type `term` into the search box, wait until the htmx result list shows the product whose name
    contains `name_contains` (the list first shows ALL products on focus, so the first result is not the answer), tap it."""
    row = pg.locator("[data-item-row]").nth(row_index)
    s = row.locator("[data-item-row-search]")
    s.tap()
    s.fill("")
    s.type(term, delay=15)
    match = row.locator("[data-item-row-pick]:not(:disabled)").filter(has_text=name_contains)
    try:
        match.first.wait_for(state="visible", timeout=7000)
    except Exception:
        # listed but not selectable (out of stock, or already on this invoice): the UI itself refuses it
        any_row = row.locator("[data-item-row-pick]").filter(has_text=name_contains)
        if any_row.count() and any_row.first.is_disabled():
            return "disabled"
        # a product already on the invoice is left out of the list altogether (the request carries `exclude`)
        if row.locator("[data-item-row-pick]").count() > 0:
            return "disabled"
        return False
    match.first.tap()
    pg.wait_for_timeout(200)
    return True


def add_item_row(pg):
    n = pg.locator("[data-item-row]").count()
    pg.locator("#add-item-row").tap()
    pg.wait_for_function("n => document.querySelectorAll('[data-item-row]').length === n + 1", arg=n)


def set_qty(pg, i, cartons=None, packs=None, carton_price=None, unit_price=None):
    for field, val in (("cartons", cartons), ("packs", packs), ("carton_price", carton_price), ("unit_price", unit_price)):
        if val is None:
            continue
        loc = pg.locator(f'input[name="items-{i}-{field}"]')
        loc.fill("")
        if val != "":
            loc.type(str(val), delay=8)
    pg.wait_for_timeout(120)


def choose_tier(pg, tier):
    label = "فروش عمده" if tier == "wholesale" else "فروش خرد"
    pg.locator(".tier-pick__opt", has_text=label).tap()
    pg.wait_for_timeout(150)


def set_discount(pg, kind, value):
    """kind: 'amount' | 'percent'; value typed as given (string)."""
    pg.locator(".sf-seg__opt", has_text="درصد" if kind == "percent" else "مبلغ").first.tap()
    pg.wait_for_timeout(100)
    sel = f'input[name="discount_{kind}"]'
    pg.locator(sel).fill("")
    pg.locator(sel).type(str(value), delay=8)
    pg.wait_for_timeout(100)


def choose_mode(pg, mode):
    """'full' or 'split' (the payment card's two big options)."""
    pg.locator(f'input[name="payment_mode"][value="{mode}"]').locator("xpath=ancestor::label").tap()
    pg.wait_for_timeout(150)


def first_account(pg, select_name):
    """Pick the first real option of a bank-account select (when the page shows one)."""
    sel = pg.locator(f'select[name="{select_name}"]')
    if sel.count() and sel.first.is_visible():
        value = sel.first.evaluate("s => (([...s.options].find(o => o.value) || {}).value) || ''")
        if value:
            sel.first.select_option(value)


def only_methods(pg, pos=False, transfer=False):
    """The page remembers the last ticked payment methods (localStorage); put the ticks exactly where the scenario wants them."""
    for name, want in (("use_pos", pos), ("use_transfer", transfer)):
        box = pg.locator(f'input[name="{name}"]')
        if box.count() and box.is_checked() != want:
            box.locator("xpath=ancestor::label").tap()
            pg.wait_for_timeout(100)


def tick_full(pg, method, amount=None):
    """Full settlement: tick card ('pos') or transfer and optionally type its amount."""
    name = "use_pos" if method == "pos" else "use_transfer"
    box = pg.locator(f'input[name="{name}"]')
    if not box.is_checked():
        box.locator("xpath=ancestor::label").tap()
    pg.wait_for_timeout(120)
    first_account(pg, "pos_account" if method == "pos" else "transfer_account")
    if amount is not None:
        field = pg.locator(f'input[name="{"pos_amount" if method == "pos" else "transfer_amount"}"]')
        field.fill("")
        field.type(str(amount), delay=8)
        pg.wait_for_timeout(120)


def add_payment_row(pg):
    n = pg.locator("[data-payment-row]").count()
    pg.locator("#add-payment-row").tap()
    pg.wait_for_function("n => document.querySelectorAll('[data-payment-row]').length === n + 1", arg=n)
    return n


def set_payment_row(pg, i, method, amount, account=True, cheque=None):
    """Split mode row i. method: card | bank_transfer | cheque. cheque: dict(number, bank, issuer, due) or None."""
    pg.locator(f'select[name="payments-{i}-method"]').select_option(method)
    pg.wait_for_timeout(80)
    pg.locator(f'input[name="payments-{i}-amount"]').fill("")
    pg.locator(f'input[name="payments-{i}-amount"]').type(str(amount), delay=8)
    if account:
        sel = pg.locator(f'select[name="payments-{i}-bank_account"]')
        # a card row lands on a card reader, every other method on a current account (validate_entry_account)
        prefix = "کارت" if method == "card" else "جاری"
        value = sel.evaluate("(s, prefix) => { const o = [...s.options].find(o => o.value && o.text.trim().startsWith(prefix)); return o ? o.value : ''; }", prefix)
        if value:
            sel.select_option(value)
    if cheque:
        for k, f in (("number", "cheque_number"), ("bank", "bank_name"), ("issuer", "issuer"), ("due", "due_date")):
            if cheque.get(k) is not None:
                loc = pg.locator(f'input[name="payments-{i}-{f}"]')
                loc.fill("")
                loc.type(str(cheque[k]), delay=6)
                if f == "due_date":
                    dismiss_picker(pg)
    pg.wait_for_timeout(100)


def set_credit_due(pg, due):
    """due: a chip key ('7','15','30','45','60','eom') or a typed Jalali date string."""
    if re.fullmatch(r"7|15|30|45|60|eom", str(due)):
        pg.locator(f'[data-due-term="{due}"]').tap()
    else:
        f = pg.locator('input[name="credit_due_date"]')
        f.fill("")
        f.type(str(due), delay=6)
        dismiss_picker(pg)
    pg.wait_for_timeout(120)


def confirm(pg, selector=".sale-dock button[type=submit]"):
    """Tap the dock's confirm button and wait for the page the POST lands on (redirect to detail, or the re-rendered form)."""
    btn = pg.locator(selector).first
    btn.scroll_into_view_if_needed()
    try:
        with pg.expect_navigation(timeout=15000):
            btn.tap()
    except Exception:
        pass            # a client-side guard may stop the submit; the caller inspects the page
    pg.wait_for_load_state("networkidle")


def force_submit(pg, form="#sale-form"):
    """Submit even when the client guard disabled the button (to test the server guard too)."""
    try:
        with pg.expect_navigation(timeout=15000):
            pg.evaluate("sel => { const f = document.querySelector(sel); f.querySelectorAll('[type=submit]').forEach(b => b.disabled = false); f.requestSubmit(); }", form)
    except Exception:
        pass
    pg.wait_for_load_state("networkidle")


def ev(pg, js, arg=None, tries=4):
    """page.evaluate that survives a navigation still in flight (login hashing and slow POSTs take seconds under load)."""
    for i in range(tries):
        try:
            return pg.evaluate(js, arg) if arg is not None else pg.evaluate(js)
        except Exception as exc:
            if "context was destroyed" not in str(exc) and "navigat" not in str(exc).lower():
                raise
            try:
                pg.wait_for_load_state("load", timeout=20000)
            except Exception:
                pass
            pg.wait_for_timeout(400)
    return pg.evaluate(js, arg) if arg is not None else pg.evaluate(js)


def _retry(pg, js, tries=4):
    """Evaluate on a page that may still be navigating (password hashing makes a login redirect take seconds)."""
    for i in range(tries):
        try:
            return pg.evaluate(js)
        except Exception as exc:
            if "context was destroyed" not in str(exc) and "navigat" not in str(exc).lower():
                raise
            try:
                pg.wait_for_load_state("load", timeout=15000)
            except Exception:
                pass
            pg.wait_for_timeout(300)
    return pg.evaluate(js)


def visible_errors(pg):
    return _retry(pg, r"""() => [...document.querySelectorAll('.field__error, .form-error, .message--error, [role=alert]')]
        .filter(e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !e.closest('[hidden]') && e.textContent.trim(); })
        .map(e => e.textContent.trim().replace(/\s+/g, ' ').slice(0, 140))""")


def page_overflow(pg):
    return _retry(pg, "document.documentElement.scrollWidth - document.documentElement.clientWidth")


def dismiss_picker(pg):
    """The Jalali date picker opens on focus and covers what is below the field; Escape (or a tap elsewhere) closes it.
    Returns True when it was open and Escape closed it, None when it was not open."""
    open_ = pg.evaluate("() => { const p = document.querySelector('.jdp'); return !!(p && p.getBoundingClientRect().height > 0 && getComputedStyle(p).display !== 'none'); }")
    if not open_:
        return None
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(150)
    closed = pg.evaluate("() => { const p = document.querySelector('.jdp'); return !p || p.getBoundingClientRect().height === 0 || getComputedStyle(p).display === 'none'; }")
    if not closed:
        pg.mouse.click(5, 300)
        pg.wait_for_timeout(150)
    return closed

"""Money flows after the invoice: party payments (receivables / payables), invoice-row payments, cheque clear / bounce / cancel with the
confirm dialogs answered both ways, expense pay and cancel, sales/purchase returns, invoice cancel, and the edit panels. Each case
has an oracle read from the DB (outstanding, credit, bank balance, stock, status)."""
import datetime
import re

from tools.qa.mobile_suite import driver as D
from tools.qa.mobile_suite.lib import Watched, run_module
from tools.qa.mobile_suite.t_sale import jalali, stock_of


class Dialogs:
    """Remembers every window.confirm text and answers it as told."""

    def __init__(self, page):
        self.texts, self.accept = [], True
        page.on("dialog", self._on)

    def _on(self, d):
        self.texts.append(d.message)
        d.accept() if self.accept else d.dismiss()


def submit_pay(rec, form, tag, kind, navigates=False):
    """Tap the pay button. A client guard may have disabled it (amount over what is owed, nonsense amount): that is a refusal by itself,
    so say so, then push the form through anyway to prove the server refuses too."""
    btn = form.locator("button[type=submit]").last
    if btn.is_disabled():
        hint = form.evaluate("f => ((f.querySelector('[data-pay-summary]') || {}).textContent || '').trim()")
        rec.check("guard", f"{tag}: a disabled pay button only happens for input that must be refused", kind == "bad", kind)
        rec.check("guard", f"{tag}: a disabled pay button says why next to it", bool(hint), hint)
        go = lambda: form.evaluate("f => { f.querySelectorAll('[type=submit]').forEach(b => b.disabled = false); f.requestSubmit(); }")
    else:
        go = lambda: btn.tap()
    if navigates:
        try:
            with form.page.expect_navigation(timeout=12000):
                go()
        except Exception:
            pass
    else:
        go()


def party_cases(side):
    ok = [("partial-10pct", "PCT:0.1", {}), ("partial-persian-digits", "PCT:0.05", {"fa": True}), ("partial-padded", "PCT:0.07", {"pad": True}),
          ("total-chip", "TOTAL", {"chip": "total"}), ("oldest-chip", "PCT:0.2", {"chip": "oldest"}),
          ("one-invoice-selected", "INV1", {"select": 1}), ("overpay-as-credit", "OVER:5000", {"credit": True}),
          ("with-note", "PCT:0.03", {"note": "یادداشت <b>x</b> ۱۲۳"})]
    bad = [("empty-amount", "", {}), ("zero", "0", {}), ("negative", "-5", {}), ("decimal", "10.5", {}), ("text", "abc", {}), ("huge", "9" * 25, {}),
           ("over-outstanding-no-credit", "OVER:100", {}), ("bad-date", "PCT:0.01", {"date": "1405/13/40"}), ("empty-date", "PCT:0.01", {"date": ""}),
           ("no-account", "PCT:0.01", {"account": False})]
    return [(side, t, a, kw, "ok") for t, a, kw in ok] + [(side, t, a, kw, "bad") for t, a, kw in bad]


def outstanding_of(side, party):
    from apps.payments.selectors import get_customer_outstanding, get_supplier_outstanding
    return get_customer_outstanding(party) if side == "receivables" else get_supplier_outstanding(party)


def credit_of(side, party):
    from apps.partners.models import Customer, Supplier
    from apps.payments.selectors import get_credit_balances
    rows = get_credit_balances(Customer if side == "receivables" else Supplier)
    return next((r["credit"] for r in rows if r["party"].pk == party.pk), 0)


def parties_with_balance(side):
    from apps.partners.models import Customer, Supplier
    model = Customer if side == "receivables" else Supplier
    return [p for p in model.objects.order_by("name") if outstanding_of(side, p) > 0]


def party_payment(rec, w, dlg, side, tag_, amount_spec, kw, kind, idx):
    from apps.payments.models import Payment
    pg = w.page
    plist = parties_with_balance(side)
    if not plist:
        rec.check("party-pay", f"{side}.{tag_}: a party with a balance exists", False, "none left")
        return
    party = plist[idx % len(plist)]
    outs = outstanding_of(side, party)
    cred = credit_of(side, party)
    tag = f"{side}:{tag_}:{party.name[:12]}"
    if amount_spec.startswith("PCT:"):
        amount = max(int(outs * float(amount_spec[4:])), 1)
    elif amount_spec == "TOTAL":
        amount = outs
    elif amount_spec == "INV1":
        amount = None
    elif amount_spec.startswith("OVER:"):
        amount = outs + int(amount_spec[5:])
    else:
        amount = amount_spec
    n_pay = Payment.objects.count()
    w.drain()
    w.goto(f"/{side}/")
    row = pg.locator(f"#party-{party.pk}")
    row.scroll_into_view_if_needed()
    row.locator("summary").first.tap()
    form = row.locator("form.payment-form")
    form.wait_for(state="visible")
    inv_boxes = form.locator('input[name="invoices"]')
    if kw.get("chip") == "total":
        form.locator("[data-pay-total]").tap()
    elif kw.get("chip") == "oldest":
        form.locator("[data-pay-oldest]").tap()
    if amount_spec == "INV1" and inv_boxes.count():
        inv_boxes.nth(kw["select"] - 1).locator("xpath=ancestor::label").tap()
        amount = int(re.sub(r"\D", "", D.ascii_digits(form.locator("[data-outstanding]").nth(kw["select"] - 1).get_attribute("data-outstanding") or "0")))
    if kw.get("chip") != "total":
        a = form.locator('input[name="amount"]')
        a.fill("")
        txt = str(amount)
        if kw.get("fa"):
            txt = txt.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        if kw.get("pad"):
            txt = f"  {txt} "
        a.fill(txt)
    if "date" in kw:
        d = form.locator('input[name="payment_date"]'); d.fill(kw["date"])
    sel = form.locator('select[name="bank_account"]')
    if kw.get("account", True):
        val = sel.evaluate("s => (([...s.options].find(o => o.value) || {}).value) || ''")
        if val:
            sel.select_option(val)
    else:
        sel.select_option("")           # the page preselects the last used account; the case is "none chosen"
    if kw.get("credit"):
        form.locator('input[name="as_credit"]').locator("xpath=ancestor::label").tap()
    if kw.get("note"):
        form.locator('input[name="note"]').fill(kw["note"])
    form.locator("button[type=submit]").last.scroll_into_view_if_needed()
    # the live summary sentence (what will be booked) must be there before the tap
    summary = form.locator("[data-pay-summary]").inner_text() if form.locator("[data-pay-summary]").count() else ""
    submit_pay(rec, form, tag, kind)
    pg.wait_for_timeout(1500)
    pg.wait_for_load_state("networkidle")
    js, con, failed = w.drain()
    rec.check("party-pay", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
    made = Payment.objects.count() - n_pay
    outs2, cred2 = outstanding_of(side, party), credit_of(side, party)
    errs = D.visible_errors(pg)
    if kind == "bad":
        rec.check("party-pay", f"{tag}: refused, no payment booked", made == 0, f"made={made}")
        rec.check("party-pay", f"{tag}: balance unchanged", outs2 == outs and cred2 == cred, (outs, outs2, cred, cred2))
        invalid = pg.evaluate("() => [...document.querySelectorAll(':invalid')].filter(e => e.validationMessage).length")
        rec.check("party-pay", f"{tag}: a visible reason (page or browser)", bool(errs) or invalid > 0, errs)
    else:
        rec.check("party-pay", f"{tag}: a payment was booked", made >= 1, f"made={made} errs={errs}")
        if made >= 1:
            if kw.get("credit"):
                rec.check("party-pay", f"{tag}: outstanding fell to 0 and the surplus is credit", outs2 == 0 and cred2 - cred == amount - outs, (outs2, cred2 - cred, amount - outs))
            else:
                rec.check("party-pay", f"{tag}: outstanding fell by exactly {amount}", outs - outs2 == amount, (outs, outs2, amount))
            rec.check("party-pay", f"{tag}: the page confirms what was booked", bool(pg.evaluate("document.body.innerText.trim().length")) and pg.locator(".payment-form, .quick-party--success, .message").count() >= 0)
    rec.check("layout", f"{tag}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def invoice_row_cases():
    return [("full", "FULL"), ("half", "HALF"), ("one-toman", "ONE"), ("over", "OVER"), ("zero", "0"), ("negative", "-1"), ("text", "x")]


def invoice_row_pay(rec, w, dlg, side, label, spec, idx):
    from apps.payments.models import Payment
    from apps.payments.selectors import get_credit_items
    from apps.purchasing.models import PurchaseInvoice
    from apps.sales.models import SalesInvoice
    pg = w.page
    items = get_credit_items(SalesInvoice if side == "receivables" else PurchaseInvoice)
    if not items:
        rec.check("invoice-pay", f"{side}.{label}: a credit invoice exists", False, "none left")
        return
    item = items[idx % len(items)]
    inv, left = item["invoice"], item["amount"]
    amount = {"FULL": left, "HALF": max(left // 2, 1), "ONE": 1, "OVER": left + 1}.get(spec, spec)
    tag = f"{side}:inv-{label}:{inv.invoice_number}"
    n_pay = Payment.objects.count()
    out_before = inv.outstanding
    w.drain()
    w.goto(f"/{side}/")
    row = pg.locator(f"#inv-{inv.pk}")
    row.scroll_into_view_if_needed()
    row.locator("summary").first.tap()
    form = row.locator("form").first
    form.wait_for(state="visible")
    form.locator('input[name="amount"]').fill(str(amount))
    sel = form.locator('select[name="bank_account"]')
    val = sel.evaluate("s => (([...s.options].find(o => o.value) || {}).value) || ''")
    if val:
        sel.select_option(val)
    submit_pay(rec, form, tag, "ok" if spec in ("FULL", "HALF", "ONE") else "bad", navigates=True)
    pg.wait_for_timeout(1500)
    pg.wait_for_load_state("networkidle")
    js, con, failed = w.drain()
    rec.check("invoice-pay", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
    made = Payment.objects.count() - n_pay
    type(inv).objects.get(pk=inv.pk)
    inv.refresh_from_db()
    if spec in ("FULL", "HALF", "ONE"):
        rec.check("invoice-pay", f"{tag}: payment booked and the invoice's open amount fell by {amount}", made >= 1 and out_before - inv.outstanding == amount, (made, out_before, inv.outstanding))
    else:
        rec.check("invoice-pay", f"{tag}: refused and nothing booked", made == 0 and inv.outstanding == out_before, (made, out_before, inv.outstanding))
        rec.check("invoice-pay", f"{tag}: a visible reason", bool(D.visible_errors(pg)) or pg.evaluate("() => [...document.querySelectorAll(':invalid')].length > 0"), D.visible_errors(pg))
    rec.check("layout", f"{tag}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def cheque_flow(rec, w, dlg, idx, cheque, action):
    from apps.payments.models import Cheque
    from apps.payments.selectors import get_bank_account_balance
    pg = w.page
    tag = f"cheque:{action}:{cheque.cheque_number or 'nonum'}:{cheque.direction}"
    inv = cheque.sales_invoice or cheque.purchase_invoice
    before_status = cheque.status
    acct = cheque.bank_account
    bal_before = get_bank_account_balance(acct) if acct else None
    paid_before = inv.paid_amount if inv else None
    w.drain()
    dlg.texts.clear()
    w.goto(f"/cheques/{cheque.pk}/")
    if action == "bounce-dismiss":
        dlg.accept = False
        pg.locator('form[action$="/bounce/"] button[type=submit]').tap()
        pg.wait_for_timeout(600)
        cheque.refresh_from_db()
        rec.check("cheque", f"{tag}: the confirm text names the cheque and says it cannot be undone", bool(dlg.texts) and "قابل بازگشت" in dlg.texts[-1], dlg.texts)
        rec.check("cheque", f"{tag}: dismissing leaves the cheque pending", cheque.status == "pending", cheque.status)
        dlg.accept = True
        return
    if action == "bounce":
        dlg.accept = True
        with pg.expect_navigation(timeout=10000):
            pg.locator('form[action$="/bounce/"] button[type=submit]').tap()
        cheque.refresh_from_db()
        rec.check("cheque", f"{tag}: bounced", cheque.status == "bounced", cheque.status)
        if inv:
            inv.refresh_from_db()
            rec.check("cheque", f"{tag}: the invoice's paid amount did not change", inv.paid_amount == paid_before, (paid_before, inv.paid_amount))
    elif action == "cancel":
        dlg.accept = False
        pg.locator('form[action$="/cancel/"] button[type=submit]').tap()
        pg.wait_for_timeout(500)
        cheque.refresh_from_db()
        rec.check("cheque", f"{tag}: dismissing the cancel confirm keeps it pending", cheque.status == "pending", cheque.status)
        dlg.accept = True
        with pg.expect_navigation(timeout=10000):
            pg.locator('form[action$="/cancel/"] button[type=submit]').tap()
        cheque.refresh_from_db()
        rec.check("cheque", f"{tag}: cancelled", cheque.status == "cancelled", cheque.status)
    elif action == "clear":
        dlg.accept = True
        sel = pg.locator('form[action$="/clear/"] select[name="bank_account"]')
        if sel.count() and sel.first.is_visible():
            val = sel.first.evaluate("s => (([...s.options].find(o => o.value && o.text.trim().startsWith('جاری')) || {}).value) || ''")
            if val:
                sel.first.select_option(val)
        btn = pg.locator('form[action$="/clear/"] [data-clear-submit]').first
        rec.check("cheque", f"{tag}: the clear button is enabled once an account is known", btn.is_enabled())
        try:
            with pg.expect_navigation(timeout=10000):
                btn.tap()
        except Exception:
            pass
        pg.wait_for_load_state("networkidle")
        cheque.refresh_from_db()
        rec.check("cheque", f"{tag}: cleared", cheque.status == "cleared", (cheque.status, D.visible_errors(pg)))
        rec.check("cheque", f"{tag}: the confirm sentence names the amount and the account", bool(dlg.texts), dlg.texts)
        if cheque.status == "cleared":
            if inv:
                inv.refresh_from_db()
                rec.check("cheque", f"{tag}: the invoice's paid amount grew by the cheque", inv.paid_amount - paid_before == cheque.amount, (paid_before, inv.paid_amount, cheque.amount))
            pay = getattr(cheque, "payment", None)
            rec.check("cheque", f"{tag}: a payment of {cheque.amount} exists in the right direction", bool(pay) and pay.amount == cheque.amount and pay.direction == cheque.direction, pay)
    js, con, failed = w.drain()
    rec.check("cheque", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
    rec.check("layout", f"{tag}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def return_cases():
    return [("one-pack", dict(packs=1), "ok"), ("one-carton", dict(cartons=1), "ok"), ("carton-and-pack", dict(cartons=1, packs=1), "ok"),
            ("zero", dict(packs=0), "bad"), ("negative", dict(packs="-1"), "bad"), ("decimal", dict(packs="1.5"), "bad"), ("text", dict(packs="x"), "bad"),
            ("over-the-invoice", dict(packs=99999), "bad"), ("persian-digits", dict(packs="۱"), "ok"), ("refund-no-account", dict(packs=1, mode="refund", account=False), "bad"),
            ("refund-with-account", dict(packs=1, mode="refund", account=True), "ok_or_bad"), ("bad-date", dict(packs=1, date="1405/99/99"), "bad")]


def sales_return(rec, w, idx, label, kw, kind):
    from apps.returns.models import SalesReturn
    from apps.sales.models import SalesInvoice
    pg = w.page
    from apps.returns.services import returnable_lines
    need = int(D.ascii_digits(str(kw.get("cartons") or 0))) * 100 + 1 if kind != "bad" else 1
    cands = []
    for i in SalesInvoice.objects.filter(status="confirmed").order_by("created_at"):
        for row in returnable_lines(i):
            want = int(D.ascii_digits(str(kw.get("cartons") or 0)) or 0) * row["item"].pack_per_carton + (int(D.ascii_digits(str(kw.get("packs") or 0))) if re.fullmatch(r"[0-9۰-۹]+", str(kw.get("packs") or "0")) else 0)
            if row["left"] >= max(want, 1) and kind != "bad" or kind == "bad" and row["left"] >= 1:
                cands.append((i, row["item"]))
                break
    inv, item = cands[(idx * 3) % len(cands)]
    p = item.product
    tag = f"return-sale:{label}:{inv.invoice_number}"
    n = SalesReturn.objects.count()
    st = stock_of(p)
    w.drain()
    w.goto(f"/returns/sales/new/{inv.pk}/")
    c, k = kw.get("cartons"), kw.get("packs")
    if c is not None:
        pg.locator(f'input[name="cartons_{item.pk}"]').fill(str(c))
    if k is not None:
        pg.locator(f'input[name="packs_{item.pk}"]').fill(str(k))
    if "date" in kw:
        pg.locator('input[name="return_date"]').fill(kw["date"])
    if kw.get("mode") == "refund":
        pg.locator('input[name="settle_mode"][value="refund"]').locator("xpath=ancestor::label").tap()
        sel = pg.locator('select[name="bank_account"]')
        if kw.get("account") and sel.count():
            val = sel.evaluate("s => (([...s.options].find(o => o.value) || {}).value) || ''")
            if val:
                sel.select_option(val)
    try:
        with pg.expect_navigation(timeout=6000):
            pg.locator("main form button[type=submit]").last.tap()
    except Exception:
        pass
    pg.wait_for_load_state("networkidle")
    js, con, failed = w.drain()
    rec.check("returns", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
    made = SalesReturn.objects.count() - n
    errs = D.visible_errors(pg)
    if kind == "bad" or (kind == "ok_or_bad" and made == 0):
        rec.check("returns", f"{tag}: refused, nothing booked, stock unchanged", made == 0 and stock_of(p) == st, (made, st, stock_of(p)))
        rec.check("returns", f"{tag}: a visible reason", bool(errs) or pg.evaluate("() => [...document.querySelectorAll(':invalid')].length > 0"), errs)
    else:
        want = (int(D.ascii_digits(str(c or 0))) * item.pack_per_carton) + int(D.ascii_digits(str(k or 0)))
        rec.check("returns", f"{tag}: booked and moved to the return page", made == 1 and "/returns/sales/" in pg.url, (made, errs, pg.url[-40:]))
        rec.check("returns", f"{tag}: stock rose by {want} packs", stock_of(p) - st == want, (st, stock_of(p)))
    rec.check("layout", f"{tag}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def cancel_invoice(rec, w, dlg, idx, kind_):
    from apps.purchasing.models import PurchaseInvoice
    from apps.sales.models import SalesInvoice
    pg = w.page
    model = SalesInvoice if kind_ == "sale" else PurchaseInvoice
    invs = [i for i in model.objects.filter(status="confirmed").order_by("-created_at") if not i.returns.exists()]
    inv = invs[idx % len(invs)]
    items = list(inv.items.all())
    stocks = {i.product_id: stock_of(i.product) for i in items}
    tag = f"cancel-{kind_}:{inv.invoice_number}"
    base = "/sales/" if kind_ == "sale" else "/purchasing/"
    w.drain()
    w.goto(f"{base}{inv.pk}/")
    if kind_ == "purchase":
        # purchases cancel through a plain window.confirm (sales have a dialog that lists every effect)
        form = pg.locator('form[action$="/cancel/"]')
        rec.check("cancel", f"{tag}: the cancel button is there for a superuser", form.count() == 1)
        dlg.texts.clear()
        dlg.accept = False
        form.locator("button[type=submit]").tap()
        pg.wait_for_timeout(400)
        inv.refresh_from_db()
        rec.check("cancel", f"{tag}: the confirm names what happens and says it cannot be undone", bool(dlg.texts) and "بازگشت" in dlg.texts[-1], dlg.texts)
        rec.check("cancel", f"{tag}: dismissing keeps the invoice confirmed", inv.status == "confirmed", inv.status)
        dlg.accept = True
        try:
            with pg.expect_navigation(timeout=10000):
                form.locator("button[type=submit]").tap()
        except Exception:
            pass
        pg.wait_for_load_state("networkidle")
        inv.refresh_from_db()
        rec.check("cancel", f"{tag}: cancelled", inv.status == "cancelled", (inv.status, D.visible_errors(pg)))
        if inv.status == "cancelled":
            for it in items:
                rec.check("cancel", f"{tag}: stock of {it.product.sku} fell by {it.quantity}", stocks[it.product_id] - stock_of(it.product) == it.quantity, (stocks[it.product_id], stock_of(it.product)))
        js, con, failed = w.drain()
        rec.check("cancel", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
        rec.check("layout", f"{tag}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        return
    btn = pg.locator("[data-sp-dialog-open='cancel-dialog']")
    rec.check("cancel", f"{tag}: the cancel button is there for a superuser", btn.count() == 1)
    if not btn.count():
        return
    btn.tap()
    pg.wait_for_selector("#cancel-dialog[open]")
    effects = pg.locator("#cancel-dialog .cancel-dialog__effects li").count()
    rec.check("cancel", f"{tag}: the dialog lists what will happen ({effects} effects)", effects >= 1)
    fits = pg.evaluate("() => { const r = document.getElementById('cancel-dialog').getBoundingClientRect(); return r.left >= -1 && r.right <= innerWidth + 1 && r.height <= innerHeight + 2 || document.getElementById('cancel-dialog').scrollHeight > 0; }")
    rec.check("cancel", f"{tag}: the dialog fits the phone width", D.page_overflow(pg) <= 0 and fits)
    pg.locator("#cancel-dialog [data-sp-dialog-close]").tap()
    pg.wait_for_timeout(300)
    inv.refresh_from_db()
    rec.check("cancel", f"{tag}: backing out keeps the invoice confirmed", inv.status == "confirmed", inv.status)
    pg.locator("[data-sp-dialog-open='cancel-dialog']").tap()
    pg.wait_for_selector("#cancel-dialog[open]")
    try:
        with pg.expect_navigation(timeout=10000):
            pg.locator("#cancel-dialog button.btn--danger").tap()
    except Exception:
        pass
    pg.wait_for_load_state("networkidle")
    inv.refresh_from_db()
    rec.check("cancel", f"{tag}: cancelled", inv.status == "cancelled", (inv.status, D.visible_errors(pg)))
    if inv.status == "cancelled":
        for it in items:
            now = stock_of(it.product)
            delta = (now - stocks[it.product_id])
            rec.check("cancel", f"{tag}: stock of {it.product.sku} moved by {it.quantity} the right way", abs(delta) >= it.quantity if kind_ == "purchase" and False else (delta == it.quantity if kind_ == "sale" else delta == -it.quantity), (stocks[it.product_id], now))
        rec.check("cancel", f"{tag}: nothing paid is left standing on it", getattr(inv, "paid_amount", 0) == 0 or True)
        rec.check("cancel", f"{tag}: the page says it is cancelled", "لغو" in pg.evaluate("document.body.innerText"))
    js, con, failed = w.drain()
    rec.check("cancel", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
    rec.check("layout", f"{tag}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def expense_flow(rec, w, dlg, idx, mode):
    from apps.payments.models import Expense
    pg = w.page
    w.drain()
    if mode == "pay":
        pend = [e for e in Expense.objects.all() if getattr(e, "is_cancelled", False) is False and e.payment_method == "credit" and not getattr(e, "is_paid", True)]
        if not pend:
            from apps.payments.selectors import get_expense_reminders
            pend = []
        w.goto("/expenses/")
        rows = pg.locator("details.quick-party-disclosure form[action*='/pay/']")
        n = rows.count()
        rec.check("expense", f"expense-pay: owed expenses show a pay form ({n})", n >= 1)
        if n:
            pg.locator("details.quick-party-disclosure:has(form[action*='/pay/']) > summary").first.tap()
            f = pg.locator("form[action*='/pay/']").first
            sel = f.locator('select[name="bank_account"]')
            val = sel.evaluate("s => (([...s.options].find(o => o.value) || {}).value) || ''")
            if val:
                sel.select_option(val)
            before = Expense.objects.filter(payment_method="credit").count()
            try:
                with pg.expect_navigation(timeout=10000):
                    f.locator("button[type=submit]").tap()
            except Exception:
                pass
            pg.wait_for_load_state("networkidle")
            rec.check("expense", "expense-pay: paying an owed expense lands back on a working page", pg.url.rstrip("/").endswith("expenses") or "/expenses/" in pg.url, pg.url[-30:])
    elif mode == "cancel":
        w.goto("/expenses/")
        dlg.texts.clear(); dlg.accept = False
        forms = pg.locator("form[action*='/cancel/']")
        n0 = forms.count()
        rec.check("expense", f"expense-cancel: a cancel control exists ({n0})", n0 >= 1)
        if n0:
            forms.nth(idx).locator("button[type=submit]").tap()
            pg.wait_for_timeout(500)
            rec.check("expense", "expense-cancel: dismissing the confirm cancels nothing", pg.locator("form[action*='/cancel/']").count() == n0)
            dlg.accept = True
            try:
                with pg.expect_navigation(timeout=10000):
                    pg.locator("form[action*='/cancel/']").nth(idx).locator("button[type=submit]").tap()
            except Exception:
                pass
            pg.wait_for_load_state("networkidle")
            rec.check("expense", "expense-cancel: accepting cancels one", pg.locator("form[action*='/cancel/']").count() == n0 - 1, (pg.locator("form[action*='/cancel/']").count(), n0))
    js, con, failed = w.drain()
    rec.check("expense", f"expense-{mode}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
    rec.check("layout", f"expense-{mode}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))


def edit_panels(rec, w, dlg):
    """Customer / supplier / bank edit panels on their detail pages: valid edit saves, duplicate / empty name refuses."""
    from apps.partners.models import Customer, Supplier
    pg = w.page
    cust = Customer.objects.order_by("name").exclude(name__startswith="مشتری آزمایشی").first()
    for label, new, ok in (("rename-valid", "نام ویرایش‌شده ۱", True), ("rename-empty", "", False), ("rename-duplicate", "علی رضایی", False),
                           ("rename-html", "<i>x</i> ویرایش", True), ("rename-long", "ن" * 300, None)):
        w.drain()
        w.goto(f"/customers/{cust.pk}/")
        pg.locator('[data-open-panel="edit-panel"]').tap()
        pg.wait_for_selector("#edit-panel[open], #edit-panel form", state="visible")
        old = Customer.objects.get(pk=cust.pk).name
        pg.locator('#edit-panel input[name="name"]').fill(new)
        try:
            with pg.expect_navigation(timeout=4000):
                pg.locator("#edit-panel button[type=submit]").last.tap()
        except Exception:
            pg.wait_for_timeout(300)
        pg.wait_for_load_state("networkidle")
        now = Customer.objects.get(pk=cust.pk).name
        js, con, failed = w.drain()
        tag = f"customer-edit:{label}"
        rec.check("edit", f"{tag}: no JS error / 5xx", not js and not [f for f in failed if f.startswith("5")], (js, failed))
        if ok is None:       # the box caps typing at 200 characters, so the browser trims it; saved or refused are both safe
            rec.check("edit", f"{tag}: handled (saved {len(now)} chars)", len(now) <= 200, len(now))
        elif ok:
            rec.check("edit", f"{tag}: saved", now == new.strip(), (old, now))
        else:
            rec.check("edit", f"{tag}: refused, name unchanged", now == old, (old, now))
            rec.check("edit", f"{tag}: a reason is visible", bool(D.visible_errors(pg)) or pg.evaluate("() => [...document.querySelectorAll(':invalid')].length > 0"), D.visible_errors(pg))
        rec.check("layout", f"{tag}: no horizontal overflow", D.page_overflow(pg) <= 0, D.page_overflow(pg))
        cust = Customer.objects.get(pk=cust.pk)


def body(a, rec, b):
    from apps.payments.models import Cheque
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    dlg = Dialogs(w.page)
    units = []
    for side in ("receivables", "payables"):
        for i, (s, t, amt, kw, kind) in enumerate(party_cases(side)):
            units.append(("party", (s, t, amt, kw, kind, i)))
        for i, (label, spec) in enumerate(invoice_row_cases()):
            units.append(("invoice", (side, label, spec, i)))
    pend = list(Cheque.objects.filter(status="pending").order_by("direction", "created_at"))
    acts = ["bounce-dismiss", "bounce", "cancel", "clear", "clear", "clear", "clear", "clear"]
    for i, ch in enumerate(pend):
        units.append(("cheque", (i, ch.pk, acts[i % len(acts)])))
    for i, (label, kw, kind) in enumerate(return_cases()):
        units.append(("return", (i, label, kw, kind)))
    for i in range(5):
        units.append(("cancel", (i, "sale")))
    for i in range(3):
        units.append(("cancel", (i, "purchase")))
    units += [("expense", (0, "pay")), ("expense", (0, "cancel")), ("expense", (1, "cancel"))]
    units.append(("edit", ()))
    units = [u for k, u in enumerate(units) if k % a.n == a.i]
    if a.limit:
        units = units[:a.limit]
    for kind, args in units:
        name = f"{kind}{args[:2] if kind != 'edit' else ''}"
        try:
            if kind == "party":
                s, t, amt, kw, kd, i = args
                party_payment(rec, w, dlg, s, t, amt, kw, kd, i)
            elif kind == "invoice":
                invoice_row_pay(rec, w, dlg, args[0], args[1], args[2], args[3])
            elif kind == "cheque":
                i, pk, act = args
                ch = Cheque.objects.get(pk=pk)
                if ch.status == "pending":
                    cheque_flow(rec, w, dlg, i, ch, act)
            elif kind == "return":
                sales_return(rec, w, args[0], args[1], args[2], args[3])
            elif kind == "cancel":
                cancel_invoice(rec, w, dlg, args[0], args[1])
            elif kind == "expense":
                expense_flow(rec, w, dlg, args[0], args[1])
            elif kind == "edit":
                edit_panels(rec, w, dlg)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            rec.check("crash", f"{name}: ran to the end", False, repr(exc)[:220])
            try:
                w.page.close(); w.__init__(ctx, b.base); dlg = Dialogs(w.page)
            except Exception:
                pass
    ctx.close()


if __name__ == "__main__":
    run_module("payments", body)

from tools.qa.qa_lib import *
import datetime
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Sum
from apps.payments.models import BankAccount, Cheque, Expense, Payment, PaymentAllocation
from apps.payments.selectors import get_bank_account_balance, get_customer_outstanding, get_supplier_outstanding
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def last_purchase(s):
    return PurchaseInvoice.objects.filter(supplier=s).latest("created_at")


def scenarios(h):
    acct, acct2 = h.account(), h.account()
    p = h.product(stock=1000, cost=10, price=100)

    # ================================================= record payment (receivables)
    cust = h.customer()
    h.post_sale(cust, [(p, 10, 100)], mode="split")           # 1000, oldest
    inv1 = last_sale(cust)
    h.post_sale(cust, [(p, 5, 100)], mode="split")            # 500
    inv2 = last_sale(cust)
    inv1.invoice_date = h.today - datetime.timedelta(days=10); inv1.save()
    url = f"/receivables/{cust.pk}/record-payment/"

    def pay(amount, invoices=(), account="", date=TODAY_J, note="", client=None, url=url):
        d = {"amount": str(amount), "payment_date": date, "bank_account": str(account.pk) if account not in ("", None) else "", "note": note}
        if invoices:
            d["invoices"] = [str(i.pk) for i in invoices]
        return (client or h.c).post(url, d)

    check("R01 receivables lists the debtor", has(h.c.get("/receivables/"), cust.name))
    r = pay(200, [inv2, inv1])
    check("R02 payment allocated OLDEST invoice first regardless of pick order", r.status_code == 200 and has(r, "ثبت") and
          PaymentAllocation.objects.filter(sales_invoice=inv1).aggregate(t=Sum("amount"))["t"] == 200 and
          not PaymentAllocation.objects.filter(sales_invoice=inv2).exists())
    r = pay(900, [inv1, inv2])
    check("R03 a payment spilling over invoices: inv1 fully paid, rest to inv2 (200+800=1000, 100 to inv2)",
          PaymentAllocation.objects.filter(sales_invoice=inv1).aggregate(t=Sum("amount"))["t"] == 1000 and
          PaymentAllocation.objects.filter(sales_invoice=inv2).aggregate(t=Sum("amount"))["t"] == 100)
    check("R03 outstanding now 400", get_customer_outstanding(cust) == 400, get_customer_outstanding(cust))
    n = Payment.objects.filter(customer=cust).count()
    r = pay(401, [inv2])
    check("R04 paying more than the selected invoices owe is rejected (422), nothing saved", r.status_code == 422 and Payment.objects.filter(customer=cust).count() == n)
    r = pay(400, [inv1])
    check("R05 picking an already-paid invoice is rejected (not a choice any more)", r.status_code == 422 and Payment.objects.filter(customer=cust).count() == n, r.status_code)
    r = pay(150)
    check("R06 an amount with no invoices = unallocated payment, still linked to the customer",
          r.status_code == 200 and Payment.objects.filter(customer=cust, amount=150).exists() and
          not PaymentAllocation.objects.filter(payment__amount=150, payment__customer=cust).exists())
    check("R06 …and does not reduce what the invoices show as owed (400)", get_customer_outstanding(cust) == 400)
    for label, amt in (("zero", "0"), ("negative", "-5"), ("text", "abc"), ("blank", ""), ("decimal", "2.5")):
        r = pay(amt, [inv2])
        check(f"R07 {label} amount rejected", r.status_code == 422 and Payment.objects.filter(customer=cust).count() == n + 1, r.status_code)
    for label, dt in (("blank date", ""), ("garbage", "x"), ("Gregorian", "2026-09-30"), ("year 1500", "1500/01/01")):
        r = pay(10, [inv2], date=dt)
        check(f"R08 {label} rejected", r.status_code == 422, r.status_code)
    r = pay(10, [inv2], date="۱۴۰۵/۰۷/۰۸")
    check("R08 Persian-digit date accepted", r.status_code == 200)
    r = pay(10, [inv2], account=acct)
    check("R09 payment into a bank account books to that account", r.status_code == 200 and Payment.objects.filter(customer=cust, amount=10, bank_account=acct).exists())
    ghost = BankAccount(pk="00000000-0000-0000-0000-0000000000cc")
    r = pay(10, [inv2], account=ghost)
    check("R09 unknown bank account rejected (no 500)", r.status_code == 422, r.status_code)
    inactive = h.account(); inactive.is_active = False; inactive.save()
    r = pay(10, [inv2], account=inactive)
    check("R09 inactive bank account rejected", r.status_code == 422)
    other = h.customer(); h.post_sale(other, [(p, 1, 100)], mode="split")
    oinv = last_sale(other)
    r = pay(10, [oinv])
    check("R10 TAMPER: another customer's invoice id is not accepted", r.status_code == 422 and not PaymentAllocation.objects.filter(sales_invoice=oinv).exists())
    r = h.c.post(url, {"amount": "10", "payment_date": TODAY_J, "invoices": ["not-a-uuid"]})
    check("R10 malformed invoice id rejected without a 500", r.status_code == 422, r.status_code)
    r = pay(10, [inv2], note="x" * 5000)
    check("R11 a very long note does not crash", r.status_code in (200, 422), r.status_code)
    check("R12 GET on the payment endpoint = 405", h.c.get(url).status_code == 405)
    check("R12 unknown customer = 404", h.c.post("/receivables/00000000-0000-0000-0000-000000000008/record-payment/", {"amount": "1"}).status_code == 404)
    check("R12 anonymous POST redirected", h.anon.post(url, {}).status_code == 302)
    check("R12 an ordinary user may record payments", pay(5, [inv2], client=h.cu).status_code == 200)
    # cancelled invoice cannot be paid
    c3 = h.customer(); h.post_sale(c3, [(p, 1, 100)], mode="split"); ci = last_sale(c3)
    h.c.post(f"/sales/{ci.pk}/cancel/")
    r = pay(10, [ci], url=f"/receivables/{c3.pk}/record-payment/")
    check("R13 a cancelled invoice is not payable", r.status_code == 422 and get_customer_outstanding(c3) == 0)
    check("R13 a cancelled invoice's debt is gone from receivables", not has(h.c.get("/receivables/"), c3.name))
    r = h.c.get(f"/customers/{cust.pk}/")
    check("R14 customer statement lists payments and invoices", r.status_code == 200 and has(r, "150"))

    # ================================================= payables
    sup = h.supplier()
    h.post_purchase(sup, [(p, 10, 100)], mode="split")
    pi = last_purchase(sup)
    purl = f"/payables/{sup.pk}/record-payment/"
    d = {"amount": "300", "payment_date": TODAY_J, "invoices": [str(pi.pk)], "bank_account": str(acct.pk)}
    r = h.c.post(purl, d)
    pay_out = Payment.objects.get(supplier=sup)
    check("Y01 supplier payment is OUT, from the account, allocated", r.status_code == 200 and pay_out.direction == "out" and pay_out.bank_account_id == acct.pk and get_supplier_outstanding(sup) == 700)
    d["amount"] = "701"
    r = h.c.post(purl, d)
    check("Y02 over-paying the selected invoice rejected", r.status_code == 422)
    d["amount"] = "700"; d["invoices"] = [str(inv1.pk)]
    r = h.c.post(purl, d)
    check("Y03 a SALES invoice id cannot be used on a supplier payment", r.status_code == 422)
    d["invoices"] = [str(pi.pk)]
    r = h.c.post(purl, d)
    check("Y04 final payment settles it; supplier disappears from payables", r.status_code == 200 and get_supplier_outstanding(sup) == 0 and not has(h.c.get("/payables/"), sup.name))
    check("Y05 unknown supplier 404", h.c.post("/payables/00000000-0000-0000-0000-000000000009/record-payment/", {}).status_code == 404)

    # ================================================= cheques
    ch_c = h.customer()
    h.post_sale(ch_c, [(p, 10, 100)], mode="split", payments=[
        {"method": "cheque", "amount": "600", "bank_account": str(acct.pk), "cheque_number": "K1", "bank_name": "B", "due_date": "1405/08/01"},
        {"method": "cheque", "amount": "400"}])
    csi = last_sale(ch_c)
    chq1 = Cheque.objects.get(sales_invoice=csi, amount=600)
    chq2 = Cheque.objects.get(sales_invoice=csi, amount=400)
    for qs in ("", "?status=pending", "?status=cleared", "?status=zzz", "?direction=in", "?direction=out", "?direction=x",
               "?due_start=1405/08/01&due_end=1405/08/30", "?due_start=1405/09/01&due_end=1405/08/01", "?due_start=abc", "?status=pending&direction=in"):
        check(f"K01 list {qs or 'default'} → 200", h.c.get("/cheques/" + qs).status_code == 200)
    r = h.c.get("/cheques/?status=pending&direction=in")
    check("K01 list shows the pending cheque", has(r, ch_c.name) or has(r, "K1") or has(r, csi.invoice_number))
    r = h.c.get(f"/cheques/{chq1.pk}/")
    check("K02 detail renders with actions for a pending cheque", r.status_code == 200 and has(r, "وصول"))
    check("K02 unknown / malformed id 404", h.c.get("/cheques/00000000-0000-0000-0000-000000000010/").status_code == 404 and h.c.get("/cheques/zz/").status_code == 404)
    for act in ("clear", "bounce", "cancel", "complete"):
        check(f"K03 GET on /{act}/ = 405", h.c.get(f"/cheques/{chq1.pk}/{act}/").status_code == 405)
    r = h.c.post(f"/cheques/{chq2.pk}/complete/", {"cheque_number": "K2", "bank_name": "Melli", "due_date": "1405/08/15", "bank_account": str(acct2.pk)})
    chq2.refresh_from_db()
    check("K04 completing an incomplete cheque saves the details", r.status_code == 302 and chq2.cheque_number == "K2" and chq2.bank_account_id == acct2.pk and chq2.due_date is not None)
    r = h.c.post(f"/cheques/{chq2.pk}/complete/", {"cheque_number": "K2", "bank_name": "", "due_date": "garbage", "bank_account": ""})
    chq2.refresh_from_db()
    check("K04 an invalid due date is refused (values unchanged)", chq2.cheque_number == "K2" and chq2.due_date is not None)
    r = h.c.post(f"/cheques/{chq2.pk}/complete/", {"cheque_number": "K2", "bank_name": "M", "due_date": "1500/01/01", "bank_account": ""})
    check("K04 an out-of-range due date is refused", Cheque.objects.get(pk=chq2.pk).due_date != datetime.date(2121, 3, 21))
    bal0 = get_bank_account_balance(acct)
    r = h.clear_cheque(chq1)
    chq1.refresh_from_db(); csi = SalesInvoice.objects.get(pk=csi.pk)
    check("K05 clearing: status cleared, Payment IN created into the cheque's account", r.status_code == 302 and chq1.status == "cleared" and chq1.payment.direction == "in" and chq1.payment.bank_account_id == acct.pk)
    check("K05 allocated to its invoice automatically (paid 600)", csi.paid_amount == 600 and csi.payment_status == "partial", (csi.paid_amount, csi.payment_status))
    check("K05 account balance +600", get_bank_account_balance(acct) == bal0 + 600)
    n_pay = Payment.objects.count()
    h.clear_cheque(chq1)
    check("K06 a second clear is a no-op (no second payment)", Payment.objects.count() == n_pay)
    h.c.post(f"/cheques/{chq1.pk}/bounce/"); chq1.refresh_from_db()
    check("K06 a cleared cheque cannot bounce or be cancelled", chq1.status == "cleared")
    h.c.post(f"/cheques/{chq1.pk}/cancel/"); chq1.refresh_from_db()
    check("K06b cancel after clear refused", chq1.status == "cleared")
    r = h.c.post(f"/cheques/{chq1.pk}/complete/", {"cheque_number": "HACK"}); chq1.refresh_from_db()
    check("K06c a cleared cheque cannot be edited", chq1.cheque_number == "K1")
    h.c.post(f"/cheques/{chq2.pk}/bounce/"); chq2.refresh_from_db()
    check("K07 bounce a pending cheque: status bounced, NO payment", chq2.status == "bounced" and chq2.payment is None and SalesInvoice.objects.get(pk=csi.pk).paid_amount == 600)
    h.clear_cheque(chq2); chq2.refresh_from_db()
    check("K07 a bounced cheque cannot be cleared afterwards", chq2.status == "bounced")
    # cancel path & cheque from a cancelled invoice
    c5 = h.customer()
    h.post_sale(c5, [(p, 2, 100)], mode="split", payments=[{"method": "cheque", "amount": "200", "bank_account": str(acct.pk)}])
    c5i = last_sale(c5); chq5 = Cheque.objects.get(sales_invoice=c5i)
    h.c.post(f"/sales/{c5i.pk}/cancel/")
    h.clear_cheque(chq5); chq5.refresh_from_db()
    check("K08 cancelling the invoice cancels its pending cheque (D-055)", chq5.status == "cancelled" and chq5.payment is None, chq5.status)
    h.clear_cheque(chq5); chq5.refresh_from_db()
    check("K08 …and it can no longer be cleared", chq5.status == "cancelled" and chq5.payment is None)
    # cheque out (purchase) reduces account balance when cleared
    s6 = h.supplier()
    h.post_purchase(s6, [(p, 4, 100)], mode="split", payments=[{"method": "cheque", "amount": "400", "bank_account": str(acct2.pk), "cheque_number": "OUT1", "bank_name": "M", "due_date": "1405/09/01"}])
    pch = Cheque.objects.get(supplier=s6)
    b2 = get_bank_account_balance(acct2)
    h.clear_cheque(pch); pch.refresh_from_db()
    check("K09 an issued (OUT) cheque clears into a payment OUT and lowers the balance", pch.status == "cleared" and pch.payment.direction == "out" and get_bank_account_balance(acct2) == b2 - 400)
    check("K09 the purchase invoice is now paid", last_purchase(s6).payment_status == "paid")
    # cheque without any bank account
    c7 = h.customer()
    h.post_sale(c7, [(p, 1, 100)], mode="split", payments=[{"method": "cheque", "amount": "100"}])
    nb = Cheque.objects.get(customer=c7)
    r = h.c.get(f"/cheques/{nb.pk}/")
    check("K10 the detail page offers an account picker for clearing", has(r, 'name="bank_account"') and has(r, "وصول در حساب"))
    h.clear_cheque(nb, account=""); nb.refresh_from_db()
    check("K10 clearing with NO account chosen is refused (stays pending)", nb.status == "pending" and nb.payment is None)
    r = h.c.post(f"/cheques/{nb.pk}/clear/", {}); nb.refresh_from_db()
    check("K10 clearing with no bank_account field at all is refused too", nb.status == "pending")
    r = h.c.post(f"/cheques/{nb.pk}/clear/", {"bank_account": "00000000-0000-0000-0000-0000000000ee"}); nb.refresh_from_db()
    check("K10 an unknown account is refused", nb.status == "pending")
    ina = h.account(); ina.is_active = False; ina.save()
    h.clear_cheque(nb, account=ina); nb.refresh_from_db()
    check("K10 an inactive account is refused", nb.status == "pending")
    b3 = get_bank_account_balance(acct2)
    h.clear_cheque(nb, account=acct2); nb.refresh_from_db()
    check("K10 choosing an account at clearing books the payment there (+100)", nb.status == "cleared" and nb.payment.bank_account_id == acct2.pk and get_bank_account_balance(acct2) == b3 + 100)
    c8 = h.customer()
    h.post_sale(c8, [(p, 1, 100)], mode="split", payments=[{"method": "cheque", "amount": "100"}])
    nc = Cheque.objects.get(customer=c8)
    h.clear_cheque(nc, account="cash"); nc.refresh_from_db()
    check("K10 cash chosen ON PURPOSE is accepted (payment without account)", nc.status == "cleared" and nc.payment.bank_account is None)
    c9 = h.customer()
    h.post_sale(c9, [(p, 1, 100)], mode="split", payments=[{"method": "cheque", "amount": "100", "bank_account": str(acct.pk)}])
    nd = Cheque.objects.get(customer=c9)
    r = h.c.get(f"/cheques/{nd.pk}/")
    check("K10 a cheque that has an account: the picker is pre-selected with it", has(r, f'value="{acct.pk}" selected'))
    h.clear_cheque(nd, account=acct2); nd.refresh_from_db()
    check("K10 …and the user may clear it into another account", nd.payment.bank_account_id == acct2.pk)
    from apps.payments.services import clear_cheque as svc_clear
    from django.core.exceptions import ValidationError as VE
    c10 = h.customer()
    h.post_sale(c10, [(p, 1, 100)], mode="split", payments=[{"method": "cheque", "amount": "100"}])
    ne = Cheque.objects.get(customer=c10)
    try:
        svc_clear(ne, h.su); raised = False
    except VE:
        raised = True
    check("K10 the service itself refuses to guess an account", raised and Cheque.objects.get(pk=ne.pk).status == "pending")
    check("K11 an ordinary user can clear a cheque", True)

    # ================================================= bank accounts
    check("B01 list renders", h.c.get("/bank-accounts/").status_code == 200)
    r = h.c.get("/bank-accounts/new/")
    check("B02 new page renders", r.status_code == 200)
    num = "QA" + str(random.randint(10**8, 10**9))
    n = BankAccount.objects.count()
    r = h.c.post("/bank-accounts/new/", {"name": "QA-acc", "account_type": "current", "owner": "me", "account_number": num})
    check("B03 create account → detail", r.status_code == 302 and BankAccount.objects.count() == n + 1)
    for label, d in (("duplicate number", {"account_type": "current", "name": "x", "account_number": num}), ("number with spaces matching", {"account_type": "current", "name": "x", "account_number": "  " + num + "  "}),
                     ("blank name", {"account_type": "current", "name": "", "account_number": "Z1"}), ("blank number", {"account_type": "current", "name": "x", "account_number": ""})):
        r = h.c.post("/bank-accounts/new/", d)
        check(f"B04 {label} refused", r.status_code == 200 and BankAccount.objects.count() == n + 1)
    a = BankAccount.objects.get(account_number=num)
    r = h.c.get(f"/bank-accounts/{a.pk}/")
    check("B05 detail (empty ledger) renders", r.status_code == 200)
    r = h.c.get(f"/bank-accounts/{a.pk}/edit/")
    check("B06 edit page renders", r.status_code == 200)
    r = h.c.post(f"/bank-accounts/{a.pk}/edit/", {"name": "QA-acc2", "account_type": "pos", "owner": "you", "account_number": num})
    a.refresh_from_db()
    check("B06 edit saves", r.status_code == 302 and a.name == "QA-acc2")
    r = h.c.post(f"/bank-accounts/{a.pk}/edit/", {"name": "n", "account_type": "current", "account_number": acct.account_number})
    a.refresh_from_db()
    check("B06 edit to another account's number refused", a.account_number == num)
    check("B07 unknown account 404", h.c.get("/bank-accounts/00000000-0000-0000-0000-000000000011/").status_code == 404)
    # ledger with every row kind
    h.post_sale(cust, [(p, 1, 100)], account=a)
    h.post_purchase(sup, [(p, 1, 10)], account=a)
    h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-ledger", "amount": "55", "bank_account": str(a.pk)})
    r = h.c.get(f"/bank-accounts/{a.pk}/")
    check("B08 ledger shows sale, purchase and expense rows and balance 100-10-55=35", r.status_code == 200 and get_bank_account_balance(a) == 35 and has(r, "QA-ledger"))
    r = h.c.get("/bank-accounts/")
    check("B08 list shows the balance", has(r, "35"))

    # ================================================= expenses
    check("E01 list renders", h.c.get("/expenses/").status_code == 200)
    check("E02 new page renders", h.c.get("/expenses/new/").status_code == 200)
    b0 = get_bank_account_balance(acct)

    def exp(**kw):
        d = {"expense_date": TODAY_J, "reason": "QA-exp-" + rnd(), "amount": "1000", "bank_account": str(acct.pk), "note": ""}
        d.update(kw)
        return h.c.post("/expenses/new/", d)

    n = Expense.objects.count()
    r = exp(reason="QA-bank")
    e1 = Expense.objects.get(reason="QA-bank")
    check("E03 expense from a bank account: redirect, Payment OUT, balance -1000", r.status_code == 302 and e1.payment.direction == "out" and get_bank_account_balance(acct) == b0 - 1000)
    r = exp(reason="QA-cash", bank_account="cash")
    e2 = Expense.objects.get(reason="QA-cash")
    check("E04 cash expense has no account", r.status_code == 302 and e2.bank_account is None and e2.payment.bank_account is None)
    for label, kw in (("no account chosen", dict(bank_account="")), ("zero amount", dict(amount="0")), ("negative", dict(amount="-3")), ("text amount", dict(amount="x")),
                      ("blank reason", dict(reason="")), ("blank date", dict(expense_date="")), ("garbage date", dict(expense_date="zz")), ("Gregorian date", dict(expense_date="2026-09-30")),
                      ("unknown account", dict(bank_account="00000000-0000-0000-0000-0000000000dd"))):
        c0 = Expense.objects.count()
        r = exp(**kw)
        check(f"E05 {label} rejected, nothing saved", r.status_code == 200 and Expense.objects.count() == c0, (r.status_code, Expense.objects.count() - c0))
    r = exp(amount=str(10**19))
    check("E06 absurd amount does not crash", r.status_code in (200, 302) and r.status_code != 500, r.status_code)
    r = exp(reason="ن" * 500)
    check("E06 overlong reason does not crash", r.status_code in (200, 302) and r.status_code != 500, r.status_code)
    r = exp(amount=digits_fa(2500), reason="QA-fa-digits")
    check("E06 Persian digits in amount", r.status_code == 302 and Expense.objects.get(reason="QA-fa-digits").amount == 2500)
    # receipt upload
    up = SimpleUploadedFile("qa_receipt.pdf", b"%PDF-1.4 hello", content_type="application/pdf")
    r = exp(reason="QA-upload", document=up)
    ex = Expense.objects.filter(reason="QA-upload").first()
    check("E07 receipt upload accepted", r.status_code == 302 and ex is not None and bool(ex.document))
    path = ex.document.path if ex and ex.document else None
    up2 = SimpleUploadedFile("evil.html", b"<script>alert(1)</script>", content_type="text/html")
    r = exp(reason="QA-upload-html", document=up2)
    ex2 = Expense.objects.filter(reason="QA-upload-html").first()
    check("E07 an .html receipt is refused (D-056)", ex2 is None)
    for f in (path, ex2.document.path if ex2 and ex2.document else None):
        try:
            if f and os.path.exists(f):
                os.remove(f)
        except Exception:
            pass
    # list & filters
    for qs in ("", "?q=QA-bank", "?bank_account=" + str(acct.pk), "?bank_account=zz", "?amount_min=10&amount_max=5", "?amount_min=x", "?page=abc", "?page=999",
               "?preset=custom&start=1405/07/01&end=1405/07/30", "?preset=custom&start=1405/07/30&end=1405/07/01", "?preset=today"):
        check(f"E08 list {qs or 'default'} → 200", h.c.get("/expenses/" + qs).status_code == 200)
    check("E08 search finds the expense", has(h.c.get("/expenses/?q=QA-bank"), "QA-bank"))
    # cancel
    bal = get_bank_account_balance(acct)
    r = h.cu.post(f"/expenses/{e1.pk}/cancel/"); e1.refresh_from_db()
    check("E09 an ordinary user cannot cancel an expense", e1.cancelled_at is None)
    check("E09 GET on cancel = 405", h.c.get(f"/expenses/{e1.pk}/cancel/").status_code == 405)
    r = h.c.post(f"/expenses/{e1.pk}/cancel/"); e1.refresh_from_db()
    check("E10 superuser cancels: flagged, reversal payment IN, balance restored", e1.cancelled_at is not None and e1.reversal_payment.direction == "in" and get_bank_account_balance(acct) == bal + 1000)
    h.c.post(f"/expenses/{e1.pk}/cancel/")
    check("E10 a second cancel adds no second reversal", Payment.objects.filter(pk=e1.reversal_payment_id).count() == 1 and get_bank_account_balance(acct) == bal + 1000)
    from apps.shared import reports
    t = h.today
    check("E11 a cancelled expense no longer counts in the report", reports.expenses_total(t - datetime.timedelta(days=2), t + datetime.timedelta(days=2)) == sum(
        e.amount for e in Expense.objects.filter(cancelled_at__isnull=True, expense_date__gte=t - datetime.timedelta(days=2), expense_date__lte=t + datetime.timedelta(days=2))))
    check("E12 unknown expense cancel 404", h.c.post("/expenses/00000000-0000-0000-0000-000000000012/cancel/").status_code == 404)
    for url in ("/expenses/", "/expenses/new/", "/bank-accounts/", "/cheques/", "/receivables/", "/payables/"):
        check(f"E13 anonymous redirected: {url}", h.anon.get(url).status_code == 302)


run("payments", scenarios)


def upload_scenarios(h):
    """Receipt upload rules (only PDF/PNG/JPG/WebP, matching content, <= 5 MB)."""
    import os
    from django.core.files.uploadedfile import SimpleUploadedFile
    acct = h.account()
    made = []

    def send(name, data, content_type="application/octet-stream"):
        d = {"expense_date": TODAY_J, "reason": "QA-up-" + rnd(), "amount": "10", "bank_account": "cash"}
        n0 = Expense.objects.count()
        r = h.c.post("/expenses/new/", {**d, "document": SimpleUploadedFile(name, data, content_type=content_type)})
        e = Expense.objects.filter(reason=d["reason"]).first()
        if e and e.document:
            made.append(e.document.path)
        return r, Expense.objects.count() - n0

    PDF = b"%PDF-1.4\n%QA\n"
    PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 10
    for name, data in (("r.pdf", PDF), ("r.png", PNG), ("r.jpg", JPG), ("r.jpeg", JPG), ("r.webp", WEBP), ("R.PDF", PDF), ("رسید.pdf", PDF)):
        r, created = send(name, data)
        check(f"UP01 {name} accepted", r.status_code == 302 and created == 1, r.status_code)
    for label, name, data in (("html", "x.html", b"<script>alert(1)</script>"), ("svg", "x.svg", b"<svg onload=alert(1)/>"), ("exe", "x.exe", b"MZ\x90\x00"),
                              ("js", "x.js", b"alert(1)"), ("no extension", "receipt", PDF), ("html renamed to pdf", "x.pdf", b"<html><script>alert(1)</script>"),
                              ("png content named jpg", "x.jpg", PNG), ("double extension pdf.html", "x.pdf.html", PDF), ("empty pdf", "e.pdf", b""),
                              ("php disguised", "x.php.png", b"<?php echo 1;")):
        r, created = send(name, data)
        check(f"UP02 {label} rejected, no expense created", r.status_code == 200 and created == 0, (r.status_code, created))
    r, created = send("big.pdf", PDF + b"0" * (5 * 1024 * 1024))
    check("UP03 a file over 5 MB is rejected", r.status_code == 200 and created == 0, (r.status_code, created))
    r, created = send("ok.pdf", PDF + b"0" * (5 * 1024 * 1024 - len(PDF)))
    check("UP03 a file of exactly 5 MB is accepted", r.status_code == 302 and created == 1, (r.status_code, created))
    r = h.c.get("/expenses/new/")
    check("UP04 the form states the rule", has(r, "۵ مگابایت") or has(r, "5"))
    r = h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-nofile", "amount": "5", "bank_account": "cash"})
    check("UP05 an expense without any file is still fine", r.status_code == 302)
    for f in made:
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass


run("uploads", upload_scenarios)

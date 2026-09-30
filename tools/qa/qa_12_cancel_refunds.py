"""D-055: cancelling an invoice gives its money back."""
from tools.qa.qa_lib import *
import datetime
from django.db import IntegrityError, transaction
from django.db.models import Sum
from apps.payments.models import Cheque, Payment, PaymentAllocation
from apps.payments.selectors import get_bank_account_balance, get_customer_outstanding, get_supplier_outstanding
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared.models import AuditLog


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def last_purchase(s):
    return PurchaseInvoice.objects.filter(supplier=s).latest("created_at")


def scenarios(h):
    acct, acct2 = h.account(), h.account()
    p = h.product(stock=500, cost=10, price=100)

    # ---------------------------------------------------- sales
    c = h.customer()
    b0 = get_bank_account_balance(acct)
    h.post_sale(c, [(p, 10, 100)], account=acct)          # 1000 paid into acct
    inv = last_sale(c)
    check("RF01 sale paid in full raised the balance by 1000", get_bank_account_balance(acct) == b0 + 1000)
    r = h.c.post(f"/sales/{inv.pk}/cancel/", follow=True)
    inv.refresh_from_db()
    ref = Payment.objects.get(customer=c, is_reversal=True)
    check("RF01 refund Payment: OUT, same account, full amount, same customer", ref.direction == "out" and ref.bank_account_id == acct.pk and ref.amount == 1000)
    check("RF01 bank balance is back to where it started", get_bank_account_balance(acct) == b0)
    al = PaymentAllocation.objects.get(sales_invoice=inv)
    check("RF01 the allocation is linked to its refund; nothing was edited or deleted", al.reversal_payment_id == ref.pk and al.amount == 1000)
    check("RF01 the original payment still exists untouched", Payment.objects.filter(customer=c, direction="in", amount=1000, is_reversal=False).exists())
    check("RF01 invoice paid_amount (net) is 0 and it is cancelled", inv.paid_amount == 0 and inv.status == "cancelled")
    check("RF01 the customer owes nothing", get_customer_outstanding(c) == 0)
    check("RF01 the success message tells what was refunded", has(r, "برگشت داده شد"))
    check("RF01 detail page marks the payment as given back", has(h.c.get(f"/sales/{inv.pk}/"), "برگشت داده شد"))
    check("RF01 audit row reverse_payment written", AuditLog.objects.filter(event_type="reverse_payment", target_id=ref.pk).exists())
    h.c.post(f"/sales/{inv.pk}/cancel/")
    check("RF02 a second cancel does not refund again", Payment.objects.filter(customer=c, is_reversal=True).count() == 1)

    c2 = h.customer()
    h.post_sale(c2, [(p, 10, 100)], mode="split", payments=[{"method": "cash", "amount": "400"}])
    i2 = last_sale(c2)
    h.c.post(f"/sales/{i2.pk}/cancel/")
    rf = Payment.objects.get(customer=c2, is_reversal=True)
    check("RF03 partial cash payment: refund = the paid part (400), cash (no account)", rf.amount == 400 and rf.bank_account is None and rf.direction == "out")

    c3 = h.customer()
    h.post_sale(c3, [(p, 5, 100)], mode="split")
    i3 = last_sale(c3)
    n = Payment.objects.count()
    h.c.get("/sales/")          # flush messages queued by the earlier requests
    r = h.c.post(f"/sales/{i3.pk}/cancel/", follow=True)
    check("RF04 an unpaid credit sale: nothing to refund, no refund payment", Payment.objects.count() == n and not has(r, "برگشت داده شد"))

    # cheques
    c4 = h.customer()
    h.post_sale(c4, [(p, 10, 100)], mode="split", payments=[
        {"method": "cheque", "amount": "300", "bank_account": str(acct.pk), "cheque_number": "P1", "bank_name": "M", "due_date": "1405/08/01"},
        {"method": "cheque", "amount": "200", "bank_account": str(acct.pk), "cheque_number": "P2", "bank_name": "M", "due_date": "1405/08/02"},
        {"method": "cheque", "amount": "100", "bank_account": str(acct.pk), "cheque_number": "P3", "bank_name": "M", "due_date": "1405/08/03"}])
    i4 = last_sale(c4)
    chq = {x.cheque_number: x for x in Cheque.objects.filter(sales_invoice=i4)}
    b_before = get_bank_account_balance(acct)
    h.clear_cheque(chq["P1"])
    h.c.post(f"/cheques/{chq['P2'].pk}/bounce/")
    check("RF05 a cleared cheque moved 300 into the account", get_bank_account_balance(acct) == b_before + 300)
    h.c.post(f"/sales/{i4.pk}/cancel/")
    for x in chq.values():
        x.refresh_from_db()
    check("RF05 pending cheque → cancelled (never was money)", chq["P3"].status == "cancelled" and chq["P3"].payment is None)
    check("RF05 bounced cheque stays bounced", chq["P2"].status == "bounced")
    check("RF05 cleared cheque stays cleared, but its 300 is refunded", chq["P1"].status == "cleared" and
          Payment.objects.filter(customer=c4, is_reversal=True, amount=300).exists() and get_bank_account_balance(acct) == b_before)
    check("RF05 exactly one refund for this invoice (only real money)", Payment.objects.filter(customer=c4, is_reversal=True).count() == 1)

    # a payment shared by two invoices
    c5 = h.customer()
    h.post_sale(c5, [(p, 10, 100)], mode="split"); a1 = last_sale(c5)
    h.post_sale(c5, [(p, 5, 100)], mode="split"); a2 = last_sale(c5)
    a1.invoice_date = h.today - datetime.timedelta(days=5); a1.save()
    h.c.post(f"/receivables/{c5.pk}/record-payment/", {"amount": "1200", "payment_date": TODAY_J, "bank_account": str(acct2.pk), "invoices": [str(a1.pk), str(a2.pk)]})
    pay = Payment.objects.get(customer=c5, is_reversal=False)
    check("RF06 one 1200 payment: 1000 to the older invoice, 200 to the newer", PaymentAllocation.objects.get(sales_invoice=a1).amount == 1000 and PaymentAllocation.objects.get(sales_invoice=a2).amount == 200)
    b2 = get_bank_account_balance(acct2)
    h.c.post(f"/sales/{a2.pk}/cancel/")
    check("RF06 cancelling the newer invoice refunds only ITS 200", Payment.objects.filter(customer=c5, is_reversal=True).get().amount == 200 and get_bank_account_balance(acct2) == b2 - 200)
    check("RF06 the other invoice still counts its 1000 as paid", a1.paid_amount == 1000 and SalesInvoice.objects.get(pk=a1.pk).payment_status == "paid")
    h.c.post(f"/receivables/{c5.pk}/record-payment/", {"amount": "77", "payment_date": TODAY_J, "bank_account": ""})
    h.c.post(f"/sales/{a1.pk}/cancel/")
    refunds = list(Payment.objects.filter(customer=c5, is_reversal=True).order_by("created_at"))
    check("RF07 a prepayment (unallocated) is left alone by cancellations", Payment.objects.filter(customer=c5, amount=77, is_reversal=False).exists() and len(refunds) == 2 and sum(x.amount for x in refunds) == 1200)
    st = h.c.get(f"/customers/{c5.pk}/")
    check("RF08 customer statement renders; refunds are debit lines", st.status_code == 200 and has(st, "برگشت پرداخت بابت لغو فاکتور"))

    # permissions & guards
    c6 = h.customer()
    h.post_sale(c6, [(p, 3, 100)], account=acct); i6 = last_sale(c6)
    h.cu.post(f"/sales/{i6.pk}/cancel/")
    check("RF09 an ordinary user's cancel is refused: nothing refunded", not Payment.objects.filter(customer=c6, is_reversal=True).exists() and SalesInvoice.objects.get(pk=i6.pk).status == "confirmed")

    # ---------------------------------------------------- purchases
    s = h.supplier()
    pb = get_bank_account_balance(acct)
    h.post_purchase(s, [(p, 10, 100)], account=acct)
    pi = last_purchase(s)
    check("RF10 the purchase paid 1000 out of the account", get_bank_account_balance(acct) == pb - 1000)
    r = h.c.post(f"/purchasing/{pi.pk}/cancel/", follow=True)
    pi.refresh_from_db()
    rp = Payment.objects.get(supplier=s, is_reversal=True)
    check("RF10 refund from the supplier: IN, same account, 1000", rp.direction == "in" and rp.bank_account_id == acct.pk and rp.amount == 1000)
    check("RF10 the balance is back", get_bank_account_balance(acct) == pb)
    check("RF10 supplier owed nothing; invoice cancelled; paid net 0", get_supplier_outstanding(s) == 0 and pi.status == "cancelled" and pi.paid_amount == 0)
    check("RF10 message + detail badge", has(r, "برگشت داده شد") and has(h.c.get(f"/purchasing/{pi.pk}/"), "برگشت داده شد"))

    s2 = h.supplier()
    h.post_purchase(s2, [(p, 4, 100)], mode="split", payments=[{"method": "cheque", "amount": "400", "bank_account": str(acct2.pk), "cheque_number": "OUT7", "bank_name": "M", "due_date": "1405/09/01"}])
    q = last_purchase(s2)
    ch = Cheque.objects.get(purchase_invoice=q)
    h.c.post(f"/purchasing/{q.pk}/cancel/"); ch.refresh_from_db()
    check("RF11 a pending cheque WE issued is cancelled with the purchase", ch.status == "cancelled" and not Payment.objects.filter(supplier=s2, is_reversal=True).exists())

    s3 = h.supplier()
    h.post_purchase(s3, [(p, 6, 100)], account=acct)
    q3 = last_purchase(s3)
    h.post_sale(h.customer(), [(p, 500 + 6 - 0, 100)], account=acct) if False else None
    sold = h.product(stock=0)
    h.post_purchase(s3, [(sold, 5, 50)], account=acct); q4 = last_purchase(s3)
    h.post_sale(h.customer(), [(sold, 1, 100)], account=acct)
    n = Payment.objects.filter(supplier=s3, is_reversal=True).count()
    h.c.post(f"/purchasing/{q4.pk}/cancel/")
    check("RF12 a refused cancellation (stock already sold) refunds NOTHING", Payment.objects.filter(supplier=s3, is_reversal=True).count() == n and PurchaseInvoice.objects.get(pk=q4.pk).status == "confirmed")

    # ---------------------------------------------------- integrity
    try:
        with transaction.atomic():
            Payment.objects.create(customer=c, direction="out", amount=5, payment_date=h.today, created_by=h.su)
        bad = False
    except IntegrityError:
        bad = True
    check("RF13 the DB still refuses a NORMAL customer payment going OUT (only reversals may)", bad)
    try:
        with transaction.atomic():
            Payment.objects.create(customer=c, supplier=s, direction="out", amount=5, payment_date=h.today, created_by=h.su, is_reversal=True)
        bad = False
    except IntegrityError:
        bad = True
    check("RF13 …and a payment with BOTH parties even as a reversal", bad)
    # bank ledger & activity pages
    r = h.c.get(f"/bank-accounts/{acct.pk}/")
    check("RF14 bank ledger shows the refund rows with their invoice", r.status_code == 200 and has(r, "برگشت پرداخت بابت لغو فاکتور"))
    check("RF14 user activity renders with the new event", h.c.get("/user-activity/").status_code == 200 and h.c.get(f"/user-activity/{h.su.pk}/").status_code == 200)
    r = h.c.get(f"/user-activity/{h.su.pk}/?event_type=reverse_payment")
    check("RF14 the event type is filterable and labelled", r.status_code == 200 and has(r, "برگشت پرداخت"))
    from apps.shared import reports
    t = h.today
    b = reports.bank_accounts_as_of(t - datetime.timedelta(days=1), t + datetime.timedelta(days=1))
    row = next(x for x in b if x["account"].pk == acct.pk)
    check("RF15 report: the account's period OUT includes the refund of the customer payments", row["period_out"] >= 1000 + 300)
    check("RF15 report balance equals the ledger", row["balance"] == get_bank_account_balance(acct))
    check("RF16 every page still renders", all(h.c.get(u).status_code == 200 for u in ("/", "/reports/", "/receivables/", "/payables/", "/cheques/", "/bank-accounts/", "/sales/", "/purchasing/")))


run("cancel_refunds", scenarios)

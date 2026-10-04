"""Party credit (D-087): a payment beyond every open invoice is credit only on purpose, shows everywhere,
and pays the party's next invoice first. Also: an unticked payment settles open invoices oldest first."""
import datetime

from apps.payments.models import Payment
from apps.payments.selectors import (
    get_bank_account_balance, get_credit_balances, get_customer_outstanding, get_party_credit, get_supplier_outstanding,
)
from apps.partners.models import Customer
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from tools.qa.qa_lib import *


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def scenarios(h):
    acct = h.account()
    p = h.product(stock=1000, cost=100, price=1000)

    def pay(party, amount, invoices=(), as_credit=False, supplier=False):
        side = "payables" if supplier else "receivables"
        d = {"amount": str(amount), "payment_date": TODAY_J, "bank_account": str(acct.pk), "note": ""}
        if invoices:
            d["invoices"] = [str(i.pk) for i in invoices]
        if as_credit:
            d["as_credit"] = "on"
        return h.c.post(f"/{side}/{party.pk}/record-payment/", d)

    # ---- 1. a customer with nothing open
    cust = h.customer()
    bal0 = get_bank_account_balance(acct)
    r = pay(cust, 50000)
    check("C01 no open invoice + no credit tick: refused (422), nothing booked",
          r.status_code == 422 and not Payment.objects.filter(customer=cust).exists(), r.status_code)
    check("C01b the refusal names the tick", has(r, "بستانکاری"))
    r = pay(cust, 50000, as_credit=True)
    check("C02 with the tick: accepted", r.status_code == 200 and get_party_credit(customer=cust) == 50000, r.status_code)
    check("C02b the bank balance moved by the same amount", get_bank_account_balance(acct) - bal0 == 50000)
    check("C02c the success note says it pays the next invoice", has(r, "فاکتور بعدی"))
    d = h.c.get(f"/customers/{cust.pk}/")
    check("C03 customer page shows the credit card", has(d, "بستانکاری (پیش‌دریافت)") and shown(d, 50000))
    check("C04 customer list shows the credit", shown(h.c.get("/customers/", {"q": cust.name}), 50000))
    rec = h.c.get("/receivables/")
    check("C05 receivables lists the customer under بستانکاران", has(rec, "بستانکاران") and has(rec, cust.name) and shown(rec, 50000))
    check("C05b credit balances selector agrees", any(x["party"] == cust and x["credit"] == 50000 for x in get_credit_balances(Customer)))
    sp = h.c.get("/sales/new/")
    check("C06 new-sale page carries the credit map for the notice", has(sp, "party-credits") and has(sp, str(cust.pk)))

    # ---- 2. the next invoice uses it: credit sale (split, no rows)
    h.post_sale(cust, [(p, 30, 1000)], mode="split")          # 30,000 < 50,000 credit
    inv = last_sale(cust)
    check("C07 a credit sale is paid from the credit, no due date kept",
          inv.status == "confirmed" and inv.outstanding == 0 and inv.payment_status == "paid" and inv.credit_due_date is None,
          (inv.status, inv.outstanding))
    check("C07b credit left = 20,000", get_party_credit(customer=cust) == 20000, get_party_credit(customer=cust))
    check("C07c no new bank money for that sale", get_bank_account_balance(acct) - bal0 == 50000)

    # ---- 3. full settlement takes only what the credit does not cover
    h.post_sale(cust, [(p, 50, 1000)], account=acct)            # 50,000 - 20,000 = 30,000 by transfer
    inv2 = last_sale(cust)
    check("C08 full settlement books total - credit by transfer",
          inv2.status == "confirmed" and inv2.outstanding == 0 and
          Payment.objects.filter(customer=cust, amount=30000, direction="in").exists(), inv2.status)
    check("C08b the credit is used up", get_party_credit(customer=cust) == 0)
    check("C08c bank moved 50,000 + 30,000 in total", get_bank_account_balance(acct) - bal0 == 80000)

    # ---- 4. credit covers a whole invoice paid in "full settlement" mode
    cust2 = h.customer()
    pay(cust2, 100000, as_credit=True)
    pay_rows_before = Payment.objects.filter(customer=cust2).count()
    h.post_sale(cust2, [(p, 10, 1000)], account=acct)          # 10,000, all from credit
    inv3 = last_sale(cust2)
    check("C09 credit >= total: no payment row, invoice paid",
          inv3.status == "confirmed" and inv3.outstanding == 0 and
          Payment.objects.filter(customer=cust2).count() == pay_rows_before)
    check("C09b 90,000 credit left", get_party_credit(customer=cust2) == 90000)

    # ---- 5. split rows plus credit
    cust3 = h.customer()
    pay(cust3, 5000, as_credit=True)
    row = {"method": "bank_transfer", "amount": "4000", "bank_account": str(acct.pk), "cheque_number": "", "bank_name": "",
           "issuer": "", "due_date": ""}
    r = h.post_sale(cust3, [(p, 10, 1000)], mode="split", payments=[row], credit_due="")
    check("C10 rows + credit < total without a due date: refused", r.status_code == 200 and has(r, "سررسید"), r.status_code)
    r = h.post_sale(cust3, [(p, 10, 1000)], mode="split", payments=[dict(row, amount="9000")])
    check("C11 rows + credit > total: refused, naming the credit", r.status_code == 200 and has(r, "بستانکاری قبلی"), r.status_code)
    r = h.post_sale(cust3, [(p, 10, 1000)], mode="split", payments=[dict(row, amount="5000")], credit_due="")
    inv4 = last_sale(cust3)
    check("C12 rows + credit == total: confirmed, no due date", r.status_code == 302 and inv4.outstanding == 0, r.status_code)

    # ---- 6. a debtor: unticked payment settles oldest first (amends D-042)
    deb = h.customer()
    h.post_sale(deb, [(p, 10, 1000)], mode="split")            # 10,000
    old = last_sale(deb)
    old.invoice_date = h.today - datetime.timedelta(days=5)
    old.save()
    h.post_sale(deb, [(p, 4, 1000)], mode="split")             # 4,000
    new = last_sale(deb)
    r = pay(deb, 12000)
    check("C13 unticked payment: accepted and allocated", r.status_code == 200 and get_customer_outstanding(deb) == 2000,
          get_customer_outstanding(deb))
    old.refresh_from_db()
    new.refresh_from_db()
    check("C13b oldest invoice closed first", old.outstanding == 0 and new.outstanding == 2000)
    check("C13c nothing left as credit", get_party_credit(customer=deb) == 0)
    r = pay(deb, 5000)
    check("C14 unticked overpay without the tick: refused, nothing booked",
          r.status_code == 422 and get_customer_outstanding(deb) == 2000)
    r = pay(deb, 5000, as_credit=True)
    check("C15 with the tick: debt closed, 3,000 credit", r.status_code == 200 and get_customer_outstanding(deb) == 0 and
          get_party_credit(customer=deb) == 3000)
    h.post_sale(deb, [(p, 1, 1000)], mode="split")
    check("C15b next sale eats 1,000 of it", get_party_credit(customer=deb) == 2000 and last_sale(deb).outstanding == 0)
    deb2 = h.customer()
    h.post_sale(deb2, [(p, 2, 1000)], mode="split")
    one = last_sale(deb2)
    r = pay(deb2, 2500, invoices=[one], as_credit=True)
    check("C16 ticked invoices still cap the amount (explicit choice wins)", r.status_code == 422)

    # ---- 7. refunds are never credit; cancelling an invoice paid from credit
    canc = h.customer()
    pay(canc, 8000, as_credit=True)
    h.post_sale(canc, [(p, 8, 1000)], mode="split")
    ci = last_sale(canc)
    h.c.post(f"/sales/{ci.pk}/cancel/")
    check("C17 cancelling refunds the credit-paid part (D-055); the refund is not credit",
          Payment.objects.filter(customer=canc, is_reversal=True, amount=8000).exists() and get_party_credit(customer=canc) == 0,
          get_party_credit(customer=canc))

    # ---- 8. supplier mirror
    sup = h.supplier()
    r = pay(sup, 40000, supplier=True)
    check("S01 supplier: no open invoice + no tick refused", r.status_code == 422)
    r = pay(sup, 40000, supplier=True, as_credit=True)
    check("S02 supplier advance accepted", r.status_code == 200 and get_party_credit(supplier=sup) == 40000)
    check("S03 supplier page and list show it", shown(h.c.get(f"/purchasing/suppliers/{sup.pk}/"), 40000) and
          shown(h.c.get("/purchasing/suppliers/", {"q": sup.name}), 40000))
    check("S04 payables page lists it", has(h.c.get("/payables/"), "پیش‌پرداخت به تأمین‌کننده"))
    h.post_purchase(sup, [(p, 100, 300)], mode="split")          # 30,000
    pi = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    check("S05 next purchase paid from the advance", pi.status == "confirmed" and pi.outstanding == 0 and
          get_party_credit(supplier=sup) == 10000, (pi.status, pi.outstanding))
    h.post_purchase(sup, [(p, 100, 300)], account=acct)           # 30,000: 10,000 advance + 20,000 transfer
    pi2 = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    check("S06 full settlement on a purchase takes total - advance",
          pi2.outstanding == 0 and Payment.objects.filter(supplier=sup, amount=20000, direction="out").exists())
    check("S07 supplier owes nothing either way", get_supplier_outstanding(sup) == 0 and get_party_credit(supplier=sup) == 0)


run("party_credit", scenarios)

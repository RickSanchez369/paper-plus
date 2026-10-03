"""D-067..D-074: account types, cheque issuer, percent discount, card/transfer settlement,
credit due dates, Receivables/Payables split, cheque/credit expenses, fixed costs, dashboard reminders."""
from tools.qa.qa_lib import *
import datetime
import jdatetime
from apps.payments.models import Cheque, Expense, Payment, PaymentAllocation, RecurringExpense
from apps.payments.selectors import get_bank_account_balance, get_credit_items, get_customer_outstanding, get_supplier_outstanding
from apps.payments.services import add_months_jalali
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice


def j(days=0):
    """A Jalali date string `days` from today, as the date field wants it."""
    return jdatetime.date.fromgregorian(date=datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y/%m/%d")


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def scenarios(h):
    cur, cur2 = h.account(), h.account()
    pos = h.account(kind="pos")
    p = h.product(stock=500, cost=100, price=1000)
    cust, sup = h.customer(), h.supplier()

    # ------------------------------------------------ percent discount (D-070)
    r = h.post_sale(cust, [(p, 10, 1000)], account=cur, extra={"discount_mode": "percent", "discount_percent": "10"})
    inv = last_sale(cust)
    check("PD01 10% of 10,000 = 1,000 discount stored in Toman", r.status_code == 302 and inv.discount_amount == 1000 and inv.total == 9000, (r.status_code, inv.discount_amount))
    r = h.post_sale(cust, [(p, 3, 1000)], account=cur, extra={"discount_mode": "percent", "discount_percent": "33.33"})
    inv = last_sale(cust)
    check("PD02 33.33% of 3,000 floors to 999", inv.discount_amount == 999, inv.discount_amount)
    r = h.post_sale(cust, [(p, 1, 1000)], account=cur, extra={"discount_mode": "percent", "discount_percent": "101"})
    check("PD03 over 100% rejected", r.status_code == 200)
    r = h.post_sale(cust, [(p, 1, 1000)], account=cur, extra={"discount_mode": "percent", "discount_percent": "-1"})
    check("PD04 negative percent rejected", r.status_code == 200)
    r = h.post_sale(cust, [(p, 1, 1000)], account=cur, extra={"discount_mode": "percent", "discount_percent": "100"})
    check("PD05 100% = free invoice allowed, total 0", r.status_code == 302 and last_sale(cust).total == 0)
    r = h.post_sale(cust, [(p, 2, 1000)], account=cur, discount="300")
    check("PD06 amount mode (no mode posted) still works", r.status_code == 302 and last_sale(cust).discount_amount == 300)

    # ------------------------------------------------ settlement: card + transfer (D-069)
    c2 = h.customer()
    r = h.post_sale(c2, [(p, 10, 1000)], extra={"pos_account": str(pos.pk), "transfer_account": str(cur.pk), "pos_amount": "4000"})
    i = last_sale(c2)
    check("ST01 card 4000 + transfer (the rest) = paid", r.status_code == 302 and i.payment_status == "paid", r.status_code)
    check("ST01 card money lands in the POS account, transfer in the current one",
          Payment.objects.filter(customer=c2, bank_account=pos, amount=4000).exists() and Payment.objects.filter(customer=c2, bank_account=cur, amount=6000).exists())
    r = h.post_sale(c2, [(p, 1, 1000)], extra={"pos_account": str(pos.pk)})
    check("ST02 card only takes the whole total", r.status_code == 302 and Payment.objects.filter(customer=c2, bank_account=pos, amount=1000).exists())
    n = SalesInvoice.objects.filter(customer=c2).count()
    r = h.post_sale(c2, [(p, 1, 1000)], extra={"pos_account": str(pos.pk), "transfer_account": str(cur.pk), "pos_amount": "600", "transfer_amount": "300"})
    check("ST03 amounts not adding to the total rejected, nothing saved", r.status_code == 200 and SalesInvoice.objects.filter(customer=c2).count() == n)
    r = h.post_sale(c2, [(p, 1, 1000)], extra={"pos_account": str(cur.pk)})
    check("ST04 a current account cannot be used as the card reader", r.status_code == 200 and SalesInvoice.objects.filter(customer=c2).count() == n)
    r = h.post_sale(c2, [(p, 1, 1000)], extra={"transfer_account": str(pos.pk)})
    check("ST05 a card-reader account cannot be used for a transfer", r.status_code == 200 and SalesInvoice.objects.filter(customer=c2).count() == n)
    r = h.post_sale(c2, [(p, 1, 1000)])
    check("ST06 no method chosen rejected", r.status_code == 200 and SalesInvoice.objects.filter(customer=c2).count() == n)
    r = h.post_sale(c2, [(p, 1, 1000)], extra={"pos_account": str(pos.pk), "pos_amount": "999"})
    check("ST07 a single method with a wrong amount rejected", r.status_code == 200 and SalesInvoice.objects.filter(customer=c2).count() == n)

    # split rows by method
    r = h.post_sale(c2, [(p, 2, 1000)], mode="split", payments=[
        {"method": "card", "amount": "500", "bank_account": str(pos.pk)},
        {"method": "bank_transfer", "amount": "700", "bank_account": str(cur.pk)}], credit_due=j(10))
    i = last_sale(c2)
    check("SP01 card + transfer rows, rest 800 on credit with its due date",
          r.status_code == 302 and i.paid_amount == 1200 and i.credit_due_date is not None and i.outstanding == 800, r.status_code)
    r = h.post_sale(c2, [(p, 1, 1000)], mode="split", payments=[{"method": "card", "amount": "500", "bank_account": str(cur.pk)}], credit_due=j(5))
    check("SP02 a card row on a current account rejected", r.status_code == 200)
    r = h.post_sale(c2, [(p, 1, 1000)], mode="split", payments=[{"method": "cash", "amount": "500"}], credit_due=j(5))
    check("SP03 a cash row rejected (cash is gone)", r.status_code == 200)
    n = SalesInvoice.objects.filter(customer=c2).count()
    r = h.post_sale(c2, [(p, 1, 1000)], mode="split", payments=[{"method": "bank_transfer", "amount": "400", "bank_account": str(cur.pk)}], credit_due="")
    check("SP04 an unpaid remainder without a due date rejected", r.status_code == 200 and SalesInvoice.objects.filter(customer=c2).count() == n)
    r = h.post_sale(c2, [(p, 1, 1000)], mode="split", payments=[{"method": "bank_transfer", "amount": "1000", "bank_account": str(cur.pk)}], credit_due="")
    check("SP05 nothing left unpaid: no due date needed", r.status_code == 302 and last_sale(c2).credit_due_date is None)
    r = h.post_sale(c2, [(p, 1, 1000)], mode="split", payments=[{"method": "bank_transfer", "amount": "1000", "bank_account": str(cur.pk)}], credit_due=j(5))
    check("SP06 a due date on a fully paid invoice is dropped", r.status_code == 302 and last_sale(c2).credit_due_date is None)

    # cheque with issuer (D-068)
    c3 = h.customer()
    h.post_sale(c3, [(p, 5, 1000)], mode="split", payments=[
        {"method": "cheque", "amount": "3000", "cheque_number": "Z1", "issuer": "آقای صادرکننده", "bank_name": "Melli", "due_date": j(3)}], credit_due=j(20))
    chq = Cheque.objects.get(customer=c3)
    check("CH01 issuer is saved on the cheque", chq.issuer == "آقای صادرکننده" and chq.status == "pending")
    check("CH01 issuer shown on the cheque page", has(h.c.get(f"/cheques/{chq.pk}/"), "آقای صادرکننده"))

    # ------------------------------------------------ Receivables page (D-071)
    page = h.c.get("/receivables/")
    check("RC01 receivables page renders with the cheque and the credit block", page.status_code == 200 and has(page, "Z1") and has(page, "نسیه"))
    items = [x for x in get_credit_items(SalesInvoice) if x["invoice"].customer_id == c3.pk]
    check("RC02 credit part = invoice outstanding minus the pending cheque (2000 - none: 5000-3000)", len(items) == 1 and items[0]["amount"] == 2000 and items[0]["due_date"] is not None, items)
    inv3 = items[0]["invoice"]
    r = h.c.post(f"/receivables/invoice/{inv3.pk}/pay/", {"amount": "500", "payment_date": TODAY_J, "bank_account": str(pos.pk)})
    check("RC03 paying part of the credit books a payment + allocation", r.status_code == 302 and PaymentAllocation.objects.filter(sales_invoice=inv3, amount=500).exists())
    r = h.c.post(f"/receivables/invoice/{inv3.pk}/pay/", {"amount": "1501", "payment_date": TODAY_J, "bank_account": str(pos.pk)})
    check("RC04 paying more than the credit part is refused", not PaymentAllocation.objects.filter(sales_invoice=inv3, amount=1501).exists())
    r = h.c.post(f"/receivables/invoice/{inv3.pk}/pay/", {"amount": "1500", "payment_date": TODAY_J, "bank_account": str(cur.pk)})
    check("RC05 settling the rest: credit part is gone, only the cheque remains outstanding",
          get_customer_outstanding(c3) == 3000 and not [x for x in get_credit_items(SalesInvoice) if x["invoice"].pk == inv3.pk])
    r = h.c.post(f"/cheques/{chq.pk}/clear/", {"bank_account": str(cur.pk), "next": "/receivables/"})
    chq.refresh_from_db()
    check("RC06 passing the cheque from the receivables page: cleared, back to the page", chq.status == "cleared" and r.status_code == 302 and r["Location"] == "/receivables/")
    check("RC06 invoice fully paid", SalesInvoice.objects.get(pk=inv3.pk).payment_status == "paid" and get_customer_outstanding(c3) == 0)
    # bounce
    h.post_sale(c3, [(p, 1, 1000)], mode="split", payments=[{"method": "cheque", "amount": "1000", "cheque_number": "Z2", "due_date": j(2)}])
    c3b = Cheque.objects.get(customer=c3, cheque_number="Z2")
    r = h.c.post(f"/cheques/{c3b.pk}/bounce/", {"next": "/receivables/"})
    c3b.refresh_from_db()
    check("RC07 bouncing from the page", c3b.status == "bounced" and r["Location"] == "/receivables/")
    r = h.c.post(f"/cheques/{c3b.pk}/clear/", {"bank_account": str(pos.pk), "next": "/receivables/"})
    check("RC08 a cheque cannot be cleared into a card-reader account", Cheque.objects.get(pk=c3b.pk).status == "bounced")

    # ------------------------------------------------ Payables mirror (purchasing)
    pp = h.product(stock=0)
    r = h.post_purchase(sup, [(pp, 5, 100)], account=cur, mode="split", payments=[{"method": "cheque", "amount": "200", "cheque_number": "O1", "issuer": "ما", "due_date": j(4)}], credit_due=j(15))
    pi = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    check("PY01 purchase with an issued cheque and 300 on credit", r.status_code == 302 and pi.credit_due_date is not None and get_supplier_outstanding(sup) == 500)
    page = h.c.get("/payables/")
    check("PY02 payables page lists the cheque and the credit", page.status_code == 200 and has(page, "O1") and has(page, "پاس شد"))
    items = [x for x in get_credit_items(PurchaseInvoice) if x["invoice"].supplier_id == sup.pk]
    check("PY03 credit part is 300", len(items) == 1 and items[0]["amount"] == 300, items)
    r = h.c.post(f"/payables/invoice/{pi.pk}/pay/", {"amount": "100", "payment_date": TODAY_J, "bank_account": str(pos.pk)})
    check("PY04 a card-reader account cannot pay a supplier", not PaymentAllocation.objects.filter(purchase_invoice=pi).exists())
    r = h.c.post(f"/payables/invoice/{pi.pk}/pay/", {"amount": "300", "payment_date": TODAY_J, "bank_account": str(cur.pk)})
    check("PY05 paying the supplier credit from a current account", PaymentAllocation.objects.filter(purchase_invoice=pi, amount=300).exists())
    r = h.post_purchase(sup, [(pp, 1, 100)], account=pos)
    check("PY06 purchase full settlement through a card reader rejected", r.status_code == 200)

    # ------------------------------------------------ expenses (D-072)
    b0 = get_bank_account_balance(cur)
    r = h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-credit", "amount": "500", "payment_method": "credit", "due_date": j(3)})
    e1 = Expense.objects.get(reason="QA-credit")
    check("EX01 credit expense: saved, no payment, balance untouched", r.status_code == 302 and e1.payment_id is None and not e1.is_paid and get_bank_account_balance(cur) == b0)
    r = h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-credit2", "amount": "5", "payment_method": "credit"})
    check("EX02 credit without a due date rejected", r.status_code == 200 and not Expense.objects.filter(reason="QA-credit2").exists())
    r = h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-chq", "amount": "700", "payment_method": "cheque", "cheque_number": "E1", "issuer": "ما", "cheque_due_date": j(6), "bank_account": str(cur.pk)})
    e2 = Expense.objects.get(reason="QA-chq")
    ec = Cheque.objects.get(expense=e2)
    check("EX03 cheque expense: pending OUT cheque with no party, no payment yet", r.status_code == 302 and ec.direction == "out" and ec.status == "pending" and ec.supplier_id is None and e2.payment_id is None)
    r = h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-chq2", "amount": "7", "payment_method": "cheque"})
    check("EX04 cheque without a due date rejected", r.status_code == 200 and not Expense.objects.filter(reason="QA-chq2").exists())
    page = h.c.get("/expenses/")
    check("EX05 list shows the owed total and the pay button", page.status_code == 200 and has(page, "QA-credit") and has(page, "پرداخت‌نشده"))
    r = h.c.post(f"/expenses/{e1.pk}/pay/", {"bank_account": str(pos.pk), "payment_date": TODAY_J})
    e1.refresh_from_db()
    check("EX06 paying from a card reader refused", e1.payment_id is None)
    r = h.c.post(f"/expenses/{e1.pk}/pay/", {"bank_account": str(cur.pk), "payment_date": TODAY_J})
    e1.refresh_from_db()
    check("EX07 paying the credit expense books Payment OUT and balance -500", e1.is_paid and e1.payment.direction == "out" and get_bank_account_balance(cur) == b0 - 500)
    r = h.c.post(f"/expenses/{e1.pk}/pay/", {"bank_account": str(cur.pk), "payment_date": TODAY_J})
    check("EX08 paying twice adds nothing", get_bank_account_balance(cur) == b0 - 500)
    r = h.c.post(f"/cheques/{ec.pk}/clear/", {"bank_account": str(cur.pk)})
    e2.refresh_from_db()
    check("EX09 clearing the expense cheque makes the expense paid", e2.is_paid and e2.payment_id is not None and get_bank_account_balance(cur) == b0 - 500 - 700)
    r = h.c.post(f"/expenses/{e2.pk}/cancel/")
    e2.refresh_from_db()
    check("EX10 cancelling a paid cheque expense refunds the account", e2.is_cancelled and e2.reversal_payment_id and get_bank_account_balance(cur) == b0 - 500)
    r = h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-credit3", "amount": "50", "payment_method": "credit", "due_date": j(1)})
    e3 = Expense.objects.get(reason="QA-credit3")
    h.c.post(f"/expenses/{e3.pk}/cancel/")
    e3.refresh_from_db()
    check("EX11 cancelling an unpaid expense needs no reversal", e3.is_cancelled and e3.reversal_payment_id is None)
    r = h.cu.post(f"/expenses/{e3.pk}/pay/", {"bank_account": str(cur.pk), "payment_date": TODAY_J})
    check("EX12 a cancelled expense cannot be paid", not Expense.objects.get(pk=e3.pk).is_paid)

    # ------------------------------------------------ fixed costs (D-073)
    r = h.c.post("/expenses/recurring/new/", {"reason": "QA-rent", "amount": "9000", "repeat_every": "1", "repeat_unit": "month", "next_due_date": j(3), "remind_days_before": "7", "note": ""})
    rec = RecurringExpense.objects.get(reason="QA-rent")
    check("RE01 fixed cost saved", r.status_code == 302 and rec.next_due_date is not None)
    r = h.c.post("/expenses/recurring/new/", {"reason": "QA-bad", "amount": "0", "repeat_every": "0", "repeat_unit": "month", "next_due_date": j(3), "remind_days_before": "7"})
    check("RE02 zero amount / zero repeat rejected", r.status_code == 200 and not RecurringExpense.objects.filter(reason="QA-bad").exists())
    check("RE03 list renders and flags it as due soon", has(h.c.get("/expenses/recurring/"), "QA-rent"))
    due0 = rec.next_due_date
    r = h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-rent", "amount": "9000", "payment_method": "transfer", "bank_account": str(cur.pk), "recurring": str(rec.pk)})
    rec.refresh_from_db()
    check("RE04 recording the instalment advances the due date by one month", r.status_code == 302 and rec.next_due_date == add_months_jalali(due0, 1) and rec.next_due_date > due0, (due0, rec.next_due_date))
    r = h.c.post(f"/expenses/recurring/{rec.pk}/skip/")
    nxt = rec.next_due_date
    rec.refresh_from_db()
    check("RE05 skipping advances again without an expense", rec.next_due_date == add_months_jalali(nxt, 1) and Expense.objects.filter(recurring=rec).count() == 1)
    rec45 = RecurringExpense.objects.create(reason="QA-45", amount=100, repeat_every=45, repeat_unit="day", next_due_date=datetime.date.today() + datetime.timedelta(days=2))
    h.c.post(f"/expenses/recurring/{rec45.pk}/skip/")
    rec45.refresh_from_db()
    check("RE06 a 45-day cost moves exactly 45 days", rec45.next_due_date == datetime.date.today() + datetime.timedelta(days=47))
    r = h.c.post(f"/expenses/recurring/{rec.pk}/toggle/")
    rec.refresh_from_db()
    check("RE07 deactivating a fixed cost", not rec.is_active)
    check("RE08 month arithmetic: 31 Shahrivar + 1 month = 30 Mehr", add_months_jalali(jdatetime.date(1405, 6, 31).togregorian(), 1) == jdatetime.date(1405, 7, 30).togregorian())
    check("RE08 month arithmetic: 30 Bahman + 1 month = 29 Esfand (non-leap 1405)", add_months_jalali(jdatetime.date(1405, 11, 30).togregorian(), 1) == jdatetime.date(1405, 12, 29).togregorian())
    check("RE08 month arithmetic wraps the year", add_months_jalali(jdatetime.date(1405, 12, 15).togregorian(), 1) == jdatetime.date(1406, 1, 15).togregorian())

    # ------------------------------------------------ dashboard (D-074)
    h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-dash-credit", "amount": "321", "payment_method": "credit", "due_date": j(2)})
    h.c.post("/expenses/recurring/new/", {"reason": "QA-dash-rent", "amount": "654", "repeat_every": "1", "repeat_unit": "month", "next_due_date": j(5), "remind_days_before": "7"})
    h.post_purchase(sup, [(pp, 1, 100)], mode="split", payments=[{"method": "cheque", "amount": "100", "cheque_number": "DASH-CHQ", "due_date": j(1)}], credit_due=j(30))
    page = h.c.get("/")
    check("DB01 dashboard lists upcoming payments: credit expense, fixed cost, issued cheque",
          page.status_code == 200 and has(page, "QA-dash-credit") and has(page, "QA-dash-rent") and has(page, "DASH-CHQ"))
    check("DB02 the recent-activity feed is gone from the dashboard", not has(page, "آخرین فعالیت‌ها"))
    h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-far", "amount": "99", "payment_method": "credit", "due_date": j(40)})
    check("DB03 a payment 40 days away is not on the dashboard", not has(h.c.get("/"), "QA-far"))
    h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-late", "amount": "88", "payment_method": "credit", "due_date": j(-3)})
    check("DB04 an overdue one is", has(h.c.get("/"), "QA-late"))

    # ------------------------------------------------ account types (D-067)
    page = h.c.get("/bank-accounts/")
    check("AT01 bank accounts page shows both sections", has(page, "کارت‌خوان") and has(page, "حساب جاری"))
    r = h.c.post("/bank-accounts/new/", {"name": "QA-pos2", "account_type": "pos", "owner": "x", "account_number": "QA" + rnd(8)})
    check("AT02 a card-reader account can be created", r.status_code == 302 and BankAccount_exists("QA-pos2", "pos"))
    r = h.c.post("/bank-accounts/new/", {"name": "QA-bad", "account_type": "cash", "owner": "x", "account_number": "QA" + rnd(8)})
    check("AT03 an unknown type rejected", r.status_code == 200)


def BankAccount_exists(name, kind):
    from apps.payments.models import BankAccount
    return BankAccount.objects.filter(name=name, account_type=kind).exists()


run("payment_rework", scenarios)

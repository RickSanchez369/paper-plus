"""Sales and purchase returns (D-089): stock back through FIFO, money off the invoice first, then refund or credit."""
import datetime

from django.core.exceptions import ValidationError

from apps.inventory.models import InventoryLayer, InventoryMovement
from apps.payments.models import Payment
from apps.payments.selectors import (
    get_bank_account_balance, get_customer_outstanding, get_party_credit, get_supplier_outstanding,
)
from apps.purchasing.models import PurchaseInvoice
from apps.returns.models import PurchaseReturn, SalesReturn, SettleMode
from apps.returns.services import record_purchase_return, record_sales_return, returnable_lines
from apps.sales.models import SalesInvoice
from apps.shared import reports
from tools.qa.qa_lib import *


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ValidationError as exc:
        return "؛ ".join(exc.messages)
    return None


def scenarios(h):
    acct = h.account()
    pos = h.account(kind="pos")
    today = h.today
    p = h.product(stock=100, cost=600, price=1000, pack_per_carton=10)

    # ---------------------------------------------------------------- sales: credit sale, partial return
    cust = h.customer()
    h.post_sale(cust, [h.carton_row(p, 2, 5, carton_price=9000, unit_price=1000)], mode="split")   # 25 packs: 18,000 + 5,000
    inv = last_sale(cust)
    item = inv.items.get()
    stock0 = h.stock(p)
    check("R00 sale confirmed, 23,000 owed", inv.status == "confirmed" and inv.outstanding == 23000, (inv.status, inv.outstanding))
    r = record_sales_return(inv, [(item, 0, 5)], today, SettleMode.CREDIT, h.su)
    check("R01 return number issued, 5 packs", r.return_number and r.items.get().quantity == 5)
    check("R02 value = 5/25 of the line's net (23,000) = 4,600", r.total_amount == 4600, r.total_amount)
    check("R03 stock back +5", h.stock(p) == stock0 + 5)
    layer = InventoryLayer.objects.get(sales_return_item=r.items.get())
    check("R04 a sales-return layer at the line's FIFO cost per pack (600)", layer.unit_cost == 600 and layer.quantity_remaining == 5)
    check("R05 movement of type sales_return on the sold line",
          InventoryMovement.objects.filter(movement_type="sales_return", sale_item=item, quantity=5).exists())
    inv.refresh_from_db()
    check("R06 the open debt drops by the return (credit note), no bank money", inv.outstanding == 18400 and r.applied_amount == 4600
          and Payment.objects.filter(customer=cust, is_credit_note=True, bank_account__isnull=True, amount=4600).exists())
    check("R07 nothing left as credit", get_party_credit(customer=cust) == 0 and r.credit_amount == 0)
    check("R08 the original line is untouched (D-014)", item.quantity == 25 and inv.total == 23000)
    rows = returnable_lines(inv)
    check("R09 returnable lines say 20 left", rows[0]["left"] == 20 and rows[0]["returned"] == 5)
    msg = refused(record_sales_return, inv, [(item, 3, 0)], today, SettleMode.CREDIT, h.su)
    check("R10 cannot return more than is left (3 cartons = 30 > 20)", msg and "حداکثر" in msg, msg)
    msg = refused(record_sales_return, inv, [(item, 0, 0)], today, SettleMode.CREDIT, h.su)
    check("R11 an empty return is refused", msg is not None)
    msg = refused(record_sales_return, inv, [(item, 0, 1)], today - datetime.timedelta(days=400), SettleMode.CREDIT, h.su)
    check("R12 a return dated before the invoice is refused", msg is not None)

    # the rest, in two goes: the shares add up to the whole line exactly
    record_sales_return(inv, [(item, 1, 3)], today, SettleMode.CREDIT, h.su)    # 13 packs
    r3 = record_sales_return(inv, [(item, 0, 7)], today, SettleMode.CREDIT, h.su)
    total_back = sum(x.total_amount for x in SalesReturn.objects.filter(invoice=inv))
    check("R13 returning a line in pieces adds up to exactly its net total", total_back == 23000, total_back)
    inv.refresh_from_db()
    check("R14 fully returned credit sale owes nothing, no credit", inv.outstanding == 0 and get_party_credit(customer=cust) == 0)
    msg = refused(record_sales_return, inv, [(item, 0, 1)], today, SettleMode.CREDIT, h.su)
    check("R15 nothing left to return", msg and "حداکثر 0" in msg, msg)

    # ---------------------------------------------------------------- sales: paid sale, surplus refunded
    c2 = h.customer()
    h.post_sale(c2, [(p, 10, 1000)], account=acct)               # paid 10,000 by transfer
    inv2 = last_sale(c2)
    bal = get_bank_account_balance(acct)
    msg = refused(record_sales_return, inv2, [(inv2.items.get(), 0, 4)], today, SettleMode.REFUND, h.su)
    check("R16 a refund needs an account", msg and "حساب" in msg, msg)
    msg = refused(record_sales_return, inv2, [(inv2.items.get(), 0, 4)], today, SettleMode.REFUND, h.su, bank_account=pos)
    check("R17 a card reader cannot pay a refund", msg and "کارت‌خوان" in msg, msg)
    r4 = record_sales_return(inv2, [(inv2.items.get(), 0, 4)], today, SettleMode.REFUND, h.su, bank_account=acct)
    check("R18 paid invoice: nothing to take off, 4,000 refunded from the account",
          r4.applied_amount == 0 and r4.refund_amount == 4000 and get_bank_account_balance(acct) == bal - 4000)
    check("R19 the refund is a reversal payment, not credit",
          r4.refund_payment.is_reversal and r4.refund_payment.direction == "out" and get_party_credit(customer=c2) == 0)
    # ... or kept as credit
    r5 = record_sales_return(inv2, [(inv2.items.get(), 0, 2)], today, SettleMode.CREDIT, h.su)
    check("R20 surplus kept as credit shows as the customer's credit", r5.credit_amount == 2000 and get_party_credit(customer=c2) == 2000)
    h.post_sale(c2, [(p, 3, 1000)], mode="split")
    check("R21 …and pays the next invoice first (D-087)", last_sale(c2).outstanding == 1000 and get_party_credit(customer=c2) == 0)

    # ---------------------------------------------------------------- sales: partly paid + pending cheque
    c3 = h.customer()
    cheque_row = {"method": "cheque", "amount": "6000", "bank_account": str(acct.pk), "cheque_number": "77",
                  "bank_name": "ملی", "issuer": "x", "due_date": TODAY_J}
    h.post_sale(c3, [(p, 10, 1000)], mode="split", payments=[cheque_row])   # 6,000 cheque pending, 4,000 credit
    inv3 = last_sale(c3)
    r6 = record_sales_return(inv3, [(inv3.items.get(), 0, 6)], today, SettleMode.CREDIT, h.su)  # 6,000
    check("R22 only the credit part (4,000) comes off; the cheque's part stays open, 2,000 credit",
          r6.applied_amount == 4000 and r6.credit_amount == 2000, (r6.applied_amount, r6.credit_amount))
    from apps.payments.models import Cheque
    ch = Cheque.objects.get(sales_invoice=inv3)
    resp = h.clear_cheque(ch, account=acct)
    ch.refresh_from_db()
    check("R23 the pending cheque can still clear afterwards", ch.status == "cleared", (resp.status_code, ch.status))

    # ---------------------------------------------------------------- cancel guard and pages
    msg = refused(__import__("apps.sales.services", fromlist=["cancel_sale"]).cancel_sale, inv2, h.su)
    check("R24 an invoice with a return cannot be cancelled", msg and "مرجوعی" in msg, msg)
    st = h.c.get(f"/customers/{c2.pk}/")
    check("R25 customer statement lists the return, not the credit note", has(st, "مرجوعی فروش") and st.status_code == 200)

    # ---------------------------------------------------------------- reports: booked on the return date
    s0 = reports.sales_returns_total(today, today)
    check("R26 sales returns total for today includes these returns", s0 >= 23000 + 4000 + 2000 + 6000, s0)
    cards = reports.summary_cards(today, today)
    check("R27 net profit = gross - profit given back - freight lost on purchase returns - expenses (D-101)",
          cards["net_profit"]["value"] == cards["gross_profit"]["value"] - cards["returns_profit"]["value"]
          - cards["purchase_returns_loss"]["value"] - cards["expenses"]["value"])

    # ---------------------------------------------------------------- purchases
    sup = h.supplier()
    q = h.product(stock=0, price=1000, pack_per_carton=10)
    h.post_purchase(sup, [h.carton_row(q, 3, 0, carton_price=5000)], mode="split")    # 30 packs, 15,000 owed
    pi = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
    pitem = pi.items.get()
    check("P00 purchase confirmed, 15,000 owed", pi.status == "confirmed" and get_supplier_outstanding(sup) == 15000)
    h.post_sale(h.customer(), [(q, 25, 2000)], account=acct)                           # 25 sold, 5 left on the shelf
    msg = refused(record_purchase_return, pi, [(pitem, 1, 0)], today, SettleMode.CREDIT, h.su)
    check("P01 cannot send back more than is still on the shelf from that purchase", msg and "مانده" in msg, msg)
    pr = record_purchase_return(pi, [(pitem, 0, 4)], today, SettleMode.CREDIT, h.su)
    check("P02 4 packs back: 4/30 of 15,000 = 2,000 off the debt", pr.total_amount == 2000 and pr.applied_amount == 2000
          and get_supplier_outstanding(sup) == 13000, (pr.total_amount, get_supplier_outstanding(sup)))
    check("P03 stock -4, layer drawn down by a consumption",
          h.stock(q) == 1 and InventoryLayer.objects.get(purchase_item=pitem).quantity_remaining == 1)
    check("P04 movement purchase_return", InventoryMovement.objects.filter(movement_type="purchase_return", purchase_item=pitem).exists())
    # paid purchase, refund from supplier into our account
    sup2 = h.supplier()
    h.post_purchase(sup2, [(q, 10, 500)], account=acct)                                # paid 5,000
    pi2 = PurchaseInvoice.objects.filter(supplier=sup2).latest("created_at")
    bal = get_bank_account_balance(acct)
    pr2 = record_purchase_return(pi2, [(pi2.items.get(), 0, 2)], today, SettleMode.REFUND, h.su, bank_account=acct)
    check("P05 the supplier pays 1,000 back into our account", pr2.refund_amount == 1000 and get_bank_account_balance(acct) == bal + 1000
          and pr2.refund_payment.direction == "in" and pr2.refund_payment.is_reversal)
    pr3 = record_purchase_return(pi2, [(pi2.items.get(), 0, 2)], today, SettleMode.CREDIT, h.su)
    check("P06 or it stays as our advance with the supplier", get_party_credit(supplier=sup2) == 1000 and pr3.credit_amount == 1000)
    msg = refused(__import__("apps.purchasing.services", fromlist=["cancel_purchase"]).cancel_purchase, pi2, h.su)
    check("P07 a purchase with a return cannot be cancelled", msg and "مرجوعی" in msg, msg)


    # ---------------------------------------------------------------- pages
    c9 = h.customer()
    h.post_sale(c9, [(p, 6, 1000)], mode="split")
    inv9 = last_sale(c9)
    it9 = inv9.items.get()
    r = h.c.get(f"/returns/sales/new/{inv9.pk}/")
    check("V01 new sales-return page renders the line with what is left", r.status_code == 200 and has(r, p.name) and has(r, "قابل مرجوع"))
    r = h.c.post(f"/returns/sales/new/{inv9.pk}/", {"return_date": TODAY_J, "settle_mode": "credit", f"packs_{it9.pk}": "9"})
    check("V02 too many packs: 422 with the reason, nothing saved", r.status_code == 422 and has(r, "حداکثر") and not inv9.returns.exists())
    r = h.c.post(f"/returns/sales/new/{inv9.pk}/", {"return_date": TODAY_J, "settle_mode": "refund", f"packs_{it9.pk}": "2"})
    check("V03 refund without an account: 422", r.status_code == 422 and not inv9.returns.exists())
    r = h.c.post(f"/returns/sales/new/{inv9.pk}/", {"return_date": TODAY_J, "settle_mode": "credit", f"packs_{it9.pk}": "۲"})
    doc = inv9.returns.first()
    check("V04 Persian digits accepted; redirects to the return", r.status_code == 302 and doc and doc.total_amount == 2000)
    check("V05 detail page renders", has(h.c.get(f"/returns/sales/{doc.pk}/"), "مرجوعی فروش"))
    lst = h.c.get("/returns/")
    check("V06 list shows it", lst.status_code == 200 and has(lst, doc.return_number))
    check("V07 list search by invoice number", has(h.c.get("/returns/", {"q": inv9.invoice_number}), doc.return_number))
    d = h.c.get(f"/sales/{inv9.pk}/")
    check("V08 invoice page: return button and the return listed, no cancel button", has(d, "ثبت مرجوعی") and has(d, doc.return_number)
          and not has(d, "cancel-dialog"))
    pv = h.c.get(f"/sales/{inv9.pk}/print/")
    check("V09 print shows the return in the payment box", has(pv, "مرجوعی"))
    r = h.c.get(f"/returns/purchases/new/{pi2.pk}/")
    check("V10 new purchase-return page renders", r.status_code == 200 and has(r, "مرجوعی از فاکتور"))
    check("V11 purchase list tab", h.c.get("/returns/?kind=purchase").status_code == 200)
    check("V12 anonymous is sent to sign in", h.anon.get("/returns/").status_code == 302)
    rep = h.c.get("/reports/")
    check("V13 reports show the returns card", rep.status_code == 200 and has(rep, "مرجوعی‌ها"))


run("returns", scenarios)

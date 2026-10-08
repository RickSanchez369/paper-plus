"""Returns v2 (D-101): damaged goods + damage deduction, cancelling a return, freight loss, pending-cheque warning, date limit."""
import datetime

from django.core.exceptions import ValidationError

from apps.inventory.models import InventoryLayer, InventoryMovement
from apps.payments.models import Cheque, Payment
from apps.payments.selectors import (
    get_bank_account_balance, get_customer_outstanding, get_party_credit, get_supplier_outstanding,
)
from apps.purchasing.models import PurchaseInvoice
from apps.returns.models import ItemCondition, PurchaseReturn, SalesReturn, SettleMode
from apps.returns.services import (
    cancel_purchase_return, cancel_sales_return, record_purchase_return, record_sales_return, returnable_lines,
)
from apps.sales.models import SalesInvoice
from apps.sales.services import cancel_sale
from apps.shared import reports
from tools.qa.qa_lib import *

DAMAGED, RESALABLE = ItemCondition.DAMAGED, ItemCondition.RESALABLE


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def last_purchase(s):
    return PurchaseInvoice.objects.filter(supplier=s).latest("created_at")


def refused(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except ValidationError as exc:
        return "؛ ".join(exc.messages)
    return None


def scenarios(h):
    acct = h.account()
    today = h.today
    p = h.product(stock=200, cost=600, price=1000, pack_per_carton=10)

    # ---------------------------------------------------------------- damaged goods + deduction
    c1 = h.customer()
    h.post_sale(c1, [(p, 10, 1000)], account=acct)                      # paid 10,000 by transfer; cost 6,000
    inv1 = last_sale(c1)
    it1 = inv1.items.get()
    stock0, bal0 = h.stock(p), get_bank_account_balance(acct)
    layers0 = InventoryLayer.objects.filter(product=p).count()
    d = record_sales_return(inv1, [(it1, 0, 4, DAMAGED, 500)], today, SettleMode.REFUND, h.su, bank_account=acct)
    row = d.items.get()
    check("DM01 a damaged line: value 4,000, deduction 500, the customer is credited 3,500",
          row.amount == 4000 and row.deduction == 500 and d.total_amount == 3500 and d.gross_amount == 4000, (row.amount, d.total_amount))
    check("DM02 damaged goods never enter stock (no layer, no movement)",
          h.stock(p) == stock0 and InventoryLayer.objects.filter(product=p).count() == layers0
          and not InventoryMovement.objects.filter(movement_type="sales_return", sale_item=it1).exists())
    check("DM03 3,500 is refunded from the account", d.refund_amount == 3500 and get_bank_account_balance(acct) == bal0 - 3500)
    check("DM04 cost back on the shelf is 0; the damaged cost (2,400) is a loss; profit given back = what was credited",
          d.cost_amount == 0 and d.damaged_cost == 2400 and d.profit_given_back == 3500, (d.cost_amount, d.damaged_cost, d.profit_given_back))
    msg = refused(record_sales_return, inv1, [(it1, 0, 2, RESALABLE, 5000)], today, SettleMode.CREDIT, h.su)
    check("DM05 a deduction above the line's value is refused", msg and "کسر خسارت" in msg, msg)
    msg = refused(record_sales_return, inv1, [(it1, 0, 2, RESALABLE, -5)], today, SettleMode.CREDIT, h.su)
    check("DM06 a negative deduction is refused", msg is not None)
    msg = refused(record_sales_return, inv1, [(it1, 0, 2, "broken")], today, SettleMode.CREDIT, h.su)
    check("DM07 an unknown condition is refused", msg and "وضعیت" in msg, msg)
    r_ok = record_sales_return(inv1, [(it1, 0, 2, RESALABLE, 0)], today, SettleMode.CREDIT, h.su)
    check("DM08 a resalable line puts the packs back as before (+2) at the line's cost",
          h.stock(p) == stock0 + 2 and r_ok.cost_amount == 1200 and r_ok.damaged_cost == 0 and r_ok.profit_given_back == 800)
    check("DM09 the packs left to return count both returns (10 - 4 - 2 = 4)", returnable_lines(inv1)[0]["left"] == 4)
    check("DM10 reports: net profit takes the damaged line's loss through profit given back",
          reports.returns_profit(today, today) >= 3500 + 800)

    # ---------------------------------------------------------------- remaining value: exact even after a cancellation
    c2 = h.customer()
    h.post_sale(c2, [(p, 7, 143)], mode="split")                       # 1,001 owed
    inv2 = last_sale(c2)
    it2 = inv2.items.get()
    ra = record_sales_return(inv2, [(it2, 0, 3)], today, SettleMode.CREDIT, h.su)
    rb = record_sales_return(inv2, [(it2, 0, 2)], today, SettleMode.CREDIT, h.su)
    cancel_sales_return(ra, h.su)
    rc = record_sales_return(inv2, [(it2, 0, 5)], today, SettleMode.CREDIT, h.su)
    active = sum(x.total_amount for x in SalesReturn.objects.filter(invoice=inv2, status="active"))
    check("RV01 after cancelling one piece, returning the rest still adds up to exactly the line (1,001)", active == 1001, active)

    # ---------------------------------------------------------------- cancel a sales return (credit sale, credit-note path)
    c3 = h.customer()
    h.post_sale(c3, [(p, 25, 1000)], mode="split")                     # 25,000 owed
    inv3 = last_sale(c3)
    it3 = inv3.items.get()
    s0 = h.stock(p)
    ret = record_sales_return(inv3, [(it3, 0, 5)], today, SettleMode.CREDIT, h.su)
    inv3.refresh_from_db()
    check("CN00 setup: 5 packs back, 5,000 off the invoice", ret.total_amount == 5000 and inv3.outstanding == 20000 and h.stock(p) == s0 + 5)
    sums0 = reports.sales_returns_total(today, today)
    msg = refused(cancel_sales_return, ret, h.user)
    check("CN01 only a superuser can cancel", msg and "ابرکاربر" in msg and ret.status == "active", msg)
    done = cancel_sales_return(ret, h.su)
    inv3.refresh_from_db()
    ret.refresh_from_db()
    check("CN02 cancelled: status, who and when are recorded", done.status == "cancelled" and ret.cancelled_by_id == h.su.pk and ret.cancelled_at)
    check("CN03 the invoice owes its 5,000 again and no credit is left",
          inv3.outstanding == 25000 and get_party_credit(customer=c3) == 0 and get_customer_outstanding(c3) == 25000)
    check("CN04 the goods leave the shelf again (stock back to before)", h.stock(p) == s0)
    layer = InventoryLayer.objects.get(sales_return_item=ret.items.get())
    check("CN05 the return's layer is taken out of the pool and an adjustment_out movement is written",
          layer.cancelled_at is not None and InventoryMovement.objects.filter(movement_type="adjustment_out", quantity=5,
                                                                              note__contains=ret.return_number).exists())
    check("CN06 the credit note is voided and its allocation released",
          Payment.objects.filter(customer=c3, is_credit_note=True, is_reversal=False, voided_at__isnull=False).exists()
          and Payment.objects.filter(customer=c3, is_credit_note=True, is_reversal=True, amount=5000).exists())
    check("CN07 reports ignore a cancelled return", reports.sales_returns_total(today, today) == sums0 - 5000, reports.sales_returns_total(today, today))
    msg = refused(cancel_sales_return, ret, h.su)
    check("CN08 a return cannot be cancelled twice", msg and "قبلاً" in msg, msg)
    check("CN09 the packs are returnable again (25 left)", returnable_lines(inv3)[0]["left"] == 25)
    st = h.c.get(f"/customers/{c3.pk}/")
    check("CN10 the customer statement no longer lists the cancelled return", st.status_code == 200 and not has(st, ret.return_number))
    check("CN11 with no active return the invoice can be cancelled again", refused(cancel_sale, inv3, h.su) is None)

    # ---------------------------------------------------------------- cancel a refunded sales return: the money comes back
    c4 = h.customer()
    h.post_sale(c4, [(p, 10, 1000)], account=acct)
    inv4 = last_sale(c4)
    bal = get_bank_account_balance(acct)
    r4 = record_sales_return(inv4, [(inv4.items.get(), 0, 4, RESALABLE, 0)], today, SettleMode.REFUND, h.su, bank_account=acct)
    check("CR00 setup: 4,000 refunded", r4.refund_amount == 4000 and get_bank_account_balance(acct) == bal - 4000)
    cancel_sales_return(r4, h.su)
    check("CR01 cancelling books the refund back into the account",
          get_bank_account_balance(acct) == bal and Payment.objects.filter(customer=c4, is_reversal=True, direction="in",
                                                                           amount=4000, bank_account=acct).exists())
    st = h.c.get(f"/customers/{c4.pk}/")
    check("CR02 the statement shows the refund and its return as a debit then a credit", st.status_code == 200 and has(st, "لغو مرجوعی"))

    # ---------------------------------------------------------------- cancel refused: the credit was used
    c5 = h.customer()
    h.post_sale(c5, [(p, 10, 1000)], account=acct)
    inv5 = last_sale(c5)
    r5 = record_sales_return(inv5, [(inv5.items.get(), 0, 3, RESALABLE, 0)], today, SettleMode.CREDIT, h.su)   # 3,000 credit
    h.post_sale(c5, [(p, 5, 1000)], mode="split")                       # uses the credit first
    check("CU00 setup: the credit was used by the next invoice", get_party_credit(customer=c5) == 0)
    msg = refused(cancel_sales_return, r5, h.su)
    r5.refresh_from_db()
    check("CU01 cancel refused when a later invoice used the credit; nothing changed", msg and "مصرف" in msg and r5.status == "active", msg)

    # ---------------------------------------------------------------- cancel refused: the goods were sold again
    q = h.product(stock=0, price=1000, pack_per_carton=10)
    sup0 = h.supplier()
    h.post_purchase(sup0, [h.item_row(q, 10, 500)], account=acct)
    c6 = h.customer()
    h.post_sale(c6, [(q, 10, 1000)], account=acct)                      # the purchase layer is empty now
    inv6 = last_sale(c6)
    r6 = record_sales_return(inv6, [(inv6.items.get(), 0, 4, RESALABLE, 0)], today, SettleMode.CREDIT, h.su)
    h.post_sale(h.customer(), [(q, 3, 1000)], account=acct)             # sells 3 of the returned packs
    msg = refused(cancel_sales_return, r6, h.su)
    check("CG01 cancel refused when the returned goods were sold again", msg and "دوباره فروخته" in msg, msg)

    # ---------------------------------------------------------------- purchases: cancel, refund and freight loss
    sup = h.supplier()
    z = h.product(stock=0, price=1000, pack_per_carton=10)
    h.post_purchase(sup, [h.item_row(z, 30, 500)], mode="split")        # 15,000 owed
    pi = last_purchase(sup)
    pitem = pi.items.get()
    pr = record_purchase_return(pi, [(pitem, 0, 4)], today, SettleMode.CREDIT, h.su)
    check("PC00 setup: 4 packs back, 2,000 off the debt", pr.total_amount == 2000 and get_supplier_outstanding(sup) == 13000)
    cancel_purchase_return(pr, h.su)
    layer = InventoryLayer.objects.get(purchase_item=pitem)
    check("PC01 cancelled: the packs are back in the purchase layer, the debt is back",
          layer.quantity_remaining == 30 and h.stock(z) == 30 and get_supplier_outstanding(sup) == 15000)
    check("PC02 an adjustment_in movement and a negative consumption row were written",
          InventoryMovement.objects.filter(movement_type="adjustment_in", quantity=4, note__contains=pr.return_number).exists()
          and pr.items.get().consumptions.filter(quantity=-4).exists())
    from apps.purchasing.services import cancel_purchase
    check("PC03 a purchase with only cancelled returns can be cancelled again", refused(cancel_purchase, pi, h.su) is None)

    sup2 = h.supplier()
    h.post_purchase(sup2, [h.item_row(z, 10, 500)], account=acct)       # paid 5,000
    pi2 = last_purchase(sup2)
    bal = get_bank_account_balance(acct)
    pr2 = record_purchase_return(pi2, [(pi2.items.get(), 0, 2)], today, SettleMode.REFUND, h.su, bank_account=acct)
    check("PR00 setup: the supplier pays 1,000 into the account", get_bank_account_balance(acct) == bal + 1000)
    cancel_purchase_return(pr2, h.su)
    check("PR01 cancelling pays that 1,000 back out of the account", get_bank_account_balance(acct) == bal)

    sup3 = h.supplier()
    h.post_purchase(sup3, [h.item_row(z, 10, 500)], account=acct, extra={"has_freight": "on", "freight_amount": "1000"})
    pi3 = last_purchase(sup3)
    pitem3 = pi3.items.get()
    lay3 = InventoryLayer.objects.get(purchase_item=pitem3)
    pr3 = record_purchase_return(pi3, [(pitem3, 0, 5)], today, SettleMode.CREDIT, h.su)
    check("FL01 goods price back 2,500; shelf value off 3,000 (freight in the cost); 500 of freight is lost",
          lay3.unit_cost == 600 and pr3.total_amount == 2500 and pr3.cost_amount == 3000 and pr3.lost_freight == 500,
          (lay3.unit_cost, pr3.total_amount, pr3.cost_amount, pr3.lost_freight))
    cards = reports.summary_cards(today, today)
    check("FL02 the lost freight is in the reports and reduces net profit",
          cards["purchase_returns_loss"]["value"] >= 500
          and cards["net_profit"]["value"] == cards["gross_profit"]["value"] - cards["returns_profit"]["value"]
          - cards["purchase_returns_loss"]["value"] - cards["expenses"]["value"])
    check("FL03 net sales = sales - sales returns", cards["net_sales"]["value"] == cards["sales"]["value"] - cards["sales_returns"]["value"])

    # ---------------------------------------------------------------- pages
    cp = h.customer()
    cheque_row = {"method": "cheque", "amount": "6000", "bank_account": str(acct.pk), "cheque_number": "88",
                  "bank_name": "ملی", "issuer": "x", "due_date": TODAY_J}
    h.post_sale(cp, [(p, 10, 1000)], mode="split", payments=[cheque_row])
    invp = last_sale(cp)
    page = h.c.get(f"/returns/sales/new/{invp.pk}/")
    check("PG01 the new-return page has the condition and deduction fields",
          page.status_code == 200 and has(page, "condition_") and has(page, "deduction_") and has(page, "کسر خسارت"))
    check("PG02 an invoice with a pending cheque carries the refund warning", has(page, "data-pending-warning") and has(page, "چک در انتظار وصول"))
    page2 = h.c.get(f"/returns/sales/new/{inv1.pk}/")
    check("PG03 an invoice without one has no warning", not has(page2, "data-pending-warning"))
    pp = h.c.get(f"/returns/purchases/new/{pi2.pk}/")
    check("PG04 the purchase form has no condition or deduction", pp.status_code == 200 and not has(pp, "condition_") and not has(pp, "deduction_"))
    far = (today + datetime.timedelta(days=90))
    from apps.shared import dates
    far_j = dates.to_persian_digits(dates.to_jalali(far).strftime("%Y/%m/%d")) if hasattr(dates, "to_jalali") else TODAY_J
    itp = invp.items.get()
    r = h.c.post(f"/returns/sales/new/{invp.pk}/", {"return_date": far_j, "settle_mode": "credit", f"packs_{itp.pk}": "1"})
    check("PG05 a return dated months ahead is refused (422) with the date message, nothing saved",
          r.status_code == 422 and has(r, "بعد از امروز") and not invp.returns.exists(), r.status_code)
    r = h.c.post(f"/returns/sales/new/{invp.pk}/", {"return_date": TODAY_J, "settle_mode": "credit", f"packs_{itp.pk}": "3",
                                                    f"condition_{itp.pk}": "damaged", f"deduction_{itp.pk}": "۴۰۰"})
    doc = invp.returns.first()
    check("PG06 the form posts condition and a Persian-digit deduction; the return is damaged with 400 held back",
          r.status_code == 302 and doc and doc.items.get().condition == "damaged" and doc.items.get().deduction == 400
          and doc.total_amount == 2600, (r.status_code, doc and doc.total_amount))
    det = h.c.get(f"/returns/sales/{doc.pk}/")
    check("PG07 the detail page shows the damaged badge, the deduction and a cancel dialog for a superuser",
          det.status_code == 200 and has(det, "معیوب") and has(det, "کسر خسارت") and has(det, "cancel-dialog") and has(det, "لغو مرجوعی") and has(det, "sales_pages.js"))
    det_user = h.cu.get(f"/returns/sales/{doc.pk}/")
    check("PG08 an ordinary user does not get the cancel button", det_user.status_code == 200 and not has(det_user, "cancel-dialog"))
    r = h.cu.post(f"/returns/sales/{doc.pk}/cancel/")
    doc.refresh_from_db()
    check("PG09 an ordinary user posting the cancel is refused; the return stays", r.status_code == 302 and doc.status == "active")
    r = h.c.post(f"/returns/sales/{doc.pk}/cancel/")
    doc.refresh_from_db()
    check("PG10 the cancel view cancels it", r.status_code == 302 and doc.status == "cancelled")
    check("PG11 a cancelled return shows its badge on the detail, list and invoice pages",
          has(h.c.get(f"/returns/sales/{doc.pk}/"), "لغوشده") and has(h.c.get("/returns/", {"q": doc.return_number}), "لغوشده")
          and has(h.c.get(f"/sales/{invp.pk}/"), "لغوشده"))
    check("PG12 the cancel buttons are POST only", h.c.get(f"/returns/sales/{doc.pk}/cancel/").status_code == 405)
    rp = h.c.post(f"/returns/purchases/{pr3.pk}/cancel/")
    pr3.refresh_from_db()
    check("PG13 a purchase return cancels through its own view", rp.status_code == 302 and pr3.status == "cancelled")
    rep = h.c.get("/reports/")
    check("PG14 reports page renders with the new lines", rep.status_code == 200 and has(rep, "فروش پس از مرجوعی"))


run("returns_v2", scenarios)

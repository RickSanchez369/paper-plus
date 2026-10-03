"""D-079: one dashboard card, receivables and payables, each split into cheques and credit."""
from tools.qa.qa_lib import *
import datetime
import jdatetime
from apps.shared import dashboard


def j(days=0):
    return jdatetime.date.fromgregorian(date=datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y/%m/%d")


def scenarios(h):
    cur = h.account()
    p = h.product(stock=500, cost=100, price=1000)
    cust, sup = h.customer(), h.supplier()
    base = dashboard.dues_overview()

    # sale: 1500 cheque due in 3 days + 500 credit due in 5 days; a second 800 credit due in 30 days (outside)
    h.post_sale(cust, [(p, 2, 1000)], mode="split",
                payments=[{"method": "cheque", "amount": "1500", "cheque_number": "R-IN", "due_date": j(3)}], credit_due=j(5))
    h.post_sale(cust, [(p, 1, 800)], mode="split", payments=[], credit_due=j(30))
    # an overdue sale credit (due yesterday)
    h.post_sale(cust, [(p, 1, 300)], mode="split", payments=[], credit_due=j(-1))
    # a sale fully settled by transfer is owed by nobody
    h.post_sale(cust, [(p, 1, 9000)], account=cur)
    # purchase: 200 cheque due in 4 days + 300 credit due in 6 days; far credit outside
    h.post_purchase(sup, [(p, 5, 100)], mode="split",
                    payments=[{"method": "cheque", "amount": "200", "cheque_number": "P-OUT", "issuer": "ما", "due_date": j(4)}],
                    credit_due=j(6))
    h.post_purchase(sup, [(p, 1, 100)], mode="split", payments=[], credit_due=j(40))

    now = dashboard.dues_overview()
    d = lambda side, group, key: now[side][group][key] - base[side][group][key]
    check("DD01 receivable cheques: +1500 (the IN cheque inside 10 days)", d("receivable", "cheques", "total") == 1500, d("receivable", "cheques", "total"))
    check("DD02 receivable credit: 500 + overdue 300 (the 800 due in 30 days is outside)", d("receivable", "credit", "total") == 800, d("receivable", "credit", "total"))
    check("DD03 overdue part counts only the late credit", d("receivable", "credit", "overdue_total") == 300)
    check("DD04 payable cheques: +200", d("payable", "cheques", "total") == 200, d("payable", "cheques", "total"))
    check("DD05 payable credit: +300 (the credit due in 40 days is outside)", d("payable", "credit", "total") == 300, d("payable", "credit", "total"))
    check("DD06 column totals add up their groups",
          now["receivable"]["total"] == now["receivable"]["cheques"]["total"] + now["receivable"]["credit"]["total"]
          and now["payable"]["total"] == now["payable"]["cheques"]["total"] + now["payable"]["credit"]["total"])
    check("DD07 the transfer-settled sale is not listed", all(i["amount"] != 9000 for i in now["receivable"]["credit"]["items"]))
    dates_ = [i["due_date"] for i in now["receivable"]["credit"]["items"]]
    check("DD08 rows are soonest first", dates_ == sorted(dates_))
    check("DD09 window is 10 days", now["days"] == 10)

    r = h.c.get("/")
    check("DD10 dashboard renders the one card with both columns",
          r.status_code == 200 and has(r, "مطالبات (دریافتنی)") and has(r, "بدهی‌ها (پرداختنی)")
          and has(r, "R-IN") and has(r, "P-OUT"), r.status_code)
    check("DD11 the old cards are gone",
          not has(r, "نیازمند توجه") and not has(r, "پرداخت‌های هفتهٔ آینده") and not has(r, "موجودی منفی"))


run("dashboard_dues", scenarios)

"""Builds a rich dataset (every status, every payment kind), then follows EVERY
internal link reachable from the dashboard and audits each page."""
from tools.qa.qa_lib import *
import datetime
import re
from apps.payments.models import Cheque, Expense
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice

HREF = re.compile(r'href="([^"#][^"]*)"')
TAG = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
ENGLISH_DJANGO = ("This field is required", "Select a valid choice", "Enter a valid", "Ensure this value", "Enter a whole number",
                  "Please correct", "Constraint", "IntegrityError", "matching query does not exist", "Traceback")


def visible(body):
    body = TAG.sub("", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return re.sub(r"<[^>]+>", " ", body)


def scenarios(h):
    acct, acct2 = h.account(), h.account()
    p1, p2, p3 = h.product(stock=100, cost=100, price=300), h.product(stock=50, cost=200, price=500), h.product(stock=0)
    c1, c2, c3 = h.customer(), h.customer(), h.customer()
    s1, s2 = h.supplier(), h.supplier()
    # sales in every state
    h.post_sale(c1, [(p1, 5, 300)], account=acct)
    h.post_sale(c1, [(p1, 2, 300), (p2, 3, 500)], mode="split", payments=[{"method": "cash", "amount": "100"}])
    h.post_sale(c2, [(p2, 4, 500)], mode="split", payments=[{"method": "cheque", "amount": "1000", "bank_account": str(acct.pk), "cheque_number": "X1", "bank_name": "M", "due_date": "1405/08/01"}, {"method": "cheque", "amount": "500"}])
    h.post_sale(c2, [(p1, 3, 300)], account="cash", discount="50")
    h.post_sale(c3, [(p1, 1, 300)], mode="split")
    cancelled = SalesInvoice.objects.filter(customer=c1).earliest("created_at")
    h.c.post(f"/sales/{cancelled.pk}/cancel/")
    # purchases
    h.post_purchase(s1, [(p3, 20, 150), (p1, 5, 120)], account=acct)
    h.post_purchase(s1, [(p2, 10, 250)], mode="split", payments=[{"method": "cheque", "amount": "1000", "bank_account": str(acct2.pk), "cheque_number": "OUT9", "bank_name": "M", "due_date": "1405/09/01"}, {"method": "bank_transfer", "amount": "500", "bank_account": str(acct2.pk)}])
    h.post_purchase(s2, [(p3, 3, 100)], mode="split")
    pc = PurchaseInvoice.objects.filter(supplier=s2).latest("created_at")
    h.c.post(f"/purchasing/{pc.pk}/cancel/")
    c3.is_active = False; c3.save(); s2.is_active = False; s2.save()
    # cheques in every status
    chs = list(Cheque.objects.all().order_by("created_at"))
    ours = [c for c in chs if (c.customer_id in (c1.pk, c2.pk)) or (c.supplier_id in (s1.pk, s2.pk))]
    for c, act in zip(ours, ("clear", "bounce", "cancel")):
        h.c.post(f"/cheques/{c.pk}/{act}/")
    # expenses incl. cancelled
    h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-rent", "amount": "900", "bank_account": str(acct.pk)})
    h.c.post("/expenses/new/", {"expense_date": "1405/07/07", "reason": "QA-tea", "amount": "40", "bank_account": "cash"})
    e = Expense.objects.get(reason="QA-tea")
    h.c.post(f"/expenses/{e.pk}/cancel/")
    # a recorded customer payment
    inv = SalesInvoice.objects.filter(customer=c1, status="confirmed").latest("created_at")
    h.c.post(f"/receivables/{c1.pk}/record-payment/", {"amount": "100", "payment_date": TODAY_J, "bank_account": str(acct.pk), "invoices": [str(inv.pk)]})
    h.c.post(f"/payables/{s1.pk}/record-payment/", {"amount": "50", "payment_date": TODAY_J, "bank_account": ""})

    seen, queue, problems = set(), ["/"], []
    skip = ("/logout/", "/admin/", "/static/", "/media/")
    pages = 0
    while queue and pages < 700:
        url = queue.pop(0)
        path = url.split("#")[0]
        if path in seen or any(path.startswith(s) for s in skip) or path.startswith(("http", "mailto", "javascript")):
            continue
        seen.add(path)
        r = h.c.get(path)
        pages += 1
        if r.status_code in (301, 302):
            loc = r["Location"]
            if not loc.startswith("http"):
                queue.append(loc)
            continue
        if r.status_code == 405:
            continue                     # a POST-only action URL, correctly refused for GET
        if r.status_code != 200:
            problems.append((path, r.status_code))
            continue
        body = text(r)
        vis = visible(body)
        for needle in ENGLISH_DJANGO:
            if needle in vis:
                problems.append((path, f"english/django text: {needle}"))
        if re.search(r"\bNone\b", vis):
            problems.append((path, "the word 'None' is visible"))
        if re.search(r"\bnan\b|\binf\b", vis, re.I):
            problems.append((path, "nan/inf visible"))
        if "{{" in vis or "{%" in vis:
            problems.append((path, "unrendered template tag"))
        if re.search(r"Decimal\(|datetime\.(date|datetime)\(|<QuerySet|<class |object at 0x", vis):
            problems.append((path, "python repr leaked"))
        if re.search(r"\d,\d{3},\d{3}\D*[a-z]{3,}", vis) and False:
            pass
        for m in HREF.finditer(body):
            queue.append(m.group(1).replace("&amp;", "&"))
    check(f"X01 crawled {pages} distinct pages from the dashboard", pages > 30, pages)
    check("X02 no broken link (every reachable page is 200/redirect/405-by-design)", not [x for x in problems if isinstance(x[1], int)], [x for x in problems if isinstance(x[1], int)][:8])
    bad = [x for x in problems if not isinstance(x[1], int)]
    check("X03 no leaked Python/English/None/template text on any page", not bad, bad[:8])
    print("   pages:", pages)


run("crawler", scenarios)

"""D-098: the amount filters are text boxes that take Persian digits (type=number dropped them), pages are gzipped for a client
that accepts it, and the pay form's invoice rows carry a no-split number."""
from apps.sales.models import SalesInvoice
from tools.qa.qa_lib import *  # noqa: F401,F403


def scenarios(h):
    cust = h.customer()
    acct = h.account()
    p = h.product(price=1000, stock=50, cost=400)
    h.post_sale(cust, [(p, 2, 1500)], account=acct)          # total 3,000
    h.post_sale(cust, [(p, 1, 9000)], account=acct)          # total 9,000
    sup = h.supplier()
    h.post_purchase(sup, [(p, 3, 700)], account=acct)

    for base in ("/sales/", "/purchasing/", "/expenses/"):
        r = h.c.get(f"{base}?preset=custom&start=1400/01/01&end=1450/12/29")
        body = text(r)
        check(f"AF01 {base}: amount filters are text boxes, not type=number",
              r.status_code == 200 and 'name="amount_min"' in body and 'type="number"' not in body.split('name="amount_min"')[0][-120:], r.status_code)
    base = "/sales/?preset=custom&start=1400/01/01&end=1450/12/29"
    rows = lambda r: text(r).count(cust.name)           # one card/row per invoice of this customer
    every = h.c.get(base)
    ascii_r = h.c.get(base + "&amount_min=5000")
    fa_r = h.c.get(base + "&amount_min=" + "۵۰۰۰")
    check("AF02 Persian digits in a filter give the same list as Latin digits", ascii_r.status_code == 200 and fa_r.status_code == 200
          and rows(ascii_r) == rows(fa_r), (rows(ascii_r), rows(fa_r)))
    check("AF03 the minimum filter really filters (fewer rows than the unfiltered list)", 0 < rows(fa_r) < rows(every), (rows(fa_r), rows(every)))
    bad = h.c.get("/sales/?amount_min=abc")
    check("AF04 a text amount is a message, not a 500", bad.status_code == 200, bad.status_code)

    # gzip
    r = h.c.get("/sales/", HTTP_ACCEPT_ENCODING="gzip")
    check("AF10 HTML is gzipped when the client accepts it", r.headers.get("Content-Encoding") == "gzip", r.headers.get("Content-Encoding"))
    r = h.c.get("/sales/")
    check("AF11 and plain when it does not", r.headers.get("Content-Encoding") is None)
    r = h.c.get("/sales/", HTTP_ACCEPT_ENCODING="gzip")
    check("AF12 the cookie/Vary header says the page depends on the encoding", "Accept-Encoding" in r.headers.get("Vary", ""))

    # the pay form carries the no-split number
    debtor = h.customer()
    sale = h.post_sale(debtor, [(p, 1, 1000)], mode="split")
    inv = SalesInvoice.objects.filter(customer=debtor).first()
    r = h.c.get("/receivables/")
    check("AF20 receivables pay form: the invoice number sits in a no-split span",
          sale.status_code == 302 and inv is not None
          and f'<span class="is-token">{digits_fa(inv.invoice_number)}</span>' in text(r), r.status_code)


run("filters_gzip", scenarios)

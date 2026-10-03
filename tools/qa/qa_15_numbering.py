"""Invoice numbers: "<Jalali year>/<running number>", per type, reset each year (D-064)."""
import re
from unittest import mock

import jdatetime

from apps.shared import dates
from apps.shared.models import DocumentSequence
from apps.shared.services import get_next_document_number
from apps.sales.models import SalesInvoice
from apps.purchasing.models import PurchaseInvoice
from tools.qa.qa_lib import *

PATTERN = re.compile(r"^(\d{4})/(\d{4,})$")


def scenarios(h):
    year = dates.today().year
    p = h.product(stock=30)
    cust, sup = h.customer(), h.supplier()

    h.post_sale(cust, [(p, 1, 1000)], account=h.account())
    h.post_sale(cust, [(p, 1, 1000)], account=h.account())
    a, b = SalesInvoice.objects.filter(customer=cust).order_by("confirmed_at")
    ma, mb = PATTERN.match(a.invoice_number), PATTERN.match(b.invoice_number)
    check("N01 sale numbers look like 1405/0001", bool(ma and mb), (a.invoice_number, b.invoice_number))
    check("N02 the year part is the current Jalali year", ma and int(ma.group(1)) == year)
    check("N03 running number goes up by one", ma and mb and int(mb.group(2)) == int(ma.group(2)) + 1)

    h.post_purchase(sup, [(p, 2, 400)], account=h.account())
    pur = PurchaseInvoice.objects.get(supplier=sup)
    mp = PATTERN.match(pur.invoice_number)
    check("N04 purchases use the same shape", bool(mp) and int(mp.group(1)) == year)
    sale_row = DocumentSequence.objects.get(doc_type="sale", year=year)
    buy_row = DocumentSequence.objects.get(doc_type="purchase", year=year)
    check("N05 sale and purchase counters are separate rows", sale_row.pk != buy_row.pk)

    # A new Jalali year starts again at 1, and the old year keeps counting where it was.
    before = DocumentSequence.objects.get(doc_type="sale", year=year).next_number
    with mock.patch.object(dates, "today", return_value=jdatetime.date(year + 1, 1, 1)):
        n1 = get_next_document_number("sale")
        n2 = get_next_document_number("sale")
    check("N06 new year restarts at 0001", n1 == f"{year + 1}/0001" and n2 == f"{year + 1}/0002", (n1, n2))
    check("N07 the old year's counter is untouched", DocumentSequence.objects.get(doc_type="sale", year=year).next_number == before)

    # Uniqueness is enforced for confirmed invoices by the DB.
    from django.db import IntegrityError, transaction
    try:
        with transaction.atomic():
            SalesInvoice.objects.filter(pk=b.pk).update(invoice_number=a.invoice_number)
        dup = False
    except IntegrityError:
        dup = True
    check("N08 the DB refuses two sale invoices with the same number", dup)

    r = h.c.get(f"/sales/{a.pk}/print/")
    check("N09 the printed invoice shows the number in Persian digits", r.status_code == 200 and has(r, a.invoice_number))
    r = h.c.get(f"/sales/?q={a.invoice_number}")
    check("N10 searching the list by the full number finds it", r.status_code == 200 and has(r, a.invoice_number))


run("numbering", scenarios)

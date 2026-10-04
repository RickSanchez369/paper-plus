"""Invoice numbers: purchases "<Jalali year>/<running number>" per year (D-064); sales "<letter>/<yyyymmdd>" per invoice day (D-086)."""
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
SALE = re.compile(r"^(\D+?)(\d*)/(\d{8})$")


def scenarios(h):
    year = dates.today().year
    p = h.product(stock=30)
    cust, sup = h.customer(), h.supplier()

    from apps.shared.services import PERSIAN_LETTERS, display_document_number, format_sale_number

    h.post_sale(cust, [(p, 1, 1000)], account=h.account())
    h.post_sale(cust, [(p, 1, 1000)], account=h.account())
    a, b = SalesInvoice.objects.filter(customer=cust).order_by("confirmed_at")
    ma, mb = SALE.match(a.invoice_number), SALE.match(b.invoice_number)
    jt = dates.today()
    stamp = f"{jt.year:04d}{jt.month:02d}{jt.day:02d}"
    check("N01 sale numbers look like الف/14050712", bool(ma and mb), (a.invoice_number, b.invoice_number))
    check("N02 the date part is the invoice's Jalali day", ma and ma.group(3) == stamp and mb.group(3) == stamp)
    check("N03 the letter moves one step along the alphabet",
          ma and mb and PERSIAN_LETTERS.index(mb.group(1)) == PERSIAN_LETTERS.index(ma.group(1)) + 1)

    # A backdated invoice takes its own day's counter, starting at الف.
    back = jt - jdatetime.timedelta(days=40)
    back_j = back.strftime("%Y/%m/%d")
    h.post_sale(cust, [(p, 1, 1000)], account=h.account(), date=back_j)
    c = SalesInvoice.objects.filter(customer=cust).latest("confirmed_at")
    seq_back = DocumentSequence.objects.filter(doc_type="sale", year=back.year, day=back.month * 100 + back.day).first()
    check("N03b a backdated sale is numbered from its own date", c.invoice_number.endswith(f"/{back.year:04d}{back.month:02d}{back.day:02d}")
          and seq_back is not None, c.invoice_number)

    d12 = jdatetime.date(1405, 7, 12)
    check("N03c formatter: 1st, 2nd, 32nd, 33rd, 65th of a day",
          [format_sale_number(d12, n) for n in (1, 2, 32, 33, 65)] ==
          ["الف/14050712", "ب/14050712", "ی/14050712", "الف2/14050712", "الف3/14050712"])
    check("N03d display: Persian digits, bidi mark only for a lettered round",
          display_document_number("الف/14050712") == "الف/۱۴۰۵۰۷۱۲" and
          display_document_number("ب2/14050712") == "ب۲؜/۱۴۰۵۰۷۱۲" and
          display_document_number("1405/0042") == "۱۴۰۵/۰۰۴۲")

    h.post_purchase(sup, [(p, 2, 400)], account=h.account())
    pur = PurchaseInvoice.objects.get(supplier=sup)
    mp = PATTERN.match(pur.invoice_number)
    check("N04 purchases use the same shape", bool(mp) and int(mp.group(1)) == year)
    sale_row = DocumentSequence.objects.get(doc_type="sale", year=jt.year, day=jt.month * 100 + jt.day)
    buy_row = DocumentSequence.objects.get(doc_type="purchase", year=year)
    check("N05 sale and purchase counters are separate rows", sale_row.pk != buy_row.pk)

    # A new Jalali year starts purchases again at 1, and the old year keeps counting where it was.
    before = DocumentSequence.objects.get(doc_type="purchase", year=year).next_number
    with mock.patch.object(dates, "today", return_value=jdatetime.date(year + 1, 1, 1)):
        n1 = get_next_document_number("purchase")
        n2 = get_next_document_number("purchase")
        s1 = get_next_document_number("sale")
    check("N06 new year restarts purchases at 0001", n1 == f"{year + 1}/0001" and n2 == f"{year + 1}/0002", (n1, n2))
    check("N07 the old year's counter is untouched", DocumentSequence.objects.get(doc_type="purchase", year=year).next_number == before)
    check("N07b a sale without a date uses today's day", s1 == f"الف/{year + 1}0101", s1)

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
    r = h.c.get("/sales/", {"q": a.invoice_number})
    check("N10 searching the list by the full number finds it", r.status_code == 200 and has(r, a.invoice_number))
    r = h.c.get("/sales/", {"q": digits_fa(a.invoice_number)})
    check("N10b searching with Persian digits finds it too", r.status_code == 200 and has(r, a.invoice_number))


run("numbering", scenarios)

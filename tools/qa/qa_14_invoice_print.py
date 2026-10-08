"""Printed sales invoice (D-061): words, company header, stamp boxes, statuses."""
from django.test import override_settings

from apps.shared.words import number_to_words
from tools.qa.qa_lib import *


def scenarios(h):
    words = {
        0: "صفر", 7: "هفت", 15: "پانزده", 20: "بیست", 21: "بیست و یک", 100: "صد", 340: "سیصد و چهل",
        1000: "یک هزار", 1250: "یک هزار و دویست و پنجاه", 2000000: "دو میلیون",
        6140000: "شش میلیون و صد و چهل هزار", 1000000000: "یک میلیارد",
        1234567890: "یک میلیارد و دویست و سی و چهار میلیون و پانصد و شصت و هفت هزار و هشتصد و نود",
    }
    for n, expect in words.items():
        check(f"PW words {n}", number_to_words(n) == expect, number_to_words(n))

    p = h.product(stock=20)
    cust = h.customer(address="تهران، خیابان آزادی")
    h.post_sale(cust, [(p, 2, 1500)], discount=500, account=h.account())
    from apps.sales.models import SalesInvoice
    inv = SalesInvoice.objects.filter(customer=cust).get()
    SalesInvoice.objects.filter(pk=inv.pk).update(note="تحویل درب انبار")   # note is admin-entered
    url = f"/sales/{inv.pk}/print/"

    check("PR01 anonymous is redirected", h.anon.get(url).status_code == 302)
    r = h.c.get(url)
    check("PR02 renders for a signed-in user", r.status_code == 200)
    check("PR03 has both stamp-and-signature boxes", has(r, "مهر و امضای فروشنده") and has(r, "مهر و امضای خریدار"))
    check("PR04 buyer name and address print", has(r, cust.name) and has(r, "تهران، خیابان آزادی"))
    check("PR05 amount in words: 3000-500 = 2500", has(r, "دو هزار و پانصد تومان"))
    check("PR06 discount line shows, note prints", has(r, "تخفیف") and has(r, "تحویل درب انبار"))
    # The on-screen (no-print) note may name a missing field; the printed header must not carry the label.
    check("PR07 no company extras by default (no economic code label)", "<dt>شمارهٔ اقتصادی" not in text(r))
    with override_settings(COMPANY={"name": "شرکت آزمون", "legal_name": "آزمون تجارت پارس", "economic_code": "411123456789",
                                    "registration_no": "", "national_id": "", "postal_code": "1234567890",
                                    "phone": "02111112222", "address": "تهران، ولیعصر", "footer_note": "کالای فروخته‌شده پس گرفته نمی‌شود"}):
        r = h.c.get(url)
        check("PR08 company details from settings appear", has(r, "آزمون تجارت پارس") and has(r, "411123456789") and has(r, "تهران، ولیعصر"))
        check("PR09 …and a blank one is left off", not has(r, "شمارهٔ ثبت"))
        check("PR10 footer note prints", has(r, "پس گرفته نمی‌شود"))
    check("PR11 confirmed invoice shows paid/outstanding", has(r, "مانده"))

    # ---- D-088: brand sheet
    r = h.c.get(url)
    check("PR14 brand, both phones with names and the email print", has(r, "کاغذ پلاس") and has(r, "09145572511") and
          has(r, "خندانی") and has(r, "09145589832") and has(r, "حقگو") and has(r, "kaghazplus1@gmail.com"))
    check("PR15 a black-and-white switch is offered", has(r, 'id="mode-mono"') and has(r, 'id="mode-color"') and has(r, "سیاه‌وسفید"))
    from apps.sales.printing import THANK_YOU_LINES, settlement_rows, thank_you_line
    check("PR16 a thank-you line prints, and the same one on a reprint",
          has(r, thank_you_line(inv)) and thank_you_line(inv) == thank_you_line(SalesInvoice.objects.get(pk=inv.pk)))
    check("PR17 terms and the payment box print", has(r, "شرایط و ضوابط") and has(r, "روش پرداخت و تسویه"))
    rows = settlement_rows(inv)
    check("PR18 settlement rows add up to what is paid plus what is still due",
          sum(x["amount"] for x in rows) == inv.paid_amount + inv.outstanding, rows)
    check("PR19 one sheet: the A4 sheet class and the fit script are there", has(r, 'class="inv') and has(r, "function fit()"))

    from apps.sales.services import cancel_sale
    cancel_sale(inv, h.su)
    r = h.c.get(url)
    check("PR12 a cancelled invoice is watermarked 'باطل شده'", r.status_code == 200 and has(r, "sheet__watermark") and has(r, "باطل شده"))
    from apps.purchasing.models import PurchaseInvoice
    sup = h.supplier()
    h.post_purchase(sup, [(p, 3, 400)], account=h.account())
    pur = PurchaseInvoice.objects.filter(supplier=sup).get()
    r = h.c.get(f"/purchasing/{pur.pk}/print/")
    check("PR13 purchase print still renders with its styles", r.status_code == 200 and has(r, "print_invoice.css"))


run("invoice_print", scenarios)

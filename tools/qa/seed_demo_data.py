"""Fill the THROWAWAY QA database (after seed_qa_db.py) with a believable week of business so every screen has something
to show: paid / part-paid / overdue sales, a cancelled invoice, a purchase with freight, cheques, credit and expenses.
Posts through the real forms (the same path the browser uses), so it also exercises them.

    python tools/qa/seed_demo_data.py
"""
import datetime
import os
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[2]
db = pathlib.Path(os.environ.get("QA_DB", root / "tools" / "qa" / ".qa.sqlite3"))
os.environ["DATABASE_URL"] = "sqlite:///" + db.as_posix()
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("SECRET_KEY", "throwaway-qa")
sys.path.insert(0, str(root))
os.chdir(root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

import jdatetime  # noqa: E402

from apps.partners.models import Customer, Supplier  # noqa: E402
from apps.payments.models import BankAccount  # noqa: E402
from apps.products.models import Product  # noqa: E402
from apps.sales.models import SalesInvoice  # noqa: E402
from tools.qa.qa_lib import Harness  # noqa: E402


def j(days=0):
    """A Jalali date string `days` from today, as the date fields want it."""
    d = datetime.date.today() + datetime.timedelta(days=days)
    return jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")


def ok(label, response):
    print(("ok   " if response.status_code in (200, 302) else "FAIL ") + label, response.status_code)


if Customer.objects.filter(name__startswith="مشتری آزمایشی").count() == 0:
    sys.exit("run tools/qa/seed_qa_db.py first")

h = Harness()
pos = BankAccount.objects.get(account_type="pos")
cur = BankAccount.objects.filter(account_type="current").order_by("name").first()
a4, a3, folder = (Product.objects.get(sku=s) for s in ("QA-P1", "QA-P2", "QA-P3"))
c1, c2 = Customer.objects.order_by("name")[:2]
sup = Supplier.objects.first()

# Sales: paid by card; part cheque + overdue credit; paid by transfer; one cancelled.
ok("sale: paid by card", h.post_sale(c1, [(a4, 3, 250000)], account=pos))
ok("sale: cheque + overdue credit", h.post_sale(
    c2, [(a3, 2, 480000)], mode="split", credit_due=j(-3), date=j(-6),
    payments=[{"method": "cheque", "amount": "400000", "bank_account": str(cur.pk), "cheque_number": "DEMO-1",
               "bank_name": "ملت", "due_date": j(5)}]))
ok("sale: paid by transfer", h.post_sale(c1, [(folder, 10, 15000)], account=cur, date=j(-1)))
ok("sale: credit due in a week", h.post_sale(c2, [(a4, 1, 250000)], mode="split", credit_due=j(7)))
ok("sale: to be cancelled", h.post_sale(c1, [(folder, 2, 15000)], account=cur))
doomed = SalesInvoice.objects.filter(customer=c1).latest("created_at")
ok("sale: cancel it", h.c.post(f"/sales/{doomed.pk}/cancel/"))

# Purchase with freight, left as credit (shows up under Payables).
ok("purchase: freight + credit", h.post_purchase(
    sup, [(a4, 20, 175000)], mode="split", credit_due=j(4),
    extra={"has_freight": "on", "freight_amount": "500000"}))

# Expenses: credit overdue, cheque, transfer.
ok("expense: overdue credit", h.c.post("/expenses/new/", {
    "expense_date": j(-5), "reason": "اجارهٔ انبار", "amount": "3000000", "payment_method": "credit", "due_date": j(-2)}))
ok("expense: cheque", h.c.post("/expenses/new/", {
    "expense_date": j(0), "reason": "تعمیر دستگاه", "amount": "700000", "payment_method": "cheque",
    "cheque_number": "DEMO-E1", "issuer": "شرکت", "cheque_due_date": j(6), "bank_account": str(cur.pk)}))
ok("expense: transfer", h.c.post("/expenses/new/", {
    "expense_date": j(0), "reason": "قبض برق", "amount": "850000", "payment_method": "transfer",
    "bank_account": str(cur.pk)}))

# A product with no stock, to see the out-of-stock state.
Product.objects.get_or_create(sku="QA-P9", defaults={"name": "کالای ناموجود (نمونه)", "unit": "بسته", "default_selling_price": 90000})
print("demo data ready")

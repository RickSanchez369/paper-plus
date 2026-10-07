"""Rich THROWAWAY demo data for the mobile test suite (run after seed_qa_db.py + seed_demo_data.py).

Enough rows for every page state: more than one page of sales/purchases/expenses (pagination), paid / part-paid / credit /
overdue / cancelled invoices of both tiers, discounts, cheques in every status, returns, recurring costs, inactive and
awkward-named parties and products (long names, Arabic letters, digits), out-of-stock and low-stock products.
Posts through the same forms the browser uses (Harness), so it exercises them too.

    QA_DB=tools/qa/.mobile/suite/base.sqlite3 python tools/qa/mobile_suite/seed_rich.py
"""
import datetime
import os
import re
import pathlib
import random
import sys

root = pathlib.Path(__file__).resolve().parents[3]
db = pathlib.Path(os.environ["QA_DB"])
os.environ["DATABASE_URL"] = "sqlite:///" + db.as_posix()
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("SECRET_KEY", "throwaway-qa")
sys.path.insert(0, str(root))
os.chdir(root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

import jdatetime  # noqa: E402

from apps.inventory.services import set_opening_stock  # noqa: E402
from apps.partners.models import Customer, Supplier  # noqa: E402
from apps.payments.models import BankAccount, Cheque  # noqa: E402
from apps.products.models import Product  # noqa: E402
from apps.purchasing.models import PurchaseInvoice  # noqa: E402
from apps.sales.models import SalesInvoice  # noqa: E402
from apps.users.models import User  # noqa: E402
from tools.qa.qa_lib import Harness  # noqa: E402

random.seed(1405)
FAILS = []


def j(days=0):
    d = datetime.date.today() + datetime.timedelta(days=days)
    return jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d")


def ok(label, response, want=(302,)):
    """Every create/cancel/return POST must redirect; a 200/422 re-render means the form said no."""
    if response.status_code not in want:
        body = response.content.decode("utf-8", "replace")
        why = re.findall(r'class="(?:field__error|form-error)[^"]*"[^>]*>([^<]{3,120})', body)
        FAILS.append(f"{label} -> {response.status_code} {why[:2]}")


h = Harness()
su = User.objects.filter(is_superuser=True).exclude(pk=h.su.pk).first() or h.su
pos = BankAccount.objects.filter(account_type="pos").first()
cur1, cur2 = BankAccount.objects.filter(account_type="current").order_by("name")[:2]
BankAccount.objects.get_or_create(account_number="QA-POS-2", defaults={"name": "کارت‌خوان فروشگاه ۲", "account_type": "pos", "owner": "شرکت"})
BankAccount.objects.get_or_create(account_number="QA-CUR-3", defaults={"name": "جاری سپه (قدیمی)", "account_type": "current", "owner": "شرکت", "is_active": False})

# ---- products: ratios 1..24, prices from cheap to expensive, stock rich / low / zero, awkward names
PRODUCTS = [
    ("دفتر ۱۰۰ برگ", "R-101", 12, 45000, 540000, 40000, 38000, 300),
    ("خودکار آبی (بسته ۱۰ تایی)", "R-102", 6, 90000, 480000, 85000, 80000, 120),
    ("ماژیک وايت‌برد", "R-103", 20, 30000, 540000, 28000, 26000, 50),
    ("کاغذ کاهی ۷۰ گرم", "R-104", 1, 1200000, 1200000, 1200000, 1100000, 40),
    ("پوشه پلاستیکی ۳ تایی", "R-105", 10, 22000, 190000, 20000, 18000, 500),
    ("چسب ۴۵ گرمی", "R-106", 24, 8000, 168000, 7500, 7000, 8),
    ("نام بسیار بلند برای آزمایش شکستن خط در کارت‌های موبایل و جدول‌ها و جست‌وجوی کالا", "R-107", 3, 150000, 400000, 140000, 135000, 90),
    ("قیچی ۲۱ سانتی", "R-108", 5, 35000, 160000, 33000, 30000, 0),
    ("منگنه شماره ۱۰", "R-109", 8, 18000, 130000, 17000, 15000, 3),
    ("گیره کاغذ ۱۰۰ عددی", "R-110", 12, 9000, 100000, 8500, 8000, 75),
    ("ك‌ي‌ك عربی تست", "R-111", 4, 70000, 260000, 65000, 60000, 60),
    ("کالای ۱۲۳ با رقم", "R-112", 2, 500000, 950000, 480000, 450000, 30),
]
for name, sku, ratio, price, carton, rcarton, wpack, stock in PRODUCTS:
    p, created = Product.objects.get_or_create(sku=sku, defaults=dict(
        name=name, pack_per_carton=ratio, default_selling_price=price, wholesale_selling_price=carton,
        retail_carton_price=rcarton, wholesale_pack_price=wpack))
    if created and stock:
        set_opening_stock(p, stock, su, int(price * 0.6))
Product.objects.get_or_create(sku="R-113", defaults=dict(name="کالای غیرفعال", pack_per_carton=2, default_selling_price=1000, is_active=False))

# ---- parties
CUSTOMER_NAMES = ["علی رضایی", "مریم احمدی", "فروشگاه نور", "کتاب‌فروشی دانش", "نوشت‌افزار آرمان", "شرکت پارس‌ایده", "محمد کریمی",
                  "زهرا موسوی", "چاپخانه سپیده", "دفتر فنی آبان", "رضا نوری", "سارا حسینی", "تعاونی فرهنگیان", "مدرسه هدف",
                  "پخش مرکزی", "فروشگاه بزرگ ایران‌مال با نام بسیار طولانی برای تست شکستن متن", "علي (با ی عربی)", "كتاب‌سرا (ک عربی)",
                  "مشتری ۱۲۳", "Customer English"]
for i, name in enumerate(CUSTOMER_NAMES):
    Customer.objects.get_or_create(name=name, defaults=dict(
        phone=f"0912{random.randint(1000000, 9999999)}" if i % 3 else "", price_tier="wholesale" if i % 4 == 0 else "retail",
        address="تهران، خیابان آزمایش، پلاک " + str(i + 1) if i % 2 else "", is_active=i != 7))
SUPPLIER_NAMES = ["پخش سراسری کاغذ", "شرکت صنایع بسته‌بندی", "تأمین ماژیک ایران", "واردات چین‌کالا", "بازرگانی میلاد", "تولیدی دفتر نگین"]
for name in SUPPLIER_NAMES:
    Supplier.objects.get_or_create(name=name, defaults=dict(phone="02155" + str(random.randint(100000, 999999))))

customers = list(Customer.objects.filter(is_active=True).order_by("name"))
suppliers = list(Supplier.objects.order_by("name"))
products = list(Product.objects.filter(is_active=True, sku__startswith="R-").exclude(sku="R-108"))

# ---- sales: 36 invoices across 35 days, every payment shape
n_sales = 0
for i in range(36):
    c = customers[i % len(customers)]
    p1, p2 = random.sample(products, 2)
    day = -(i % 35)
    rows = [(p1, random.randint(1, 6), p1.default_selling_price)]
    if i % 3 == 0:
        rows.append((p2, random.randint(1, 4), p2.default_selling_price))
    kind = i % 9
    extra = {"price_tier": c.price_tier}
    if i % 5 == 0:
        extra.update({"discount_mode": "percent", "discount_percent": "10"})
    discount = 5000 if i % 7 == 0 else ""
    if kind in (0, 1):
        r = h.post_sale(c, rows, account=pos, date=j(day), discount=discount, extra=extra)
    elif kind == 2:
        r = h.post_sale(c, rows, account=cur1, date=j(day), discount=discount, extra=extra)
    elif kind == 3:
        r = h.post_sale(c, rows, mode="split", credit_due=j(day - 5), date=j(day), extra=extra)       # overdue credit
    elif kind == 4:
        r = h.post_sale(c, rows, mode="split", credit_due=j(day + 20), date=j(day), extra=extra)      # future credit
    elif kind == 5:
        total = sum(q * pr for _, q, pr in rows)
        r = h.post_sale(c, rows, mode="split", credit_due=j(day + 15), date=j(day), extra=extra, payments=[
            {"method": "cheque", "amount": str(max(total // 3, 1)), "bank_account": str(cur1.pk), "cheque_number": f"SEED-{i:03d}",
             "bank_name": "ملت", "issuer": c.name, "due_date": j(day + random.choice([-4, 3, 12, 40]))}])
    elif kind == 6:
        r = h.post_sale(c, rows, mode="split", credit_due=j(day + 9), date=j(day), extra=extra, payments=[
            {"method": "card", "amount": "10000", "bank_account": str(pos.pk)}])
    elif kind == 7:
        r = h.post_sale(c, rows, account=pos, date=j(day), extra=extra)
    else:
        r = h.post_sale(c, rows, account=cur2, date=j(day), extra=extra)
    ok(f"sale {i}", r)
    n_sales += 1
# cancel two
for inv in SalesInvoice.objects.filter(status="confirmed").order_by("-created_at")[:2]:
    ok("cancel sale", h.c.post(f"/sales/{inv.pk}/cancel/"))

# ---- purchases: 28
for i in range(28):
    s = suppliers[i % len(suppliers)]
    p1, p2 = random.sample(products, 2)
    rows = [(p1, random.randint(5, 40), int(p1.default_selling_price * 0.6))]
    if i % 4 == 0:
        rows.append((p2, random.randint(5, 20), int(p2.default_selling_price * 0.6)))
    extra = {"has_freight": "on", "freight_amount": "250000"} if i % 6 == 0 else {}
    day = -(i % 30)
    if i % 4 == 0:
        r = h.post_purchase(s, rows, account=cur1, date=j(day), supplier_invoice=f"SI-{1000 + i}", extra=extra)
    elif i % 4 == 1:
        r = h.post_purchase(s, rows, mode="split", credit_due=j(day + 12), date=j(day), extra=extra)
    elif i % 4 == 2:
        total = sum(q * pr for _, q, pr in rows)
        r = h.post_purchase(s, rows, mode="split", credit_due=j(day + 30), date=j(day), extra=extra, payments=[
            {"method": "cheque", "amount": str(max(total // 2, 1)), "bank_account": str(cur2.pk), "cheque_number": f"PCH-{i:03d}",
             "bank_name": "ملی", "issuer": "شرکت", "due_date": j(day + 25)}])
    else:
        r = h.post_purchase(s, rows, mode="split", credit_due=j(day - 3), date=j(day), extra=extra)
    ok(f"purchase {i}", r)
for inv in PurchaseInvoice.objects.filter(status="confirmed").order_by("-created_at")[:1]:
    ok("cancel purchase", h.c.post(f"/purchasing/{inv.pk}/cancel/"))

# ---- cheques: clear a few, bounce one, cancel one
pending = list(Cheque.objects.filter(status="pending").order_by("created_at"))
for ch in pending[:3]:
    ok("clear cheque", h.clear_cheque(ch, account=cur1))
if len(pending) > 3:
    ok("bounce cheque", h.c.post(f"/cheques/{pending[3].pk}/bounce/"))
if len(pending) > 4:
    ok("cancel cheque", h.c.post(f"/cheques/{pending[4].pk}/cancel/"))

# ---- expenses: 30 (and a fixed one that repeats)
REASONS = ["اجارهٔ انبار", "قبض برق", "قبض آب", "حقوق کارمند", "ارسال بار", "تعمیرات", "تبلیغات", "ناهار", "بسته‌بندی", "خدمات حسابداری"]
for i in range(30):
    reason = REASONS[i % len(REASONS)]
    amount = random.choice([85000, 150000, 600000, 1250000, 3000000, 9800000])
    day = -(i % 28)
    kind = i % 3
    data = {"expense_date": j(day), "reason": reason, "amount": str(amount), "payment_method": ("transfer", "credit", "cheque")[kind]}
    if kind == 0:
        data["bank_account"] = str(cur1.pk)
    elif kind == 1:
        data["due_date"] = j(day + random.choice([-9, -1, 6, 25]))
    else:
        data.update({"bank_account": str(cur2.pk), "cheque_number": f"EXP-{i:03d}", "issuer": "شرکت", "cheque_due_date": j(day + 14)})
    ok(f"expense {i}", h.c.post("/expenses/new/", data))
for n, (reason, amount) in enumerate((("اجارهٔ دفتر", 8000000), ("اینترنت", 450000), ("بیمه", 2100000), ("نگهبانی", 1500000))):
    ok("recurring", h.c.post("/expenses/recurring/new/", {
        "reason": reason, "amount": str(amount), "repeat_every": "1", "repeat_unit": "month",
        "next_due_date": j((-3, 4, 12, 40)[n]), "remind_days_before": "3", "note": ""}))

# ---- a couple of returns (sales and purchase)
from apps.returns.services import record_sales_return  # noqa: E402,F401
for inv in SalesInvoice.objects.filter(status="confirmed").order_by("created_at")[:2]:
    item = inv.items.first()
    if item:
        ok("sales return", h.c.post(f"/returns/sales/new/{inv.pk}/", {
            "return_date": j(0), "settle_mode": "credit", f"cartons_{item.pk}": "", f"packs_{item.pk}": "1", "note": "نمونه"}))
for inv in PurchaseInvoice.objects.filter(status="confirmed").order_by("created_at")[:1]:
    item = inv.items.first()
    if item:
        ok("purchase return", h.c.post(f"/returns/purchases/new/{inv.pk}/", {
            "return_date": j(0), "settle_mode": "credit", f"packs_{item.pk}": "1", "note": "نمونه"}))

print("rich data ready:",
      f"{Customer.objects.count()} customers, {Supplier.objects.count()} suppliers, {Product.objects.count()} products,",
      f"{SalesInvoice.objects.count()} sales, {PurchaseInvoice.objects.count()} purchases, {Cheque.objects.count()} cheques")
if FAILS:
    print("seed failures:", len(FAILS))
    for line in FAILS[:15]:
        print("  ", line)

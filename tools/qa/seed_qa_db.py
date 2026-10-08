"""Fill the throwaway QA database (tools/qa/run_qa_server.py) with a sign-in user, accounts, products,
customers and suppliers. Writes the generated sign-in to a file next to the database, never to the console."""
import os
import pathlib
import random
import secrets
import sys

root = pathlib.Path(__file__).resolve().parents[2]
db = pathlib.Path(os.environ.get("QA_DB", root / "tools" / "qa" / ".qa.sqlite3"))
os.environ["DATABASE_URL"] = "sqlite:///" + db.as_posix()
os.environ.setdefault("SECRET_KEY", "throwaway-qa")
sys.path.insert(0, str(root))
os.chdir(root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from apps.inventory.services import set_opening_stock  # noqa: E402
from apps.partners.models import Customer, Supplier  # noqa: E402
from apps.payments.models import BankAccount  # noqa: E402
from apps.products.models import Product  # noqa: E402
from apps.users.models import User  # noqa: E402

phone = f"09{random.randint(100000000, 999999999)}"
password = secrets.token_urlsafe(10)
user = User.objects.create_superuser(phone=phone, password=password)
(db.parent / ".qa_login.txt").write_text(f"{phone}\n{password}\n", encoding="utf-8")
# One login file per database too, so parallel throwaway servers never read each other's credentials.
(db.parent / (db.name + ".login.txt")).write_text(f"{phone}\n{password}\n", encoding="utf-8")

BankAccount.objects.create(name="جاری ملت", account_number="QA-CUR-1", account_type="current", owner="شرکت")
BankAccount.objects.create(name="جاری ملی", account_number="QA-CUR-2", account_type="current", owner="شرکت")
BankAccount.objects.create(name="کارت‌خوان صندوق", account_number="QA-POS-1", account_type="pos", owner="شرکت")
for i, (name, price) in enumerate((("کاغذ A4", 250000), ("کاغذ A3", 480000), ("پوشه", 15000)), 1):
    product = Product.objects.create(name=name, sku=f"QA-P{i}", default_selling_price=price)
    set_opening_stock(product, 100, user, int(price * 0.7))
Customer.objects.create(name="مشتری آزمایشی ۱")
Customer.objects.create(name="مشتری آزمایشی ۲")
Supplier.objects.create(name="تأمین‌کنندهٔ آزمایشی")
print("seeded")

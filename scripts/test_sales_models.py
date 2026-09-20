# path: scripts/test_sales_models.py

from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.partners.models import Customer
from apps.products.models import Product
from apps.sales.models import SaleItem, SalesInvoice
from apps.shared.models import Business
from apps.shared.utils import format_rial

U = get_user_model()
u = U.objects.first()

b = Business.objects.create(name="تست", phone="02100000000")
c = Customer.objects.create(business=b, name="چاپخانه الف")
p1 = Product.objects.create(business=b, name="کاغذ A4", sku="P-001", unit="بسته")
p2 = Product.objects.create(business=b, name="کاغذ A5", sku="P-002", unit="بسته")

inv = SalesInvoice.objects.create(
    business=b, customer=c, invoice_number="SI-1001",
    invoice_date=date(2026, 9, 21), created_by=u,
)
SaleItem.objects.create(invoice=inv, product=p1, quantity=3, unit_price=3000000)
SaleItem.objects.create(invoice=inv, product=p2, quantity=2, unit_price=2000000)

print(inv, "| status:", inv.status, "| editable:", inv.is_editable)
print("total:", format_rial(inv.total_amount))

try:
    with transaction.atomic():
        SaleItem.objects.create(invoice=inv, product=p1, quantity=1, unit_price=100)
    print("FAIL: duplicate product allowed")
except IntegrityError:
    print("OK: unique product per invoice")

try:
    with transaction.atomic():
        SaleItem.objects.create(invoice=inv, product=p2, quantity=0, unit_price=100)
    print("FAIL: zero qty allowed")
except IntegrityError:
    print("OK: quantity>0 enforced")

print("items:", inv.items.count())
inv.delete()
print("items after delete:", SaleItem.objects.count())

Product.objects.all().delete()
Customer.objects.all().delete()
Business.objects.all().delete()
print("cleanup done:", Business.objects.count())
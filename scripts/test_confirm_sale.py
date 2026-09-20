# path: scripts/test_confirm_sale.py

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.inventory.models import InventoryMovement as IM
from apps.inventory.selectors import get_stock
from apps.partners.models import Customer, Supplier
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice, PurchaseItem
from apps.purchasing.services import confirm_purchase
from apps.sales.models import SaleItem, SalesInvoice
from apps.sales.services import confirm_sale
from apps.shared.models import Business

U = get_user_model()
u = U.objects.first()

b = Business.objects.create(name="تست", phone="02100000000")
c = Customer.objects.create(business=b, name="چاپخانه الف")
s = Supplier.objects.create(business=b, name="کارخانه ب")
p1 = Product.objects.create(business=b, name="کاغذ A4", sku="P-001", unit="بسته")
p2 = Product.objects.create(business=b, name="کاغذ A5", sku="P-002", unit="بسته")

# seed stock: 10 of p1, 4 of p2
pi = PurchaseInvoice.objects.create(business=b, supplier=s, invoice_number="PI-1",
                                    invoice_date=date(2026, 9, 21), created_by=u)
PurchaseItem.objects.create(invoice=pi, product=p1, quantity=10, unit_price=2500000)
PurchaseItem.objects.create(invoice=pi, product=p2, quantity=4, unit_price=1800000)
confirm_purchase(pi, u)
print("seed stock:", get_stock(p1), get_stock(p2))

# 1) empty invoice
si0 = SalesInvoice.objects.create(business=b, customer=c, invoice_number="SI-0",
                                  invoice_date=date(2026, 9, 21), created_by=u)
try:
    confirm_sale(si0, u)
    print("FAIL: empty confirmed")
except ValidationError as e:
    print("OK empty:", e.messages[0])

# 2) happy path, enough stock
si1 = SalesInvoice.objects.create(business=b, customer=c, invoice_number="SI-1",
                                  invoice_date=date(2026, 9, 21), created_by=u)
SaleItem.objects.create(invoice=si1, product=p1, quantity=3, unit_price=3000000)
inv, short = confirm_sale(si1, u)
print("status:", inv.status, "| shortages:", len(short))
print("stock p1:", get_stock(p1))

# 3) oversell -> allowed, reported
si2 = SalesInvoice.objects.create(business=b, customer=c, invoice_number="SI-2",
                                  invoice_date=date(2026, 9, 21), created_by=u)
SaleItem.objects.create(invoice=si2, product=p2, quantity=6, unit_price=2000000)
inv2, short2 = confirm_sale(si2, u)
print("oversell shortages:", [(x["product"].sku, x["available"], x["requested"], x["resulting"]) for x in short2])
print("stock p2:", get_stock(p2))
print("note marked:", "منفی" in IM.objects.filter(product=p2, movement_type="sale").first().note)

# 4) double confirm
before = IM.objects.count()
try:
    confirm_sale(inv2, u)
    print("FAIL: double confirm")
except ValidationError as e:
    print("OK double:", e.messages[0])
print("no extra movement:", IM.objects.count() == before)

# 5) foreign business product
b2 = Business.objects.create(name="تست۲", phone="02133333333")
px = Product.objects.create(business=b2, name="کالای غریبه", sku="X-1", unit="بسته")
si3 = SalesInvoice.objects.create(business=b, customer=c, invoice_number="SI-3",
                                  invoice_date=date(2026, 9, 21), created_by=u)
SaleItem.objects.create(invoice=si3, product=px, quantity=1, unit_price=100)
before = IM.objects.count()
try:
    confirm_sale(si3, u)
    print("FAIL: foreign accepted")
except ValidationError as e:
    print("OK foreign:", e.messages[0])
print("nothing written:", IM.objects.count() == before,
      "| still draft:", SalesInvoice.objects.get(pk=si3.pk).status)

# cleanup
IM.objects.all().delete()
SalesInvoice.objects.all().delete()
PurchaseInvoice.objects.all().delete()
Product.objects.all().delete()
Customer.objects.all().delete()
Supplier.objects.all().delete()
Business.objects.all().delete()
print("cleanup done:", IM.objects.count(), Business.objects.count())
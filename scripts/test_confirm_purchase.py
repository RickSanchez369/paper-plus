# path: scripts/test_confirm_purchase.py
# Throwaway verification script. Run with:  python manage.py shell < scripts/test_confirm_purchase.py

from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Case, F, IntegerField, Sum, When

from apps.inventory.models import InventoryMovement as IM
from apps.partners.models import Supplier
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice, PurchaseItem
from apps.purchasing.services import confirm_purchase
from apps.shared.models import Business

U = get_user_model()
u = U.objects.first()

b = Business.objects.create(name="طھط³طھ", phone="02100000000")
s = Supplier.objects.create(business=b, name="ع©ط§ط±ط®ط§ظ†ظ‡ ط¨")
p1 = Product.objects.create(business=b, name="ع©ط§ط؛ط° A4", sku="P-001", unit="ط¨ط³طھظ‡")
p2 = Product.objects.create(business=b, name="ع©ط§ط؛ط° A5", sku="P-002", unit="ط¨ط³طھظ‡")


def stock(p):
    return p.movements.aggregate(
        s=Sum(Case(
            When(movement_type__in=IM.INFLOW_TYPES, then=F("quantity")),
            default=-F("quantity"),
            output_field=IntegerField(),
        ))
    )["s"] or 0


# 1) empty invoice must fail
inv0 = PurchaseInvoice.objects.create(
    business=b, supplier=s, invoice_number="PI-0",
    invoice_date=date(2026, 9, 21), created_by=u,
)
try:
    confirm_purchase(inv0, u)
    print("FAIL: empty confirmed")
except ValidationError as e:
    print("OK empty:", e.messages[0])

# 2) happy path
inv = PurchaseInvoice.objects.create(
    business=b, supplier=s, invoice_number="PI-1",
    invoice_date=date(2026, 9, 21), created_by=u,
)
PurchaseItem.objects.create(invoice=inv, product=p1, quantity=10, unit_price=2500000)
PurchaseItem.objects.create(invoice=inv, product=p2, quantity=4, unit_price=1800000)
r = confirm_purchase(inv, u)
print("status:", r.status, "| confirmed_at set:", r.confirmed_at is not None)
print("stock p1:", stock(p1), "| p2:", stock(p2))
print("movements:", IM.objects.filter(business=b).count())

# 3) double confirmation must fail and write nothing
try:
    confirm_purchase(r, u)
    print("FAIL: double confirm")
except ValidationError as e:
    print("OK double:", e.messages[0])
print("movements after retry:", IM.objects.filter(business=b).count())

# 4) foreign-business product must fail and write nothing
b2 = Business.objects.create(name="طھط³طھغ²", phone="02133333333")
px = Product.objects.create(business=b2, name="ع©ط§ظ„ط§غŒ ط؛ط±غŒط¨ظ‡", sku="X-1", unit="ط¨ط³طھظ‡")
inv2 = PurchaseInvoice.objects.create(
    business=b, supplier=s, invoice_number="PI-2",
    invoice_date=date(2026, 9, 21), created_by=u,
)
PurchaseItem.objects.create(invoice=inv2, product=px, quantity=5, unit_price=100)
before = IM.objects.count()
try:
    confirm_purchase(inv2, u)
    print("FAIL: foreign product accepted")
except ValidationError as e:
    print("OK foreign:", e.messages[0])
print("no movement written:", IM.objects.count() == before,
      "| still draft:", PurchaseInvoice.objects.get(pk=inv2.pk).status)

# cleanup
IM.objects.all().delete()
PurchaseInvoice.objects.all().delete()
Product.objects.all().delete()
Supplier.objects.all().delete()
Business.objects.all().delete()
print("cleanup done:", IM.objects.count(), Business.objects.count())
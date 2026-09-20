"""Verify set_opening_stock (D-017)."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.inventory.models import InventoryMovement
from apps.inventory.selectors import get_stock
from apps.inventory.services import set_opening_stock
from apps.products.models import Product
from apps.shared.models import Business

User = get_user_model()

# --- fresh fixtures (Business created in this same block on purpose) ---
Business.objects.filter(name="TEST-OPENING").delete()
biz = Business.objects.create(name="TEST-OPENING")

user, _ = User.objects.get_or_create(phone="09120000001")

unit_field = Product._meta.get_field("unit")
unit_value = unit_field.choices[0][0] if unit_field.choices else "بسته"


def make_product(sku):
    return Product.objects.create(
        business=biz, name=f"P-{sku}", sku=sku, unit=unit_value
    )


ok = []
fail = []


def check(label, condition):
    (ok if condition else fail).append(label)


# 1. happy path: quantity > 0
p1 = make_product("SKU-1")
m = set_opening_stock(p1, 25, user)
p1.refresh_from_db()
check("1 movement created", m is not None and m.quantity == 25)
check("1 movement_type is opening", m.movement_type == "opening")
check("1 product onboarded", p1.is_onboarded is True)
check("1 stock == 25", get_stock(p1) == 25)

# 2. quantity == 0: no movement, still onboarded
p2 = make_product("SKU-2")
m2 = set_opening_stock(p2, 0, user)
p2.refresh_from_db()
check("2 returns None", m2 is None)
check("2 no movement row", not InventoryMovement.objects.filter(product=p2).exists())
check("2 product onboarded", p2.is_onboarded is True)
check("2 stock == 0", get_stock(p2) == 0)

# 3. second opening on an onboarded product is rejected
try:
    set_opening_stock(p1, 5, user)
    check("3 rejected", False)
except ValidationError:
    check("3 rejected", True)
check("3 stock unchanged", get_stock(p1) == 25)

# 4. rejected on a product that has movements but is not onboarded
p3 = make_product("SKU-3")
InventoryMovement.objects.create(
    business=biz,
    product=p3,
    movement_type="purchase",
    quantity=4,
    created_by=user,
)
try:
    set_opening_stock(p3, 10, user)
    check("4 rejected", False)
except ValidationError:
    check("4 rejected", True)
check("4 stock unchanged", get_stock(p3) == 4)

# 5. negative quantity rejected, nothing written
p4 = make_product("SKU-4")
try:
    set_opening_stock(p4, -3, user)
    check("5 rejected", False)
except ValidationError:
    check("5 rejected", True)
p4.refresh_from_db()
check("5 not onboarded", p4.is_onboarded is False)
check("5 no movement row", not InventoryMovement.objects.filter(product=p4).exists())

# --- report ---
for label in ok:
    print("PASS", label)
for label in fail:
    print("FAIL", label)
print(f"--- {len(ok)} passed, {len(fail)} failed ---")

# --- cleanup ---
InventoryMovement.objects.filter(business=biz).delete()
Product.objects.filter(business=biz).delete()
biz.delete()
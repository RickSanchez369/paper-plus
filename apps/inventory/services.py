#path: apps/inventory/services.py
"""Write services for the inventory ledger."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.products.models import Product
from apps.shared.audit import log_event

from .models import InventoryMovement


@transaction.atomic
def set_opening_stock(product, quantity, user, unit_price):
    """Record the one-time opening stock of a product (D-017).

    Refuses if the product is already onboarded or has any movement.
    A quantity of 0 marks the product onboarded without creating a movement,
    because the ledger forbids quantity = 0 (D-012); in that case unit_price
    is accepted but unused.

    Args:
        unit_price: Rial value for stock valuation (2.9); required even
            though this movement has no source invoice item.

    Returns the created InventoryMovement, or None when quantity == 0.
    """
    quantity = int(quantity)
    if quantity < 0:
        raise ValidationError("موجودی اولیه نمی‌تواند منفی باشد.")
    if unit_price is None or unit_price < 0:
        raise ValidationError("قیمت واحد نامعتبر است.")

    # Lock the product row; list() forces the queryset to evaluate.
    locked = list(Product.objects.select_for_update().filter(pk=product.pk))
    if not locked:
        raise ValidationError("محصول یافت نشد.")
    product = locked[0]

    if product.is_onboarded:
        raise ValidationError("موجودی اولیه این محصول قبلاً ثبت شده است.")

    if InventoryMovement.objects.filter(product=product).exists():
        raise ValidationError(
            "این محصول گردش انبار دارد؛ ثبت موجودی اولیه ممکن نیست."
        )

    movement = None
    if quantity > 0:
        movement = InventoryMovement.objects.create(
            product=product,
            movement_type=InventoryMovement.MovementType.OPENING,
            quantity=quantity,
            unit_price=unit_price,
            note="موجودی اولیه",
            created_by=user,
        )

    product.is_onboarded = True
    product.save(update_fields=["is_onboarded", "updated_at"])

    log_event(
        actor=user,
        event_type="opening_stock",
        target=movement or product,
        payload={"quantity": quantity},
    )

    return movement
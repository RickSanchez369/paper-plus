"""Write services for the inventory ledger."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.products.models import Product

from .models import InventoryMovement


@transaction.atomic
def set_opening_stock(product, quantity, user):
    """Record the one-time opening stock of a product (D-017).

    Refuses if the product is already onboarded or has any movement.
    A quantity of 0 marks the product onboarded without creating a movement,
    because the ledger forbids quantity = 0 (D-012).

    Returns the created InventoryMovement, or None when quantity == 0.
    """
    quantity = int(quantity)
    if quantity < 0:
        raise ValidationError("موجودی اولیه نمی‌تواند منفی باشد.")

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
            business=product.business,
            product=product,
            movement_type=InventoryMovement.MovementType.OPENING,
            quantity=quantity,
            note="موجودی اولیه",
            created_by=user,
        )

    product.is_onboarded = True
    product.save(update_fields=["is_onboarded", "updated_at"])
    return movement
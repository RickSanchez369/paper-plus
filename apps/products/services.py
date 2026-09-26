# path: apps/products/services.py

"""Write services for the product catalogue."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.shared.audit import log_event

from .models import Product


@transaction.atomic
def update_selling_price(product, new_price, user):
    """
    Set a product's current selling price (Product.default_selling_price).

    Touches nothing else, by design: every SaleItem already stores its own
    price snapshot (2.4), every purchase line and FIFO layer its own cost,
    and inventory value reads only those costs -- so a new selling price
    changes what the next sale suggests, never any past document or the
    value of stock on hand. History is kept twice: HistoricalProduct (the
    price-history section, attributed to `user`) and an AuditLog row.

    Returns the updated Product.

    Raises:
        ValidationError: the price is missing or negative.
    """
    if new_price is None or int(new_price) < 0:
        raise ValidationError("قیمت فروش نمی‌تواند منفی باشد.")
    new_price = int(new_price)

    locked = Product.objects.select_for_update().get(pk=product.pk)
    old_price = locked.default_selling_price
    if old_price == new_price:
        return locked

    locked.default_selling_price = new_price
    locked._history_user = user  # simple_history attributes the history row to this user
    locked.save(update_fields=["default_selling_price", "updated_at"])

    log_event(
        actor=user,
        event_type="change_selling_price",
        target=locked,
        # Not "amount": no money moved, and User Activity totals payload["amount"].
        payload={"old_price": old_price, "new_price": new_price},
    )
    return locked

# path: apps/products/services.py

"""Write services for the product catalogue."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.shared.audit import log_event

from .models import Product


@transaction.atomic
def update_selling_prices(product, user, *, retail=None, wholesale=None):
    """
    Set a product's current selling prices (D-075, D-100): ``retail`` is the
    pack price (Product.default_selling_price), ``wholesale`` the carton price
    (Product.wholesale_selling_price; 0 = unset, a carton then follows pack price x ratio).
    ``None`` means "leave that one alone" -- never 0 -- so two people editing
    different prices cannot overwrite each other with a blank.

    Touches nothing else, by design: every SaleItem already stores its own
    price snapshot (2.4), every purchase line and FIFO layer its own cost,
    and inventory value reads only those costs -- so a new selling price
    changes what the next sale suggests, never any past document or the
    value of stock on hand. History is kept twice: HistoricalProduct (the
    price-history section, attributed to `user`) and one AuditLog row per
    price that really changed.

    Returns the updated Product.

    Raises:
        ValidationError: a price is negative.
    """
    wanted = {}
    for tier, value, field in (
        ("retail", retail, "default_selling_price"),
        ("wholesale", wholesale, "wholesale_selling_price"),
    ):
        if value is None:
            continue
        if int(value) < 0:
            raise ValidationError("قیمت فروش نمی‌تواند منفی باشد.")
        wanted[tier] = (field, int(value))

    locked = Product.objects.select_for_update().get(pk=product.pk)
    changed = []
    for tier, (field, new_price) in wanted.items():
        old_price = getattr(locked, field)
        if old_price != new_price:
            setattr(locked, field, new_price)
            changed.append((tier, field, old_price, new_price))
    if not changed:
        return locked

    locked._history_user = user  # simple_history attributes the history row to this user
    locked.save(update_fields=[field for _, field, _, _ in changed] + ["updated_at"])
    for tier, _, old_price, new_price in changed:
        log_event(
            actor=user,
            event_type="change_selling_price",
            target=locked,
            # Not "amount": no money moved, and User Activity totals payload["amount"].
            payload={"tier": tier, "old_price": old_price, "new_price": new_price},
        )
    return locked


def update_selling_price(product, new_price, user):
    """Set the RETAIL price only (the one price there was before D-075); kept for callers that predate tiers."""
    return update_selling_prices(product, user, retail=new_price)

# path: apps/products/services.py

"""Write services for the product catalogue."""

from django.core.exceptions import PermissionDenied, ValidationError
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


def _has_records(product):
    """True when any document, movement or layer still points at the product."""
    return any(
        rel.related_model._default_manager.filter(**{rel.field.name: product}).exists()
        for rel in Product._meta.related_objects
        if rel.one_to_many or rel.one_to_one
    )


@transaction.atomic
def remove_product(product, user):
    """
    Take a product out of the warehouse (superuser only). Returns "deleted" or "archived".

    A product nothing ever touched (a typo, a test entry) is really deleted. One with
    history -- opening stock, an invoice line, a layer -- can never be deleted, because
    those documents and the FIFO cost trail must keep reading; it is archived instead
    (is_active=False: gone from the inventory list and from the sale / purchase pickers,
    history intact). Stock must be zero first: archiving stock that is still on the
    shelf would hide value the reports still count.
    """
    # Local import: inventory.selectors imports products.models, not the other way round.
    from apps.inventory.selectors import get_stock_map

    if not user.is_superuser:
        raise PermissionDenied("حذف کالا فقط برای مدیر سیستم مجاز است.")
    product = Product.objects.select_for_update().get(pk=product.pk)
    stock = get_stock_map([product.pk]).get(product.pk, 0)
    if stock != 0:
        raise ValidationError("موجودی این کالا صفر نیست؛ حذف فقط وقتی ممکن است که موجودی صفر باشد.")

    name, sku = product.name, product.sku
    if not _has_records(product):
        # Logged first: delete() clears the instance's pk, and the log row keeps no FK anyway (D-029).
        log_event(actor=user, event_type="product.deleted", target=product, payload={"name": name, "sku": sku})
        product.delete()
        return "deleted"

    product.is_active = False
    product.save(update_fields=["is_active", "updated_at"])
    log_event(actor=user, event_type="product.archived", target=product, payload={"name": name, "sku": sku})
    return "archived"

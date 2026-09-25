#path: apps/inventory/services.py
"""Write services for the inventory ledger and its FIFO cost layers."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.products.models import Product
from apps.shared.audit import log_event

from .models import InventoryConsumption, InventoryLayer, InventoryMovement


@transaction.atomic
def set_opening_stock(product, quantity, user, unit_price):
    """Record the one-time opening stock of a product (D-017).

    Refuses if the product is already onboarded or has any movement.
    A quantity of 0 marks the product onboarded without creating a movement,
    because the ledger forbids quantity = 0 (D-012); in that case unit_price
    is accepted but unused.

    Args:
        unit_price: Rial value for stock valuation (2.9); required even
            though this movement has no source invoice item. It also becomes
            the cost basis of the InventoryLayer this creates.

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
        # The first FIFO layer: counted-in stock, at the price it is valued at.
        layer = InventoryLayer.objects.create(
            product=product,
            source=InventoryLayer.Source.OPENING,
            quantity=quantity,
            quantity_remaining=quantity,
            unit_cost=unit_price,
            created_by=user,
        )
        movement = InventoryMovement.objects.create(
            product=product,
            movement_type=InventoryMovement.MovementType.OPENING,
            quantity=quantity,
            unit_price=unit_price,
            layer=layer,
            note="موجودی اولیه",
            created_by=user,
        )

    product.is_onboarded = True
    product.save(update_fields=["is_onboarded", "updated_at"])

    log_event(
        actor=user,
        event_type="opening_stock",
        target=movement or product,
        payload={"quantity": quantity, "unit_price": unit_price},
    )

    return movement


def consume_fifo(sale_item, quantity, user, note=""):
    """
    Draw ``quantity`` units for ``sale_item`` from its product's layers,
    oldest first, recording exactly what each layer gave.

    Must be called inside the caller's transaction, with the product row
    already locked (confirm_sale does both) -- the layer rows are locked
    here as well, so two concurrent sales of the same product cannot both
    read the same remaining balance.

    Returns:
        (consumptions, uncosted) -- the InventoryConsumption rows created,
        and how many units found no layer at all. ``uncosted`` is only ever
        non-zero on an oversell, which is superuser-only (D-016) and should
        not happen under the current policy; those units genuinely have no
        cost basis, so they are reported rather than guessed at.
    """
    remaining_to_take = quantity
    consumptions = []

    layers = (
        InventoryLayer.objects
        .select_for_update()
        .filter(
            product_id=sale_item.product_id,
            cancelled_at__isnull=True,
            quantity_remaining__gt=0,
        )
        .order_by("created_at", "id")
    )

    for layer in layers:
        if remaining_to_take <= 0:
            break
        taken = min(layer.quantity_remaining, remaining_to_take)
        consumptions.append(
            InventoryConsumption.objects.create(
                sale_item=sale_item,
                layer=layer,
                quantity=taken,
                note=note,
                created_by=user,
            )
        )
        layer.quantity_remaining -= taken
        layer.save(update_fields=["quantity_remaining", "updated_at"])
        remaining_to_take -= taken

    return consumptions, remaining_to_take


def restore_consumptions(sale_item, user, note=""):
    """
    Give back to each layer exactly what ``sale_item`` took from it.

    Reversal is by recorded amount, not by FIFO order: a later sale may
    have drawn further from the same layers in the meantime, and putting
    the units back where they came from keeps every layer's arithmetic
    right regardless of what happened in between (REDESIGN_VISION 8).

    Append-only: the original consumption rows are never edited or deleted,
    an opposite row is added instead, so a layer's balance stays
    ``quantity - sum(its consumption quantities)``.

    Must be called inside the caller's transaction.
    """
    balances = {}
    for consumption in InventoryConsumption.objects.filter(sale_item=sale_item):
        balances[consumption.layer_id] = balances.get(consumption.layer_id, 0) + consumption.quantity

    reversals = []
    for layer in InventoryLayer.objects.select_for_update().filter(pk__in=balances):
        outstanding = balances[layer.pk]
        if outstanding == 0:
            # Already reversed; cancelling twice must not hand stock back twice.
            continue
        reversals.append(
            InventoryConsumption.objects.create(
                sale_item=sale_item,
                layer=layer,
                quantity=-outstanding,
                note=note,
                created_by=user,
            )
        )
        layer.quantity_remaining += outstanding
        layer.save(update_fields=["quantity_remaining", "updated_at"])

    return reversals


@transaction.atomic
def record_adjustment(product, movement_type, quantity, user, note, unit_price=None):
    """
    Manual stock correction, outside any invoice (REDESIGN_VISION 4.3).

    A mandatory reason note is the only safeguard -- any authenticated
    user may record one, same as confirm_sale/confirm_purchase
    (apps/shared/permissions.py: exactly two actions are superuser-gated,
    and this is not one of them).

    `movement_type` is `InventoryMovement.MovementType.ADJUSTMENT_IN` or
    `ADJUSTMENT_OUT`:
    - IN opens a brand-new FIFO layer at `unit_price` (required -- an
      increase has to enter the cost basis somewhere, same rule
      `set_opening_stock` already follows).
    - OUT consumes existing active layers oldest-first, exactly like a
      sale, recording an `InventoryConsumption` per layer touched
      (`movement=` instead of `sale_item=`) -- so it can never remove more
      stock than the FIFO ledger says exists; an adjustment corrects a
      count, it does not manufacture an oversell. Its `unit_price` is the
      weighted-average cost of what it actually consumed, filled in after.

    Returns the created InventoryMovement.
    """
    quantity = int(quantity)
    if quantity <= 0:
        raise ValidationError("مقدار اصلاح باید بزرگ‌تر از صفر باشد.")
    note = (note or "").strip()
    if not note:
        raise ValidationError("دلیل اصلاح الزامی است.")
    if movement_type not in (InventoryMovement.MovementType.ADJUSTMENT_IN, InventoryMovement.MovementType.ADJUSTMENT_OUT):
        raise ValidationError("نوع اصلاح نامعتبر است.")

    locked = list(Product.objects.select_for_update().filter(pk=product.pk))
    if not locked:
        raise ValidationError("محصول یافت نشد.")
    product = locked[0]

    if movement_type == InventoryMovement.MovementType.ADJUSTMENT_IN:
        if unit_price is None or unit_price < 0:
            raise ValidationError("قیمت واحد نامعتبر است.")
        layer = InventoryLayer.objects.create(
            product=product,
            source=InventoryLayer.Source.ADJUSTMENT,
            quantity=quantity,
            quantity_remaining=quantity,
            unit_cost=unit_price,
            created_by=user,
        )
        movement = InventoryMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=quantity,
            unit_price=unit_price,
            layer=layer,
            note=note,
            created_by=user,
        )
    else:
        movement = InventoryMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=quantity,
            unit_price=0,  # replaced below with the real weighted cost once known
            note=note,
            created_by=user,
        )
        layers = (
            InventoryLayer.objects
            .select_for_update()
            .filter(product=product, cancelled_at__isnull=True, quantity_remaining__gt=0)
            .order_by("created_at", "id")
        )
        remaining_to_take = quantity
        total_cost = 0
        for layer in layers:
            if remaining_to_take <= 0:
                break
            taken = min(layer.quantity_remaining, remaining_to_take)
            InventoryConsumption.objects.create(
                movement=movement,
                layer=layer,
                quantity=taken,
                note=note,
                created_by=user,
            )
            layer.quantity_remaining -= taken
            layer.save(update_fields=["quantity_remaining", "updated_at"])
            total_cost += taken * layer.unit_cost
            remaining_to_take -= taken

        if remaining_to_take > 0:
            # Rolls back the whole atomic block -- movement and every
            # consumption row created above are undone with it.
            raise ValidationError(
                f"موجودی «{product.name}» کافی نیست؛ حداکثر {quantity - remaining_to_take} "
                f"واحد از {quantity} واحد درخواستی قابل کاهش است."
            )

        movement.unit_price = total_cost // quantity
        movement.save(update_fields=["unit_price", "updated_at"])

    log_event(
        actor=user,
        event_type="record_adjustment",
        target=movement,
        payload={"movement_type": movement_type, "quantity": quantity, "note": note},
    )

    return movement


def cancel_layer(layer, user):
    """
    Take a layer out of the FIFO pool, for a cancelled purchase.

    Only an untouched layer may go: once any of it has been sold, removing
    it would leave that sale's recorded cost pointing at stock the system
    says never existed (REDESIGN_VISION 3). Such a purchase has to be
    corrected some other way, not cancelled.

    Must be called inside the caller's transaction.
    """
    locked = InventoryLayer.objects.select_for_update().get(pk=layer.pk)
    if locked.cancelled_at is not None:
        raise ValidationError("این لایه انبار قبلاً لغو شده است.")
    if locked.quantity_remaining != locked.quantity:
        sold = locked.quantity - locked.quantity_remaining
        raise ValidationError(
            f"از «{locked.product.name}» {sold} واحد از این خرید قبلاً فروخته شده است؛ "
            f"لغو این فاکتور خرید ممکن نیست."
        )
    locked.cancelled_at = timezone.now()
    locked.save(update_fields=["cancelled_at", "updated_at"])
    return locked

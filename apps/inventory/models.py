# path: apps/inventory/models.py

from django.conf import settings
from django.db import models

from apps.products.models import Product
from apps.shared.models import BaseModel


class InventoryMovement(BaseModel):
    """
    Append-only ledger of stock changes. The single source of truth for stock.

    Rows are never updated or deleted. Stock changes through documents
    only (D-044): opening stock once, at product creation; a confirmed
    purchase or sale; and the ADJUSTMENT rows that cancel_purchase /
    cancel_sale write to reverse one. There is no manual adjustment path --
    ADJUSTMENT_IN/OUT exist solely for those system reversals.
    quantity is always > 0; direction comes from movement_type (D-012).
    """

    class MovementType(models.TextChoices):
        OPENING = "opening", "موجودی اولیه"
        PURCHASE = "purchase", "خرید"
        SALE = "sale", "فروش"
        ADJUSTMENT_IN = "adjustment_in", "برگشت لغو فاکتور - افزایش"  # cancel_sale only (D-044)
        ADJUSTMENT_OUT = "adjustment_out", "برگشت لغو فاکتور - کاهش"  # cancel_purchase only (D-044)

    # movement types that increase stock; everything else decreases it
    INFLOW_TYPES = (
        MovementType.OPENING,
        MovementType.PURCHASE,
        MovementType.ADJUSTMENT_IN,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,  # a product with history can never be deleted
        related_name="movements",
        verbose_name="کالا",
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
        verbose_name="نوع حرکت",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="مقدار",  # always positive; see D-012
    )
    unit_price = models.BigIntegerField(
        null=True,
        blank=True,  # required in practice for every type (2.9); nullable here only
        verbose_name="قیمت واحد (تومان)",  # because a CHECK cannot express "required per type"
    )
    purchase_item = models.ForeignKey(
        "purchasing.PurchaseItem",
        on_delete=models.PROTECT,  # a confirmed invoice's items are frozen anyway (D-014)
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="ردیف فاکتور خرید",
    )
    sale_item = models.ForeignKey(
        "sales.SaleItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="ردیف فاکتور فروش",
    )
    layer = models.ForeignKey(
        "InventoryLayer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set only for opening, the one layer-creating type with no invoice
        related_name="+",  # the layer already links back via InventoryLayer.purchase_item / consumptions
        verbose_name="لایهٔ ایجادشده",
        help_text="فقط برای موجودی اولیه؛ نوع‌های دیگر لایه را از طریق فاکتور یا مصرف پیدا می‌کنند.",
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیح",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # keep the audit trail
        related_name="inventory_movements",
        verbose_name="ثبت‌کننده",
    )

    class Meta:
        verbose_name = "حرکت انبار"
        verbose_name_plural = "حرکات انبار"
        ordering = ["-created_at"]
        indexes = [
            # stock is computed per product; this is the hot query path
            models.Index(fields=["product", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="inventory_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__isnull=True) | models.Q(unit_price__gte=0),
                name="inventory_unit_price_non_negative",
            ),
            models.CheckConstraint(
                # Each row's item reference must match its own movement_type;
                # opening/adjustment rows carry neither (R 13, ROADMAP 2.9).
                condition=(
                    models.Q(movement_type="purchase", purchase_item__isnull=False, sale_item__isnull=True)
                    | models.Q(movement_type="sale", sale_item__isnull=False, purchase_item__isnull=True)
                    | models.Q(
                        movement_type__in=["opening", "adjustment_in", "adjustment_out"],
                        purchase_item__isnull=True,
                        sale_item__isnull=True,
                    )
                ),
                name="inventory_item_reference_matches_type",
            ),
        ]

    def __str__(self):
        sign = "+" if self.movement_type in self.INFLOW_TYPES else "-"
        return f"{self.product} {sign}{self.quantity} ({self.get_movement_type_display()})"

    @property
    def signed_quantity(self):
        """Quantity with its effect on stock: positive for inflow, negative for outflow."""
        return self.quantity if self.movement_type in self.INFLOW_TYPES else -self.quantity

class InventoryLayer(BaseModel):
    """
    One batch of stock bought (or counted in) at one known unit cost.

    The cost basis of the business, replacing the old "latest purchase
    price" approximation (`get_cost_map`) with real FIFO: a sale consumes
    the oldest layer first and records exactly what it took in
    `InventoryConsumption`, so every sold line has a true cost and every
    cancellation can be reversed exactly.

    Layers do not replace `InventoryMovement`, which stays the immutable
    source of truth for *how much* stock exists. A layer answers a
    different question -- *what that stock cost* -- and unlike a movement
    it carries a running balance (`quantity_remaining`) that is maintained
    as sales consume it. That balance is never authoritative on its own:
    it is always reconstructable as
    ``quantity - sum(consumption.quantity)``, the same
    way `Payment.allocated_amount` derives from its allocations.
    """

    class Source(models.TextChoices):
        OPENING = "opening_stock", "موجودی اولیه"
        PURCHASE = "purchase_item", "قلم فاکتور خرید"

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_layers",
        verbose_name="کالا",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        verbose_name="منشأ",
    )
    purchase_item = models.OneToOneField(
        "purchasing.PurchaseItem",
        on_delete=models.PROTECT,  # a confirmed invoice's items are frozen (D-014)
        null=True,
        blank=True,  # null for an opening-stock layer; see the CHECK below
        related_name="layer",
        verbose_name="ردیف فاکتور خرید",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="مقدار اولیه",  # never changes; the cancellation guard compares against it
    )
    quantity_remaining = models.PositiveIntegerField(
        verbose_name="مانده",
    )
    unit_cost = models.BigIntegerField(
        verbose_name="بهای واحد (تومان)",
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,  # set by cancel_purchase; a cancelled layer leaves the FIFO pool
        editable=False,
        verbose_name="زمان لغو",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # keep the audit trail
        related_name="inventory_layers",
        verbose_name="ثبت‌کننده",
    )

    class Meta:
        verbose_name = "لایه انبار"
        verbose_name_plural = "لایه‌های انبار"
        # FIFO order. `id` breaks ties so two layers created in the same
        # instant are still consumed in one fixed, reproducible order.
        ordering = ["created_at", "id"]
        indexes = [
            # The hot path: "oldest layer of this product with stock left".
            models.Index(fields=["product", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="inventory_layer_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_remaining__lte=models.F("quantity")),
                name="inventory_layer_remaining_within_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="inventory_layer_unit_cost_non_negative",
            ),
            models.CheckConstraint(
                # Each layer's source must match its item reference, mirroring
                # InventoryMovement's own item-reference CHECK. An opening-stock
                # layer has no invoice line to point at.
                condition=(
                    models.Q(source="purchase_item", purchase_item__isnull=False)
                    | models.Q(source="opening_stock", purchase_item__isnull=True)
                ),
                name="inventory_layer_source_matches_item",
            ),
        ]

    def __str__(self):
        return f"{self.product} — {self.quantity_remaining}/{self.quantity} @ {self.unit_cost}"

    @property
    def is_active(self):
        """True while this layer can still be sold from."""
        return self.cancelled_at is None and self.quantity_remaining > 0

    @property
    def remaining_value(self):
        """Toman still sitting in this layer."""
        return self.quantity_remaining * self.unit_cost


class InventoryConsumption(BaseModel):
    """
    Exactly how much of one layer one sale item took (D-036). A sale is the
    only thing that draws FIFO layers down -- the manual adjustment_out
    that once did too is gone (D-044).

    Append-only, like every other ledger here (D-012): a cancellation does
    not delete or edit these rows, it adds an opposite one with a negative
    `quantity`, the same way a cancelled invoice gets a compensating
    `InventoryMovement` instead of having its original row rewritten.
    A layer's balance is therefore always
    ``layer.quantity - sum(its consumption quantities)``.
    """

    sale_item = models.ForeignKey(
        "sales.SaleItem",
        on_delete=models.PROTECT,
        related_name="consumptions",
        verbose_name="ردیف فاکتور فروش",
    )
    layer = models.ForeignKey(
        InventoryLayer,
        on_delete=models.PROTECT,
        related_name="consumptions",
        verbose_name="لایه انبار",
    )
    quantity = models.IntegerField(
        verbose_name="مقدار",  # > 0 consumed by a sale, < 0 returned by a cancellation
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیح",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_consumptions",
        verbose_name="ثبت‌کننده",
    )

    class Meta:
        verbose_name = "مصرف لایه انبار"
        verbose_name_plural = "مصارف لایه انبار"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["sale_item"]),
            models.Index(fields=["layer"]),
        ]
        constraints = [
            models.CheckConstraint(
                # 0 would be a no-op row with no meaning; the sign carries
                # the direction, exactly like InventoryMovement (D-012).
                condition=~models.Q(quantity=0),
                name="inventory_consumption_quantity_not_zero",
            ),
        ]

    def __str__(self):
        return f"{self.sale_item} ← {self.layer} ({self.quantity})"

    @property
    def cost(self):
        """Toman this row accounts for, at the layer's own cost."""
        return self.quantity * self.layer.unit_cost

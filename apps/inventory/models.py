# path: apps/inventory/models.py

from django.conf import settings
from django.db import models

from apps.products.models import Product
from apps.shared.models import BaseModel, Business


class InventoryMovement(BaseModel):
    """
    Append-only ledger of stock changes. The single source of truth for stock.

    Rows are never updated or deleted. A mistake is corrected by adding a
    compensating ADJUSTMENT movement, so the history stays auditable.
    quantity is always > 0; direction comes from movement_type (D-012).
    """

    class MovementType(models.TextChoices):
        OPENING = "opening", "موجودی اولیه"
        PURCHASE = "purchase", "خرید"
        SALE = "sale", "فروش"
        ADJUSTMENT_IN = "adjustment_in", "اصلاح - افزایش"
        ADJUSTMENT_OUT = "adjustment_out", "اصلاح - کاهش"

    # movement types that increase stock; everything else decreases it
    INFLOW_TYPES = (
        MovementType.OPENING,
        MovementType.PURCHASE,
        MovementType.ADJUSTMENT_IN,
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
        verbose_name="کسب‌وکار",
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
        ]

    def __str__(self):
        sign = "+" if self.movement_type in self.INFLOW_TYPES else "-"
        return f"{self.product} {sign}{self.quantity} ({self.get_movement_type_display()})"

    @property
    def signed_quantity(self):
        """Quantity with its effect on stock: positive for inflow, negative for outflow."""
        return self.quantity if self.movement_type in self.INFLOW_TYPES else -self.quantity
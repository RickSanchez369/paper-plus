# path: apps/products/models.py

from django.db import models
from simple_history.models import HistoricalRecords

from apps.shared.models import BaseModel
from apps.shared.utils import format_number


class Product(BaseModel):
    """
    A product the business sells or purchases.

    Stock is never stored here; it is derived from InventoryMovement.
    """

    name = models.CharField(
        max_length=200,
        verbose_name="نام کالا",
    )
    sku = models.CharField(
        max_length=50,
        verbose_name="کد کالا",
    )
    unit = models.CharField(
        max_length=20,
        verbose_name="واحد",  # e.g. بسته، رول، کیلوگرم
    )
    description = models.TextField(
        blank=True,
        verbose_name="توضیحات",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )
    is_onboarded = models.BooleanField(
        default=False,
        verbose_name="موجودی اولیه ثبت شده",
        help_text="پس از ثبت موجودی اولیه True می‌شود و ثبت مجدد ممکن نیست.",
    )
    default_selling_price = models.BigIntegerField(
        default=0,
        verbose_name="قیمت فروش پیش‌فرض (ریال)",
        help_text="برای پر کردن خودکار قیمت در فاکتور فروش؛ تغییر آن قیمت فاکتورهای قبلی را عوض نمی‌کند.",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "کالا"
        verbose_name_plural = "کالاها"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["sku"],
                name="unique_product_sku",
            ),
            models.CheckConstraint(
                condition=models.Q(default_selling_price__gte=0),
                name="product_default_selling_price_non_negative",
            ),
        ]

    def __str__(self):
        # Unsaved instance (e.g. an add-form preview): no pk yet, so no
        # ledger to query.
        if self._state.adding:
            return f"{self.name} ({self.sku})"      
        # Local import: apps.inventory.models imports Product, so importing
        # apps.inventory.selectors at module level here would be circular.
        from apps.inventory.selectors import get_stock

        return f"{self.name} ({self.sku}) — موجودی: {format_number(get_stock(self))}"
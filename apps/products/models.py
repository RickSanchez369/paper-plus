# path: apps/products/models.py

from django.db import models
from simple_history.models import HistoricalRecords

from apps.shared.models import BaseModel, Business


class Product(BaseModel):
    """
    A product sold or purchased by a business.

    Stock is never stored here; it is derived from InventoryMovement.
    """

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,  # never lose products by deleting a business
        related_name="products",
        verbose_name="کسب‌وکار",
    )
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

    history = HistoricalRecords()

    class Meta:
        verbose_name = "کالا"
        verbose_name_plural = "کالاها"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "sku"],
                name="unique_sku_per_business",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"
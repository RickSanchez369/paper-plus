# path: apps/partners/models.py

from django.db import models

from apps.products.models import PriceTier
from apps.shared.models import BaseModel


class Customer(BaseModel):
    """A buyer of the business's products."""

    name = models.CharField(
        max_length=200,
        verbose_name="نام مشتری",
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="تلفن",
    )
    address = models.TextField(
        blank=True,
        verbose_name="نشانی",
    )
    note = models.TextField(
        blank=True,
        verbose_name="یادداشت",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )
    # D-090: the sale type a new invoice for this customer starts with (still changeable there).
    price_tier = models.CharField(
        max_length=10,
        choices=PriceTier.choices,
        default=PriceTier.RETAIL,
        verbose_name="نوع مشتری",
        help_text="فاکتور فروش جدید برای این مشتری با همین نوع (خرد/عمده) باز می‌شود؛ روی فاکتور قابل تغییر است.",
    )

    class Meta:
        verbose_name = "مشتری"
        verbose_name_plural = "مشتریان"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="unique_customer_name",
            ),
        ]

    def __str__(self):
        return self.name


class Supplier(BaseModel):
    """A vendor the business buys products from."""

    name = models.CharField(
        max_length=200,
        verbose_name="نام تأمین‌کننده",
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="تلفن",
    )
    address = models.TextField(
        blank=True,
        verbose_name="نشانی",
    )
    note = models.TextField(
        blank=True,
        verbose_name="یادداشت",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    class Meta:
        verbose_name = "تأمین‌کننده"
        verbose_name_plural = "تأمین‌کنندگان"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="unique_supplier_name",
            ),
        ]

    def __str__(self):
        return self.name
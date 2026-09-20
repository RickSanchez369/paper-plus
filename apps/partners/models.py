# path: apps/partners/models.py

from django.db import models

from apps.shared.models import BaseModel, Business


class Customer(BaseModel):
    """A buyer of the business's products."""

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,  # customers hold financial history
        related_name="customers",
        verbose_name="کسب‌وکار",
    )
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

    class Meta:
        verbose_name = "مشتری"
        verbose_name_plural = "مشتریان"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="unique_customer_name_per_business",
            ),
        ]

    def __str__(self):
        return self.name


class Supplier(BaseModel):
    """A vendor the business buys products from."""

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="suppliers",
        verbose_name="کسب‌وکار",
    )
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
                fields=["business", "name"],
                name="unique_supplier_name_per_business",
            ),
        ]

    def __str__(self):
        return self.name
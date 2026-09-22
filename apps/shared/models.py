# path: apps/shared/models.py

import uuid

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class BaseModel(models.Model):
    """
    Abstract base for all main models.

    Provides a UUID primary key and creation/update timestamps.
    Being abstract, it creates no table of its own; the fields are
    added to each concrete model that inherits from it.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,  # the function itself, not a call
        editable=False,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,  # set once, on creation
        verbose_name="تاریخ ایجاد",
    )
    updated_at = models.DateTimeField(
        auto_now=True,  # refreshed on every save()
        verbose_name="آخرین ویرایش",
    )

    class Meta:
        abstract = True


class Business(BaseModel):
    """
    A single business managed by the system.

    Every other record in the system belongs to exactly one Business
    (non-negotiable rule 1). Data of different businesses never mixes.
    """

    name = models.CharField(
        max_length=200,
        verbose_name="نام کسب‌وکار",
    )
    legal_name = models.CharField(
        max_length=255,
        blank=True,  # optional in forms; stored as "" when empty
        verbose_name="نام حقوقی",
    )
    registration_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="شماره ثبت",
    )
    phone = models.CharField(
        max_length=30,
        verbose_name="تلفن",
    )
    address = models.TextField(
        blank=True,
        verbose_name="نشانی",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    class Meta:
        verbose_name = "کسب‌وکار"
        verbose_name_plural = "کسب‌وکارها"
        ordering = ["name"]

    def __str__(self):
        return self.name
    
    
class BusinessMembership(BaseModel):
    """Which user belongs to which business, and in what role."""

    class Role(models.TextChoices):
        OWNER = "owner", "مالک"
        SALESPERSON = "salesperson", "فروشنده"

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="کسب‌وکار",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="کاربر",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        verbose_name="نقش",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "عضویت در کسب‌وکار"
        verbose_name_plural = "عضویت‌های کسب‌وکار"
        constraints = [
            models.UniqueConstraint(
                fields=["business", "user"],
                name="unique_membership_per_business_user",
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.business} ({self.get_role_display()})"
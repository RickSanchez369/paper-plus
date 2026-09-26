# path: apps/shared/models.py

import uuid

from django.conf import settings
from django.db import models


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


class AuditLog(BaseModel):
    """
    Append-only record of service-level events (D-029).

    Never updated or deleted after creation; edit/delete are blocked
    at the admin layer, same policy as InventoryMovement (D-012).
    """

    class EventType(models.TextChoices):
        OPENING_STOCK = "opening_stock", "ثبت موجودی اولیه"
        CONFIRM_PURCHASE = "confirm_purchase", "تأیید فاکتور خرید"
        CONFIRM_SALE = "confirm_sale", "تأیید فاکتور فروش"
        CANCEL_PURCHASE = "cancel_purchase", "لغو فاکتور خرید"
        CANCEL_SALE = "cancel_sale", "لغو فاکتور فروش"
        RECORD_PAYMENT = "record_payment", "ثبت پرداخت"
        ALLOCATE_PAYMENT = "allocate_payment", "تخصیص پرداخت"
        RECORD_CHEQUE = "record_cheque", "ثبت چک"
        CLEAR_CHEQUE = "clear_cheque", "وصول چک"
        BOUNCE_CHEQUE = "bounce_cheque", "برگشت چک"
        CANCEL_CHEQUE = "cancel_cheque", "لغو چک"
        RECORD_EXPENSE = "record_expense", "ثبت هزینه"
        CANCEL_EXPENSE = "cancel_expense", "لغو هزینه"
        # No longer written (manual adjustment removed, D-044); kept so
        # rows logged before that still show a label instead of a raw key.
        RECORD_ADJUSTMENT = "record_adjustment", "ثبت اصلاح موجودی"
        CHANGE_SELLING_PRICE = "change_selling_price", "تغییر قیمت فروش"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        verbose_name="عامل",
    )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        verbose_name="نوع رویداد",
    )
    # lightweight reference instead of GenericForeignKey, e.g. "purchasing.PurchaseInvoice"
    target_type = models.CharField(
        max_length=100,
        verbose_name="نوع هدف",
    )
    target_id = models.UUIDField(
        verbose_name="شناسه هدف",
    )
    payload = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="جزئیات",
    )

    class Meta:
        verbose_name = "رویداد ممیزی"
        verbose_name_plural = "رویدادهای ممیزی"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.target_type}:{self.target_id}"


class DocumentSequence(BaseModel):
    """
    Per-document-type counter for invoice numbers (D-022).

    ``next_number`` is the number to hand out next. Issuing it safely
    under concurrency is the job of the service function that locks
    this row with ``select_for_update()`` inside a transaction — this
    model only holds the state.
    """

    class DocType(models.TextChoices):
        SALE = "sale", "فاکتور فروش"
        PURCHASE = "purchase", "فاکتور خرید"

    doc_type = models.CharField(
        max_length=20,
        choices=DocType.choices,
        verbose_name="نوع سند",
    )
    next_number = models.PositiveIntegerField(
        default=1,  # configurable once, at setup time
        verbose_name="شماره بعدی",
    )

    class Meta:
        verbose_name = "شمارنده سند"
        verbose_name_plural = "شمارنده‌های سند"
        constraints = [
            models.UniqueConstraint(
                fields=["doc_type"],
                name="unique_document_sequence_per_doctype",
            ),
        ]

    def __str__(self):
        return f"{self.get_doc_type_display()} ({self.next_number})"
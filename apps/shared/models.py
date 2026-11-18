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


class FinancialSubmission(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    path = models.CharField(max_length=255)
    token = models.UUIDField()
    location = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "path", "token"], name="unique_financial_submission"),
        ]


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
        REVERSE_PAYMENT = "reverse_payment", "برگشت پرداخت بابت لغو فاکتور"
        APPLY_CREDIT = "apply_credit", "کسر بستانکاری از فاکتور"
        SALES_RETURN = "sales_return", "ثبت مرجوعی فروش"
        PURCHASE_RETURN = "purchase_return", "ثبت مرجوعی خرید"
        CANCEL_SALES_RETURN = "cancel_sales_return", "لغو مرجوعی فروش"
        CANCEL_PURCHASE_RETURN = "cancel_purchase_return", "لغو مرجوعی خرید"
        RECORD_EXPENSE = "record_expense", "ثبت هزینه"
        CANCEL_EXPENSE = "cancel_expense", "لغو هزینه"
        PAY_EXPENSE = "pay_expense", "پرداخت هزینه"
        SKIP_RECURRING_EXPENSE = "skip_recurring_expense", "رد کردن نوبت هزینهٔ ثابت"
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
    Per-document-type, per-Jalali-year counter for invoice numbers (D-022, D-064);
    sales count per Jalali day instead (``day``, D-086).

    ``next_number`` is the number to hand out next within ``year``; a new
    year starts again at 1. Issuing it safely under concurrency is the job
    of the service function that locks this row with ``select_for_update()``
    inside a transaction — this model only holds the state. ``year`` 0 is
    the single legacy counter from before D-064 and is no longer used.
    """

    class DocType(models.TextChoices):
        SALE = "sale", "فاکتور فروش"
        PURCHASE = "purchase", "فاکتور خرید"
        SALES_RETURN = "sales_return", "مرجوعی فروش"
        PURCHASE_RETURN = "purchase_return", "مرجوعی خرید"

    doc_type = models.CharField(
        max_length=20,
        choices=DocType.choices,
        verbose_name="نوع سند",
    )
    year = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="سال شمسی",
    )
    # Sales count per invoice day since D-086 (Jalali MMDD, e.g. 712 for 12 Mehr);
    # 0 = a whole-year counter (purchases, and every row from before D-086).
    day = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="روز (ماه‌روز شمسی)",
    )
    next_number = models.PositiveIntegerField(
        default=1,
        verbose_name="شماره بعدی",
    )

    class Meta:
        verbose_name = "شمارنده سند"
        verbose_name_plural = "شمارنده‌های سند"
        constraints = [
            models.UniqueConstraint(
                fields=["doc_type", "year", "day"],
                name="unique_document_sequence_per_doctype_year_day",
            ),
        ]

    def __str__(self):
        return f"{self.get_doc_type_display()} {self.year} ({self.next_number})"


class ExchangeRate(BaseModel):
    """
    One attempt to read the USD rate (D-080). Append-only, like AuditLog:
    an old rate is never overwritten, and a failed attempt stores NO number
    (``rate`` stays null), so a broken source can never put a made-up or zero
    rate on an invoice. Amounts are whole Toman (D-043).

    An invoice keeps a reference to the latest ``ok`` row at the moment it is
    confirmed, which carries the rate, its date, the time it was read and
    where it came from.
    """

    class Status(models.TextChoices):
        OK = "ok", "موفق"
        FAILED = "failed", "ناموفق"

    rate = models.BigIntegerField(null=True, blank=True, verbose_name="نرخ دلار (تومان)")
    rate_date = models.DateField(verbose_name="تاریخ نرخ")
    fetched_at = models.DateTimeField(verbose_name="زمان دریافت")
    source = models.CharField(max_length=40, verbose_name="منبع")
    status = models.CharField(max_length=10, choices=Status.choices, verbose_name="وضعیت دریافت")
    error = models.TextField(blank=True, verbose_name="خطا")

    class Meta:
        verbose_name = "نرخ دلار"
        verbose_name_plural = "نرخ‌های دلار"
        ordering = ["-fetched_at"]
        indexes = [models.Index(fields=["status", "fetched_at"])]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(status="ok", rate__gt=0)
                    | models.Q(status="failed", rate__isnull=True)
                ),
                name="exchange_rate_value_matches_status",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("نرخ ثبت‌شده قابل ویرایش نیست.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rate or '—'} ({self.get_status_display()}, {self.source})"

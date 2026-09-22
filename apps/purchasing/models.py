# path: apps/purchasing/models.py

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.partners.models import Supplier
from apps.products.models import Product
from apps.shared.models import BaseModel, Business


class PurchaseInvoice(BaseModel):
    """
    A purchase from a supplier.

    Draft invoices are editable. Once confirmed by `confirm_purchase`, the
    invoice and its items are immutable (D-014); stock movements have been
    written and must stay reconcilable with the paper ledger.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        CONFIRMED = "confirmed", "تأیید شده"

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        verbose_name="کسب‌وکار",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        verbose_name="تأمین‌کننده",
    )
    invoice_number = models.CharField(
        max_length=50,
        blank=True,  # assigned by confirm_purchase at confirmation (D-022); empty while draft
        verbose_name="شماره فاکتور",
    )
    supplier_invoice_number = models.CharField(
        max_length=50,
        blank=True,  # number on the supplier's own paper invoice, typed by hand (D-022)
        verbose_name="شماره فاکتور تأمین‌کننده",
    )
    invoice_date = models.DateField(
        verbose_name="تاریخ فاکتور",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="وضعیت",
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="زمان تأیید",
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیحات",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        verbose_name="ثبت‌کننده",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "فاکتور خرید"
        verbose_name_plural = "فاکتورهای خرید"
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "invoice_number"],
                condition=~models.Q(invoice_number=""),
                name="unique_purchase_invoice_number_per_business",
            ),
        ]

    def __str__(self):
        return f"خرید {self.invoice_number} - {self.supplier}"

    @property
    def is_editable(self):
        """Confirmed invoices are frozen (D-014)."""
        return self.status == self.Status.DRAFT

    @property
    def total_amount(self):
        """Sum of line totals, in Rial."""
        return sum(item.line_total for item in self.items.all())


class PurchaseItem(BaseModel):
    """One line of a purchase invoice."""

    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,  # a line has no meaning without its invoice
        related_name="items",
        verbose_name="فاکتور",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="purchase_items",
        verbose_name="کالا",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="مقدار",
    )
    unit_price = models.BigIntegerField(
        verbose_name="قیمت واحد (ریال)",  # whole Rial (D-013)
    )

    class Meta:
        verbose_name = "قلم فاکتور خرید"
        verbose_name_plural = "اقلام فاکتور خرید"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="purchase_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="purchase_item_price_non_negative",
            ),
            models.UniqueConstraint(
                fields=["invoice", "product"],
                name="unique_product_per_purchase_invoice",
            ),
        ]

    def __str__(self):
        return f"{self.product} x {self.quantity}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price
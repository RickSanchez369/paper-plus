# path: apps/sales/models.py

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.partners.models import Customer
from apps.products.models import Product
from apps.shared.models import BaseModel, Business


class SalesInvoice(BaseModel):
    """
    A sale to a customer.

    Mirrors PurchaseInvoice. Draft invoices are editable; once confirmed by
    `confirm_sale` the invoice and its items are frozen (D-014) and the stock
    movements it produced must stay reconcilable with the paper ledger.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        CONFIRMED = "confirmed", "تأیید شده"

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        verbose_name="کسب‌وکار",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        verbose_name="مشتری",
    )
    invoice_number = models.CharField(
        max_length=50,
        verbose_name="شماره فاکتور",
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
        related_name="sales_invoices",
        verbose_name="ثبت‌کننده",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "فاکتور فروش"
        verbose_name_plural = "فاکتورهای فروش"
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "invoice_number"],
                name="unique_sales_invoice_number_per_business",
            ),
        ]

    def __str__(self):
        return f"فروش {self.invoice_number} - {self.customer}"

    @property
    def is_editable(self):
        """Confirmed invoices are frozen (D-014)."""
        return self.status == self.Status.DRAFT

    @property
    def total_amount(self):
        """Sum of line totals, in Rial."""
        return sum(item.line_total for item in self.items.all())


class SaleItem(BaseModel):
    """One line of a sales invoice."""

    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="فاکتور",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sale_items",
        verbose_name="کالا",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="مقدار",
    )
    unit_price = models.BigIntegerField(
        verbose_name="قیمت واحد (ریال)",  # whole Rial (D-013)
    )

    class Meta:
        verbose_name = "قلم فاکتور فروش"
        verbose_name_plural = "اقلام فاکتور فروش"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sale_item_price_non_negative",
            ),
            models.UniqueConstraint(
                fields=["invoice", "product"],
                name="unique_product_per_sales_invoice",
            ),
        ]

    def __str__(self):
        return f"{self.product} x {self.quantity}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price
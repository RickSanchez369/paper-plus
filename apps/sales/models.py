# path: apps/sales/models.py

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.partners.models import Customer
from apps.products.models import Product
from apps.shared.models import BaseModel


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
        CANCELLED = "cancelled", "لغو شده"


    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقدی"
        CARD = "card", "کارت‌خوان"
        BANK_TRANSFER = "bank_transfer", "حواله بانکی"
        CHEQUE = "cheque", "چک"
        CREDIT = "credit", "نسیه"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        verbose_name="مشتری",
    )
    invoice_number = models.CharField(
        max_length=50,
        blank=True,  # assigned by confirm_sale at confirmation (D-022); empty while draft
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
    discount_amount = models.BigIntegerField(
        default=0,
        verbose_name="تخفیف (ریال)",  # invoice-level only for now; line-level discount is a later step (R 9)
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="روش پرداخت",
    )
    payment_note = models.TextField(
        blank=True,  # free text for now: bank/account name, cheque number, etc.
        verbose_name="یادداشت پرداخت",  # real BankAccount/Cheque tracking is phase 4.3/4.4, not here
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
                fields=["invoice_number"],
                condition=~models.Q(invoice_number=""),
                name="unique_sales_invoice_number",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="sales_invoice_discount_non_negative",
            ),
        ]

    def __str__(self):
        return f"فروش {self.invoice_number} - {self.customer}"

    @property
    def is_editable(self):
        """Confirmed and cancelled invoices are both frozen (D-014, D-023)."""
        return self.status == self.Status.DRAFT

    @property
    def subtotal(self):
        """Sum of line totals, before discount, in Rial (R 9)."""
        return sum(item.line_total for item in self.items.all())

    @property
    def total_amount(self):
        """Deprecated alias for `subtotal`; kept until admin.py is checked (2.7 cleanup)."""
        return self.subtotal

    @property
    def total(self):
        """Subtotal minus the invoice-level discount, in Rial (R 9)."""
        return self.subtotal - self.discount_amount

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "پرداخت‌نشده"
        PARTIAL = "partial", "نیمه‌پرداخت"
        PAID = "paid", "تسویه‌شده"

    @property
    def paid_amount(self):
        """Sum of PaymentAllocation rows against this invoice, in Rial (4.3)."""
        return self.payment_allocations.aggregate(total=models.Sum("amount"))["total"] or 0

    @property
    def payment_status(self):
        """unpaid / partial / paid, derived from paid_amount vs total -- never typed (D-025)."""
        paid = self.paid_amount
        if paid <= 0:
            return self.PaymentStatus.UNPAID
        if paid < self.total:
            return self.PaymentStatus.PARTIAL
        return self.PaymentStatus.PAID


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
        blank=True,  # admin may leave it empty; filled from the product default (R 7, 17C)
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

    def clean_fields(self, exclude=None):
        """
        Fill a blank unit_price from the product's current default before
        the null/blank checks run (R 7, 17C).

        Must happen here, not in save(): a ModelForm's full_clean() (the
        admin included) validates before save() is ever reached, so a None
        value fails validation first. Once filled, unit_price is a plain
        stored field -- later changes to Product.default_selling_price
        never touch it (it's a snapshot, not a live reference).
        """
        if self.unit_price is None and self.product_id:
            self.unit_price = self.product.default_selling_price
        super().clean_fields(exclude=exclude)

    def __str__(self):
        return f"{self.product} x {self.quantity}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class SalesPaymentEntry(BaseModel):
    """
    One planned payment line on a draft sales invoice (added at Sina's
    request, 2026-09-24): "2M by cheque, 1M cash, the rest بقیه بانکی,
    leave 2M as نسیه" -- entered while drafting, turned into real
    `Payment`/`Cheque` rows by `confirm_sale` at confirmation, the same
    way `SaleItem` rows turn into `InventoryMovement` rows.

    Rows do not need to add up to the invoice total; whatever is left
    over is exactly the نسیه/credit portion -- it already shows up as
    SalesInvoice.payment_status, no separate tracking needed.
    """

    class Method(models.TextChoices):
        CASH = "cash", "نقدی"
        CARD = "card", "کارت‌خوان"
        BANK_TRANSFER = "bank_transfer", "حواله بانکی"
        CHEQUE = "cheque", "چک"

    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,  # a line has no meaning without its invoice
        related_name="payment_entries",
        verbose_name="فاکتور",
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        verbose_name="روش",
    )
    amount = models.BigIntegerField(
        verbose_name="مبلغ (ریال)",
    )
    bank_account = models.ForeignKey(
        "payments.BankAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="حساب بانکی",
    )
    cheque_number = models.CharField(
        max_length=50,
        blank=True,  # required only when method=cheque (validated in the admin form)
        verbose_name="شماره چک",
    )
    bank_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="نام بانک صادرکننده چک",
    )
    due_date = models.DateField(
        null=True,
        blank=True,  # required only when method=cheque (validated in the admin form)
        verbose_name="تاریخ سررسید چک",
    )

    class Meta:
        verbose_name = "ردیف پرداخت فاکتور فروش"
        verbose_name_plural = "ردیف‌های پرداخت فاکتور فروش"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sales_payment_entry_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.get_method_display()} - {self.amount}"
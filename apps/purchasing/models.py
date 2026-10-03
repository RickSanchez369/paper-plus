# path: apps/purchasing/models.py

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.partners.models import Supplier
from apps.products.models import Product
from apps.shared.models import BaseModel


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
        CANCELLED = "cancelled", "لغو شده"


    class PaymentMethod(models.TextChoices):
        CASH = "cash", "نقدی"
        CARD = "card", "کارت‌خوان"
        BANK_TRANSFER = "bank_transfer", "حواله بانکی"
        CHEQUE = "cheque", "چک"
        CREDIT = "credit", "نسیه"

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
    credit_due_date = models.DateField(
        null=True,
        blank=True,  # only meaningful when part of the invoice is left unpaid (نسیه), D-069
        verbose_name="تاریخ سررسید نسیه",
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
                fields=["invoice_number"],
                condition=~models.Q(invoice_number=""),
                name="unique_purchase_invoice_number",
            ),
        ]

    def __str__(self):
        return f"خرید {self.invoice_number} - {self.supplier}"

    @property
    def is_editable(self):
        """Confirmed and cancelled invoices are both frozen (D-014, D-023)."""
        return self.status == self.Status.DRAFT

    @property
    def total_amount(self):
        """Sum of line totals, in Toman."""
        return sum(item.line_total for item in self.items.all())

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "پرداخت‌نشده"
        PARTIAL = "partial", "نیمه‌پرداخت"
        PAID = "paid", "تسویه‌شده"

    @property
    def paid_amount(self):
        """Sum of PaymentAllocation rows against this invoice, in Toman (4.3),
        not counting allocations whose money was given back (D-055)."""
        return (
            self.payment_allocations.filter(reversal_payment__isnull=True)
            .aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

    @property
    def payment_status(self):
        """unpaid / partial / paid, derived from paid_amount vs total_amount -- never typed (D-025)."""
        paid = self.paid_amount
        if paid <= 0:
            return self.PaymentStatus.UNPAID
        if paid < self.total_amount:
            return self.PaymentStatus.PARTIAL
        return self.PaymentStatus.PAID

    @property
    def outstanding(self):
        """How much of this invoice is still open, never below zero (an
        overpayment does not make an invoice owe negative money, D-025)."""
        return max(self.total_amount - self.paid_amount, 0)


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
        verbose_name="قیمت واحد (تومان)",  # whole Toman (D-043)
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


class PurchasePaymentEntry(BaseModel):
    """
    One planned payment line on a draft purchase invoice -- mirrors
    sales.SalesPaymentEntry, but for money paid OUT to a supplier.
    Turned into real `Payment`/`Cheque` rows by `confirm_purchase` at
    confirmation, the same way `PurchaseItem` rows turn into
    `InventoryMovement` rows.

    Rows do not need to add up to the invoice total; whatever is left
    over is exactly the نسیه/credit portion -- already visible as
    PurchaseInvoice.payment_status, no separate tracking needed.
    """

    class Method(models.TextChoices):
        CASH = "cash", "نقدی (قدیمی)"
        CARD = "card", "کارت‌خوان"
        BANK_TRANSFER = "bank_transfer", "حواله بانکی"
        CHEQUE = "cheque", "چک"

    invoice = models.ForeignKey(
        PurchaseInvoice,
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
        verbose_name="مبلغ (تومان)",
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
        verbose_name="نام بانک دریافت‌کنندهٔ چک",
    )
    issuer = models.CharField(
        max_length=150,
        blank=True,  # who signed the cheque; may differ from the customer/supplier (D-068)
        verbose_name="صادرکنندهٔ چک",
    )
    due_date = models.DateField(
        null=True,
        blank=True,  # required only when method=cheque (validated in the admin form)
        verbose_name="تاریخ سررسید چک",
    )

    class Meta:
        verbose_name = "ردیف پرداخت فاکتور خرید"
        verbose_name_plural = "ردیف‌های پرداخت فاکتور خرید"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="purchase_payment_entry_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.get_method_display()} - {self.amount}"
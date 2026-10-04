# path: apps/returns/models.py

"""
Sales and purchase returns (D-089).

A return always points at one confirmed invoice and, per line, at the invoice
line it gives back, so it can never return more than was sold/bought and its
money is the line's own net value. It is written once by its service and never
edited (D-014, append-only like every other document here).

Money: what the return is worth first comes off what is still open on that
invoice (a credit-note Payment allocated to it, no bank account, so no bank
balance moves); the rest is either paid back through a bank account or left
as the party's credit (D-087), chosen when the return is recorded.
"""

from django.conf import settings
from django.db import models

from apps.shared.models import BaseModel


class SettleMode(models.TextChoices):
    """What happens to the part of a return that the invoice's open debt does not absorb."""

    CREDIT = "credit", "بستانکاری طرف حساب (کسر از فاکتور بعدی)"
    REFUND = "refund", "برگشت وجه از حساب بانکی"


class _ReturnDocument(BaseModel):
    """Fields shared by both kinds of return."""

    return_number = models.CharField(max_length=50, unique=True, verbose_name="شمارهٔ مرجوعی")
    return_date = models.DateField(verbose_name="تاریخ مرجوعی")
    settle_mode = models.CharField(
        max_length=10, choices=SettleMode.choices, default=SettleMode.CREDIT, verbose_name="تسویهٔ مازاد",
    )
    bank_account = models.ForeignKey(
        "payments.BankAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # only for a refund
        related_name="+",
        verbose_name="حساب بانکی",
    )
    # Snapshots of how the money was split, written once by the service (D-014).
    total_amount = models.BigIntegerField(verbose_name="مبلغ مرجوعی (تومان)")
    applied_amount = models.BigIntegerField(default=0, verbose_name="کسر از مانده فاکتور (تومان)")
    refund_amount = models.BigIntegerField(default=0, verbose_name="برگشت وجه (تومان)")
    credit_amount = models.BigIntegerField(default=0, verbose_name="بستانکاری (تومان)")
    credit_note = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="سند اعتبار",
    )
    refund_payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="پرداخت برگشت وجه",
    )
    note = models.TextField(blank=True, verbose_name="توضیح")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="ثبت‌کننده",
    )

    class Meta:
        abstract = True

    @property
    def cost_amount(self):
        """FIFO cost of the goods that came back (sales) or went back (purchases), in Toman."""
        return sum(item.cost for item in self.items.all())


class SalesReturn(_ReturnDocument):
    """Goods a customer brought back from one confirmed sales invoice."""

    invoice = models.ForeignKey(
        "sales.SalesInvoice", on_delete=models.PROTECT, related_name="returns", verbose_name="فاکتور فروش",
    )

    class Meta:
        verbose_name = "مرجوعی فروش"
        verbose_name_plural = "مرجوعی‌های فروش"
        ordering = ["-return_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0, applied_amount__gte=0, refund_amount__gte=0, credit_amount__gte=0),
                name="sales_return_amounts_non_negative",
            ),
        ]

    def __str__(self):
        return f"مرجوعی فروش {self.return_number}"

    @property
    def party(self):
        return self.invoice.customer

    @property
    def profit_given_back(self):
        """Profit this return takes back from the original sale: its value minus the cost that came back."""
        return self.total_amount - self.cost_amount


class SalesReturnItem(BaseModel):
    """One returned line: how many packs of which sold line, what they are worth, what they cost."""

    sales_return = models.ForeignKey(SalesReturn, on_delete=models.CASCADE, related_name="items", verbose_name="مرجوعی")
    sale_item = models.ForeignKey(
        "sales.SaleItem", on_delete=models.PROTECT, related_name="return_items", verbose_name="ردیف فاکتور فروش",
    )
    quantity = models.PositiveIntegerField(verbose_name="مقدار (بسته)")
    cartons = models.PositiveIntegerField(default=0, verbose_name="تعداد کارتن")
    pack_per_carton = models.PositiveSmallIntegerField(default=1, verbose_name="بسته در هر کارتن")
    amount = models.BigIntegerField(verbose_name="مبلغ (تومان)")
    cost = models.BigIntegerField(verbose_name="بهای تمام‌شده (تومان)")

    class Meta:
        verbose_name = "ردیف مرجوعی فروش"
        verbose_name_plural = "ردیف‌های مرجوعی فروش"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sales_return_item_quantity_positive"),
            models.CheckConstraint(condition=models.Q(amount__gte=0, cost__gte=0), name="sales_return_item_money_non_negative"),
        ]

    @property
    def loose_packs(self):
        return self.quantity - self.cartons * self.pack_per_carton


class PurchaseReturn(_ReturnDocument):
    """Goods sent back to the supplier from one confirmed purchase invoice."""

    invoice = models.ForeignKey(
        "purchasing.PurchaseInvoice", on_delete=models.PROTECT, related_name="returns", verbose_name="فاکتور خرید",
    )

    class Meta:
        verbose_name = "مرجوعی خرید"
        verbose_name_plural = "مرجوعی‌های خرید"
        ordering = ["-return_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0, applied_amount__gte=0, refund_amount__gte=0, credit_amount__gte=0),
                name="purchase_return_amounts_non_negative",
            ),
        ]

    def __str__(self):
        return f"مرجوعی خرید {self.return_number}"

    @property
    def party(self):
        return self.invoice.supplier


class PurchaseReturnItem(BaseModel):
    """One line sent back: packs taken out of that purchase line's own FIFO layer."""

    purchase_return = models.ForeignKey(
        PurchaseReturn, on_delete=models.CASCADE, related_name="items", verbose_name="مرجوعی",
    )
    purchase_item = models.ForeignKey(
        "purchasing.PurchaseItem", on_delete=models.PROTECT, related_name="return_items", verbose_name="ردیف فاکتور خرید",
    )
    quantity = models.PositiveIntegerField(verbose_name="مقدار (بسته)")
    cartons = models.PositiveIntegerField(default=0, verbose_name="تعداد کارتن")
    pack_per_carton = models.PositiveSmallIntegerField(default=1, verbose_name="بسته در هر کارتن")
    amount = models.BigIntegerField(verbose_name="مبلغ (تومان)")
    cost = models.BigIntegerField(verbose_name="ارزش انبار خارج‌شده (تومان)")

    class Meta:
        verbose_name = "ردیف مرجوعی خرید"
        verbose_name_plural = "ردیف‌های مرجوعی خرید"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_return_item_quantity_positive"),
            models.CheckConstraint(condition=models.Q(amount__gte=0, cost__gte=0), name="purchase_return_item_money_non_negative"),
        ]

    @property
    def loose_packs(self):
        return self.quantity - self.cartons * self.pack_per_carton

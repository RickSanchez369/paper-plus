# path: apps/payments/models.py

"""
Money movements, independent of the invoices they settle (ROADMAP 4.3).

A Payment is a fact: "this much money moved, in this direction, on this
date, through this bank account (or cash, if none)." A PaymentAllocation
says which invoice(s) that money belongs to. Splitting them lets one
payment settle several invoices, or one invoice be settled by several
payments over time -- and lets a payment exist before it is allocated
(e.g. a customer prepayment).

Both are append-only, like InventoryMovement (D-012): a mistake is never
edited, only corrected by a new, opposite entry (enforced at the admin
layer, apps/payments/admin.py).
"""
from django.conf import settings
from django.db import models

from apps.shared.models import BaseModel, Business


class BankAccount(BaseModel):
    """A bank account belonging to a business, used to record where money moved."""

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="bank_accounts",
        verbose_name="کسب‌وکار",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="نام حساب",
    )
    account_number = models.CharField(
        max_length=50,
        verbose_name="شماره حساب",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    class Meta:
        verbose_name = "حساب بانکی"
        verbose_name_plural = "حساب‌های بانکی"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "account_number"],
                name="unique_account_number_per_business",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.account_number})"


class Payment(BaseModel):
    """
    One movement of money, in or out (D-012-style direction, like InventoryMovement).

    `bank_account` is left blank for cash: the amount still counts toward
    invoice payment status, it just is not attributed to any account ledger.
    """

    class Direction(models.TextChoices):
        IN = "in", "دریافت"
        OUT = "out", "پرداخت"

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="کسب‌وکار",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # blank = cash
        related_name="payments",
        verbose_name="حساب بانکی",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        verbose_name="جهت",
    )
    amount = models.BigIntegerField(
        verbose_name="مبلغ (ریال)",
    )
    payment_date = models.DateField(
        verbose_name="تاریخ پرداخت",
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیح",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="ثبت‌کننده",
    )

    class Meta:
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
        ordering = ["-payment_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_positive",
            ),
        ]

    def __str__(self):
        sign = "+" if self.direction == self.Direction.IN else "-"
        return f"{sign}{self.amount} ({self.get_direction_display()})"

    @property
    def allocated_amount(self):
        """Sum of this payment's allocations so far, in Rial."""
        return self.allocations.aggregate(total=models.Sum("amount"))["total"] or 0

    @property
    def unallocated_amount(self):
        """How much of this payment has not yet been tied to an invoice."""
        return self.amount - self.allocated_amount


class PaymentAllocation(BaseModel):
    """
    Ties part (or all) of a Payment to exactly one invoice (D-025).

    Exactly one of `sales_invoice` / `purchase_invoice` is set -- mirrors
    InventoryMovement.purchase_item/sale_item (2.9): an explicit FK pair
    with a CHECK, not a GenericForeignKey, so the target stays a normal,
    PROTECT-able, joinable foreign key.
    """

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,  # a line has no meaning without its payment
        related_name="allocations",
        verbose_name="پرداخت",
    )
    sales_invoice = models.ForeignKey(
        "sales.SalesInvoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_allocations",
        verbose_name="فاکتور فروش",
    )
    purchase_invoice = models.ForeignKey(
        "purchasing.PurchaseInvoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_allocations",
        verbose_name="فاکتور خرید",
    )
    amount = models.BigIntegerField(
        verbose_name="مبلغ تخصیص‌یافته (ریال)",
    )

    class Meta:
        verbose_name = "تخصیص پرداخت"
        verbose_name_plural = "تخصیص‌های پرداخت"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_allocation_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(sales_invoice__isnull=False, purchase_invoice__isnull=True)
                    | models.Q(sales_invoice__isnull=True, purchase_invoice__isnull=False)
                ),
                name="payment_allocation_exactly_one_invoice",
            ),
        ]

    def __str__(self):
        invoice = self.sales_invoice or self.purchase_invoice
        return f"{self.payment} -> {invoice} ({self.amount})"

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

from apps.shared.models import BaseModel

from .validators import validate_receipt


class BankAccount(BaseModel):
    """A bank account of the business, used to record where money moved."""

    class AccountType(models.TextChoices):
        # Two kinds only (D-067): a card reader (POS) receives card
        # payments; a current account receives transfers and cheques and
        # pays suppliers/expenses. Cash has no account (D-069).
        POS = "pos", "کارت‌خوان"
        CURRENT = "current", "حساب جاری"

    name = models.CharField(
        max_length=100,
        verbose_name="نام حساب",
    )
    owner = models.CharField(
        max_length=200,
        blank=True,  # existing accounts predate this field; not every one is known
        verbose_name="صاحب حساب",
    )
    account_number = models.CharField(
        max_length=50,
        verbose_name="شماره حساب",
    )
    account_type = models.CharField(
        max_length=10,
        choices=AccountType.choices,
        default=AccountType.CURRENT,  # every account that existed before D-067 is a normal current account
        verbose_name="نوع حساب",
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
                fields=["account_number"],
                name="unique_bank_account_number",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.account_number})"


class Payment(BaseModel):
    """
    One movement of money, in or out (D-012-style direction, like InventoryMovement).

    `bank_account` is left blank for cash: the amount still counts toward
    invoice payment status, it just is not attributed to any account ledger.

    `customer`/`supplier` answer "whose money is this" without going
    through an allocation. Before they existed, a payment not yet tied to
    an invoice -- a prepayment, say -- had no trace to anyone at all, which
    breaks the rule that every movement of money resolves back to a person.
    Both stay optional: an expense's payment belongs
    to neither. Mirrors `Cheque`'s pair, with a looser constraint.
    """

    class Direction(models.TextChoices):
        IN = "in", "دریافت"
        OUT = "out", "پرداخت"

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # blank = cash
        related_name="payments",
        verbose_name="حساب بانکی",
    )
    customer = models.ForeignKey(
        "partners.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when direction=in and the money came from a customer
        related_name="payments",
        verbose_name="مشتری",
    )
    supplier = models.ForeignKey(
        "partners.Supplier",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when direction=out and the money went to a supplier
        related_name="payments",
        verbose_name="تأمین‌کننده",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        verbose_name="جهت",
    )
    amount = models.BigIntegerField(
        verbose_name="مبلغ (تومان)",
    )
    payment_date = models.DateField(
        verbose_name="تاریخ پرداخت",
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیح",
    )
    is_reversal = models.BooleanField(
        default=False,
        verbose_name="برگشت پرداخت",
        help_text="پولی که بابت لغو یک فاکتور به مشتری/تأمین‌کننده برگشت داده شده است (D-055).",
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
            models.CheckConstraint(
                # At most one party, and it has to agree with the direction:
                # money coming IN can only come from a customer, money going
                # OUT can only go to a supplier. Neither is the expense /
                # unattributed case. Same shape as Cheque's own constraint.
                # A reversal (D-055) is the one exception: it runs against the
                # party's usual direction (a refund goes OUT to a customer).
                condition=(
                    models.Q(customer__isnull=True, supplier__isnull=True)
                    | models.Q(is_reversal=False, direction="in", customer__isnull=False, supplier__isnull=True)
                    | models.Q(is_reversal=False, direction="out", supplier__isnull=False, customer__isnull=True)
                    | models.Q(is_reversal=True, customer__isnull=True)
                    | models.Q(is_reversal=True, supplier__isnull=True)
                ),
                name="payment_party_matches_direction",
            ),
        ]

    def __str__(self):
        sign = "+" if self.direction == self.Direction.IN else "-"
        return f"{sign}{self.amount} ({self.get_direction_display()})"

    @property
    def allocated_amount(self):
        """Sum of this payment's allocations so far, in Toman."""
        return self.allocations.aggregate(total=models.Sum("amount"))["total"] or 0

    @property
    def unallocated_amount(self):
        """How much of this payment has not yet been tied to an invoice."""
        return self.amount - self.allocated_amount

    @property
    def party(self):
        """Whoever this money moved with, or None for an expense/unattributed row."""
        return self.customer or self.supplier


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
        verbose_name="مبلغ تخصیص‌یافته (تومان)",
    )
    # Set when the invoice was cancelled and this money was given back
    # (D-055): the refund Payment that reverses exactly this allocation. The
    # allocation itself is never edited or deleted.
    reversal_payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_allocation",
        verbose_name="پرداخت برگشتی",
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


class Cheque(BaseModel):
    """
    A physical cheque's lifecycle (ROADMAP 4.4): pending -> cleared / bounced.

    A pending cheque is not yet money -- no Payment exists for it, and it
    does not count toward any invoice's payment_status (Sina's call,
    2026-09-24). `clear_cheque` (apps/payments/services.py) is the only
    way a Payment gets created and linked here; `bounce_cheque` and
    `cancel_cheque` close it with no Payment at all. All three are one-way:
    a closed cheque never goes back to pending.

    CANCELLED means "I entered this by mistake", not a reversal: a pending
    cheque never counted toward anything, so withdrawing it moves no money.
    Nothing is ever deleted -- the row stays as
    history, same as a cancelled invoice.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار وصول"
        CLEARED = "cleared", "وصول شده"
        BOUNCED = "bounced", "برگشت خورده"
        CANCELLED = "cancelled", "لغو شده"

    direction = models.CharField(
        max_length=10,
        choices=Payment.Direction.choices,
        verbose_name="جهت",
    )
    customer = models.ForeignKey(
        "partners.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when direction=in
        related_name="cheques",
        verbose_name="مشتری",
    )
    supplier = models.ForeignKey(
        "partners.Supplier",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when direction=out
        related_name="cheques",
        verbose_name="تأمین‌کننده",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # the account it will be deposited into / drawn from, if known yet
        related_name="cheques",
        verbose_name="حساب بانکی",
    )
    cheque_number = models.CharField(
        max_length=50,
        blank=True,  # a cheque entered from an invoice may still be incomplete (4.3b)
        verbose_name="شماره چک",
    )
    bank_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="نام بانک صادرکننده",
    )
    issuer = models.CharField(
        max_length=150,
        blank=True,  # who signed the cheque; may differ from the customer/supplier (D-068)
        verbose_name="صادرکنندهٔ چک",
    )
    due_date = models.DateField(
        null=True,
        blank=True,  # a cheque entered from an invoice may still be incomplete (4.3b)
        verbose_name="تاریخ سررسید",
    )
    amount = models.BigIntegerField(
        verbose_name="مبلغ (تومان)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="وضعیت",
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set only once cleared, by clear_cheque
        related_name="cheque",
        verbose_name="پرداخت",
    )
    sales_invoice = models.ForeignKey(
        "sales.SalesInvoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when this cheque was entered from a sales invoice (4.3b)
        related_name="cheques",
        verbose_name="فاکتور فروش",
    )
    purchase_invoice = models.ForeignKey(
        "purchasing.PurchaseInvoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when this cheque was entered from a purchase invoice (4.3b)
        related_name="cheques",
        verbose_name="فاکتور خرید",
    )
    expense = models.ForeignKey(
        "payments.Expense",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when the cheque pays an expense (D-072); such a cheque has no customer/supplier
        related_name="cheques",
        verbose_name="هزینه",
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیح",
    )

    class Meta:
        verbose_name = "چک"
        verbose_name_plural = "چک‌ها"
        ordering = ["due_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="cheque_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(direction=Payment.Direction.IN, customer__isnull=False, supplier__isnull=True)
                    | models.Q(direction=Payment.Direction.OUT, supplier__isnull=False, customer__isnull=True)
                    # An expense cheque (D-072) is ours going out, to nobody in particular.
                    | models.Q(
                        direction=Payment.Direction.OUT, supplier__isnull=True, customer__isnull=True,
                        expense__isnull=False,
                    )
                ),
                name="cheque_direction_matches_party",
            ),
            models.CheckConstraint(
                # A cheque need not come from any invoice at all (a general
                # prepayment); when it does, the invoice side must agree
                # with `direction` (mirrors PaymentAllocation, 4.3).
                condition=(
                    models.Q(sales_invoice__isnull=True, purchase_invoice__isnull=True)
                    | models.Q(sales_invoice__isnull=False, purchase_invoice__isnull=True, direction=Payment.Direction.IN)
                    | models.Q(sales_invoice__isnull=True, purchase_invoice__isnull=False, direction=Payment.Direction.OUT)
                ),
                name="cheque_invoice_link_matches_direction",
            ),
        ]

    def __str__(self):
        return f"چک {self.cheque_number} ({self.get_status_display()})"


class Expense(BaseModel):
    """
    Money spent on running the business: rent, wages, fuel, a repair.

    Deliberately backed by a real `Payment` rather than a second, parallel
    accounting path: an expense moves money out of a
    bank account (or out of the till, when `bank_account` is blank) exactly
    like any other payment, so bank balances, cash flow and the reports
    built on `Payment` all pick it up for free. The Expense row adds only
    what a payment cannot say: what it was for.

    No counterparty field (D-045): the question every report asks of an
    expense is "which account paid it", and that is `bank_account` --
    picked explicitly on the form, with cash an explicit choice rather
    than what an untouched field falls back to.

    Never edited or deleted after recording, like everything else financial
    here. A mistake is corrected by `cancel_expense`,
    which books an opposite Payment and flags this row cancelled.
    """

    class PaymentMethod(models.TextChoices):
        # How the expense is (or will be) paid (D-072). Cash does not exist (D-069).
        TRANSFER = "transfer", "حواله بانکی"
        CHEQUE = "cheque", "چک"
        CREDIT = "credit", "نسیه"

    expense_date = models.DateField(
        verbose_name="تاریخ",
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.TRANSFER,  # every expense that existed before D-072 was paid on the spot
        verbose_name="روش پرداخت",
    )
    due_date = models.DateField(
        null=True,
        blank=True,  # the date an unpaid (نسیه) expense must be paid by; cheques carry their own
        verbose_name="سررسید پرداخت",
    )
    recurring = models.ForeignKey(
        "payments.RecurringExpense",
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set when this expense is one instalment of a fixed, repeating cost (D-073)
        related_name="expenses",
        verbose_name="هزینهٔ ثابت",
    )
    amount = models.BigIntegerField(
        verbose_name="مبلغ (تومان)",
    )
    reason = models.CharField(
        max_length=255,
        verbose_name="بابت",
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # blank = cash, same meaning as on Payment; the form makes it an explicit choice (D-045)
        related_name="expenses",
        verbose_name="پرداخت از حساب",
    )
    document = models.FileField(
        upload_to="expenses/%Y/%m/",
        blank=True,
        validators=[validate_receipt],
        verbose_name="سند/رسید",
        help_text="PDF یا تصویر (PNG، JPG، WebP)، حداکثر ۵ مگابایت.",
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیح",
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # empty while a cheque is pending or a نسیه expense is unpaid (D-072)
        related_name="expense",
        verbose_name="پرداخت",  # created by record_expense / pay_expense / clear_cheque
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="زمان لغو",
    )
    reversal_payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,  # set by cancel_expense; the opposite entry that undoes it
        related_name="reversed_expense",
        verbose_name="پرداخت برگشتی",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="ثبت‌کننده",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_expenses",
        verbose_name="لغوکننده",
    )

    class Meta:
        verbose_name = "هزینه"
        verbose_name_plural = "هزینه‌ها"
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["expense_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="expense_amount_positive",
            ),
            models.CheckConstraint(
                # A cancelled expense always has its timestamp and who did it; the
                # reversing payment exists only when money had actually left (D-072).
                condition=(
                    models.Q(cancelled_at__isnull=True, reversal_payment__isnull=True, cancelled_by__isnull=True)
                    | models.Q(cancelled_at__isnull=False, cancelled_by__isnull=False)
                ),
                name="expense_cancellation_is_complete",
            ),
        ]

    def __str__(self):
        return f"{self.reason} — {self.amount}"

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None

    @property
    def is_paid(self):
        """True once money has left for it: a bank payment exists (derived, never typed, D-025)."""
        return self.payment_id is not None

    @property
    def counts_toward_totals(self):
        """
        False once cancelled, so no card, report or statement counts it.

        Stated on the model rather than left to each page, because every
        place that totals money has to agree.
        """
        return not self.is_cancelled


class RecurringExpense(BaseModel):
    """
    A fixed cost that comes round again: shop rent, electricity, water --
    every month, every 45 days, every few months (D-073).

    It is a reminder plus a shortcut, not a ledger: nothing is booked until
    someone records the instalment as an ordinary Expense (which then advances
    `next_due_date`). The page and the dashboard remind from
    `remind_days_before` days ahead of the due date until it is dealt with.
    """

    class Unit(models.TextChoices):
        DAY = "day", "روز"
        MONTH = "month", "ماه"

    reason = models.CharField(
        max_length=255,
        verbose_name="بابت",
    )
    amount = models.BigIntegerField(
        verbose_name="مبلغ (تومان)",
        help_text="مبلغ معمول؛ هنگام ثبت پرداخت می‌توان آن را تغییر داد.",
    )
    repeat_every = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="تکرار هر",
    )
    repeat_unit = models.CharField(
        max_length=10,
        choices=Unit.choices,
        default=Unit.MONTH,
        verbose_name="واحد تکرار",
    )
    next_due_date = models.DateField(
        verbose_name="سررسید بعدی",
    )
    remind_days_before = models.PositiveSmallIntegerField(
        default=7,
        verbose_name="یادآوری از چند روز قبل",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )
    note = models.TextField(
        blank=True,
        verbose_name="توضیح",
    )

    class Meta:
        verbose_name = "هزینهٔ ثابت"
        verbose_name_plural = "هزینه‌های ثابت"
        ordering = ["next_due_date", "reason"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="recurring_expense_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(repeat_every__gte=1),
                name="recurring_expense_repeat_positive",
            ),
        ]

    def __str__(self):
        return self.reason

    @property
    def interval_label(self):
        """"هر ۱ ماه" style text for lists."""
        return f"هر {self.repeat_every} {self.get_repeat_unit_display()}"

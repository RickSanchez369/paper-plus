# path: apps/sales/models.py

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.partners.models import Customer
from apps.products.models import CartonLine, PriceTier, Product
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
    price_tier = models.CharField(
        max_length=10,
        choices=PriceTier.choices,
        default=PriceTier.RETAIL,  # every invoice before D-075 was sold at the one price there was
        verbose_name="نوع فروش",
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
        verbose_name="تخفیف (تومان)",  # invoice-level only for now; line-level discount is a later step (R 9)
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
    # The USD rate in force when the invoice was confirmed (D-080); null on older invoices.
    usd_rate = models.ForeignKey(
        "shared.ExchangeRate",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
        verbose_name="نرخ دلار هنگام تأیید",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        verbose_name="ثبت‌کننده",
    )
    submission_id = models.UUIDField(null=True, blank=True, editable=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "فاکتور فروش"
        verbose_name_plural = "فاکتورهای فروش"
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "submission_id"],
                name="unique_sales_submission_per_user",
            ),
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
        """Sum of line totals, before discount, in Toman (R 9)."""
        return sum(item.line_total for item in self.items.all())

    @property
    def total_amount(self):
        """Deprecated alias for `subtotal`; kept until admin.py is checked (2.7 cleanup)."""
        return self.subtotal

    @property
    def total(self):
        """Subtotal minus the invoice-level discount, in Toman (R 9)."""
        return self.subtotal - self.discount_amount

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
        """unpaid / partial / paid, derived from paid_amount vs total -- never typed (D-025)."""
        paid = self.paid_amount
        if paid <= 0:
            return self.PaymentStatus.UNPAID
        if paid < self.total:
            return self.PaymentStatus.PARTIAL
        return self.PaymentStatus.PAID

    @property
    def outstanding(self):
        """How much of this invoice is still open, never below zero (an
        overpayment does not make an invoice owe negative money, D-025)."""
        return max(self.total - self.paid_amount, 0)

    @property
    def cost_of_goods(self):
        """Real FIFO cost of everything on this invoice, in Toman."""
        return sum(item.cost_of_goods for item in self.items.all())

    @property
    def profit(self):
        """
        Realised profit: invoice total minus real cost of goods, in Toman.

        The discount comes off the total, so it comes out of profit -- it
        is a price reduction, not a cost. Zero for a draft or cancelled
        invoice, same rule as SaleItem.profit. Always equals the sum of
        its lines' profit, since the lines share the discount exactly
        (`discount_allocation`, D-048).
        """
        if self.status != self.Status.CONFIRMED:
            return 0
        return self.total - self.cost_of_goods

    @property
    def discount_allocation(self):
        """
        {item pk: that line's share of the invoice discount}, in whole Toman
        (D-048).

        The discount is invoice-level (D-032), but "which product earns
        what" needs it per line: each line carries the part proportional to
        its own line total, so a line's revenue and profit are what that
        product really brought in. Largest remainder keeps the shares
        summing to exactly `discount_amount` -- floor every share, then hand
        the leftover Toman, one each, to the lines with the biggest
        remainders (ties by pk, so the same invoice always splits the same
        way). Derived on every read, never stored (D-025).
        """
        items = list(self.items.all())
        subtotal = sum(item.line_total for item in items)
        if not self.discount_amount or subtotal <= 0:
            return {item.pk: 0 for item in items}

        shares = {}
        remainders = []
        for item in items:
            numerator = self.discount_amount * item.line_total
            shares[item.pk] = numerator // subtotal
            remainders.append((numerator % subtotal, str(item.pk), item.pk))
        leftover = self.discount_amount - sum(shares.values())
        for _, _, pk in sorted(remainders, key=lambda r: (-r[0], r[1]))[:leftover]:
            shares[pk] += 1
        return shares

    @property
    def has_uncosted_items(self):
        """True when any line was sold without a cost basis (see SaleItem)."""
        return any(item.uncosted_quantity for item in self.items.all())


class SaleItem(CartonLine, BaseModel):
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
        verbose_name="مقدار (بسته)",  # the total in packs, the base unit (D-081)
    )
    unit_price = models.BigIntegerField(
        blank=True,  # admin may leave it empty; filled from the product default (R 7, 17C)
        verbose_name="قیمت هر بسته (تومان)",  # whole Toman (D-043)
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
            models.CheckConstraint(
                condition=models.Q(carton_price__gte=0, pack_per_carton__gte=1),
                name="sale_item_carton_fields_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=models.F("cartons") * models.F("pack_per_carton")),
                name="sale_item_cartons_within_quantity",
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
        if self.product_id:
            # The unit alone picks the price: pack -> pack price, carton -> carton price (D-100).
            if self.unit_price is None:
                self.unit_price = self.product.price_for("pack")
            if self.cartons and not self.carton_price:
                self.carton_price = self.product.price_for("carton")
        super().clean_fields(exclude=exclude)

    def __str__(self):
        return f"{self.product} x {self.quantity}"

    @property
    def discount_share(self):
        """This line's part of the invoice discount (D-048, see
        SalesInvoice.discount_allocation)."""
        return self.invoice.discount_allocation.get(self.pk, 0)

    @property
    def net_total(self):
        """What this line actually brought in: line total minus its share
        of the invoice discount. The lines' net totals sum to invoice.total."""
        return self.line_total - self.discount_share

    @property
    def cost_of_goods(self):
        """
        What these units actually cost, in Toman, from the FIFO layers this
        line drew from. Derived, never stored (D-025):
        it is the sum over this line's InventoryConsumption rows of
        quantity x that layer's own unit_cost, so a cancelled line -- whose
        consumptions net to zero -- correctly costs nothing.
        """
        return sum(
            consumption.quantity * consumption.layer.unit_cost
            for consumption in self.consumptions.select_related("layer")
        )

    @property
    def costed_quantity(self):
        """How many of these units FIFO could actually find a layer for."""
        return sum(consumption.quantity for consumption in self.consumptions.all())

    @property
    def uncosted_quantity(self):
        """
        Units sold with no layer behind them, so no cost basis at all.

        Non-zero only after an oversell, which is superuser-only (D-016).
        Surfaced rather than hidden: profit on those units is overstated by
        exactly whatever they really cost, and a page showing profit has to
        be able to say so.
        """
        if self.invoice.status != SalesInvoice.Status.CONFIRMED:
            return 0
        return self.quantity - self.costed_quantity

    @property
    def profit(self):
        """
        Realised profit: net total (after this line's share of the invoice
        discount, D-048) minus its real FIFO cost, in Toman -- so the lines
        of an invoice add up to exactly the invoice's own profit.

        Zero unless the invoice is confirmed. A draft has not sold anything
        yet, and a cancelled line's consumptions net back to zero cost --
        without this guard both would report their whole revenue as profit,
        and every total built on this property would count cancelled
        invoices.
        """
        if self.invoice.status != SalesInvoice.Status.CONFIRMED:
            return 0
        return self.net_total - self.cost_of_goods


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
        CASH = "cash", "نقدی (قدیمی)"
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
        verbose_name="نام بانک صادرکننده چک",
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

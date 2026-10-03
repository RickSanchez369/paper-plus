# path: apps/products/models.py

from django.db import models
from simple_history.models import HistoricalRecords

from apps.shared.models import BaseModel
from apps.shared.utils import format_number


class PriceTier(models.TextChoices):
    """The two ways the business sells (D-075): to shops in bulk, or to walk-in buyers."""

    RETAIL = "retail", "خرد"
    WHOLESALE = "wholesale", "عمده"


class CartonLine(models.Model):
    """
    The carton + pack part shared by a sales and a purchase invoice line
    (D-081). `quantity` (declared on the line) stays the one stored total in
    packs, which is all stock and FIFO ever read; `cartons` and
    `pack_per_carton` remember how it was entered, so a printed line can say
    "6 carton + 4 pack" and the loose packs are always `quantity - cartons x ratio`.

    A line's money is `cartons x carton_price + loose packs x unit_price`
    (`unit_price` is the price of one pack), so a carton priced as a whole
    never goes through a rounded per-pack figure.
    """

    cartons = models.PositiveIntegerField(default=0, verbose_name="تعداد کارتن")
    # Snapshot of Product.pack_per_carton when the line was written: editing the product's
    # ratio later must not rewrite what an old invoice says it sold.
    pack_per_carton = models.PositiveSmallIntegerField(default=5, verbose_name="بسته در هر کارتن")
    carton_price = models.BigIntegerField(default=0, blank=True, verbose_name="قیمت هر کارتن (تومان)")

    class Meta:
        abstract = True

    @property
    def loose_packs(self):
        """Packs beyond the whole cartons, as entered on the line."""
        return self.quantity - self.cartons * self.pack_per_carton

    @property
    def line_total(self):
        """Toman for the whole line: cartons at the carton price plus loose packs at the pack price."""
        return self.cartons * self.carton_price + self.loose_packs * self.unit_price


class Product(BaseModel):
    """
    A product the business sells or purchases.

    Stock is never stored here; it is derived from InventoryMovement.

    One product, two ways to trade it (D-081): by the pack (the base unit
    every stock, layer and FIFO figure is counted in) or by the carton,
    which is `pack_per_carton` packs. Stock is one number; the carton +
    pack split is only how it is entered and shown.
    """

    class Unit(models.TextChoices):
        # Retired by D-081 (a product is no longer counted in one chosen unit); the column
        # stays until the data conversion has run, then a later migration drops it.
        PACK = "بسته", "بسته"
        CARTON = "کارتن", "کارتن"

    name = models.CharField(
        max_length=200,
        verbose_name="نام کالا",
    )
    sku = models.CharField(
        max_length=50,
        verbose_name="کد کالا",
    )
    unit = models.CharField(
        max_length=20,
        choices=Unit.choices,
        default=Unit.PACK,
        verbose_name="واحد",
    )
    description = models.TextField(
        blank=True,
        verbose_name="توضیحات",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )
    is_onboarded = models.BooleanField(
        default=False,
        verbose_name="موجودی اولیه ثبت شده",
        help_text="پس از ثبت موجودی اولیه True می‌شود و ثبت مجدد ممکن نیست.",
    )
    pack_per_carton = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="تعداد بسته در هر کارتن",
        help_text="نسبت تبدیل کارتن به بسته برای همین کالا.",
    )
    # The column keeps its old name (it is read in ~20 places and renaming it
    # would rebuild the table on SQLite): it now means the price of ONE PACK,
    # the retail price (D-075, D-081).
    default_selling_price = models.BigIntegerField(
        default=0,
        verbose_name="قیمت فروش خرد - هر بسته (تومان)",
        help_text="قیمت یک بسته؛ برای پر کردن خودکار قیمت بسته در فاکتور فروش. تغییر آن قیمت فاکتورهای قبلی را عوض نمی‌کند.",
    )
    # Since D-081 this is the price of ONE WHOLE CARTON, not of a unit.
    wholesale_selling_price = models.BigIntegerField(
        default=0,
        verbose_name="قیمت فروش عمده - هر کارتن (تومان)",
        help_text="قیمت یک کارتن کامل. صفر یعنی تعیین نشده؛ در این صورت قیمت کارتن = قیمت هر بسته × تعداد بسته در کارتن.",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "کالا"
        verbose_name_plural = "کالاها"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["sku"],
                name="unique_product_sku",
            ),
            models.CheckConstraint(
                condition=models.Q(default_selling_price__gte=0),
                name="product_default_selling_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(wholesale_selling_price__gte=0),
                name="product_wholesale_selling_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(pack_per_carton__gte=1),
                name="product_pack_per_carton_positive",
            ),
        ]

    @property
    def pack_price(self):
        """The price suggested for one pack (retail, D-081)."""
        return self.default_selling_price

    @property
    def carton_price(self):
        """
        The price suggested for one whole carton (D-081): the wholesale price,
        or, while that is unset (0), pack price x packs per carton -- never a
        guess at a discount, so a carton is never suggested for free.
        """
        if self.wholesale_selling_price > 0:
            return self.wholesale_selling_price
        return self.default_selling_price * self.pack_per_carton

    @property
    def wholesale_is_unset(self):
        """True while the carton price was never set or only repeats pack price x ratio -- worth flagging in Inventory."""
        return (
            self.wholesale_selling_price == 0
            or self.wholesale_selling_price == self.default_selling_price * self.pack_per_carton
        )

    def __str__(self):
        # Unsaved instance (e.g. an add-form preview): no pk yet, so no
        # ledger to query.
        if self._state.adding:
            return f"{self.name} ({self.sku})"      
        # Local import: apps.inventory.models imports Product, so importing
        # apps.inventory.selectors at module level here would be circular.
        from apps.inventory.selectors import get_stock

        return f"{self.name} ({self.sku}) — موجودی: {format_number(get_stock(self))}"
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

    name = models.CharField(
        max_length=200,
        verbose_name="نام کالا",
    )
    sku = models.CharField(
        max_length=50,
        verbose_name="کد کالا",
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
    # D-090: the other two cells of the price grid (sale type x unit). 0 = unset;
    # `price_for` then suggests a value from the prices that are set, never a free item.
    retail_carton_price = models.BigIntegerField(
        default=0,
        verbose_name="قیمت فروش خرد - هر کارتن (تومان)",
        help_text="صفر یعنی تعیین نشده؛ در این صورت قیمت بسته خرد × تعداد بسته در کارتن.",
    )
    wholesale_pack_price = models.BigIntegerField(
        default=0,
        verbose_name="قیمت فروش عمده - هر بسته (تومان)",
        help_text="صفر یعنی تعیین نشده؛ در این صورت قیمت کارتن عمده ÷ تعداد بسته در کارتن (یا قیمت بسته خرد).",
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
            models.CheckConstraint(
                condition=models.Q(retail_carton_price__gte=0, wholesale_pack_price__gte=0),
                name="product_tier_unit_prices_non_negative",
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

    def price_for(self, tier, unit):
        """
        The suggested price of one ``unit`` ("pack"/"carton") on a ``tier`` (PriceTier) invoice (D-090):
        the one place the four-cell grid is read. An unset cell (0) is derived only from cells
        the owner did set, in a fixed order, and never comes out lower than a set cell implies:

        - retail pack: the retail pack price;
        - retail carton: set, else retail pack x ratio;
        - wholesale carton: set, else wholesale pack x ratio, else the retail carton;
        - wholesale pack: set, else wholesale carton / ratio (rounded up to a Toman), else retail pack.
        """
        ratio = self.pack_per_carton or 1
        retail_pack = self.default_selling_price
        retail_carton = self.retail_carton_price or retail_pack * ratio
        if tier == PriceTier.WHOLESALE:
            if unit == "carton":
                return self.wholesale_selling_price or (self.wholesale_pack_price * ratio) or retail_carton
            if self.wholesale_pack_price:
                return self.wholesale_pack_price
            if self.wholesale_selling_price:
                return -(-self.wholesale_selling_price // ratio)
            return retail_pack
        return retail_carton if unit == "carton" else retail_pack

    def price_is_set(self, tier, unit):
        """True when that cell of the grid was typed by the owner, not derived."""
        field = {
            (PriceTier.RETAIL, "pack"): "default_selling_price",
            (PriceTier.RETAIL, "carton"): "retail_carton_price",
            (PriceTier.WHOLESALE, "pack"): "wholesale_pack_price",
            (PriceTier.WHOLESALE, "carton"): "wholesale_selling_price",
        }[(tier, unit)]
        return getattr(self, field) > 0

    @property
    def price_grid(self):
        """The four suggested prices with a set/derived flag each, for pages and data-* attributes."""
        return {
            f"{tier}_{unit}": {"price": self.price_for(tier, unit), "set": self.price_is_set(tier, unit)}
            for tier in (PriceTier.RETAIL, PriceTier.WHOLESALE) for unit in ("pack", "carton")
        }

    @property
    def prices_incomplete(self):
        """True while any of the four cells is derived rather than set -- flagged in Inventory (D-090)."""
        return not all(cell["set"] for cell in self.price_grid.values())

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
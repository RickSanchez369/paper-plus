# path: apps/products/models.py

from django.db import models
from simple_history.models import HistoricalRecords

from apps.shared.models import BaseModel
from apps.shared.utils import format_number


class PriceTier(models.TextChoices):
    """The two ways the business sells (D-075): to shops in bulk, or to walk-in buyers."""

    RETAIL = "retail", "خرد"
    WHOLESALE = "wholesale", "عمده"


class Product(BaseModel):
    """
    A product the business sells or purchases.

    Stock is never stored here; it is derived from InventoryMovement.

    A product is counted in ONE unit, pack or carton (D-076). The same goods
    sold in both units are two products, each with its own stock, FIFO cost
    and prices -- there is deliberately no pack-per-carton ratio.
    """

    class Unit(models.TextChoices):
        # The stored value is the Persian word itself, so every page that
        # prints `product.unit` keeps working unchanged.
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
    # The column keeps its old name (it is read in ~20 places and renaming it
    # would rebuild the table on SQLite): it now means the RETAIL price (D-075).
    default_selling_price = models.BigIntegerField(
        default=0,
        verbose_name="قیمت فروش خرد (تومان)",
        help_text="برای پر کردن خودکار قیمت در فاکتور فروش خرد؛ تغییر آن قیمت فاکتورهای قبلی را عوض نمی‌کند.",
    )
    wholesale_selling_price = models.BigIntegerField(
        default=0,
        verbose_name="قیمت فروش عمده (تومان)",
        help_text="برای فاکتور فروش عمده. صفر یعنی تعیین نشده؛ در این صورت قیمت خرد پیشنهاد می‌شود.",
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
        ]

    def price_for(self, tier):
        """
        The price to suggest on a sales line of this tier (D-075): the
        wholesale price for a wholesale sale, the retail one otherwise.
        An unset (0) wholesale price falls back to retail, so a wholesale
        invoice never silently suggests a free item.
        """
        if tier == PriceTier.WHOLESALE and self.wholesale_selling_price > 0:
            return self.wholesale_selling_price
        return self.default_selling_price

    @property
    def wholesale_is_unset(self):
        """True while the wholesale price still equals retail or was never set -- worth flagging in Inventory."""
        return self.wholesale_selling_price == 0 or self.wholesale_selling_price == self.default_selling_price

    def __str__(self):
        # Unsaved instance (e.g. an add-form preview): no pk yet, so no
        # ledger to query.
        if self._state.adding:
            return f"{self.name} ({self.sku})"      
        # Local import: apps.inventory.models imports Product, so importing
        # apps.inventory.selectors at module level here would be circular.
        from apps.inventory.selectors import get_stock

        return f"{self.name} ({self.sku}) — موجودی: {format_number(get_stock(self))}"
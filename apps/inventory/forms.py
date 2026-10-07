# path: apps/inventory/forms.py

"""
The Inventory module's one stock-creating form: a new product, with its
opening stock entered right there or never (D-044).

Stock otherwise changes only through documents -- a confirmed purchase
adds, a confirmed sale removes, a cancellation reverses exactly what its
document did. There is no manual adjustment or later "opening stock"
page: a product that already has stock in the warehouse on the day it is
added gets it once, here, at its own cost (D-017's rule, unchanged).
"""

from django import forms

from apps.shared.widgets import NumericInput
from apps.products.forms import QuickProductForm
from apps.products.units import to_packs

_NUMBER = {"class": "field__control", "dir": "ltr", "inputmode": "numeric"}


class InventoryProductForm(QuickProductForm):
    """
    QuickProductForm plus an optional one-time opening stock. Blank
    quantity: the product starts at zero and its first stock arrives by
    purchase invoice. A quantity needs its purchase cost too -- that cost
    becomes the product's first FIFO layer, so inventory value stays
    cost-based from the very first unit (never the selling price).
    """

    MAX_OPENING_PACKS = 10**8
    MAX_OPENING_COST = 10**10

    opening_cartons = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=10**9,
        label="موجودی فعلی - کارتن",
        help_text="فقط برای کالایی که همین حالا در انبار موجود است؛ بعداً فقط با فاکتور خرید/فروش تغییر می‌کند.",
        widget=NumericInput(attrs=_NUMBER),
        error_messages={"min_value": "مقدار نمی‌تواند منفی باشد."},
    )
    opening_packs = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=10**9,
        label="موجودی فعلی - بسته",
        widget=NumericInput(attrs=_NUMBER),
        error_messages={"min_value": "مقدار نمی‌تواند منفی باشد."},
    )
    opening_unit_cost = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=10**12,
        label="بهای خرید هر بسته (تومان)",
        help_text="بهای تمام‌شدهٔ همین موجودی؛ مبنای ارزش انبار است، نه قیمت فروش. اگر موجودی وارد کرده‌اید، این مورد الزامی است.",
        widget=NumericInput(attrs=_NUMBER),
        error_messages={"min_value": "بها نمی‌تواند منفی باشد."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Typing starts on the name; skipped on a re-render so an error is not buried by a focus jump.
        if not self.is_bound:
            self.fields["name"].widget.attrs["autofocus"] = True

    def clean(self):
        cleaned = super().clean()
        # The stored quantity is always packs (D-081): cartons x ratio + loose packs.
        quantity = to_packs(cleaned.get("opening_cartons"), cleaned.get("opening_packs"), cleaned.get("pack_per_carton") or 1)
        cleaned["opening_quantity"] = quantity or None
        cost = cleaned.get("opening_unit_cost")
        # Bounds, so quantity x cost stays far inside SQLite's 64-bit sums: a 20-digit opening quantity was a 500 (OverflowError).
        too_much = bool(quantity and quantity > self.MAX_OPENING_PACKS)
        too_dear = cost is not None and cost > self.MAX_OPENING_COST
        if too_much:
            self.add_error("opening_cartons", "این مقدار موجودی غیرواقعی است؛ عدد را بررسی کنید.")
            cleaned["opening_quantity"] = None
        if too_dear:
            self.add_error("opening_unit_cost", "این بهای خرید غیرواقعی است؛ عدد را بررسی کنید.")
        if not too_much and not too_dear:
            if quantity and cost is None:
                self.add_error("opening_unit_cost", "همراه موجودی فعلی، بهای خرید هر بسته هم لازم است.")
            elif quantity and cost == 0:
                # D-097: a free first layer would make every later sale of it pure profit.
                self.add_error("opening_unit_cost", "بهای خرید نمی‌تواند صفر باشد؛ بهای واقعی را وارد کنید.")
            if cost is not None and not quantity:
                self.add_error("opening_cartons", "بها بدون مقدار معنایی ندارد؛ مقدار را وارد کنید یا بها را خالی بگذارید.")
        return cleaned

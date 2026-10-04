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

    opening_cartons = forms.IntegerField(
        required=False,
        min_value=0,
        label="موجودی فعلی - کارتن (اختیاری)",
        help_text="فقط برای کالایی که همین حالا در انبار موجود است؛ بعداً فقط با فاکتور خرید/فروش تغییر می‌کند.",
        widget=NumericInput(attrs=_NUMBER),
        error_messages={"min_value": "مقدار نمی‌تواند منفی باشد."},
    )
    opening_packs = forms.IntegerField(
        required=False,
        min_value=0,
        label="موجودی فعلی - بسته (اختیاری)",
        widget=NumericInput(attrs=_NUMBER),
        error_messages={"min_value": "مقدار نمی‌تواند منفی باشد."},
    )
    opening_unit_cost = forms.IntegerField(
        required=False,
        min_value=0,
        label="بهای خرید هر بسته (تومان)",
        help_text="بهای تمام‌شدهٔ همین موجودی؛ مبنای ارزش انبار است، نه قیمت فروش.",
        widget=NumericInput(attrs=_NUMBER),
        error_messages={"min_value": "بها نمی‌تواند منفی باشد."},
    )

    def clean(self):
        cleaned = super().clean()
        # The stored quantity is always packs (D-081): cartons x ratio + loose packs.
        quantity = to_packs(cleaned.get("opening_cartons"), cleaned.get("opening_packs"), cleaned.get("pack_per_carton") or 1)
        cleaned["opening_quantity"] = quantity or None
        cost = cleaned.get("opening_unit_cost")
        if quantity and cost is None:
            self.add_error("opening_unit_cost", "همراه موجودی فعلی، بهای خرید هر بسته هم لازم است.")
        if cost is not None and not quantity:
            self.add_error("opening_cartons", "بها بدون مقدار معنایی ندارد؛ مقدار را وارد کنید یا بها را خالی بگذارید.")
        return cleaned

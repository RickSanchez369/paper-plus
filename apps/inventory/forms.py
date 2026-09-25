# path: apps/inventory/forms.py

"""
The three Inventory list-page actions (REDESIGN_VISION 4.3): new product
(reuses apps.products.forms.QuickProductForm as-is), opening stock entry,
manual adjustment. Each is a small dedicated page, not a modal -- these are
rare, deliberate actions (a wrong opening stock or adjustment is corrected
only by another entry, never edited), so a full page with a clear result
beats a disclosure that is easy to submit by accident.
"""

from django import forms

from apps.products.models import Product

from .models import InventoryMovement

TOMAN_HINT = "به ریال وارد شود. (۱ تومان = ۱۰ ریال)"


class OpeningStockForm(forms.Form):
    """Feeds apps.inventory.services.set_opening_stock. Only a
    not-yet-onboarded product may be picked -- the service itself also
    refuses, this just keeps the picker from offering a doomed choice."""

    product = forms.ModelChoiceField(
        label="کالا",
        queryset=Product.objects.filter(is_active=True, is_onboarded=False).order_by("name"),
        empty_label="— انتخاب کالا —",
        widget=forms.Select(attrs={"class": "field__control"}),
        error_messages={"required": "انتخاب کالا الزامی است."},
    )
    quantity = forms.IntegerField(
        min_value=0,
        label="مقدار",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"required": "مقدار الزامی است.", "min_value": "مقدار نمی‌تواند منفی باشد."},
    )
    unit_price = forms.IntegerField(
        min_value=0,
        label="قیمت واحد (ریال)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        help_text=TOMAN_HINT,
        error_messages={"required": "قیمت واحد الزامی است.", "min_value": "قیمت نمی‌تواند منفی باشد."},
    )


class AdjustmentForm(forms.Form):
    """Feeds apps.inventory.services.record_adjustment. `unit_price` is
    required only for an increase -- a decrease draws its cost from the
    layers it consumes, it does not invent one."""

    product = forms.ModelChoiceField(
        label="کالا",
        queryset=Product.objects.filter(is_active=True).order_by("name"),
        empty_label="— انتخاب کالا —",
        widget=forms.Select(attrs={"class": "field__control"}),
        error_messages={"required": "انتخاب کالا الزامی است."},
    )
    direction = forms.ChoiceField(
        label="نوع اصلاح",
        choices=(
            (InventoryMovement.MovementType.ADJUSTMENT_IN, "افزایش موجودی"),
            (InventoryMovement.MovementType.ADJUSTMENT_OUT, "کاهش موجودی"),
        ),
        initial=InventoryMovement.MovementType.ADJUSTMENT_IN,
        widget=forms.Select(attrs={"class": "field__control"}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        label="مقدار",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"required": "مقدار الزامی است.", "min_value": "مقدار باید بزرگ‌تر از صفر باشد."},
    )
    unit_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت واحد (ریال) — فقط برای افزایش",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        help_text=TOMAN_HINT,
        error_messages={"min_value": "قیمت نمی‌تواند منفی باشد."},
    )
    note = forms.CharField(
        label="دلیل اصلاح",
        widget=forms.Textarea(attrs={"class": "field__control", "rows": 2}),
        error_messages={"required": "دلیل اصلاح الزامی است."},
    )

    def clean(self):
        cleaned = super().clean()
        direction = cleaned.get("direction")
        unit_price = cleaned.get("unit_price")
        if direction == InventoryMovement.MovementType.ADJUSTMENT_IN and unit_price is None:
            self.add_error("unit_price", "برای افزایش موجودی، قیمت واحد الزامی است.")
        return cleaned

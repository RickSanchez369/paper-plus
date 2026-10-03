# path: apps/products/forms.py

"""
"کالای جدید", inline mid-purchase.

Unlike the quick customer/supplier forms, `default_selling_price` is
required here even though the user is in a *purchase* flow: the vision
doc's own real-gaps review (gap #6) called out that silently accepting
the field's `0` default would let a product go out the door as an
accidental free sale later, since nothing else ever prompts for a
selling price after this moment.
"""

import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property

from .models import Product

_WIDGETS = {
    "name": forms.TextInput(attrs={"class": "field__control", "autocomplete": "off"}),
    "sku": forms.TextInput(attrs={"class": "field__control", "dir": "ltr", "autocomplete": "off"}),
    "unit": forms.Select(attrs={"class": "field__control"}),
    "default_selling_price": forms.NumberInput(
        attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}
    ),
    "wholesale_selling_price": forms.NumberInput(
        attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}
    ),
}


def excluded_product_ids(raw):
    """Ids from the item-row search's `exclude` parameter (products already
    on the invoice), ignoring anything that is not a UUID."""
    ids = []
    for part in raw.split(","):
        try:
            ids.append(uuid.UUID(part.strip()))
        except ValueError:
            continue
    return ids


class SelectedProductMixin:
    """
    For an invoice item form whose `product` is a hidden input filled by the
    row's JS search box (SaleItemForm, PurchaseItemForm): the product that
    row already holds, so a form re-rendered after a validation error can
    show its name and stock again (C.fix-2). Before this the hidden id
    survived but the visible search box came back empty, and nothing on
    the page said which product each row still held.

    Read from cleaned_data when the row itself validated, otherwise from
    the raw submitted id -- a row rejected for its quantity still holds a
    product. None for an unbound form (a fresh page, the row template).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A deactivated product must not be sold or bought by a hand-made
        # POST any more than the search box offers it.
        self.fields["product"].queryset = Product.objects.filter(is_active=True)
        self.fields["product"].error_messages["invalid_choice"] = "این کالا معتبر یا فعال نیست."

    @cached_property
    def selected_product(self):
        if not self.is_bound:
            return None
        product = getattr(self, "cleaned_data", {}).get("product")
        if product is not None:
            return product
        value = self["product"].value()
        if not value:
            return None
        try:
            return Product.objects.filter(pk=value).first()
        except (ValueError, ValidationError):
            return None  # a tampered id: nothing to show, the field error says why

    @cached_property
    def selected_stock(self):
        """Live stock of `selected_product`, the same figure a search result shows."""
        if self.selected_product is None:
            return None
        # Local import: apps.inventory.models imports Product (same reason as Product.__str__).
        from apps.inventory.selectors import get_stock

        return get_stock(self.selected_product)


class QuickProductForm(forms.ModelForm):
    """New product, inline. Reused wherever a purchase or (later) the
    Inventory module needs to create one without leaving the page."""

    class Meta:
        model = Product
        fields = ("name", "sku", "unit", "default_selling_price", "wholesale_selling_price")
        widgets = _WIDGETS
        error_messages = {
            "name": {"required": "نام کالا الزامی است."},
            "sku": {
                "required": "کد کالا الزامی است.",
                "unique": "کالای دیگری با همین کد ثبت شده است.",
            },
            "unit": {"required": "واحد کالا الزامی است."},
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("wholesale_selling_price") is None:
            cleaned["wholesale_selling_price"] = cleaned.get("default_selling_price") or 0
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model's `default=0` would otherwise pre-fill the box with 0,
        # and an untouched 0 passes "required" -- exactly the accidental
        # free sale gap #6 is about. Starting empty makes someone type it.
        self.fields["default_selling_price"].initial = None
        # Wholesale is optional here: left blank it starts equal to retail
        # (the owner sets the real one in Inventory, D-075).
        self.fields["wholesale_selling_price"].required = False
        self.fields["wholesale_selling_price"].initial = None
        self.fields["wholesale_selling_price"].help_text = "اگر خالی بماند، برابر قیمت خرد ثبت می‌شود."
        # Already required (the model field has no blank=True); only the
        # message changes, since Django's generic one gives no hint why a
        # *purchase* flow is asking for a *selling* price.
        self.fields["default_selling_price"].error_messages["required"] = (
            "قیمت فروش را وارد کنید — حتی برای کالایی که تازه خریداری می‌شود، "
            "تا بعداً به‌صورت رایگان فروخته نشود."
        )


class SellingPriceForm(forms.Form):
    """The prices a user sets by hand after creation: what the product sells
    for from now on, retail and wholesale (feeds
    products.services.update_selling_prices). A blank box leaves that price
    alone. Purchase cost is never typed here -- it comes only from purchase
    invoices, and inventory value only ever reads that cost."""

    default_selling_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت فروش خرد (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "قیمت فروش نمی‌تواند منفی باشد."},
    )
    wholesale_selling_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت فروش عمده (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "قیمت فروش نمی‌تواند منفی باشد."},
    )

    def clean(self):
        cleaned = super().clean()
        if (
            not self.errors
            and cleaned.get("default_selling_price") is None
            and cleaned.get("wholesale_selling_price") is None
        ):
            raise forms.ValidationError("قیمت فروش را وارد کنید.")
        return cleaned

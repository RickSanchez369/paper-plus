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

from apps.shared.widgets import NumericInput
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils.functional import cached_property

from .models import Product
from .units import to_packs

_WIDGETS = {
    "name": forms.TextInput(attrs={"class": "field__control", "autocomplete": "off"}),
    "sku": forms.TextInput(attrs={"class": "field__control", "dir": "ltr", "autocomplete": "off"}),
    "pack_per_carton": NumericInput(
        attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric", "min": "1"}
    ),
    "default_selling_price": NumericInput(
        attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}
    ),
    "wholesale_selling_price": NumericInput(
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


# What a PositiveIntegerField column holds; a line's total in packs may not pass it.
MAX_QUANTITY = 2_147_483_647

_COUNT_ATTRS = {"class": "field__control", "dir": "ltr", "inputmode": "numeric"}
_PRICE_ATTRS = {"class": "field__control item-row__price", "dir": "ltr", "inputmode": "numeric"}


class CartonPackItemFormMixin(forms.Form):
    """
    The carton + pack part of an invoice line form (D-081), shared by the
    sales and purchase lines. A line is typed as cartons and loose packs in
    ONE row; `quantity` (the stored total in packs) and the ratio snapshot are
    derived here from the product's `pack_per_carton`, so no row ever has to
    be split in two for one product.

    It subclasses `forms.Form` only so its declared fields are collected by
    Django (the same trick as `InvoicePaymentFields`); put it before
    `SelectedProductMixin`/`forms.ModelForm` in the bases and list "cartons",
    "unit_price" and "carton_price" in `Meta.fields`. Subclasses
    say, through `price_required`, whether a price may be left blank (a sale
    fills it from the product; a purchase never does).
    """

    price_required = False

    cartons = forms.IntegerField(
        required=False,
        min_value=0,
        label="کارتن",
        widget=NumericInput(attrs={**_COUNT_ATTRS, "class": "field__control item-row__cartons", "aria-label": "تعداد کارتن"}),
        error_messages={"min_value": "تعداد کارتن نمی‌تواند منفی باشد."},
    )
    packs = forms.IntegerField(
        required=False,
        min_value=0,
        label="بسته",
        widget=NumericInput(attrs={**_COUNT_ATTRS, "class": "field__control item-row__packs", "aria-label": "تعداد بسته"}),
        error_messages={"min_value": "تعداد بسته نمی‌تواند منفی باشد."},
    )
    carton_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت هر کارتن (تومان)",
        widget=NumericInput(attrs={**_PRICE_ATTRS, "class": "field__control item-row__carton-price", "aria-label": "قیمت هر کارتن (تومان)"}),
        error_messages={"min_value": "قیمت نمی‌تواند منفی باشد."},
    )
    unit_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت هر بسته (تومان)",
        widget=NumericInput(attrs={**_PRICE_ATTRS, "aria-label": "قیمت هر بسته (تومان)"}),
        error_messages={"min_value": "قیمت نمی‌تواند منفی باشد."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A re-rendered row shows what was typed, and a stored line shows its cartons + loose packs.
        instance = self.instance
        if not self.is_bound and not instance._state.adding:
            self.initial.setdefault("packs", instance.loose_packs)

    def suggested_price(self, product, unit):
        """The price a blank box gets: the product's pack / carton price. A sale line asks its invoice's tier (D-090)."""
        return product.pack_price if unit == "pack" else product.carton_price

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        if product is None:
            return cleaned
        cartons = cleaned.get("cartons") or 0
        packs = cleaned.get("packs") or 0
        ratio = product.pack_per_carton
        quantity = to_packs(cartons, packs, ratio)
        if quantity <= 0:
            self.add_error("cartons", "تعداد کارتن یا بسته را وارد کنید.")
            return cleaned
        # `quantity` is not a form field, so the model's own range check never sees it.
        if quantity > MAX_QUANTITY:
            self.add_error("cartons", "مقدار واردشده بیش از حد بزرگ است.")
            return cleaned
        cleaned["cartons"] = cartons
        cleaned["quantity"] = quantity
        # The stored total and the ratio snapshot are not form fields; set them on the instance.
        self.instance.quantity = quantity
        self.instance.pack_per_carton = ratio
        for count, price, label in ((cartons, "carton_price", "کارتن"), (packs, "unit_price", "بسته")):
            if cleaned.get(price) is None:
                if count and self.price_required:
                    self.add_error(price, f"قیمت هر {label} الزامی است.")
                elif price == "carton_price":
                    cleaned[price] = self.suggested_price(product, "carton") if count else 0
                else:
                    cleaned[price] = self.suggested_price(product, "pack") if (count or not self.price_required) else 0
            # D-097: a zero price on a part that is used is never a real price (a purchase at 0 would
            # inflate profit later); a gift or sample is entered at 1 Toman.
            if count and not cleaned.get(price) and price not in self.errors:
                self.add_error(price, f"قیمت هر {label} نمی‌تواند صفر باشد (برای هدیه یا نمونه ۱ تومان بزنید).")
        return cleaned


class QuickProductForm(forms.ModelForm):
    """New product, inline. Reused wherever a purchase or (later) the
    Inventory module needs to create one without leaving the page."""

    class Meta:
        model = Product
        fields = (
            "name", "sku", "pack_per_carton", "default_selling_price", "wholesale_selling_price",
        )
        widgets = _WIDGETS
        error_messages = {
            "name": {"required": "نام کالا الزامی است."},
            "sku": {
                "required": "کد کالا الزامی است.",
                "unique": "کالای دیگری با همین کد ثبت شده است.",
            },
            "pack_per_carton": {
                "required": "تعداد بسته در هر کارتن الزامی است.",
                "min_value": "تعداد بسته در هر کارتن باید حداقل ۱ باشد.",
            },
        }

    def clean(self):
        cleaned = super().clean()
        # Blank carton price = unset (0): a carton is then suggested at pack price x ratio (D-081, D-100).
        if cleaned.get("wholesale_selling_price") is None:
            cleaned["wholesale_selling_price"] = 0
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model's `default=0` would otherwise pre-fill the box with 0,
        # and an untouched 0 passes "required" -- exactly the accidental
        # free sale gap #6 is about. Starting empty makes someone type it.
        self.fields["default_selling_price"].initial = None
        # The carton price is optional here: left blank it follows the pack price
        # (the owner sets the real one in Inventory, D-075, D-081).
        self.fields["wholesale_selling_price"].required = False
        self.fields["wholesale_selling_price"].initial = None
        self.fields["wholesale_selling_price"].help_text = "اگر خالی بماند، قیمت کارتن = قیمت هر بسته × تعداد بسته در کارتن."
        self.fields["pack_per_carton"].min_value = 1
        self.fields["pack_per_carton"].validators.append(MinValueValidator(1))
        # Already required (the model field has no blank=True); only the
        # message changes, since Django's generic one gives no hint why a
        # *purchase* flow is asking for a *selling* price.
        self.fields["default_selling_price"].error_messages["required"] = (
            "قیمت فروش را وارد کنید — حتی برای کالایی که تازه خریداری می‌شود، "
            "تا بعداً به‌صورت رایگان فروخته نشود."
        )


class SellingPriceForm(forms.Form):
    """The prices a user sets by hand after creation: what the product sells
    for from now on: the pack price (retail) and the carton price (wholesale) (D-100; feeds
    products.services.update_selling_prices). A blank box leaves that price
    alone. Purchase cost is never typed here -- it comes only from purchase
    invoices, and inventory value only ever reads that cost."""

    default_selling_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت فروش خرد - هر بسته (تومان)",
        widget=NumericInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "قیمت فروش نمی‌تواند منفی باشد."},
    )
    wholesale_selling_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت فروش عمده - هر کارتن (تومان)",
        widget=NumericInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "قیمت فروش نمی‌تواند منفی باشد."},
    )

    PRICE_FIELDS = ("default_selling_price", "wholesale_selling_price")

    def clean(self):
        cleaned = super().clean()
        if not self.errors and all(cleaned.get(f) is None for f in self.PRICE_FIELDS):
            raise forms.ValidationError("قیمت فروش را وارد کنید.")
        return cleaned

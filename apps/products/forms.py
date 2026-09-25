# path: apps/products/forms.py

"""
"کالای جدید", inline mid-purchase (REDESIGN_VISION 4.2, vision doc §13).

Unlike the quick customer/supplier forms, `default_selling_price` is
required here even though the user is in a *purchase* flow: the vision
doc's own real-gaps review (gap #6) called out that silently accepting
the field's `0` default would let a product go out the door as an
accidental free sale later, since nothing else ever prompts for a
selling price after this moment.
"""

from django import forms

from .models import Product

_WIDGETS = {
    "name": forms.TextInput(attrs={"class": "field__control", "autocomplete": "off"}),
    "sku": forms.TextInput(attrs={"class": "field__control", "dir": "ltr", "autocomplete": "off"}),
    "unit": forms.TextInput(attrs={"class": "field__control"}),
    "default_selling_price": forms.NumberInput(
        attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}
    ),
}


class QuickProductForm(forms.ModelForm):
    """New product, inline. Reused wherever a purchase or (later) the
    Inventory module needs to create one without leaving the page."""

    class Meta:
        model = Product
        fields = ("name", "sku", "unit", "default_selling_price")
        widgets = _WIDGETS
        error_messages = {
            "name": {"required": "نام کالا الزامی است."},
            "sku": {
                "required": "کد کالا الزامی است.",
                "unique": "کالای دیگری با همین کد ثبت شده است.",
            },
            "unit": {"required": "واحد کالا الزامی است."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Already required (the model field has no blank=True); only the
        # message changes, since Django's generic one gives no hint why a
        # *purchase* flow is asking for a *selling* price.
        self.fields["default_selling_price"].error_messages["required"] = (
            "قیمت فروش را وارد کنید — حتی برای کالایی که تازه خریداری می‌شود، "
            "تا بعداً به‌صورت رایگان فروخته نشود."
        )

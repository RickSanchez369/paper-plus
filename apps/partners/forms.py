# path: apps/partners/forms.py

"""
"مشتری جدید" / "تأمین‌کننده جدید" — the inline mini-forms.

A party can be created without leaving the invoice being written, and the
same form appears on the Customers page.
One form class per model, rendered by one shared partial, so the three
places cannot disagree about which fields a new party needs.

Only name is required. A customer met once, mid-invoice, has a name and
maybe a phone number; demanding an address would train people to type
rubbish into it.
"""

from django import forms

from .models import Customer, Supplier

_WIDGETS = {
    "name": forms.TextInput(attrs={"class": "field__control", "autocomplete": "off"}),
    "phone": forms.TextInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "tel"}),
    "address": forms.Textarea(attrs={"class": "field__control", "rows": 2}),
    "note": forms.TextInput(attrs={"class": "field__control"}),
}


class QuickCustomerForm(forms.ModelForm):
    """New customer, inline. Reused by the Customers page and the sale form."""

    class Meta:
        model = Customer
        fields = ("name", "phone", "address", "note")
        widgets = _WIDGETS
        error_messages = {
            "name": {
                # Names are globally unique now that there is one business
                # (D-033); without this the user would get Django's English
                # default for a uniqueness clash.
                "unique": "مشتری دیگری با همین نام ثبت شده است.",
                "required": "نام مشتری الزامی است.",
            },
        }


class QuickSupplierForm(forms.ModelForm):
    """New supplier, inline. Reused by the Suppliers sub-section and the purchase form."""

    class Meta:
        model = Supplier
        fields = ("name", "phone", "address", "note")
        widgets = _WIDGETS
        error_messages = {
            "name": {
                "unique": "تأمین‌کنندهٔ دیگری با همین نام ثبت شده است.",
                "required": "نام تأمین‌کننده الزامی است.",
            },
        }


class CustomerForm(forms.ModelForm):
    """Full edit form for the Customers detail page --
    the quick-create form only asks name/phone/address/note; this one adds
    is_active, since deactivating a customer is an edit-page action, not a
    mid-invoice one."""

    class Meta:
        model = Customer
        fields = ("name", "phone", "address", "note", "is_active")
        widgets = {
            **_WIDGETS,
            "is_active": forms.CheckboxInput(),
        }
        error_messages = {
            "name": {
                "unique": "مشتری دیگری با همین نام ثبت شده است.",
                "required": "نام مشتری الزامی است.",
            },
        }


class SupplierForm(forms.ModelForm):
    """Full create/edit form for the Suppliers sub-section -- the supplier
    counterpart of CustomerForm, so a supplier can be added from its own
    list page instead of only mid-purchase. Same fields as the quick form
    plus is_active, which only makes sense once the supplier exists (the
    create view leaves it out)."""

    class Meta:
        model = Supplier
        fields = ("name", "phone", "address", "note", "is_active")
        widgets = {
            **_WIDGETS,
            "is_active": forms.CheckboxInput(),
        }
        error_messages = {
            "name": {
                "unique": "تأمین‌کنندهٔ دیگری با همین نام ثبت شده است.",
                "required": "نام تأمین‌کننده الزامی است.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance._state.adding:
            # A new supplier is active by definition; deactivating is an edit.
            del self.fields["is_active"]


class CustomerFilterForm(forms.Form):
    """Customers list filters: free-text search over
    name/phone, account status (owes/settled, derived from
    get_customer_outstanding -- never stored, D-025), and active/inactive."""

    ACCOUNT_STATUS_CHOICES = [("", "همه"), ("owes", "بدهکار"), ("settled", "تسویه‌شده")]
    ACTIVE_CHOICES = [("true", "فعال"), ("false", "غیرفعال"), ("", "همه")]

    q = forms.CharField(required=False, label="جست‌وجو (نام یا تلفن)")
    account_status = forms.ChoiceField(required=False, label="وضعیت حساب", choices=ACCOUNT_STATUS_CHOICES)
    # data-fold-default: the phone filter fold (mobile.js) must not read the default «فعال» as an applied filter.
    is_active = forms.ChoiceField(required=False, label="وضعیت فعالیت", choices=ACTIVE_CHOICES, initial="true",
                                  widget=forms.Select(attrs={"data-fold-default": "true"}))

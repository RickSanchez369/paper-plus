# path: apps/purchasing/forms.py

"""
The one-shot new-purchase form.

Symmetric to apps/sales/forms.py, with these differences: no discount concept anywhere (the model never had
one), `unit_price` is always manually typed -- there is no per-product
default to fall back to the way a sale has -- and cancel is stricter
(handled entirely in `cancel_purchase`/`cancel_layer`, not here).
"""

from django import forms

from apps.partners.models import Supplier
from apps.payments.forms import PaymentSourceField
from apps.payments.models import BankAccount
from apps.products.forms import SelectedProductMixin
from apps.products.models import Product
from apps.shared.forms import JalaliDateField

from .models import PurchaseInvoice, PurchaseItem, PurchasePaymentEntry

PAYMENT_MODE_FULL = "full"
PAYMENT_MODE_SPLIT = "split"


class PurchasingFilterForm(forms.Form):
    """Mirrors sales.forms.SalesFilterForm; see there for why the date
    range and the free-text search are deliberately separate forms."""

    q = forms.CharField(required=False, label="جست‌وجو")
    payment_status = forms.ChoiceField(
        required=False,
        label="وضعیت پرداخت",
        choices=[("", "همه"), *PurchaseInvoice.PaymentStatus.choices],
    )
    product = forms.ModelChoiceField(
        required=False,
        label="کالا",
        queryset=Product.objects.filter(is_active=True).order_by("name"),
        empty_label="— همهٔ کالاها —",
    )
    amount_min = forms.IntegerField(required=False, label="حداقل مبلغ (تومان)", min_value=0)
    amount_max = forms.IntegerField(required=False, label="حداکثر مبلغ (تومان)", min_value=0)

    def clean(self):
        cleaned = super().clean()
        lo, hi = cleaned.get("amount_min"), cleaned.get("amount_max")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("amount_max", "حداکثر مبلغ نمی‌تواند از حداقل کمتر باشد.")
        return cleaned


class PurchaseInvoiceForm(forms.ModelForm):
    """Header fields: who, when, the supplier's own invoice number. No
    discount field -- the model has none."""

    invoice_date = JalaliDateField(label="تاریخ فاکتور")
    payment_mode = forms.ChoiceField(
        label="نحوهٔ تسویه",
        choices=(
            (PAYMENT_MODE_FULL, "تسویهٔ کامل (کل مبلغ پرداخت شد)"),
            (PAYMENT_MODE_SPLIT, "تفکیکی / چک / نسیه"),
        ),
        initial=PAYMENT_MODE_FULL,
        widget=forms.RadioSelect,
    )
    paid_from = PaymentSourceField(label="حساب پرداخت‌کننده", required=False)

    class Meta:
        model = PurchaseInvoice
        fields = ("supplier", "invoice_date", "supplier_invoice_number")
        widgets = {
            # form="purchase-form": rendered outside <form id="purchase-form">
            # on purpose, same reason and same fix as Sales' customer field
            # (see apps/sales/forms.py / STATE.md 6d4521a) -- its "+
            # تأمین‌کنندهٔ جدید" disclosure is itself a <form>.
            "supplier": forms.Select(attrs={"class": "field__control", "form": "purchase-form"}),
            "supplier_invoice_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
        }
        error_messages = {
            "supplier": {"required": "انتخاب تأمین‌کننده الزامی است."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True).order_by("name")
        self.fields["supplier"].empty_label = "— انتخاب تأمین‌کننده —"
        self.fields["supplier_invoice_number"].required = False

    def clean(self):
        cleaned = super().clean()
        # Full settlement books real money, so it needs a real answer to
        # "out of which account" -- never cash by omission (D-045).
        if cleaned.get("payment_mode") == PAYMENT_MODE_FULL and cleaned.get("paid_from") == "":
            self.add_error("paid_from", "حساب پرداخت‌کننده (یا «نقدی») را انتخاب کنید.")
        return cleaned

    @property
    def is_full_payment(self):
        return self.cleaned_data.get("payment_mode") == PAYMENT_MODE_FULL


class PurchaseItemForm(SelectedProductMixin, forms.ModelForm):
    """
    One invoice line. `product` is a hidden input filled by the same
    JS-driven search box Sales uses (apps/purchasing/static/purchasing/js/
    purchase_form.js); `unit_price` is always typed by hand here -- a
    purchase price is not a default to fall back to, it is what this
    specific purchase actually cost (the last known cost is only ever a
    placeholder hint, filled client-side from the search result).
    """

    quantity = forms.IntegerField(
        min_value=1,
        label="مقدار",
        widget=forms.NumberInput(attrs={"class": "field__control item-row__qty", "dir": "ltr", "inputmode": "numeric", "aria-label": "مقدار"}),
        error_messages={"required": "مقدار الزامی است.", "min_value": "مقدار باید بزرگ‌تر از صفر باشد."},
    )
    unit_price = forms.IntegerField(
        min_value=0,
        label="قیمت واحد (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control item-row__price", "dir": "ltr", "inputmode": "numeric", "aria-label": "قیمت خرید واحد (تومان)"}),
        error_messages={"required": "قیمت واحد الزامی است.", "min_value": "قیمت نمی‌تواند منفی باشد."},
    )

    class Meta:
        model = PurchaseItem
        fields = ("product", "quantity", "unit_price")
        widgets = {"product": forms.HiddenInput()}
        error_messages = {
            "product": {"required": "یک کالا از فهرست جست‌وجو انتخاب کنید."},
        }


class BasePurchaseItemFormSet(forms.BaseFormSet):
    """Catches the same product picked twice before the DB's unique
    constraint (`unique_product_per_purchase_invoice`) would -- mirrors
    sales.forms.BaseSaleItemFormSet."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if not form.cleaned_data:
                continue
            product = form.cleaned_data.get("product")
            if product is None or product.pk not in seen:
                if product is not None:
                    seen.add(product.pk)
                continue
            raise forms.ValidationError(
                "کالای «%(name)s» بیش از یک بار در فاکتور انتخاب شده است.",
                params={"name": product.name},
            )


PurchaseItemFormSet = forms.formset_factory(PurchaseItemForm, formset=BasePurchaseItemFormSet, extra=1)


class PurchasePaymentEntryForm(forms.ModelForm):
    """One planned payment row -- mirrors sales.forms.SalesPaymentEntryForm
    exactly (same two fixes baked in from the start: `method` declared
    explicitly with an initial so it never gets Django's English blank
    choice, `amount` declared with min_value since BigIntegerField has no
    built-in positivity)."""

    due_date = JalaliDateField(required=False, label="تاریخ سررسید چک")
    method = forms.ChoiceField(
        choices=PurchasePaymentEntry.Method.choices,
        initial=PurchasePaymentEntry.Method.CASH,
        label="روش",
        widget=forms.Select(attrs={"class": "field__control"}),
    )
    amount = forms.IntegerField(
        min_value=1,
        label="مبلغ (تومان)",
        widget=forms.NumberInput(
            attrs={"class": "field__control payment-row__amount", "dir": "ltr", "inputmode": "numeric"}
        ),
        error_messages={"required": "مبلغ الزامی است.", "min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )

    class Meta:
        model = PurchasePaymentEntry
        fields = ("method", "amount", "bank_account", "cheque_number", "bank_name", "due_date")
        widgets = {
            "bank_account": forms.Select(attrs={"class": "field__control"}),
            "cheque_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
            "bank_name": forms.TextInput(attrs={"class": "field__control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bank_account"].queryset = BankAccount.objects.filter(is_active=True)
        self.fields["bank_account"].empty_label = "نقدی"
        self.fields["bank_account"].required = False
        self.fields["cheque_number"].required = False
        self.fields["bank_name"].required = False

    def clean(self):
        cleaned = super().clean()
        # Only a cheque has a number, an issuing bank and a due date; the
        # page hides those fields for the other methods, so whatever a
        # switched-away row still holds must not be saved.
        if cleaned.get("method") != PurchasePaymentEntry.Method.CHEQUE:
            cleaned["cheque_number"] = ""
            cleaned["bank_name"] = ""
            cleaned["due_date"] = None
        return cleaned


PurchasePaymentEntryFormSet = forms.formset_factory(PurchasePaymentEntryForm, extra=0)

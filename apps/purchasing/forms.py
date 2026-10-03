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
from apps.payments.forms import ENTRY_METHOD_CHOICES, InvoicePaymentFields, PaymentEntryFormMixin
from apps.products.forms import CartonPackItemFormMixin, SelectedProductMixin
from apps.products.models import Product
from apps.shared.forms import JalaliDateField

from .models import PurchaseInvoice, PurchaseItem, PurchasePaymentEntry


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


class SupplierFilterForm(forms.Form):
    """Suppliers list filters: free-text search over name/phone and
    active/inactive (mirrors the Customers list; a deactivated supplier is
    only ever hidden by default, never lost)."""

    ACTIVE_CHOICES = [("true", "فعال"), ("false", "غیرفعال"), ("", "همه")]

    q = forms.CharField(required=False, label="جست‌وجو (نام یا تلفن)")
    is_active = forms.ChoiceField(required=False, label="وضعیت فعالیت", choices=ACTIVE_CHOICES, initial="true")


class PurchaseInvoiceForm(InvoicePaymentFields, forms.ModelForm):
    """Header fields: who, when, the supplier's own invoice number. No
    discount field -- the model has none."""

    invoice_date = JalaliDateField(label="تاریخ فاکتور")
    class Meta:
        model = PurchaseInvoice
        fields = ("supplier", "invoice_date", "supplier_invoice_number", "credit_due_date")
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


class PurchaseItemForm(CartonPackItemFormMixin, SelectedProductMixin, forms.ModelForm):
    """
    One invoice line, typed as cartons + loose packs in a single row (D-081).
    `product` is a hidden input filled by the same JS-driven search box Sales
    uses. A price is never defaulted here: a purchase price is what this
    specific purchase cost, so the price of each part that is used (carton
    price for cartons, pack price for packs) must be typed. The last known
    cost is only a placeholder hint, filled client-side from the search result.
    """

    price_required = True

    class Meta:
        model = PurchaseItem
        fields = ("product", "cartons", "unit_price", "carton_price")
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


class PurchasePaymentEntryForm(PaymentEntryFormMixin, forms.ModelForm):
    """One planned payment row -- mirrors sales.forms.SalesPaymentEntryForm
    (method list without cash, account checked against the method, cheque-only
    fields dropped for other methods: all in `PaymentEntryFormMixin`, D-069).
    `amount` is declared with min_value since BigIntegerField has no built-in
    positivity."""

    # Paying a supplier: transfer or cheque; a card reader only receives money.
    entry_methods = tuple(m for m in ENTRY_METHOD_CHOICES if m[0] != "card")

    due_date = JalaliDateField(required=False, label="تاریخ سررسید چک")
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
        fields = ("method", "amount", "bank_account", "cheque_number", "bank_name", "issuer", "due_date")
        widgets = {
            "cheque_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
            "bank_name": forms.TextInput(attrs={"class": "field__control"}),
            "issuer": forms.TextInput(attrs={"class": "field__control"}),
        }


PurchasePaymentEntryFormSet = forms.formset_factory(PurchasePaymentEntryForm, extra=0)

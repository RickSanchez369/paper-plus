# path: apps/sales/forms.py

"""
The one-shot new-sale form.

Three pieces submitted together: the invoice itself, a formset of item
rows, and a formset of payment-entry rows. None of them touch the
database directly -- the view builds unsaved instances from each,
saves them as a draft inside one `transaction.atomic()`, then calls
`confirm_sale` in the same transaction, so a rejection (empty items,
discount over subtotal, payment rows over total, oversell by a non-
superuser) rolls back everything, not just the confirm step. That is
what "one-shot" means here: never a saved, unconfirmed invoice left
behind by a failed submission.

Payment has two modes (D-046). "تسویه کامل", the default: the customer
paid the whole total, and the only question is which account received it
-- no payment rows at all. "تفکیکی / نسیه": the existing rows (cash, card,
transfer, cheque), with whatever they leave unpaid staying as credit.

Field-level validation stays exactly what SaleItem/SalesPaymentEntry
already validate as ModelForms (unit_price falls back to the product's
default via SaleItem.clean_fields, cheque fields stay optional -- same
decision as apps/sales/admin.py's inlines). Cross-row rules (no items,
discount too big, payment rows exceeding the total) are `confirm_sale`'s
job already; duplicating them here would be a second source of truth.
"""

from django import forms
from django.utils.functional import cached_property

from apps.shared.widgets import NumericInput
from apps.inventory.selectors import get_stock_map
from apps.partners.models import Customer
from apps.payments.forms import InvoicePaymentFields, PaymentEntryFormMixin
from apps.products.forms import CartonPackItemFormMixin, SelectedProductMixin
from apps.products.models import Product
from apps.products.units import split_units, units_phrase
from apps.shared.forms import JalaliDateField

from .models import SaleItem, SalesInvoice, SalesPaymentEntry

DISCOUNT_MODE_AMOUNT = "amount"
DISCOUNT_MODE_PERCENT = "percent"


class SalesFilterForm(forms.Form):
    """
    The list page's structured filters, deliberately separate from the
    free-text search box. The date range itself
    is `shared.forms.DateRangeForm`, rendered alongside this one -- same
    <form method="get">, disjoint field names, one querystring.
    """

    q = forms.CharField(required=False, label="جست‌وجو")
    payment_status = forms.ChoiceField(
        required=False,
        label="وضعیت پرداخت",
        choices=[("", "همه"), *SalesInvoice.PaymentStatus.choices],
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


class SaleInvoiceForm(InvoicePaymentFields, forms.ModelForm):
    """
    Invoice-level fields: who, when, how much discount, and how it was
    settled. The payment fields come from `InvoicePaymentFields`: they are
    not model fields -- they decide which payment-entry rows the view plans
    before confirm_sale (D-046, D-069); the invoice itself stores no payment
    state (D-025) except the due date of an unpaid (نسیه) remainder.
    """

    invoice_date = JalaliDateField(label="تاریخ فاکتور")
    # BigIntegerField has no built-in non-negativity; only the DB
    # CheckConstraint (`sales_invoice_discount_non_negative`) enforces
    # discount_amount >= 0 -- declared explicitly so a negative discount
    # never reaches the DB (confirm_sale only checks discount <= subtotal).
    discount_amount = forms.IntegerField(
        required=False,
        min_value=0,
        label="تخفیف (تومان)",
        widget=NumericInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "تخفیف نمی‌تواند منفی باشد."},
    )
    # The discount can be typed as a Toman amount or as a percent of the
    # subtotal (D-070). Neither mode adds a stored field: the percent is
    # turned into Toman by the view once the lines (hence the subtotal) exist.
    discount_mode = forms.ChoiceField(
        label="نوع تخفیف",
        required=False,  # absent = a Toman amount, the original behaviour
        choices=((DISCOUNT_MODE_AMOUNT, "مبلغ (تومان)"), (DISCOUNT_MODE_PERCENT, "درصد")),
        initial=DISCOUNT_MODE_AMOUNT,
        widget=forms.RadioSelect,
    )
    discount_percent = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=100,
        max_digits=5,
        decimal_places=2,
        label="تخفیف (درصد)",
        widget=NumericInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "decimal", "step": "any"}),
        error_messages={
            "min_value": "درصد تخفیف نمی‌تواند منفی باشد.",
            "max_value": "درصد تخفیف نمی‌تواند از ۱۰۰ بیشتر باشد.",
            "invalid": "درصد تخفیف معتبر نیست.",
        },
    )

    class Meta:
        model = SalesInvoice
        fields = ("customer", "invoice_date", "discount_amount", "credit_due_date")
        widgets = {
            # `form="sale-form"` because new.html renders this field (and
            # its "+ مشتری جدید" disclosure) outside the <form> tag on
            # purpose: the disclosure is itself a <form> (see
            # partners/_quick_party_form.html), and HTML forbids a <form>
            # nested inside another -- the browser silently truncates the
            # outer form right there, and every field after it (all the
            # item/payment rows, the submit button) stops belonging to any
            # form at all. The `form` attribute reattaches this one field
            # to #sale-form despite living outside its DOM subtree.
            "customer": forms.Select(attrs={"class": "field__control", "form": "sale-form"}),
        }
        error_messages = {
            "customer": {"required": "انتخاب مشتری الزامی است."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("name")
        self.fields["customer"].empty_label = "— انتخاب مشتری —"

    def clean_discount_mode(self):
        return self.cleaned_data.get("discount_mode") or DISCOUNT_MODE_AMOUNT

    def clean_discount_amount(self):
        # required=False on an IntegerField cleans a blank box to None, but
        # the column is NOT NULL with no ORM-level default substitution on
        # an explicit None (Model.save() only applies `default=0` when the
        # field was never set at all) -- an empty discount box is "no
        # discount", 0, not "no value" (caught by actually submitting the
        # form with the field left blank, the normal case for most sales).
        return self.cleaned_data.get("discount_amount") or 0

    @property
    def is_percent_discount(self):
        return self.cleaned_data.get("discount_mode") == DISCOUNT_MODE_PERCENT


class SaleItemForm(CartonPackItemFormMixin, SelectedProductMixin, forms.ModelForm):
    """
    One invoice line, typed as cartons + loose packs in a single row (D-081).

    `product` is a hidden input: the visible picker is the JS-driven search
    box in _item_row.html. A blank price is filled from the product (the
    pack price for packs, the carton price for cartons); a typed one wins.
    """

    @cached_property
    def selected_prices(self):
        """(pack price, carton price) of the product this row already holds, so a
        re-rendered row keeps both for the live total."""
        product = self.selected_product
        if product is None:
            return None
        return product.pack_price, product.carton_price

    class Meta:
        model = SaleItem
        fields = ("product", "cartons", "unit_price", "carton_price")
        widgets = {"product": forms.HiddenInput()}
        error_messages = {
            "product": {"required": "یک کالا از فهرست جست‌وجو انتخاب کنید."},
        }


class BaseSaleItemFormSet(forms.BaseFormSet):
    """Catches the same product picked twice before the DB's unique
    constraint (`unique_product_per_sales_invoice`) would, and any line
    above the stock on hand (D-052; `confirm_sale` re-checks under lock)."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        lines = {}
        for form in self.forms:
            if not form.cleaned_data:
                continue
            product = form.cleaned_data.get("product")
            if product is None:
                continue
            if product.pk in lines:
                raise forms.ValidationError(
                    "کالای «%(name)s» بیش از یک بار در فاکتور انتخاب شده است.",
                    params={"name": product.name},
                )
            lines[product.pk] = (product, form.cleaned_data["quantity"])
        stock = get_stock_map(list(lines))
        for pk, (product, quantity) in lines.items():
            available = stock.get(pk, 0)
            if quantity > available:
                raise forms.ValidationError(
                    "موجودی «%(name)s» کافی نیست (موجودی %(available)s، درخواست %(qty)s). "
                    "ابتدا خرید را ثبت کنید.",
                    params={
                        "name": product.name,
                        "available": units_phrase(*split_units(available, product.pack_per_carton)),
                        "qty": units_phrase(*split_units(quantity, product.pack_per_carton)),
                    },
                )


SaleItemFormSet = forms.formset_factory(SaleItemForm, formset=BaseSaleItemFormSet, extra=1)


class SalesPaymentEntryForm(PaymentEntryFormMixin, forms.ModelForm):
    """
    One planned payment row (card reader / bank transfer / cheque, D-069),
    same shape as the admin inline it replaces -- cheque number/issuer/bank/due
    date stay optional (Sina, 2026-09-24: finished later on the Cheques page).
    The method list, the account-vs-method check and the dropping of cheque
    fields for other methods live in `PaymentEntryFormMixin`.
    """

    due_date = JalaliDateField(required=False, label="تاریخ سررسید چک")
    # BigIntegerField has no built-in positivity; only the DB CheckConstraint
    # (`sales_payment_entry_amount_positive`) enforces amount > 0, so this
    # is declared explicitly with min_value, same as RecordPaymentForm.amount.
    amount = forms.IntegerField(
        min_value=1,
        label="مبلغ (تومان)",
        widget=NumericInput(
            attrs={"class": "field__control payment-row__amount", "dir": "ltr", "inputmode": "numeric"}
        ),
        error_messages={"required": "مبلغ الزامی است.", "min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )

    class Meta:
        model = SalesPaymentEntry
        fields = ("method", "amount", "bank_account", "cheque_number", "bank_name", "issuer", "due_date")
        widgets = {
            "cheque_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
            "bank_name": forms.TextInput(attrs={"class": "field__control"}),
            "issuer": forms.TextInput(attrs={"class": "field__control"}),
        }


SalesPaymentEntryFormSet = forms.formset_factory(SalesPaymentEntryForm, extra=0)

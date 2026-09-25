# path: apps/sales/forms.py

"""
The one-shot new-sale form (REDESIGN_VISION 4.1, MASTER_PROMPT Phase C).

Three pieces submitted together: the invoice itself, a formset of item
rows, and a formset of payment-entry rows. None of them touch the
database directly -- the view builds unsaved instances from each,
saves them as a draft inside one `transaction.atomic()`, then calls
`confirm_sale` in the same transaction, so a rejection (empty items,
discount over subtotal, payment rows over total, oversell by a non-
superuser) rolls back everything, not just the confirm step. That is
what "one-shot" means here: never a saved, unconfirmed invoice left
behind by a failed submission.

Field-level validation stays exactly what SaleItem/SalesPaymentEntry
already validate as ModelForms (unit_price falls back to the product's
default via SaleItem.clean_fields, cheque fields stay optional -- same
decision as apps/sales/admin.py's inlines). Cross-row rules (no items,
discount too big, payment rows exceeding the total) are `confirm_sale`'s
job already; duplicating them here would be a second source of truth.
"""

from django import forms

from apps.partners.models import Customer
from apps.payments.models import BankAccount
from apps.products.models import Product
from apps.shared.forms import JalaliDateField

from .models import SaleItem, SalesInvoice, SalesPaymentEntry

TOMAN_HINT = "به ریال وارد شود. (۱ تومان = ۱۰ ریال)"


class SalesFilterForm(forms.Form):
    """
    The list page's structured filters, deliberately separate from the
    free-text search box (REDESIGN_VISION vision doc §26: never conflate
    "find this invoice" with "narrow this list"). The date range itself
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
    amount_min = forms.IntegerField(required=False, label="حداقل مبلغ (ریال)", min_value=0)
    amount_max = forms.IntegerField(required=False, label="حداکثر مبلغ (ریال)", min_value=0)

    def clean(self):
        cleaned = super().clean()
        lo, hi = cleaned.get("amount_min"), cleaned.get("amount_max")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("amount_max", "حداکثر مبلغ نمی‌تواند از حداقل کمتر باشد.")
        return cleaned


class SaleInvoiceForm(forms.ModelForm):
    """Header fields: who, when, how much discount."""

    invoice_date = JalaliDateField(label="تاریخ فاکتور")
    # BigIntegerField has no built-in non-negativity; only the DB
    # CheckConstraint (`sales_invoice_discount_non_negative`) enforces
    # discount_amount >= 0 -- declared explicitly so a negative discount
    # never reaches the DB (confirm_sale only checks discount <= subtotal).
    discount_amount = forms.IntegerField(
        required=False,
        min_value=0,
        label="تخفیف (ریال)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "تخفیف نمی‌تواند منفی باشد."},
    )

    class Meta:
        model = SalesInvoice
        fields = ("customer", "invoice_date", "discount_amount")
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
        help_texts = {"discount_amount": TOMAN_HINT}
        error_messages = {
            "customer": {"required": "انتخاب مشتری الزامی است."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("name")
        self.fields["customer"].empty_label = "— انتخاب مشتری —"

    def clean_discount_amount(self):
        # required=False on an IntegerField cleans a blank box to None, but
        # the column is NOT NULL with no ORM-level default substitution on
        # an explicit None (Model.save() only applies `default=0` when the
        # field was never set at all) -- an empty discount box is "no
        # discount", 0, not "no value" (caught by actually submitting the
        # form with the field left blank, the normal case for most sales).
        return self.cleaned_data.get("discount_amount") or 0


class SaleItemForm(forms.ModelForm):
    """
    One invoice line.

    `product` is a hidden input: the visible picker is the JS-driven
    search box in _item_row.html, not a plain <select> of every product
    (REDESIGN_VISION wants live stock in the label, which a <select>
    cannot show per option without pre-rendering every product's stock
    on every page load).
    """

    # Declared explicitly, not left to ModelForm's auto-generation: the
    # model's CheckConstraints say quantity > 0 and unit_price >= 0, and
    # `min_value` only becomes a real validator when passed to the field's
    # own __init__ -- setting it as a post-hoc attribute does nothing
    # (lesson already learned once for a different field, see 66d4acc).
    quantity = forms.IntegerField(
        min_value=1,
        label="مقدار",
        widget=forms.NumberInput(attrs={"class": "field__control item-row__qty", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"required": "مقدار الزامی است.", "min_value": "مقدار باید بزرگ‌تر از صفر باشد."},
    )
    unit_price = forms.IntegerField(
        required=False,
        min_value=0,
        label="قیمت واحد (ریال)",
        widget=forms.NumberInput(attrs={"class": "field__control item-row__price", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "قیمت نمی‌تواند منفی باشد."},
    )

    class Meta:
        model = SaleItem
        fields = ("product", "quantity", "unit_price")
        widgets = {"product": forms.HiddenInput()}
        error_messages = {
            "product": {"required": "یک کالا از فهرست جست‌وجو انتخاب کنید."},
        }


class BaseSaleItemFormSet(forms.BaseFormSet):
    """Catches the same product picked twice before the DB's unique
    constraint (`unique_product_per_sales_invoice`) would."""

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


SaleItemFormSet = forms.formset_factory(SaleItemForm, formset=BaseSaleItemFormSet, extra=1)


class SalesPaymentEntryForm(forms.ModelForm):
    """
    One planned payment row (cash/card/bank/cheque), same shape as the
    admin inline it replaces -- cheque number/bank/due date stay optional
    (Sina, 2026-09-24: finished later on the Cheques page, see D-014-style
    note on apps/sales/admin.SalesPaymentEntryForm).
    """

    due_date = JalaliDateField(required=False, label="تاریخ سررسید چک")
    # BigIntegerField has no built-in positivity; only the DB CheckConstraint
    # (`sales_payment_entry_amount_positive`) enforces amount > 0, so this
    # is declared explicitly with min_value, same as RecordPaymentForm.amount.
    #
    # `method` is declared too: it has no model-level `default`, so Django's
    # ModelForm machinery inserts an English "---------"-style blank choice
    # for it even though the field is required (Field.get_choices() adds a
    # blank entry whenever a required choices-field has neither a default
    # nor an initial). Cash is overwhelmingly the common case, so it is the
    # initial value and the blank choice never appears at all.
    method = forms.ChoiceField(
        choices=SalesPaymentEntry.Method.choices,
        initial=SalesPaymentEntry.Method.CASH,
        label="روش",
        widget=forms.Select(attrs={"class": "field__control"}),
    )
    amount = forms.IntegerField(
        min_value=1,
        label="مبلغ (ریال)",
        widget=forms.NumberInput(
            attrs={"class": "field__control payment-row__amount", "dir": "ltr", "inputmode": "numeric"}
        ),
        error_messages={"required": "مبلغ الزامی است.", "min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )

    class Meta:
        model = SalesPaymentEntry
        fields = ("method", "amount", "bank_account", "cheque_number", "bank_name", "due_date")
        widgets = {
            "bank_account": forms.Select(attrs={"class": "field__control"}),
            "cheque_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
            "bank_name": forms.TextInput(attrs={"class": "field__control"}),
        }
        help_texts = {"amount": TOMAN_HINT}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bank_account"].queryset = BankAccount.objects.filter(is_active=True)
        self.fields["bank_account"].empty_label = "نقدی"
        self.fields["bank_account"].required = False
        self.fields["cheque_number"].required = False
        self.fields["bank_name"].required = False


SalesPaymentEntryFormSet = forms.formset_factory(SalesPaymentEntryForm, extra=0)

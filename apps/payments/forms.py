# path: apps/payments/forms.py

"""
"ثبت پرداخت" — one form, four entry points.

REDESIGN_VISION 8 item 2 called this out explicitly: the button appears on
Receivables, Payables, Customer detail and Supplier detail, and four
implementations of it would drift apart on what an allocation means. So it
is written once, here, and each page renders the same partial.

The form only validates and shapes input. Money is moved by
`apps/payments/services.py` inside `transaction.atomic()`, never by a form
or a view — the rule that used to say "Admin never writes" (D-035).
"""

from django import forms

from apps.shared.forms import JalaliDateField

from .models import BankAccount, Cheque, Payment


class RecordPaymentForm(forms.Form):
    """
    Money received from a customer, or paid to a supplier.

    The party is fixed by whichever page opened the form (a Receivables row
    is already about one customer), so it is passed to the constructor
    rather than being a field the user could change to someone else.

    Allocation is optional. A payment may sit unallocated — a prepayment
    taken before any invoice is picked — and `Payment.customer` keeps it
    traceable to a person regardless (D-038). The invoices a user may
    allocate to are narrowed to that party's own open ones, so nothing on
    this form can reach anybody else's invoice.
    """

    amount = forms.IntegerField(
        min_value=1,
        label="مبلغ (ریال)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )
    payment_date = JalaliDateField(label="تاریخ")
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.none(),
        required=False,
        label="حساب بانکی",
        empty_label="نقدی",  # blank means cash, same rule as the model (2.6)
        widget=forms.Select(attrs={"class": "field__control"}),
    )
    note = forms.CharField(
        required=False,
        label="توضیح",
        widget=forms.TextInput(attrs={"class": "field__control"}),
    )
    invoices = forms.MultipleChoiceField(
        required=False,
        label="تخصیص به فاکتورها",
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, customer=None, supplier=None, open_invoices=(), **kwargs):
        super().__init__(*args, **kwargs)
        if bool(customer) == bool(supplier):
            # A programmer error, not a user one: the page that renders this
            # form always knows which side it is on.
            raise ValueError("Exactly one of customer/supplier is required.")

        self.customer = customer
        self.supplier = supplier
        self.open_invoices = list(open_invoices)

        self.fields["bank_account"].queryset = BankAccount.objects.filter(is_active=True)
        self.fields["invoices"].choices = [
            (str(invoice.pk), invoice) for invoice in self.open_invoices
        ]
        self.fields["payment_date"].initial = None

    @property
    def direction(self):
        """Money from a customer comes in; money to a supplier goes out."""
        return Payment.Direction.IN if self.customer else Payment.Direction.OUT

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get("amount")
        chosen = cleaned.get("invoices") or []

        if amount and chosen:
            # Allocating more than the payment itself is caught again in
            # allocate_payment; catching it here means the user sees which
            # field is wrong instead of a rejected submission.
            by_id = {str(invoice.pk): invoice for invoice in self.open_invoices}
            outstanding = sum(by_id[pk].outstanding for pk in chosen if pk in by_id)
            if amount > outstanding:
                self.add_error(
                    "amount",
                    "مبلغ پرداخت از باقیماندهٔ فاکتورهای انتخاب‌شده بیشتر است.",
                )
        return cleaned


class ChequeFilterForm(forms.Form):
    """Cheques list filters (REDESIGN_VISION 4.4): status, direction, and
    a due-date range -- deliberately separate fields, not one date-range
    picker, since a cheque's due date has nothing to do with when it was
    entered (the shared DateRangeForm's presets don't apply here)."""

    status = forms.ChoiceField(
        required=False, label="وضعیت", choices=[("", "همه"), *Cheque.Status.choices],
    )
    direction = forms.ChoiceField(
        required=False, label="جهت", choices=[("", "همه"), *Payment.Direction.choices],
    )
    due_start = JalaliDateField(required=False, label="سررسید از")
    due_end = JalaliDateField(required=False, label="سررسید تا")

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("due_start"), cleaned.get("due_end")
        if start and end and start > end:
            self.add_error("due_end", "تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")
        return cleaned


class ChequeCompletionForm(forms.ModelForm):
    """"تکمیل مشخصات" for a cheque entered incomplete from an invoice's
    payment rows (4.3b) -- the same fields `ChequeAdmin` leaves editable
    while still PENDING, on a page of its own here."""

    due_date = JalaliDateField(required=False, label="تاریخ سررسید")

    class Meta:
        model = Cheque
        fields = ("cheque_number", "bank_name", "due_date", "bank_account")
        widgets = {
            "cheque_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
            "bank_name": forms.TextInput(attrs={"class": "field__control"}),
            "bank_account": forms.Select(attrs={"class": "field__control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bank_account"].queryset = BankAccount.objects.filter(is_active=True)
        self.fields["bank_account"].empty_label = "— نامشخص —"
        self.fields["bank_account"].required = False

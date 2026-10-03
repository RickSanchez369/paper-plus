# path: apps/payments/forms.py

"""
"ثبت پرداخت" — one form, four entry points.

The button appears on Receivables, Payables, Customer detail and Supplier
detail, and four implementations of it would drift apart on what an
allocation means. So it is written once, here, and each page renders the
same partial.

The form only validates and shapes input. Money is moved by
`apps/payments/services.py` inside `transaction.atomic()`, never by a form
or a view — the rule that used to say "Admin never writes" (D-035).
"""

from django import forms

from apps.shared.forms import JalaliDateField

from .models import BankAccount, Cheque, Expense, Payment, RecurringExpense


class AccountSelect(forms.Select):
    """
    A <select> whose options carry `data-type` (pos/current), so the invoice
    form's script can offer a card reader for "کارت‌خوان" and a current
    account for "حواله بانکی" without a round trip (D-067, D-069).
    """

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-type"] = instance.account_type
        return option


class AccountChoiceField(forms.ModelChoiceField):
    """
    One active bank account of a given type (or of any type when
    `account_type` is None). Cash does not exist as a choice (D-069): the
    blank option is only a prompt, and a required field refuses it.
    """

    def __init__(self, account_type=None, **kwargs):
        queryset = BankAccount.objects.filter(is_active=True).order_by("name")
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        kwargs.setdefault("widget", AccountSelect(attrs={"class": "field__control"}))
        kwargs.setdefault("empty_label", "— انتخاب حساب —")
        kwargs.setdefault("error_messages", {
            "required": "حساب بانکی را انتخاب کنید.",
            "invalid_choice": "این حساب بانکی معتبر یا فعال نیست یا از نوع مناسب نیست.",
        })
        super().__init__(queryset=queryset, **kwargs)


def current_account_field(**kwargs):
    """A current account: where transfers and cheques land and where payments leave from."""
    return AccountChoiceField(account_type=BankAccount.AccountType.CURRENT, **kwargs)


def pos_account_field(**kwargs):
    """A card-reader account: where card payments land."""
    return AccountChoiceField(account_type=BankAccount.AccountType.POS, **kwargs)


PAYMENT_MODE_FULL = "full"
PAYMENT_MODE_SPLIT = "split"

# The ways a payment row can be made. Cash is gone (D-069).
ENTRY_METHOD_CHOICES = (
    ("card", "کارت‌خوان"),
    ("bank_transfer", "حواله بانکی"),
    ("cheque", "چک"),
)


class InvoicePaymentFields(forms.Form):
    """
    The payment half of the sales/purchase invoice forms (D-069), written
    once so both invoices behave the same.

    Full settlement ("تسویهٔ کامل"): the whole total was paid by card reader,
    by bank transfer, or by both at once (each into its own account, with its
    own amount). Split mode ("تفکیکی"): the payment rows, and whatever they
    leave unpaid is credit (نسیه), which then needs a due date.

    These fields only collect input. The amounts are settled against the
    real total by `resolve_full_payment_amounts` once the lines exist.
    """

    payment_mode = forms.ChoiceField(
        label="نحوهٔ تسویه",
        choices=(
            (PAYMENT_MODE_FULL, "تسویهٔ کامل (کل مبلغ پرداخت شد)"),
            (PAYMENT_MODE_SPLIT, "تفکیکی / چک / نسیه"),
        ),
        initial=PAYMENT_MODE_FULL,
        widget=forms.RadioSelect,
    )
    pos_account = pos_account_field(required=False, label="حساب کارت‌خوان", empty_label="— بدون کارت‌خوان —")
    pos_amount = forms.IntegerField(
        required=False,
        min_value=1,
        label="مبلغ کارت‌خوان (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )
    transfer_account = current_account_field(required=False, label="حساب جاری (حواله بانکی)", empty_label="— بدون حواله —")
    transfer_amount = forms.IntegerField(
        required=False,
        min_value=1,
        label="مبلغ حواله بانکی (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )
    credit_due_date = JalaliDateField(required=False, label="تاریخ سررسید نسیه")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("payment_mode") == PAYMENT_MODE_FULL:
            if not cleaned.get("pos_account") and not cleaned.get("transfer_account"):
                self.add_error(None, "حداقل یک روش پرداخت (کارت‌خوان یا حواله بانکی) را انتخاب کنید.")
            for account, amount in (("pos_account", "pos_amount"), ("transfer_account", "transfer_amount")):
                if cleaned.get(amount) and not cleaned.get(account):
                    self.add_error(account, "برای این مبلغ حساب را انتخاب کنید.")
        return cleaned

    @property
    def is_full_payment(self):
        return self.cleaned_data.get("payment_mode") == PAYMENT_MODE_FULL

    @property
    def full_payment_parts(self):
        """``[(method, account, amount_or_None)]`` for the methods picked, for `resolve_full_payment_amounts`."""
        data = self.cleaned_data
        parts = []
        if data.get("pos_account"):
            parts.append(("card", data["pos_account"], data.get("pos_amount")))
        if data.get("transfer_account"):
            parts.append(("bank_transfer", data["transfer_account"], data.get("transfer_amount")))
        return parts


class PaymentEntryFormMixin:
    """
    Shared behaviour of the sales/purchase payment-row forms (D-069): the
    method list without cash, the account select tagged by type, the account
    checked against the method, and cheque-only fields dropped for other
    methods. Put it before `forms.ModelForm` in the bases. A form that pays
    OUT sets `entry_methods` without "card" (a card reader only receives).
    """

    entry_methods = ENTRY_METHOD_CHOICES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["method"] = forms.ChoiceField(
            choices=self.entry_methods,
            initial=self.entry_methods[0][0],
            label="روش",
            widget=forms.Select(attrs={"class": "field__control"}),
        )
        self.fields["bank_account"] = AccountChoiceField(required=False, label="حساب بانکی", empty_label="— انتخاب حساب —")
        for name in ("cheque_number", "bank_name", "issuer"):
            self.fields[name].required = False

    def clean(self):
        from django.core.exceptions import ValidationError

        from .services import validate_entry_account

        cleaned = super().clean()
        method = cleaned.get("method")
        if method:
            try:
                validate_entry_account(method, cleaned.get("bank_account"))
            except ValidationError as exc:
                self.add_error("bank_account", exc)
        # Only a cheque has a number, an issuer, a bank and a due date; the
        # page hides them for other methods, so whatever a switched-away row
        # still holds must not be saved.
        if method != "cheque":
            cleaned["cheque_number"] = ""
            cleaned["bank_name"] = ""
            cleaned["issuer"] = ""
            cleaned["due_date"] = None
        return cleaned


class BankAccountForm(forms.ModelForm):
    """
    Add or edit an account from the Bank Accounts page itself -- before
    this, an account could only be created in /admin/, so every expense
    or payment form offered nothing but cash on a fresh install.
    Deactivation stays an admin task: an account with a ledger behind it
    is never something to switch off by accident from a list page.
    """

    class Meta:
        model = BankAccount
        fields = ("name", "account_type", "owner", "account_number")
        widgets = {
            "name": forms.TextInput(attrs={"class": "field__control", "autocomplete": "off"}),
            "account_type": forms.Select(attrs={"class": "field__control"}),
            "owner": forms.TextInput(attrs={"class": "field__control", "autocomplete": "off"}),
            "account_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr", "autocomplete": "off"}),
        }
        error_messages = {
            "name": {"required": "نام حساب الزامی است."},
            "account_number": {
                "required": "شماره حساب الزامی است.",
                "unique": "حساب دیگری با همین شماره ثبت شده است.",
            },
        }

    def clean_account_number(self):
        # Stray spaces would let the same number slip past the unique
        # constraint as a "different" account.
        return (self.cleaned_data.get("account_number") or "").strip()


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
        label="مبلغ (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )
    payment_date = JalaliDateField(label="تاریخ")
    # Never cash (D-069). Money in may land in a card reader or a current
    # account; money out only leaves a current account (narrowed in __init__).
    bank_account = AccountChoiceField(label="حساب بانکی")
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
        # Several of these forms share one page (a row per debtor, or beside
        # the customer's own edit form): ids must differ per party or every
        # <label for> points at the first form's input.
        party = customer or supplier
        if party is not None:
            kwargs.setdefault("auto_id", f"pay_{party.pk.hex[:8]}_%s")
        super().__init__(*args, **kwargs)
        if bool(customer) == bool(supplier):
            # A programmer error, not a user one: the page that renders this
            # form always knows which side it is on.
            raise ValueError("Exactly one of customer/supplier is required.")

        self.customer = customer
        self.supplier = supplier
        self.open_invoices = list(open_invoices)

        accounts = BankAccount.objects.filter(is_active=True).order_by("name")
        if supplier is not None:
            accounts = accounts.filter(account_type=BankAccount.AccountType.CURRENT)
        self.fields["bank_account"].queryset = accounts
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


class PayInvoiceForm(forms.Form):
    """
    Settle (all or part of) one invoice's credit part from the Receivables /
    Payables page (D-071). The invoice is fixed by the row, so it is passed to
    the constructor; the amount may not exceed the credit still open on it
    (cheques pending against the invoice are settled by clearing them).
    """

    amount = forms.IntegerField(
        min_value=1,
        label="مبلغ (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "مبلغ باید بزرگ‌تر از صفر باشد.", "required": "مبلغ الزامی است."},
    )
    payment_date = JalaliDateField(label="تاریخ")
    bank_account = AccountChoiceField(label="حساب بانکی")
    note = forms.CharField(required=False, label="توضیح", widget=forms.TextInput(attrs={"class": "field__control"}))

    def __init__(self, *args, invoice=None, credit_amount=0, paying_supplier=False, **kwargs):
        if invoice is not None:
            kwargs.setdefault("auto_id", f"payinv_{invoice.pk.hex[:8]}_%s")
        super().__init__(*args, **kwargs)
        self.invoice = invoice
        self.credit_amount = credit_amount
        accounts = BankAccount.objects.filter(is_active=True).order_by("name")
        if paying_supplier:
            accounts = accounts.filter(account_type=BankAccount.AccountType.CURRENT)
        self.fields["bank_account"].queryset = accounts
        self.fields["amount"].initial = credit_amount

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount > self.credit_amount:
            raise forms.ValidationError("مبلغ از باقیماندهٔ نسیهٔ این فاکتور بیشتر است.")
        return amount


class ChequeFilterForm(forms.Form):
    """Cheques list filters: status, direction, and
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


class ClearChequeForm(forms.Form):
    """"وصول چک": which account the money lands in / leaves from. A real
    answer is required (an account, or cash picked on purpose), pre-selected
    with the cheque's own account when it has one (D-045)."""

    bank_account = current_account_field(label="وصول در حساب")


class ChequeCompletionForm(forms.ModelForm):
    """"تکمیل مشخصات" for a cheque entered incomplete from an invoice's
    payment rows (4.3b) -- the same fields `ChequeAdmin` leaves editable
    while still PENDING, on a page of its own here."""

    due_date = JalaliDateField(required=False, label="تاریخ سررسید")

    class Meta:
        model = Cheque
        fields = ("cheque_number", "bank_name", "issuer", "due_date", "bank_account")
        widgets = {
            "cheque_number": forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
            "bank_name": forms.TextInput(attrs={"class": "field__control"}),
            "issuer": forms.TextInput(attrs={"class": "field__control"}),
            "bank_account": forms.Select(attrs={"class": "field__control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bank_account"].queryset = BankAccount.objects.filter(is_active=True)
        self.fields["bank_account"].empty_label = "— نامشخص —"
        self.fields["bank_account"].required = False


class ExpenseFilterForm(forms.Form):
    """
    Expenses list filters: free-text search over
    reason/note, bank account, and an amount range -- the date range
    itself is the shared `DateRangeForm`, rendered alongside this one,
    same split as Sales/Purchasing's own list filters.
    """

    q = forms.CharField(required=False, label="جست‌وجو")
    bank_account = forms.ModelChoiceField(
        required=False,
        label="حساب بانکی",
        queryset=BankAccount.objects.filter(is_active=True),
        empty_label="— همهٔ حساب‌ها —",
    )
    amount_min = forms.IntegerField(required=False, label="حداقل مبلغ (تومان)", min_value=0)
    amount_max = forms.IntegerField(required=False, label="حداکثر مبلغ (تومان)", min_value=0)
    status = forms.ChoiceField(
        required=False, label="وضعیت پرداخت",
        choices=[("", "همه"), ("owed", "پرداخت‌نشده (نسیه / چک در انتظار)"), ("paid", "پرداخت‌شده")],
    )

    def clean(self):
        cleaned = super().clean()
        lo, hi = cleaned.get("amount_min"), cleaned.get("amount_max")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("amount_max", "حداکثر مبلغ نمی‌تواند از حداقل کمتر باشد.")
        return cleaned


class ExpenseForm(forms.ModelForm):
    """
    New-expense one-shot form (D-045, D-072): date, reason, amount and HOW it
    is paid -- by bank transfer from a current account, by cheque, or on
    credit (نسیه, paid later by its due date). The view passes the unsaved
    instance (and `build_cheque()` for a cheque) to `record_expense`, which
    books any money in the same transaction -- this form never touches money.

    `recurring` (hidden) ties the expense to a fixed cost it settles (D-073).
    """

    expense_date = JalaliDateField(label="تاریخ")
    amount = forms.IntegerField(
        min_value=1,
        label="مبلغ (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )
    payment_method = forms.ChoiceField(
        label="روش پرداخت",
        required=False,  # absent = a bank transfer, the original behaviour
        choices=Expense.PaymentMethod.choices,
        initial=Expense.PaymentMethod.TRANSFER,
        widget=forms.RadioSelect,
    )
    # Transfer: the account it leaves from. Cheque: the account it is drawn on, if known.
    bank_account = current_account_field(required=False, label="حساب جاری (پرداخت از / چک روی)")
    due_date = JalaliDateField(required=False, label="سررسید پرداخت نسیه")
    cheque_number = forms.CharField(
        required=False, label="شمارهٔ چک",
        widget=forms.TextInput(attrs={"class": "field__control", "dir": "ltr"}),
    )
    bank_name = forms.CharField(
        required=False, label="نام بانک", widget=forms.TextInput(attrs={"class": "field__control"}),
    )
    issuer = forms.CharField(
        required=False, label="صادرکنندهٔ چک", widget=forms.TextInput(attrs={"class": "field__control"}),
    )
    cheque_due_date = JalaliDateField(required=False, label="سررسید چک")
    recurring = forms.ModelChoiceField(
        queryset=RecurringExpense.objects.filter(is_active=True), required=False, widget=forms.HiddenInput,
    )

    class Meta:
        model = Expense
        fields = (
            "expense_date", "reason", "amount", "payment_method", "bank_account", "due_date",
            "recurring", "document", "note",
        )
        widgets = {
            "reason": forms.TextInput(attrs={"class": "field__control"}),
            "note": forms.Textarea(attrs={"class": "field__control", "rows": 2}),
        }

    def clean_payment_method(self):
        return self.cleaned_data.get("payment_method") or Expense.PaymentMethod.TRANSFER

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("payment_method")
        if method == Expense.PaymentMethod.TRANSFER:
            if not cleaned.get("bank_account"):
                self.add_error("bank_account", "حساب جاری پرداخت‌کننده را انتخاب کنید.")
            cleaned["due_date"] = None
        elif method == Expense.PaymentMethod.CREDIT:
            if not cleaned.get("due_date"):
                self.add_error("due_date", "تاریخ سررسید پرداخت را وارد کنید.")
            cleaned["bank_account"] = None
        elif method == Expense.PaymentMethod.CHEQUE:
            if not cleaned.get("cheque_due_date"):
                self.add_error("cheque_due_date", "تاریخ سررسید چک را وارد کنید.")
            cleaned["due_date"] = None
        return cleaned

    def build_cheque(self):
        """An unsaved Cheque with the typed cheque details, for a cheque expense (else None)."""
        data = self.cleaned_data
        if data.get("payment_method") != Expense.PaymentMethod.CHEQUE:
            return None
        return Cheque(
            cheque_number=data.get("cheque_number", ""),
            bank_name=data.get("bank_name", ""),
            issuer=data.get("issuer", ""),
            due_date=data.get("cheque_due_date"),
        )


class PayExpenseForm(forms.Form):
    """"پرداخت" for an expense that is still owed (a نسیه one when its date comes, or one whose cheque bounced)."""

    bank_account = current_account_field(label="پرداخت از حساب جاری")
    payment_date = JalaliDateField(label="تاریخ پرداخت")

    def __init__(self, *args, expense=None, **kwargs):
        if expense is not None:
            kwargs.setdefault("auto_id", f"payexp_{expense.pk.hex[:8]}_%s")
        super().__init__(*args, **kwargs)


class RecurringExpenseForm(forms.ModelForm):
    """Add or edit a fixed, repeating cost (D-073): what, how much, how often, when next, and how early to remind."""

    next_due_date = JalaliDateField(label="سررسید بعدی")
    amount = forms.IntegerField(
        min_value=1,
        label="مبلغ (تومان)",
        widget=forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "inputmode": "numeric"}),
        error_messages={"min_value": "مبلغ باید بزرگ‌تر از صفر باشد."},
    )

    class Meta:
        model = RecurringExpense
        fields = ("reason", "amount", "repeat_every", "repeat_unit", "next_due_date", "remind_days_before", "note")
        widgets = {
            "reason": forms.TextInput(attrs={"class": "field__control"}),
            "repeat_every": forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "min": 1}),
            "repeat_unit": forms.Select(attrs={"class": "field__control"}),
            "remind_days_before": forms.NumberInput(attrs={"class": "field__control", "dir": "ltr", "min": 0}),
            "note": forms.Textarea(attrs={"class": "field__control", "rows": 2}),
        }
        error_messages = {
            "reason": {"required": "عنوان هزینه الزامی است."},
        }

    def clean_repeat_every(self):
        value = self.cleaned_data["repeat_every"]
        if value < 1:
            raise forms.ValidationError("تعداد تکرار باید حداقل ۱ باشد.")
        return value

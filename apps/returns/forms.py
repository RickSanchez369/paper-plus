# path: apps/returns/forms.py

"""The header of a return (D-089). Line quantities are read per invoice line in the view."""

from django import forms

from apps.payments.forms import AccountChoiceField
from apps.payments.models import BankAccount
from apps.shared.forms import JalaliDateField

from .models import SettleMode


class ReturnForm(forms.Form):
    """Date, what to do with the surplus, the refund account (current accounts only), a note."""

    return_date = JalaliDateField(label="تاریخ مرجوعی")
    settle_mode = forms.ChoiceField(
        choices=SettleMode.choices,
        initial=SettleMode.CREDIT,
        widget=forms.RadioSelect,
        label="مازاد بر مانده فاکتور",
    )
    # A card reader only receives money (D-069): a refund goes through a current account.
    bank_account = AccountChoiceField(
        account_type=BankAccount.AccountType.CURRENT, required=False, label="حساب برگشت وجه",
    )
    note = forms.CharField(
        required=False, label="توضیح",
        widget=forms.TextInput(attrs={"class": "field__control", "placeholder": "مثلاً: کارتن آسیب‌دیده"}),
    )

    def __init__(self, *args, purchase=False, **kwargs):
        super().__init__(*args, **kwargs)
        if purchase:
            self.fields["settle_mode"].choices = [
                (SettleMode.CREDIT, "پیش‌پرداخت نزد تأمین‌کننده (کسر از خرید بعدی)"),
                (SettleMode.REFUND, "تأمین‌کننده وجه را به حساب ما برمی‌گرداند"),
            ]
            self.fields["bank_account"].label = "حساب دریافت وجه"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("settle_mode") == SettleMode.REFUND and not cleaned.get("bank_account"):
            # Only needed when there is a surplus; the service checks that, this catches the common case early.
            self.add_error("bank_account", "برای برگشت وجه، حساب بانکی را انتخاب کنید.")
        return cleaned

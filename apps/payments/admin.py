# path: apps/payments/admin.py

"""
Admin for BankAccount, Payment, PaymentAllocation and Cheque (ROADMAP 4.3, 4.4).

Payments, allocations and cheques are append-only, like InventoryMovement
(D-012): every add goes through a service (record_payment /
allocate_payment / record_cheque), never a raw model save; change and
delete are closed to everyone, superusers included -- a mistake means a
new, correcting entry, not an edit. A cheque's pending -> cleared/bounced
transition is a dedicated admin action, not a field edit, for the same
reason.
"""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from apps.shared.utils import format_toman

from .models import BankAccount, Cheque, Expense, Payment, PaymentAllocation
from .selectors import get_bank_account_balance
from .services import (
    allocate_payment,
    bounce_cheque,
    cancel_cheque,
    cancel_expense,
    clear_cheque,
    record_cheque,
    record_expense,
    record_payment,
)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "account_type", "owner", "account_number", "balance_display", "is_active")
    list_filter = ("account_type", "is_active")
    search_fields = ("name", "account_number")

    @admin.display(description="موجودی")
    def balance_display(self, obj):
        if obj is None or obj._state.adding:
            return "-"
        return format_toman(get_bank_account_balance(obj))


class PaymentForm(forms.ModelForm):
    """
    Turns the model's CHECK constraints into Persian field errors.

    Django validates CheckConstraints inside full_clean(), which runs before
    save_model() and therefore before record_payment()'s own checks -- so
    without this the user sees "Constraint ... is violated" instead of a
    sentence. Same fix as ChequeForm below, for the same reason.
    """

    class Meta:
        model = Payment
        fields = ("bank_account", "direction", "customer", "supplier", "amount", "payment_date", "note")

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("مبلغ پرداخت باید بزرگ‌تر از صفر باشد.")
        return amount

    def clean(self):
        cleaned = super().clean()
        direction = cleaned.get("direction")
        customer = cleaned.get("customer")
        supplier = cleaned.get("supplier")
        if customer and supplier:
            self.add_error("supplier", "یک پرداخت نمی‌تواند هم‌زمان مشتری و تأمین‌کننده داشته باشد.")
        elif customer and direction != Payment.Direction.IN:
            self.add_error("customer", "فقط دریافتی می‌تواند به مشتری نسبت داده شود.")
        elif supplier and direction != Payment.Direction.OUT:
            self.add_error("supplier", "فقط پرداختی می‌تواند به تأمین‌کننده نسبت داده شود.")
        return cleaned


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Add-only: every Payment is created through `record_payment` (see save_model)."""

    form = PaymentForm
    list_display = (
        "payment_date", "direction", "amount_display", "bank_account",
        "party_display", "allocation_display", "created_by",
    )
    list_filter = ("direction", "bank_account")
    search_fields = ("note", "customer__name", "supplier__name")
    autocomplete_fields = ("bank_account", "customer", "supplier")
    list_select_related = ("bank_account", "customer", "supplier", "created_by")
    date_hierarchy = "payment_date"
    ordering = ("-payment_date", "-created_at")
    readonly_fields = ("created_by", "id", "created_at", "updated_at")

    @admin.display(description="مبلغ")
    def amount_display(self, obj):
        if obj is None:
            return "-"
        return format_toman(obj.amount)

    @admin.display(description="طرف حساب")
    def party_display(self, obj):
        # Blank for an expense's payment, and for anything not yet attributed.
        if obj is None:
            return "-"
        return obj.party or "-"

    @admin.display(description="تخصیص‌یافته / مانده")
    def allocation_display(self, obj):
        if obj is None or obj._state.adding:
            return "-"
        return f"{format_toman(obj.allocated_amount)} / {format_toman(obj.unallocated_amount)}"

    def save_model(self, request, obj, form, change):
        record_payment(obj, request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentAllocationForm(forms.ModelForm):
    """Persian errors for the amount and exactly-one-invoice CHECKs (see PaymentForm)."""

    class Meta:
        model = PaymentAllocation
        fields = ("payment", "sales_invoice", "purchase_invoice", "amount")

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("مبلغ تخصیص باید بزرگ‌تر از صفر باشد.")
        return amount

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get("sales_invoice")) == bool(cleaned.get("purchase_invoice")):
            self.add_error(
                "sales_invoice",
                "دقیقاً یکی از فاکتور فروش یا خرید باید انتخاب شود.",
            )
        return cleaned


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    """Add-only: every allocation is created through `allocate_payment` (see save_model)."""

    form = PaymentAllocationForm
    list_display = ("payment", "sales_invoice", "purchase_invoice", "amount_display")
    autocomplete_fields = ("payment", "sales_invoice", "purchase_invoice")
    list_select_related = ("payment", "sales_invoice", "purchase_invoice")

    @admin.display(description="مبلغ")
    def amount_display(self, obj):
        if obj is None:
            return "-"
        return format_toman(obj.amount)

    def save_model(self, request, obj, form, change):
        allocate_payment(obj, request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ChequeForm(forms.ModelForm):
    """
    Shows a friendly Persian error for the direction/party (or
    direction/invoice) mismatch instead of Django's generic "Constraint
    ... is violated" (Django 4.1+ validates CheckConstraints as part of
    full_clean(), before save_model() -- and therefore before
    record_cheque()'s own check -- ever runs).

    sales_invoice/purchase_invoice are editable here (unlike most other
    fields on a saved Cheque, see ChequeAdmin.has_change_permission): a
    cheque entered incomplete from an invoice's payment rows (4.3b) can be
    attached to, or corrected to, an invoice later, as long as it is still
    PENDING.
    """

    class Meta:
        model = Cheque
        fields = (
            "direction", "customer", "supplier", "bank_account",
            "cheque_number", "bank_name", "issuer", "due_date", "amount",
            "sales_invoice", "purchase_invoice", "note",
        )

    def clean(self):
        cleaned = super().clean()
        direction = cleaned.get("direction")
        customer = cleaned.get("customer")
        supplier = cleaned.get("supplier")
        sales_invoice = cleaned.get("sales_invoice")
        purchase_invoice = cleaned.get("purchase_invoice")
        if direction == "in" and (not customer or supplier):
            self.add_error("customer", "چک دریافتی باید دقیقاً یک مشتری داشته باشد، بدون تأمین‌کننده.")
        elif direction == "out" and (not supplier or customer):
            self.add_error("supplier", "چک پرداختی باید دقیقاً یک تأمین‌کننده داشته باشد، بدون مشتری.")
        if sales_invoice and purchase_invoice:
            self.add_error("purchase_invoice", "چک نمی‌تواند هم‌زمان به فاکتور فروش و خرید وصل باشد.")
        elif sales_invoice and direction != "in":
            self.add_error("sales_invoice", "فقط چک دریافتی («جهت: دریافت») می‌تواند به فاکتور فروش وصل شود.")
        elif purchase_invoice and direction != "out":
            self.add_error("purchase_invoice", "فقط چک پرداختی («جهت: پرداخت») می‌تواند به فاکتور خرید وصل شود.")
        return cleaned


@admin.register(Cheque)
class ChequeAdmin(admin.ModelAdmin):
    """
    A PENDING cheque is still editable (Sina, 2026-09-24: entering one
    incomplete from an invoice and finishing its details here later must
    work) -- `record_cheque` runs on add, a plain save on change. Once
    CLEARED or BOUNCED it locks, same as a confirmed invoice (D-014
    style): `status`/`payment` never come from a field edit, only from the
    two actions below.
    """

    form = ChequeForm
    list_display = (
        "cheque_number", "direction", "party_display", "amount_display",
        "due_date", "status", "invoice_display",
    )
    list_filter = ("direction", "status")
    search_fields = ("cheque_number", "customer__name", "supplier__name")
    autocomplete_fields = (
        "customer", "supplier", "bank_account",
        "sales_invoice", "purchase_invoice",
    )
    list_select_related = (
        "customer", "supplier", "bank_account", "payment",
        "sales_invoice", "purchase_invoice",
    )
    date_hierarchy = "due_date"
    ordering = ("due_date",)
    readonly_fields = ("status", "payment", "id", "created_at", "updated_at")
    actions = ("mark_cleared", "mark_bounced", "mark_cancelled")

    @admin.display(description="طرف حساب")
    def party_display(self, obj):
        if obj is None:
            return "-"
        return obj.customer or obj.supplier

    @admin.display(description="فاکتور")
    def invoice_display(self, obj):
        # Set automatically when the cheque was entered on an invoice's
        # payment rows (4.3b); blank for a general, unattached cheque.
        if obj is None:
            return "-"
        invoice = obj.sales_invoice or obj.purchase_invoice
        return invoice.invoice_number or "-" if invoice else "-"

    @admin.display(description="مبلغ")
    def amount_display(self, obj):
        if obj is None:
            return "-"
        return format_toman(obj.amount)

    def save_model(self, request, obj, form, change):
        if change:
            # Only a still-PENDING cheque reaches here at all (see
            # has_change_permission); status/payment are readonly, so this
            # can only touch the descriptive fields.
            obj.save()
        else:
            record_cheque(obj, request.user)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status != Cheque.Status.PENDING:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="وصول چک‌های انتخاب‌شده")
    def mark_cleared(self, request, queryset):
        """One clear_cheque call per row; a rejected one does not affect the rest."""
        for cheque in queryset:
            try:
                clear_cheque(cheque, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"چک {cheque.cheque_number} وصول نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request, f"چک {cheque.cheque_number} وصول شد.", messages.SUCCESS,
                )

    @admin.action(description="لغو چک‌های انتخاب‌شده")
    def mark_cancelled(self, request, queryset):
        """One cancel_cheque call per row; a rejected one does not affect the rest."""
        for cheque in queryset:
            try:
                cancel_cheque(cheque, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"چک {cheque.cheque_number} لغو نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request, f"چک {cheque.cheque_number} لغو شد.", messages.WARNING,
                )

    @admin.action(description="برگشت خوردن چک‌های انتخاب‌شده")
    def mark_bounced(self, request, queryset):
        """One bounce_cheque call per row; a rejected one does not affect the rest."""
        for cheque in queryset:
            try:
                bounce_cheque(cheque, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"چک {cheque.cheque_number} ثبت برگشت نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request, f"چک {cheque.cheque_number} برگشت خورد.", messages.WARNING,
                )


class ExpenseForm(forms.ModelForm):
    """
    `payment` and the cancellation fields belong to the services, not a form.

    `clean_amount` keeps expense_amount_positive from surfacing as a raw
    constraint message, same reasoning as PaymentForm.
    """

    class Meta:
        model = Expense
        fields = (
            "expense_date", "amount", "reason",
            "bank_account", "document", "note",
        )

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("مبلغ هزینه باید بزرگ‌تر از صفر باشد.")
        return amount


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """
    Add-only: every Expense is created through `record_expense`, which also
    books the Payment that moves the money (see save_model). Never edited or
    deleted -- a mistake is undone by the "لغو" action, which books the
    opposite entry.
    """

    form = ExpenseForm
    list_display = (
        "expense_date", "reason", "amount_display",
        "bank_account_display", "document_display", "status_display", "created_by",
    )
    list_filter = ("expense_date", "bank_account")
    search_fields = ("reason", "note")
    list_select_related = ("bank_account", "created_by")
    autocomplete_fields = ("bank_account",)
    date_hierarchy = "expense_date"
    ordering = ("-expense_date", "-created_at")
    readonly_fields = ("payment", "cancelled_at", "cancelled_by", "reversal_payment", "id", "created_at", "updated_at")
    actions = ("mark_cancelled",)

    @admin.display(description="مبلغ")
    def amount_display(self, obj):
        if obj is None:
            return "-"
        return format_toman(obj.amount)

    @admin.display(description="حساب پرداخت")
    def bank_account_display(self, obj):
        # No account means it came out of the till, same rule as Payment (2.6).
        if obj is None:
            return "-"
        return obj.bank_account or "نقدی"

    @admin.display(description="سند", boolean=True)
    def document_display(self, obj):
        return bool(obj and obj.document)

    @admin.display(description="وضعیت")
    def status_display(self, obj):
        if obj is None:
            return "-"
        return "لغو شده" if obj.is_cancelled else "ثبت شده"

    def save_model(self, request, obj, form, change):
        record_expense(obj, request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="لغو هزینه‌های انتخاب‌شده")
    def mark_cancelled(self, request, queryset):
        """One cancel_expense call per row; a rejected one does not affect the rest."""
        for expense in queryset:
            try:
                cancel_expense(expense, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"هزینهٔ «{expense.reason}» لغو نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request, f"هزینهٔ «{expense.reason}» لغو شد.", messages.WARNING,
                )

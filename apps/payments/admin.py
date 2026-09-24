# path: apps/payments/admin.py

"""
Admin for BankAccount, Payment and PaymentAllocation (ROADMAP 4.3).

Payments and their allocations are append-only, like InventoryMovement
(D-012): every add goes through a service (record_payment /
allocate_payment), never a raw model save; change and delete are closed
to everyone, superusers included -- a mistake means a new, correcting
entry, not an edit.
"""
from django import forms
from django.contrib import admin

from apps.shared.admin_mixins import BusinessScopedAdminMixin
from apps.shared.utils import format_rial

from .models import BankAccount, Payment, PaymentAllocation
from .selectors import get_bank_account_balance
from .services import allocate_payment, record_payment


@admin.register(BankAccount)
class BankAccountAdmin(BusinessScopedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "account_number", "business", "balance_display", "is_active")
    list_filter = ("business", "is_active")
    search_fields = ("name", "account_number")
    autocomplete_fields = ("business",)

    @admin.display(description="موجودی")
    def balance_display(self, obj):
        if obj is None or obj._state.adding:
            return "-"
        return format_rial(get_bank_account_balance(obj))


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("business", "bank_account", "direction", "amount", "payment_date", "note")


@admin.register(Payment)
class PaymentAdmin(BusinessScopedAdminMixin, admin.ModelAdmin):
    """Add-only: every Payment is created through `record_payment` (see save_model)."""

    form = PaymentForm
    list_display = (
        "payment_date", "direction", "amount_display", "bank_account",
        "allocation_display", "business", "created_by",
    )
    list_filter = ("business", "direction", "bank_account")
    search_fields = ("note", "business__name")
    autocomplete_fields = ("business", "bank_account")
    list_select_related = ("bank_account", "business", "created_by")
    date_hierarchy = "payment_date"
    ordering = ("-payment_date", "-created_at")
    readonly_fields = ("created_by", "id", "created_at", "updated_at")

    @admin.display(description="مبلغ")
    def amount_display(self, obj):
        if obj is None:
            return "-"
        return format_rial(obj.amount)

    @admin.display(description="تخصیص‌یافته / مانده")
    def allocation_display(self, obj):
        if obj is None or obj._state.adding:
            return "-"
        return f"{format_rial(obj.allocated_amount)} / {format_rial(obj.unallocated_amount)}"

    def save_model(self, request, obj, form, change):
        record_payment(obj, request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentAllocationForm(forms.ModelForm):
    class Meta:
        model = PaymentAllocation
        fields = ("payment", "sales_invoice", "purchase_invoice", "amount")


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(BusinessScopedAdminMixin, admin.ModelAdmin):
    """Add-only: every allocation is created through `allocate_payment` (see save_model)."""

    form = PaymentAllocationForm
    business_lookup = "payment__business"
    list_display = ("payment", "sales_invoice", "purchase_invoice", "amount_display")
    autocomplete_fields = ("payment", "sales_invoice", "purchase_invoice")
    list_select_related = ("payment", "sales_invoice", "purchase_invoice")

    @admin.display(description="مبلغ")
    def amount_display(self, obj):
        if obj is None:
            return "-"
        return format_rial(obj.amount)

    def save_model(self, request, obj, form, change):
        allocate_payment(obj, request.user)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

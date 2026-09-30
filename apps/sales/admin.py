#path: apps/sales/admin.py
"""
Admin for SalesInvoice and its items.

Mirror of apps/purchasing/admin.py, with one difference: confirm_sale
returns (invoice, shortages) and may drive stock negative (D-016).
Shortages are shown as a warning.

Rules enforced here:
- Stock is written only by confirm_sale; the admin never creates
  InventoryMovement rows and never sets status itself.
- A confirmed invoice is immutable (D-014): its page becomes view-only,
  its items are locked, and it cannot be deleted. Only drafts may be deleted.
"""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from simple_history.admin import SimpleHistoryAdmin

from apps.shared.utils import format_toman

from .models import SaleItem, SalesInvoice, SalesPaymentEntry
from .services import cancel_sale, confirm_sale

# Only a draft invoice may be edited or deleted.
DRAFT_STATUS = "draft"

# Inherited from BaseModel; visible for debugging, never editable.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")

def is_locked(invoice):
    """True when an invoice exists and is no longer a draft (D-014)."""
    return invoice is not None and invoice.status != DRAFT_STATUS


class SaleItemInline(admin.TabularInline):
    """
    Invoice lines, edited inside the invoice page.

    In the permission methods below, `obj` is the parent invoice,
    not the item.
    """

    model = SaleItem
    extra = 1
    fields = ("product", "quantity", "unit_price", "line_total")
    readonly_fields = ("line_total",)
    # Search box instead of a dropdown of every product.
    autocomplete_fields = ("product",)

    class Media:
        # Autofill unit_price from the product's default on selection (4.3b UX).
        js = ("sales/js/sale_item_autoprice.js",)

    @admin.display(description="جمع ردیف (تومان)")
    def line_total(self, obj):
        # Unsaved row: quantity and price may still be empty.
        if obj is None or obj._state.adding:
            return "-"
        return format_toman(obj.quantity * obj.unit_price)

    def has_add_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_delete_permission(request, obj)


class SalesPaymentEntryForm(forms.ModelForm):
    """
    The cheque fields (number/bank/due date) are optional here on purpose
    (Sina, 2026-09-24): a cheque row can be left incomplete at invoice time
    and finished later on the Cheques page, since a PENDING Cheque stays
    editable (see apps/payments/admin.ChequeAdmin.has_change_permission).
    """

    class Meta:
        model = SalesPaymentEntry
        fields = "__all__"


class SalesPaymentEntryInline(admin.TabularInline):
    """
    Planned payment lines, edited inside the invoice page while it is a
    draft; confirm_sale turns each row into a real Payment or Cheque (4.3b).
    """

    model = SalesPaymentEntry
    form = SalesPaymentEntryForm
    extra = 0
    fields = ("method", "amount", "bank_account", "cheque_number", "bank_name", "due_date")
    autocomplete_fields = ("bank_account",)

    class Media:
        # Pre-fills a new row's amount with the invoice's remaining total (4.3b UX).
        js = ("shared/js/payment_entry_autofill.js",)

    def has_add_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_delete_permission(request, obj)


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    """Sales invoices: draft entry in admin, confirmation via the service."""

    list_display = (
        "invoice_number", "customer", "invoice_date",
        "status", "total_display", "payment_status_display",
        "confirmed_at", "created_by",
    )
    list_filter = ("status", "invoice_date")
    search_fields = ("invoice_number", "customer__name")
    # One JOIN per related column instead of one query per row.
    list_select_related = ("customer", "created_by")
    autocomplete_fields = ("customer",)
    date_hierarchy = "invoice_date"
    # status/confirmed_at belong to the service; created_by to save_model.
    # invoice_number is assigned by confirm_sale at confirmation (D-022);
    # never editable in the admin.
    readonly_fields = (
        "invoice_number", "status", "confirmed_at", "created_by",
        "subtotal_display", "total_display", "payment_status_display",
    ) + SYSTEM_FIELDS
    fieldsets = (
        ("اطلاعات فاکتور", {"fields": ("customer", "invoice_date")}),
        ("مبلغ", {"fields": ("discount_amount", "subtotal_display", "total_display")}),
        # payment_method/payment_note (2.8) are superseded by the payment-entry
        # rows below (4.3b): one place to pick method + amount, not two (Sina,
        # 2026-09-24). The fields stay on the model, just unused from here on.
        ("پرداخت", {"fields": ("payment_status_display",)}),
        ("وضعیت", {"fields": ("invoice_number", "status", "confirmed_at", "created_by")}),
        ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
    )
    inlines = (SaleItemInline, SalesPaymentEntryInline)
    actions = ("confirm_selected", "cancel_selected")

    def get_queryset(self, request):
        # subtotal/total each iterate obj.items; prefetch once per page
        # instead of one query per row.
        return super().get_queryset(request).prefetch_related("items")

    @admin.display(description="جمع جزء (تومان)")
    def subtotal_display(self, obj):
        if obj is None or obj._state.adding:
            return "-"
        return format_toman(obj.subtotal)

    @admin.display(description="جمع نهایی (تومان)")
    def total_display(self, obj):
        if obj is None or obj._state.adding:
            return "-"
        return format_toman(obj.total)

    @admin.display(description="وضعیت پرداخت")
    def payment_status_display(self, obj):
        # Derived from PaymentAllocation, never typed (D-025, 4.3).
        # payment_status is a @property (not a model field), so there is
        # no auto-generated get_payment_status_display() -- .label works
        # because it returns the TextChoices member itself.
        if obj is None or obj._state.adding:
            return "-"
        return obj.payment_status.label

    def save_model(self, request, obj, form, change):
        # Record who entered the invoice; set once, on creation only.
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        # Confirmed invoice: Django renders the page view-only.
        return not is_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # obj is None on the list page: returning False removes the bulk
        # "delete selected" action, which cannot check each invoice's status.
        if obj is None or is_locked(obj):
            return False
        return super().has_delete_permission(request, obj)

    @admin.action(description="تأیید فاکتورهای انتخاب‌شده", permissions=["change"])
    def confirm_selected(self, request, queryset):
        """
        Confirm each selected invoice through confirm_sale.

        One service call per invoice: each runs in its own transaction,
        so a rejected invoice does not roll back the others. A sale that
        drives stock negative is still confirmed (D-016) but reported
        as a warning so the discrepancy is visible.
        """
        for invoice in queryset:
            try:
                _, shortages = confirm_sale(invoice, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} تأیید نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
                continue

            if shortages:
                shortage_text = "، ".join(str(item) for item in shortages)
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} تأیید شد، اما موجودی منفی شد: {shortage_text}",
                    messages.WARNING,
                )
            else:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} تأیید شد.",
                    messages.SUCCESS,
                )

    @admin.action(description="لغو فاکتورهای انتخاب‌شده", permissions=["change"])
    def cancel_selected(self, request, queryset):
        """
        Cancel each selected invoice through cancel_sale (D-023).

        One service call per invoice: each runs in its own transaction, so
        a rejected cancellation (wrong status, or user is not a
        superuser) does not roll back the others.
        """
        for invoice in queryset:
            try:
                cancel_sale(invoice, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} لغو نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} لغو شد.",
                    messages.SUCCESS,
                )
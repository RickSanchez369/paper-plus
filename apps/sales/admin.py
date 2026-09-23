#path: apps/sales/admin.py
"""
Admin for SalesInvoice and its items.

Mirror of apps/purchasing/admin.py, with one difference: confirm_sale
returns (invoice, shortages) and may drive stock negative (D-016).
Shortages are shown as a warning; during SHADOW each one is a
discrepancy to log against the paper ledger.

Rules enforced here:
- Stock is written only by confirm_sale; the admin never creates
  InventoryMovement rows and never sets status itself.
- A confirmed invoice is immutable (D-014): its page becomes view-only,
  its items are locked, and it cannot be deleted. Only drafts may be deleted.
"""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from simple_history.admin import SimpleHistoryAdmin

from apps.shared.admin_mixins import BusinessScopedAdminMixin
from apps.shared.utils import format_rial

from .models import SaleItem, SalesInvoice
from .services import cancel_sale, confirm_sale

# Only a draft invoice may be edited or deleted.
DRAFT_STATUS = "draft"

# Inherited from BaseModel; visible for debugging, never editable.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")


def is_locked(invoice):
    """True when an invoice exists and is no longer a draft (D-014)."""
    return invoice is not None and invoice.status != DRAFT_STATUS


class SaleItemInline(BusinessScopedAdminMixin, admin.TabularInline):
    """
    Invoice lines, edited inside the invoice page.

    In the permission methods below, `obj` is the parent invoice,
    not the item.
    """

    model = SaleItem
    # Items have no business FK; they reach it through their invoice.
    business_lookup = "invoice__business"
    extra = 1
    fields = ("product", "quantity", "unit_price", "line_total")
    readonly_fields = ("line_total",)
    # Search box instead of a dropdown of every product.
    autocomplete_fields = ("product",)

    @admin.display(description="جمع ردیف (ریال)")
    def line_total(self, obj):
        # Unsaved row: quantity and price may still be empty.
        if obj is None or obj._state.adding:
            return "-"
        return format_rial(obj.quantity * obj.unit_price)

    def has_add_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_delete_permission(request, obj)


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(BusinessScopedAdminMixin, SimpleHistoryAdmin, admin.ModelAdmin):
    """Sales invoices: draft entry in admin, confirmation via the service."""

    list_display = (
        "invoice_number", "customer", "business", "invoice_date",
        "status", "payment_method", "confirmed_at", "created_by",
    )
    list_filter = ("business", "status", "invoice_date")
    search_fields = ("invoice_number", "customer__name")
    # One JOIN per related column instead of one query per row.
    list_select_related = ("customer", "business", "created_by")
    autocomplete_fields = ("business", "customer")
    date_hierarchy = "invoice_date"
    # status/confirmed_at belong to the service; created_by to save_model.
    # invoice_number is assigned by confirm_sale at confirmation (D-022);
    # never editable in the admin.
    readonly_fields = ("invoice_number", "status", "confirmed_at", "created_by") + SYSTEM_FIELDS
    fieldsets = (
        ("اطلاعات فاکتور", {"fields": ("business", "customer", "invoice_date")}),
        ("پرداخت", {"fields": ("payment_method", "payment_note")}),
        ("وضعیت", {"fields": ("invoice_number", "status", "confirmed_at", "created_by")}),
        ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
    )
    inlines = (SaleItemInline,)
    actions = ("confirm_selected", "cancel_selected")

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
        a rejected cancellation (wrong status, or user is not Owner) does
        not roll back the others.
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
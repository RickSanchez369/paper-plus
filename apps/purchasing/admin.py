#path: apps/purchasing/admin.py
"""
Admin for PurchaseInvoice and its items.

Rules enforced here:
- Stock is written only by confirm_purchase; the admin never creates
  InventoryMovement rows and never sets status itself.
- A confirmed invoice is immutable (D-014): its page becomes view-only,
  its items can no longer be added, changed or deleted, and it cannot be
  deleted. Only drafts may be deleted.
"""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from simple_history.admin import SimpleHistoryAdmin

from apps.shared.admin_mixins import BusinessScopedAdminMixin
from apps.shared.utils import format_rial

from .models import PurchaseInvoice, PurchaseItem
from .services import confirm_purchase

# Only a draft invoice may be edited or deleted.
DRAFT_STATUS = "draft"

# Inherited from BaseModel; visible for debugging, never editable.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")


def is_locked(invoice):
    """True when an invoice exists and is no longer a draft (D-014)."""
    return invoice is not None and invoice.status != DRAFT_STATUS


class PurchaseItemInline(BusinessScopedAdminMixin, admin.TabularInline):
    """
    Invoice lines, edited inside the invoice page.

    In the permission methods below, `obj` is the parent invoice,
    not the item.
    """

    model = PurchaseItem
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


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(BusinessScopedAdminMixin, SimpleHistoryAdmin, admin.ModelAdmin):
    """Purchase invoices: draft entry in admin, confirmation via the service."""

    list_display = (
        "invoice_number", "supplier", "business", "invoice_date",
        "status", "confirmed_at", "created_by",
    )
    list_filter = ("business", "status", "invoice_date")
    search_fields = ("invoice_number", "supplier__name")
    # One JOIN per related column instead of one query per row.
    list_select_related = ("supplier", "business", "created_by")
    autocomplete_fields = ("business", "supplier")
    date_hierarchy = "invoice_date"
    # status/confirmed_at belong to the service; created_by to save_model.
    # invoice_number is assigned by confirm_purchase at confirmation (D-022);
    # never editable in the admin.
    readonly_fields = ("invoice_number", "status", "confirmed_at", "created_by") + SYSTEM_FIELDS
    fieldsets = (
        ("اطلاعات فاکتور", {"fields": ("business", "supplier", "supplier_invoice_number", "invoice_date")}),
        ("وضعیت", {"fields": ("invoice_number", "status", "confirmed_at", "created_by")}),
        ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
    )
    inlines = (PurchaseItemInline,)
    actions = ("confirm_selected",)

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
        Confirm each selected invoice through confirm_purchase.

        One service call per invoice: each runs in its own transaction,
        so a rejected invoice does not roll back the others.
        """
        for invoice in queryset:
            try:
                confirm_purchase(invoice, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} تأیید نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} تأیید شد.",
                    messages.SUCCESS,
                )
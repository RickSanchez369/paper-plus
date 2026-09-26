"""
Admin for Customer and Supplier (D-010: two separate models).

Both models share the same fields, so their admin configuration lives in
one base class. Partners are deactivated, never deleted: sales and
purchase invoices reference them through PROTECT foreign keys.
"""
from django.contrib import admin

from .models import Customer, Supplier

# Inherited from BaseModel; visible for debugging, never editable.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")


class PartnerAdmin(admin.ModelAdmin):
    """
    Shared configuration for Customer and Supplier.

    Not registered itself; a plain Python base class. Also provides the
    search_fields that invoice admins need for autocomplete (admin.E039).
    """

    list_display = ("name", "phone", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "phone")
    readonly_fields = SYSTEM_FIELDS
    fieldsets = (
        ("اطلاعات اصلی", {"fields": ("name",)}),
        ("اطلاعات تماس", {"fields": ("phone", "address")}),
        ("توضیحات و وضعیت", {"fields": ("note", "is_active")}),
        ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
    )

    def has_delete_permission(self, request, obj=None):
        # Deactivate with is_active instead (see module docstring).
        return False


@admin.register(Customer)
class CustomerAdmin(PartnerAdmin):
    """Customers: the counterparty of sales invoices."""


@admin.register(Supplier)
class SupplierAdmin(PartnerAdmin):
    """Suppliers: the counterparty of purchase invoices."""
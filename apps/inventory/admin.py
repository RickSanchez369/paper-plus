"""
Admin for InventoryMovement: a read-only view of the stock ledger.

The ledger is append-only. Rows are created only by services
(confirm_purchase, confirm_sale, set_opening_stock); corrections are new
adjustment_in / adjustment_out rows, never edits or deletes. Add, change
and delete are therefore closed to everyone, superusers included.
This page exists to trace discrepancies against the paper ledger.
"""
from django.contrib import admin

from apps.shared.admin_mixins import BusinessScopedAdminMixin
from apps.shared.utils import format_rial

from .models import InventoryMovement


@admin.register(InventoryMovement)
class InventoryMovementAdmin(BusinessScopedAdminMixin, admin.ModelAdmin):
    """Read-only ledger browser: filter, search, inspect. Never write."""

    list_display = (
        "created_at", "product", "movement_type", "quantity",
        "unit_price_display", "business", "created_by", "note",
    )
    list_filter = ("business", "movement_type", "created_at")
    search_fields = ("product__name", "product__sku", "note")
    # One JOIN per related column instead of one query per row.
    list_select_related = ("product", "business", "created_by")
    date_hierarchy = "created_at"
    # Newest first: the most recent movement is usually the one being traced.
    ordering = ("-created_at",)
    # Keeps the detail page readable; with change permission closed,
    # Django renders every field read-only anyway.
    fields = (
        "business", "product", "movement_type", "quantity",
        "unit_price_display", "note", "created_by", "id", "created_at", "updated_at",
    )

    @admin.display(description="قیمت واحد")
    def unit_price_display(self, obj):
        # unit_price is nullable at the DB level (2.9); guard anyway.
        if obj is None or obj.unit_price is None:
            return "-"
        return format_rial(obj.unit_price)


    def has_add_permission(self, request):
        # Movements are created only by services.
        return False

    def has_change_permission(self, request, obj=None):
        # History is never edited; corrections are new adjustment rows.
        return False

    def has_delete_permission(self, request, obj=None):
        # Deleting a movement silently rewrites every stock figure after it.
        return False
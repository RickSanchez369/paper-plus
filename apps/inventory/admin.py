"""
Admin for InventoryMovement: a read-only view of the stock ledger.

The ledger is append-only. Rows are created only by services
(confirm_purchase, confirm_sale, set_opening_stock); corrections are new
adjustment_in / adjustment_out rows, never edits or deletes. Add, change
and delete are therefore closed to everyone, superusers included.
This page exists to trace discrepancies against the paper ledger.
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.shared.utils import format_rial

from .models import InventoryConsumption, InventoryLayer, InventoryMovement


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    """Read-only ledger browser: filter, search, inspect. Never write."""

    list_display = (
        "created_at", "product", "movement_type", "quantity",
        "unit_price_display", "invoice_display", "created_by", "note",
    )
    list_filter = ("movement_type", "created_at")
    search_fields = ("product__name", "product__sku", "note")
    # One JOIN per related column instead of one query per row.
    list_select_related = (
        "product", "created_by",
        "purchase_item__invoice", "sale_item__invoice",
    )
    date_hierarchy = "created_at"
    # Newest first: the most recent movement is usually the one being traced.
    ordering = ("-created_at",)
    # Keeps the detail page readable; with change permission closed,
    # Django renders every field read-only anyway.
    fields = (
        "product", "movement_type", "quantity",
        "unit_price_display", "invoice_display", "note", "created_by",
        "id", "created_at", "updated_at",
    )

    @admin.display(description="قیمت واحد")
    def unit_price_display(self, obj):
        # unit_price is nullable at the DB level (2.9); guard anyway.
        if obj is None or obj.unit_price is None:
            return "-"
        return format_rial(obj.unit_price)

    @admin.display(description="فاکتور مرتبط")
    def invoice_display(self, obj):
        # opening/adjustment rows carry neither FK (2.9 CHECK constraint).
        if obj is None:
            return "-"
        item = obj.purchase_item or obj.sale_item
        if item is None:
            return "-"
        invoice = item.invoice
        opts = invoice._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[invoice.pk])
        return format_html('<a href="{}">{}</a>', url, invoice.invoice_number or "(تأیید نشده)")


    def has_add_permission(self, request):
        # Movements are created only by services.
        return False

    def has_change_permission(self, request, obj=None):
        # History is never edited; corrections are new adjustment rows.
        return False

    def has_delete_permission(self, request, obj=None):
        # Deleting a movement silently rewrites every stock figure after it.
        return False

@admin.register(InventoryLayer)
class InventoryLayerAdmin(admin.ModelAdmin):
    """
    Read-only view of the FIFO cost layers.

    Written only by services (set_opening_stock, confirm_purchase) and
    drawn down only by confirm_sale, exactly like the movement ledger
    above. Editing `quantity_remaining` by hand would silently rewrite the
    cost of every sale that ever drew from the layer.
    """

    list_display = (
        "created_at", "product", "source", "quantity", "quantity_remaining",
        "unit_cost_display", "remaining_value_display", "invoice_display",
        "cancelled_at", "created_by",
    )
    list_filter = ("source", "created_at")
    search_fields = ("product__name", "product__sku")
    list_select_related = ("product", "created_by", "purchase_item__invoice")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="بهای واحد")
    def unit_cost_display(self, obj):
        if obj is None:
            return "-"
        return format_rial(obj.unit_cost)

    @admin.display(description="ارزش مانده")
    def remaining_value_display(self, obj):
        if obj is None:
            return "-"
        return format_rial(obj.remaining_value)

    @admin.display(description="فاکتور خرید")
    def invoice_display(self, obj):
        # Opening-stock layers have no source invoice (the CHECK enforces it).
        if obj is None or obj.purchase_item is None:
            return "-"
        invoice = obj.purchase_item.invoice
        opts = invoice._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[invoice.pk])
        return format_html('<a href="{}">{}</a>', url, invoice.invoice_number or "(تأیید نشده)")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InventoryConsumption)
class InventoryConsumptionAdmin(admin.ModelAdmin):
    """
    Read-only view of which layer each sold line drew from.

    Append-only: a cancellation adds an opposite row, it never edits or
    removes one, so this list is the full history of a layer's drawdown.
    """

    list_display = (
        "created_at", "layer", "sale_item", "quantity", "cost_display",
        "invoice_display", "created_by", "note",
    )
    search_fields = ("layer__product__name", "sale_item__product__name")
    list_select_related = ("layer__product", "sale_item__invoice", "created_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="بهای تمام‌شده")
    def cost_display(self, obj):
        if obj is None:
            return "-"
        return format_rial(obj.cost)

    @admin.display(description="فاکتور فروش")
    def invoice_display(self, obj):
        if obj is None:
            return "-"
        invoice = obj.sale_item.invoice
        opts = invoice._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[invoice.pk])
        return format_html('<a href="{}">{}</a>', url, invoice.invoice_number or "(تأیید نشده)")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

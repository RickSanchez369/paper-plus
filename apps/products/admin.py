"""
Admin for Product.

Stock is never stored on Product; it is derived from the InventoryMovement
ledger through apps.inventory.selectors. The admin only displays it.
`is_onboarded` is owned by set_opening_stock (D-017) and is read-only here.
Products are deactivated, never deleted: movements and invoice items
reference them through PROTECT foreign keys.
"""
from django.contrib import admin

from apps.inventory.selectors import get_stock, get_stock_map
from apps.shared.utils import format_number

from .models import Product

# Inherited from BaseModel; visible for debugging, never editable.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Product catalogue with a live, read-only stock column."""

    list_display = ("name", "sku", "business", "unit", "stock_display", "is_onboarded", "is_active")
    list_filter = ("business", "is_active", "is_onboarded")
    search_fields = ("name", "sku")
    # One JOIN for the business column instead of one query per row.
    list_select_related = ("business",)
    # Search box instead of a dropdown; BusinessAdmin has search_fields.
    autocomplete_fields = ("business",)
    readonly_fields = ("stock_display", "is_onboarded") + SYSTEM_FIELDS
    fieldsets = (
        ("اطلاعات اصلی", {"fields": ("business", "name", "sku", "unit", "description")}),
        ("موجودی", {"fields": ("stock_display", "is_onboarded")}),
        ("وضعیت", {"fields": ("is_active",)}),
        ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
    )

    def get_changelist_instance(self, request):
        """
        Pre-compute stock for the current page in one query.

        list() evaluates the page queryset and fills its cache, so the
        template later iterates these same instances and finds `_stock`.
        """
        changelist = super().get_changelist_instance(request)
        products = list(changelist.result_list)
        stock_map = get_stock_map([p.pk for p in products])
        for product in products:
            # A product with no movements is absent from the map: stock 0.
            product._stock = stock_map.get(product.pk, 0)
        return changelist

    @admin.display(description="موجودی")
    def stock_display(self, obj):
        # Add page: the product is not saved yet, so there is no stock.
        if obj is None or obj._state.adding:
            return "-"
        # List page uses the pre-computed value; change page asks the selector.
        quantity = getattr(obj, "_stock", None)
        if quantity is None:
            quantity = get_stock(obj)
        return format_number(quantity)

    def has_delete_permission(self, request, obj=None):
        # Deactivate with is_active instead (see module docstring).
        return False
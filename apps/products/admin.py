"""
Admin for Product.

Stock is never stored on Product; it is derived from the InventoryMovement
ledger through apps.inventory.selectors. The admin only displays it.

Opening stock (D-017) is entered through a non-model form field that is
shown only while the product is not onboarded. After the product is saved,
the value is passed to set_opening_stock; the admin never writes the
movement itself. `is_onboarded` is owned by that service and is read-only.

Products are deactivated, never deleted: movements and invoice items
reference them through PROTECT foreign keys.
"""
from django import forms
from django.contrib import admin, messages
from simple_history.admin import SimpleHistoryAdmin
from apps.inventory.selectors import get_stock, get_stock_map
from apps.inventory.services import set_opening_stock
from apps.shared.admin_mixins import BusinessScopedAdminMixin
from apps.shared.utils import format_number
from .models import Product

# Inherited from BaseModel; visible for debugging, never editable.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")


class ProductAdminForm(forms.ModelForm):
    """
    Product form plus a one-time opening stock field.

    Blank  -> not counted yet; the product stays un-onboarded.
    0      -> onboarded with no movement row (the ledger forbids quantity 0).
    N > 0  -> one `opening` movement of N packages.
    Negative values are rejected here, before the service is reached.
    """

    opening_quantity = forms.IntegerField(
        label="موجودی اولیه",
        required=False,
        min_value=0,
        help_text="فقط یک بار قابل ثبت است. اگر هنوز شمارش نشده، خالی بگذارید.",
    )

    class Meta:
        model = Product
        fields = "__all__"


@admin.register(Product)
class ProductAdmin(BusinessScopedAdminMixin, SimpleHistoryAdmin):
    """Product catalogue with a live stock column and one-time opening stock."""

    form = ProductAdminForm
    list_display = ("name", "sku", "business", "unit", "stock_display", "is_onboarded", "is_active")
    list_filter = ("business", "is_active", "is_onboarded")
    search_fields = ("name", "sku")
    # One JOIN for the business column instead of one query per row.
    list_select_related = ("business",)
    # Search box instead of a dropdown; BusinessAdmin has search_fields.
    autocomplete_fields = ("business",)
    readonly_fields = ("stock_display", "is_onboarded") + SYSTEM_FIELDS

    def get_fieldsets(self, request, obj=None):
        # The opening field exists only until the product is onboarded (D-017).
        stock_fields = ("stock_display", "is_onboarded")
        if obj is None or not obj.is_onboarded:
            stock_fields = ("opening_quantity",) + stock_fields
        return (
            ("اطلاعات اصلی", {"fields": ("business", "name", "sku", "unit", "description")}),
            ("موجودی", {"fields": stock_fields}),
            ("وضعیت", {"fields": ("is_active",)}),
            ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
        )

    def save_model(self, request, obj, form, change):
        """
        Save the product, then hand opening stock to the service.

        The product must be saved first: the movement row needs its pk.
        Both run inside the admin's request transaction, so a service
        failure also rolls back the product save.
        """
        super().save_model(request, obj, form, change)
        quantity = form.cleaned_data.get("opening_quantity")
        if quantity is None or obj.is_onboarded:
            return
        set_opening_stock(obj, quantity, request.user)
        self.message_user(
            request,
            f"موجودی اولیه‌ی «{obj.name}» ثبت شد: {format_number(quantity)}",
            messages.SUCCESS,
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
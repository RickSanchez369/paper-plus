"""
Admin for Product.

Stock is never stored on Product; it is derived from the InventoryMovement
ledger through apps.inventory.selectors. The admin only displays it.

Opening stock (D-017) is entered through a non-model form field shown on
the add page only -- the same "at creation, or never" rule as the
Inventory module's new-product form (D-044). After the product is saved,
the value is passed to set_opening_stock; the admin never writes the
movement itself. `is_onboarded` is owned by that service and is read-only.

Products are deactivated, never deleted: movements and invoice items
reference them through PROTECT foreign keys.
"""
from django import forms
from django.contrib import admin, messages
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from apps.inventory.selectors import (
    get_current_cost_map,
    get_inventory_value_map,
    get_last_known_cost_map,
    get_stock,
    get_stock_map,
)
from apps.inventory.services import set_opening_stock
from apps.shared.utils import format_number, format_toman
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
    opening_unit_price = forms.IntegerField(
        label="قیمت واحد موجودی اولیه (تومان)",
        required=False,
        min_value=0,
        help_text="برای ارزش‌گذاری موجودی؛ همراه با موجودی اولیه الزامی است (R 13).",
    )

    class Meta:
        model = Product
        fields = "__all__"

    def clean(self):
        # opening_quantity and opening_unit_price must arrive together --
        # a quantity with no price would reach the service as an invalid
        # None (2.9), so this is caught here, in the form, before that.
        cleaned = super().clean()
        quantity = cleaned.get("opening_quantity")
        price = cleaned.get("opening_unit_price")
        if quantity is not None and price is None:
            self.add_error(
                "opening_unit_price",
                "همراه موجودی اولیه، قیمت واحد هم لازم است.",
            )
        return cleaned


@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin):
    """Product catalogue with a live stock column and one-time opening stock."""

    form = ProductAdminForm
    list_display = (
        "name", "sku", "unit", "price_display",
        "stock_display", "cost_display", "value_display", "history_link",
        "is_onboarded", "is_active",
    )
    list_filter = ("is_active", "is_onboarded")
    search_fields = ("name", "sku")
    readonly_fields = ("stock_display", "is_onboarded") + SYSTEM_FIELDS

    def get_fieldsets(self, request, obj=None):
        # Opening stock only while creating the product (D-017, D-044):
        # afterwards stock changes through invoices alone.
        stock_fields = ("stock_display", "is_onboarded")
        if obj is None:
            stock_fields = ("opening_quantity", "opening_unit_price") + stock_fields
        return (
            ("اطلاعات اصلی", {"fields": ("name", "sku", "unit", "description", "default_selling_price")}),
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
        if change or quantity is None:
            return
        unit_price = form.cleaned_data.get("opening_unit_price")
        set_opening_stock(obj, quantity, request.user, unit_price)
        self.message_user(
            request,
            f"موجودی اولیه‌ی «{obj.name}» ثبت شد: {format_number(quantity)}",
            messages.SUCCESS,
        )

    def get_changelist_instance(self, request):
        """
        Pre-compute stock and cost for the current page in one query each.

        list() evaluates the page queryset and fills its cache, so the
        template later iterates these same instances and finds `_stock`/`_cost`.
        """
        changelist = super().get_changelist_instance(request)
        products = list(changelist.result_list)
        product_ids = [p.pk for p in products]
        stock_map = get_stock_map(product_ids)
        cost_map = get_current_cost_map(product_ids)
        # Fallback so a sold-out product shows the cost it was last bought
        # at instead of a blank (REDESIGN_VISION 8, item 5). Display only.
        last_cost_map = get_last_known_cost_map(product_ids)
        value_map = get_inventory_value_map(product_ids)
        for product in products:
            # A product with no movements is absent from the map: stock 0.
            product._stock = stock_map.get(product.pk, 0)
            # A product never purchased or onboarded has no known cost yet.
            product._cost = cost_map.get(product.pk, last_cost_map.get(product.pk))
            product._value = value_map.get(product.pk, 0)
        return changelist

    def changelist_view(self, request, extra_context=None):
        """
        Add the total inventory value (4.1: "دارایی کل") across the current
        (filtered) page of products to the change list.

        Reuses the same per-row `_stock`/`_cost` computed by
        get_changelist_instance, so this costs no extra query.
        """
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            products = response.context_data["cl"].result_list
        except (AttributeError, KeyError):
            return response
        # Every layer at its own cost -- layers of the same product carry
        # different costs, so "stock x one cost" would be wrong (4.3).
        total = sum(product._value for product in products)
        response.context_data["total_inventory_value_display"] = format_toman(total)
        return response

    @admin.display(description="قیمت فروش پیش‌فرض")
    def price_display(self, obj):
        if obj is None or obj._state.adding:
            return "-"
        return format_toman(obj.default_selling_price)

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

    @admin.display(description="بهای خرید جاری")
    def cost_display(self, obj):
        # The cost the NEXT sale will consume: the oldest active layer's own
        # cost, not the latest purchase price (4.3). Falls back to the last
        # known cost once stock hits zero.
        if obj is None or obj._state.adding:
            return "-"
        cost = getattr(obj, "_cost", "unset")
        if cost == "unset":
            cost = get_current_cost_map([obj.pk]).get(
                obj.pk, get_last_known_cost_map([obj.pk]).get(obj.pk)
            )
        if cost is None:
            return "-"
        return format_toman(cost)

    @admin.display(description="ارزش موجودی")
    def value_display(self, obj):
        # Sum of this product's active layers, each at its own cost (4.3).
        if obj is None or obj._state.adding:
            return "-"
        value = getattr(obj, "_value", None)
        if value is None:
            value = get_inventory_value_map([obj.pk]).get(obj.pk, 0)
        return format_toman(value)

    @admin.display(description="تاریخچه تراکنش‌ها")
    def history_link(self, obj):
        # Links into InventoryMovementAdmin pre-filtered to this product
        # (4.2) -- every movement already carries its invoice link (via
        # invoice_display, added alongside this) and its user (created_by).
        if obj is None or obj._state.adding:
            return "-"
        url = reverse("admin:inventory_inventorymovement_changelist")
        return format_html('<a href="{}?product__id__exact={}">مشاهده</a>', url, obj.pk)

    def has_delete_permission(self, request, obj=None):
        # Deactivate with is_active instead (see module docstring).
        return False

    def get_urls(self):
        # JSON endpoint the sales-invoice product-price autofill JS calls
        # (4.3b UX: Sina, "قیمت پیش‌فرض برای فروش رو باید خود به خود بیاره").
        custom = [
            path(
                "<uuid:pk>/default-price/",
                self.admin_site.admin_view(self.default_price_view),
                name="products_product_default_price",
            ),
        ]
        return custom + super().get_urls()

    def default_price_view(self, request, pk):
        product = self.get_queryset(request).filter(pk=pk).first()
        if product is None:
            return JsonResponse({"error": "not found"}, status=404)
        return JsonResponse({"default_selling_price": product.default_selling_price})
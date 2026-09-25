# path: apps/inventory/views.py

"""
Inventory module views (REDESIGN_VISION 4.3, MASTER_PROMPT Phase C).

Nothing here writes stock directly -- set_opening_stock and
record_adjustment own that, same non-negotiable as every other module
(views never write).
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.products.forms import QuickProductForm
from apps.products.models import Product

from .forms import AdjustmentForm, OpeningStockForm
from .models import InventoryMovement
from .selectors import (
    get_active_layers,
    get_current_cost_map,
    get_inventory_value_map,
    get_last_known_cost_map,
    get_stock_map,
    get_total_inventory_value,
)
from .services import record_adjustment, set_opening_stock


class InventoryListView(LoginRequiredMixin, TemplateView):
    """
    List (REDESIGN_VISION 4.3): cards (total value, item count,
    negative-stock warning, a USD placeholder), table (stock, current
    purchase cost, selling price, value, % share of total value).
    """

    template_name = "inventory/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = list(Product.objects.filter(is_active=True).order_by("name"))
        product_ids = [p.pk for p in products]

        stock_map = get_stock_map(product_ids)
        current_cost_map = get_current_cost_map(product_ids)
        last_cost_map = get_last_known_cost_map(product_ids)
        value_map = get_inventory_value_map(product_ids)
        total_value = get_total_inventory_value()

        rows = []
        negative_count = 0
        for product in products:
            stock = stock_map.get(product.pk, 0)
            if stock < 0:
                negative_count += 1
            value = value_map.get(product.pk, 0)
            rows.append({
                "product": product,
                "stock": stock,
                # the oldest active layer's cost -- what the next sale
                # consumes; falls back to the last known cost once stock
                # hits zero, display-only (4.1's already-established rule)
                "current_cost": current_cost_map.get(product.pk, last_cost_map.get(product.pk)),
                "has_active_cost": product.pk in current_cost_map,
                "value": value,
                "share": (value * 100 // total_value) if total_value else 0,
            })

        context.update({
            "rows": rows,
            "total_value": total_value,
            "item_count": len(products),
            "negative_count": negative_count,
        })
        return context


class ProductCreateView(LoginRequiredMixin, View):
    """"+ کالای جدید" (REDESIGN_VISION 4.3). A full page here, unlike the
    inline mid-invoice version reused from Purchasing/Sales -- Inventory is
    not mid-transaction, so there is no invoice to keep alive around it."""

    template_name = "inventory/product_new.html"

    def get(self, request):
        return render(request, self.template_name, {"form": QuickProductForm()})

    def post(self, request):
        form = QuickProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"کالای «{product.name}» ثبت شد. اکنون می‌توانید موجودی اولیه‌اش را وارد کنید.")
            return redirect("inventory:opening_stock")
        return render(request, self.template_name, {"form": form})


class OpeningStockCreateView(LoginRequiredMixin, View):
    """"موجودی اولیه" button (REDESIGN_VISION 4.3) -- feeds
    set_opening_stock (D-017: once per product, ever)."""

    template_name = "inventory/opening_stock_new.html"

    def get(self, request):
        return render(request, self.template_name, {"form": OpeningStockForm()})

    def post(self, request):
        form = OpeningStockForm(request.POST)
        error = None
        if form.is_valid():
            try:
                set_opening_stock(
                    form.cleaned_data["product"],
                    form.cleaned_data["quantity"],
                    request.user,
                    form.cleaned_data["unit_price"],
                )
            except ValidationError as exc:
                error = "؛ ".join(exc.messages)
            else:
                messages.success(request, "موجودی اولیه ثبت شد.")
                return redirect("inventory:list")
        return render(request, self.template_name, {"form": form, "error": error})


class AdjustmentCreateView(LoginRequiredMixin, View):
    """"اصلاح موجودی" button (REDESIGN_VISION 4.3) -- feeds
    record_adjustment. Any authenticated user may record one; the
    mandatory reason note is the only safeguard (apps/shared/permissions.py:
    only oversell-confirm and cancellation are superuser-gated)."""

    template_name = "inventory/adjustment_new.html"

    def get(self, request):
        return render(request, self.template_name, {"form": AdjustmentForm()})

    def post(self, request):
        form = AdjustmentForm(request.POST)
        error = None
        if form.is_valid():
            data = form.cleaned_data
            try:
                record_adjustment(
                    data["product"],
                    data["direction"],
                    data["quantity"],
                    request.user,
                    data["note"],
                    unit_price=data.get("unit_price"),
                )
            except ValidationError as exc:
                error = "؛ ".join(exc.messages)
            else:
                messages.success(request, "اصلاح موجودی ثبت شد.")
                return redirect("inventory:list")
        return render(request, self.template_name, {"form": form, "error": error})


class InventoryDetailView(LoginRequiredMixin, DetailView):
    """
    Per-product detail (REDESIGN_VISION 4.3): active layers, the existing
    chronological movement history (ROADMAP 4.2) extended to show which
    layer each row touched and a link back to its source invoice, and a
    "تاریخچهٔ قیمت" tab reusing the existing HistoricalProduct (gap #7 --
    no dedicated view needed).
    """

    model = Product
    template_name = "inventory/detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object

        context["active_layers"] = get_active_layers(product)
        context["stock"] = get_stock_map([product.pk]).get(product.pk, 0)
        context["value"] = get_inventory_value_map([product.pk]).get(product.pk, 0)

        movements = (
            product.movements
            .select_related("purchase_item__invoice", "sale_item__invoice", "layer")
            .prefetch_related("consumptions__layer", "sale_item__consumptions__layer")
            .order_by("-created_at")
        )
        context["movement_rows"] = [self._movement_row(m) for m in movements]
        context["price_history"] = product.history.all()
        return context

    @staticmethod
    def _movement_row(movement):
        """Which layer(s) this row touched, and which invoice (if any) it
        traces back to -- one lookup shape per movement type, since each
        type resolves its layer through a different relation."""
        layers = []
        invoice = None
        if movement.movement_type in (
            InventoryMovement.MovementType.OPENING,
            InventoryMovement.MovementType.ADJUSTMENT_IN,
        ):
            if movement.layer_id:
                layers = [movement.layer]
        elif movement.movement_type == InventoryMovement.MovementType.PURCHASE:
            layer = getattr(movement.purchase_item, "layer", None)
            layers = [layer] if layer else []
            invoice = movement.purchase_item.invoice
        elif movement.movement_type == InventoryMovement.MovementType.SALE:
            layers = [c.layer for c in movement.sale_item.consumptions.all()]
            invoice = movement.sale_item.invoice
        elif movement.movement_type == InventoryMovement.MovementType.ADJUSTMENT_OUT:
            layers = [c.layer for c in movement.consumptions.all()]
        return {"movement": movement, "layers": layers, "invoice": invoice}

# path: apps/inventory/views.py

"""
Inventory module views.

Nothing here writes stock directly -- set_opening_stock (at product
creation only, D-044) and the invoice services own that; the selling
price goes through products.services.update_selling_price. Same
non-negotiable as every other module: views never write.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.products.forms import SellingPriceForm
from apps.products.models import Product
from apps.products.services import update_selling_prices

from .forms import InventoryProductForm
from .models import InventoryMovement
from .selectors import (
    get_active_layers,
    get_current_cost_map,
    get_inventory_value_map,
    get_last_known_cost_map,
    get_stock_map,
    get_total_inventory_value,
)
from .services import set_opening_stock


class InventoryListView(LoginRequiredMixin, TemplateView):
    """
    List: cards (total value, item count,
    negative-stock warning, a USD placeholder), table (stock, current
    FIFO cost, last purchase cost, selling price, value, % share of total
    value). Every value figure is cost-based -- Σ active layers × their
    own cost; the selling price is shown beside it, never multiplied in.
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
                # consumes (absent once stock hits zero: no layer left)
                "current_cost": current_cost_map.get(product.pk),
                # the most recent layer's cost, exhausted or not -- "what
                # did we last buy it at", display-only
                "last_cost": last_cost_map.get(product.pk),
                "value": value,
                "share": (value * 100 // total_value) if total_value else 0,
            })

        # Pack and carton products are shown apart, each with its own stock
        # total (D-076): the two units are never added together.
        groups = []
        for unit_value, unit_label in Product.Unit.choices:
            unit_rows = [r for r in rows if r["product"].unit == unit_value]
            groups.append({
                "unit": unit_label,
                "rows": unit_rows,
                "stock_total": sum(r["stock"] for r in unit_rows),
                "value_total": sum(r["value"] for r in unit_rows),
            })

        context.update({
            "rows": rows,
            "groups": groups,
            "total_value": total_value,
            "item_count": len(products),
            "negative_count": negative_count,
        })
        return context


class ProductCreateView(LoginRequiredMixin, View):
    """"+ کالای جدید", with an optional one-time
    opening stock (D-044) -- the only place stock can enter the ledger
    without an invoice. Product and opening layer are saved in one
    transaction: a rejected opening stock leaves no half-created product."""

    template_name = "inventory/product_new.html"

    def get(self, request):
        return render(request, self.template_name, {"form": InventoryProductForm()})

    def post(self, request):
        form = InventoryProductForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data.get("opening_quantity")
            try:
                with transaction.atomic():
                    product = form.save()
                    if quantity:
                        set_opening_stock(product, quantity, request.user, form.cleaned_data["opening_unit_cost"])
            except ValidationError as exc:
                form.add_error(None, "؛ ".join(exc.messages))
            else:
                messages.success(request, f"کالای «{product.name}» ثبت شد.")
                return redirect("inventory:detail", pk=product.pk)
        return render(request, self.template_name, {"form": form})


class SellingPriceUpdateView(LoginRequiredMixin, View):
    """POST-only: the per-product "قیمت فروش" form (retail + wholesale).
    update_selling_prices changes those fields only -- no invoice, layer or
    cost is touched."""

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        form = SellingPriceForm(request.POST)
        if form.is_valid():
            try:
                update_selling_prices(
                    product, request.user,
                    retail=form.cleaned_data.get("default_selling_price"),
                    wholesale=form.cleaned_data.get("wholesale_selling_price"),
                )
            except ValidationError as exc:
                messages.error(request, "؛ ".join(exc.messages))
            else:
                messages.success(request, "قیمت فروش بروزرسانی شد.")
        else:
            messages.error(request, "؛ ".join(error for errors in form.errors.values() for error in errors))
        return redirect("inventory:detail", pk=pk)


class InventoryDetailView(LoginRequiredMixin, DetailView):
    """
    Per-product detail: cost vs. selling price side
    by side (with the selling-price form), active layers, the chronological
    movement history (ROADMAP 4.2) extended to show which layer each row
    touched and a link back to its source invoice, and a "تاریخچهٔ قیمت"
    section reusing the existing HistoricalProduct (gap #7).
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
        context["current_cost"] = get_current_cost_map([product.pk]).get(product.pk)
        context["last_cost"] = get_last_known_cost_map([product.pk]).get(product.pk)
        context["price_form"] = SellingPriceForm(
            initial={
                "default_selling_price": product.default_selling_price,
                "wholesale_selling_price": product.wholesale_selling_price,
            },
        )

        movements = (
            product.movements
            .select_related("purchase_item__invoice", "sale_item__invoice", "layer")
            .prefetch_related("sale_item__consumptions__layer")
            .order_by("-created_at")
        )
        context["movement_rows"] = [self._movement_row(m) for m in movements]
        context["price_history"] = product.history.all()
        return context

    @staticmethod
    def _movement_row(movement):
        """Which layer(s) this row touched, and which invoice (if any) it
        traces back to -- one lookup shape per movement type, since each
        type resolves its layer through a different relation. ADJUSTMENT
        rows are only ever a cancellation's reversal now (D-044); their
        note names the cancelled invoice, and they carry no layer link."""
        layers = []
        invoice = None
        if movement.movement_type == InventoryMovement.MovementType.OPENING:
            if movement.layer_id:
                layers = [movement.layer]
        elif movement.movement_type == InventoryMovement.MovementType.PURCHASE:
            layer = getattr(movement.purchase_item, "layer", None)
            layers = [layer] if layer else []
            invoice = movement.purchase_item.invoice
        elif movement.movement_type == InventoryMovement.MovementType.SALE:
            layers = [c.layer for c in movement.sale_item.consumptions.all()]
            invoice = movement.sale_item.invoice
        return {"movement": movement, "layers": layers, "invoice": invoice}

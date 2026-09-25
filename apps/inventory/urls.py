# path: apps/inventory/urls.py

"""Inventory module routes (REDESIGN_VISION 4.3)."""

from django.urls import path

from .views import (
    AdjustmentCreateView,
    InventoryDetailView,
    InventoryListView,
    OpeningStockCreateView,
    ProductCreateView,
)

app_name = "inventory"

urlpatterns = [
    path("", InventoryListView.as_view(), name="list"),
    path("products/new/", ProductCreateView.as_view(), name="product_new"),
    path("opening-stock/", OpeningStockCreateView.as_view(), name="opening_stock"),
    path("adjustment/", AdjustmentCreateView.as_view(), name="adjustment"),
    path("<uuid:pk>/", InventoryDetailView.as_view(), name="detail"),
]

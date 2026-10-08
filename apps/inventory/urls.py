# path: apps/inventory/urls.py

"""Inventory module routes. No opening-stock or
adjustment page: stock changes through documents only (D-044)."""

from django.urls import path

from .views import (
    InventoryDetailView,
    InventoryListView,
    ProductRemoveView,
    ProductCreateView,
    SellingPriceUpdateView,
)

app_name = "inventory"

urlpatterns = [
    path("", InventoryListView.as_view(), name="list"),
    path("products/new/", ProductCreateView.as_view(), name="product_new"),
    path("<uuid:pk>/", InventoryDetailView.as_view(), name="detail"),
    path("<uuid:pk>/selling-price/", SellingPriceUpdateView.as_view(), name="selling_price"),
    path("<uuid:pk>/remove/", ProductRemoveView.as_view(), name="remove"),
]

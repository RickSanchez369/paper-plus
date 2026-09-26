# path: apps/purchasing/urls.py

"""Purchasing module routes, including the Suppliers sub-section (REDESIGN_VISION 4.2)."""

from django.urls import path

from .views import (
    ProductSearchView,
    PurchaseCancelView,
    PurchaseCreateView,
    PurchaseDetailView,
    PurchasePrintView,
    PurchasingListView,
    QuickProductCreateView,
    QuickSupplierCreateView,
    SupplierCreateView,
    SupplierDetailView,
    SupplierListView,
    SupplierUpdateView,
)

app_name = "purchasing"

urlpatterns = [
    path("", PurchasingListView.as_view(), name="list"),
    path("new/", PurchaseCreateView.as_view(), name="new"),
    path("product-search/", ProductSearchView.as_view(), name="product_search"),
    path("quick-product/", QuickProductCreateView.as_view(), name="quick_product"),
    path("quick-supplier/", QuickSupplierCreateView.as_view(), name="quick_supplier"),
    path("<uuid:pk>/", PurchaseDetailView.as_view(), name="detail"),
    path("<uuid:pk>/cancel/", PurchaseCancelView.as_view(), name="cancel"),
    path("<uuid:pk>/print/", PurchasePrintView.as_view(), name="print"),
    # A sub-section of Purchasing, not its own nav item (Sina's call, 4.2).
    path("suppliers/", SupplierListView.as_view(), name="suppliers"),
    path("suppliers/new/", SupplierCreateView.as_view(), name="supplier_new"),
    path("suppliers/<uuid:pk>/", SupplierDetailView.as_view(), name="supplier_detail"),
    path("suppliers/<uuid:pk>/edit/", SupplierUpdateView.as_view(), name="supplier_edit"),
]

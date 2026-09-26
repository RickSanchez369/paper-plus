# path: apps/sales/urls.py

"""Sales module routes (REDESIGN_VISION 4.1)."""

from django.urls import path

from .views import (
    ProductSearchView,
    SalesCancelView,
    SalesCreateView,
    SalesDetailView,
    SalesListView,
    SalesPrintView,
)

app_name = "sales"

urlpatterns = [
    path("", SalesListView.as_view(), name="list"),
    path("new/", SalesCreateView.as_view(), name="new"),
    path("product-search/", ProductSearchView.as_view(), name="product_search"),
    path("<uuid:pk>/", SalesDetailView.as_view(), name="detail"),
    path("<uuid:pk>/cancel/", SalesCancelView.as_view(), name="cancel"),
    path("<uuid:pk>/print/", SalesPrintView.as_view(), name="print"),
]

from django.urls import path

from .views import (
    PurchaseReturnCreateView, PurchaseReturnDetailView, ReturnListView, SalesReturnCreateView, SalesReturnDetailView,
)

app_name = "returns"

urlpatterns = [
    path("", ReturnListView.as_view(), name="list"),
    path("sales/new/<uuid:invoice_pk>/", SalesReturnCreateView.as_view(), name="sales_new"),
    path("sales/<uuid:pk>/", SalesReturnDetailView.as_view(), name="sales_detail"),
    path("purchases/new/<uuid:invoice_pk>/", PurchaseReturnCreateView.as_view(), name="purchase_new"),
    path("purchases/<uuid:pk>/", PurchaseReturnDetailView.as_view(), name="purchase_detail"),
]

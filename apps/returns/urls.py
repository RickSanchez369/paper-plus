from django.urls import path

from .views import (
    PurchaseReturnCancelView, PurchaseReturnCreateView, PurchaseReturnDetailView, ReturnListView,
    SalesReturnCancelView, SalesReturnCreateView, SalesReturnDetailView,
)

app_name = "returns"

urlpatterns = [
    path("", ReturnListView.as_view(), name="list"),
    path("sales/new/<uuid:invoice_pk>/", SalesReturnCreateView.as_view(), name="sales_new"),
    path("sales/<uuid:pk>/", SalesReturnDetailView.as_view(), name="sales_detail"),
    path("sales/<uuid:pk>/cancel/", SalesReturnCancelView.as_view(), name="sales_cancel"),
    path("purchases/new/<uuid:invoice_pk>/", PurchaseReturnCreateView.as_view(), name="purchase_new"),
    path("purchases/<uuid:pk>/", PurchaseReturnDetailView.as_view(), name="purchase_detail"),
    path("purchases/<uuid:pk>/cancel/", PurchaseReturnCancelView.as_view(), name="purchase_cancel"),
]

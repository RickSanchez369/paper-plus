# path: apps/partners/urls.py

"""Customers module routes (REDESIGN_VISION 4.7). Suppliers live under Purchasing."""

from django.urls import path

from apps.shared.views import ModulePlaceholderView

from .views import QuickCustomerCreateView

app_name = "customers"

urlpatterns = [
    path(
        "",
        ModulePlaceholderView.as_view(
            title="مشتریان",
            description="فهرست مشتریان با مانده حساب، تعداد فاکتور و آخرین خرید.",
        ),
        name="list",
    ),
    # Embedded inline wherever a `customer` field is picked (Sales' new-
    # invoice form today; the Customers list itself later).
    path("quick-new/", QuickCustomerCreateView.as_view(), name="quick_new"),
]

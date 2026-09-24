# path: apps/partners/urls.py

"""Customers module routes (REDESIGN_VISION 4.7). Suppliers live under Purchasing."""

from django.urls import path

from apps.shared.views import ModulePlaceholderView

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
]

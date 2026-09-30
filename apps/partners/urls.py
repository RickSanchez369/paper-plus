# path: apps/partners/urls.py

"""Customers module routes. Suppliers live under Purchasing."""

from django.urls import path

from .views import CustomerDetailView, CustomerListView, CustomerUpdateView, QuickCustomerCreateView

app_name = "customers"

urlpatterns = [
    path("", CustomerListView.as_view(), name="list"),
    path("<uuid:pk>/", CustomerDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/", CustomerUpdateView.as_view(), name="edit"),
    # Embedded inline wherever a `customer` field is picked (Sales' new-
    # invoice form, and the Customers list itself).
    path("quick-new/", QuickCustomerCreateView.as_view(), name="quick_new"),
]

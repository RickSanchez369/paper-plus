# path: apps/sales/urls.py

"""Sales module routes (REDESIGN_VISION 4.1)."""

from django.urls import path

from apps.shared.views import ModulePlaceholderView

app_name = "sales"

urlpatterns = [
    path(
        "",
        ModulePlaceholderView.as_view(
            title="فروش",
            description="فهرست فاکتورهای فروش با وضعیت پرداخت و سود هر فاکتور.",
        ),
        name="list",
    ),
]

# path: apps/inventory/urls.py

"""Inventory module routes (REDESIGN_VISION 4.3)."""

from django.urls import path

from apps.shared.views import ModulePlaceholderView

app_name = "inventory"

urlpatterns = [
    path(
        "",
        ModulePlaceholderView.as_view(
            title="انبار",
            description="موجودی، بهای خرید جاری و ارزش هر کالا بر پایهٔ لایه‌های FIFO.",
        ),
        name="list",
    ),
]

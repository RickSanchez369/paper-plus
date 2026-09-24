# path: apps/purchasing/urls.py

"""Purchasing module routes, including the Suppliers sub-section (REDESIGN_VISION 4.2)."""

from django.urls import path

from apps.shared.views import ModulePlaceholderView

app_name = "purchasing"

urlpatterns = [
    path(
        "",
        ModulePlaceholderView.as_view(
            title="خرید",
            description="فهرست فاکتورهای خرید و وضعیت پرداخت آن‌ها.",
        ),
        name="list",
    ),
    # A sub-section of Purchasing, not its own nav item (Sina's call, 4.2).
    path(
        "suppliers/",
        ModulePlaceholderView.as_view(
            title="تأمین‌کنندگان",
            description="فهرست تأمین‌کنندگان با جمع خرید و بدهی باز هرکدام.",
        ),
        name="suppliers",
    ),
]

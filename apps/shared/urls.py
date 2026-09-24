# path: apps/shared/urls.py

"""Dashboard, plus the two cross-cutting report modules (REDESIGN_VISION 4.8, 4.9)."""

from django.urls import path

from .views import DashboardView, ModulePlaceholderView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
]

reports_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="گزارش‌های مالی",
            description="فروش، خرید، هزینه، سود ناخالص و خالص در بازهٔ انتخابی — همه زنده از دفترها.",
        ),
        name="index",
    ),
], "reports")

user_activity_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="فعالیت کاربران",
            description="شمارش ثبت‌ها و لغوها به تفکیک کاربر، در بازهٔ انتخابی.",
        ),
        name="index",
    ),
], "user_activity")

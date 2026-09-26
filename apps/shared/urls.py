# path: apps/shared/urls.py

"""Dashboard, plus the two cross-cutting report modules (REDESIGN_VISION 4.8, 4.9)."""

from django.urls import path

from .views import DashboardView, DatePickerMonthView, ModulePlaceholderView, ReportsView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    # Fed to the Jalali picker; see DatePickerMonthView for why the calendar
    # is computed here rather than in the browser.
    path("date-picker/month/", DatePickerMonthView.as_view(), name="date_picker_month"),
]

reports_patterns = ([
    path("", ReportsView.as_view(), name="index"),
], "reports")

user_activity_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="فعالیت کاربران",
            description="شمارش ثبت‌ها و لغوها به تفکیک کاربر، در بازهٔ انتخابی.",
            with_date_range=True,
        ),
        name="index",
    ),
], "user_activity")

# path: apps/shared/urls.py

"""Dashboard, plus the two cross-cutting report modules."""

from django.urls import path

from .views import (
    BackupView,
    DashboardView,
    DatePickerMonthView,
    ReportsView,
    UserActivityDetailView,
    UserActivityView,
    UsdRateRefreshView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("usd-rate/refresh/", UsdRateRefreshView.as_view(), name="usd_rate_refresh"),
    # Fed to the Jalali picker; see DatePickerMonthView for why the calendar
    # is computed here rather than in the browser.
    path("date-picker/month/", DatePickerMonthView.as_view(), name="date_picker_month"),
]

backup_patterns = ([
    path("", BackupView.as_view(), name="index"),
], "backup")

reports_patterns = ([
    path("", ReportsView.as_view(), name="index"),
], "reports")

user_activity_patterns = ([
    path("", UserActivityView.as_view(), name="index"),
    path("<uuid:pk>/", UserActivityDetailView.as_view(), name="detail"),
], "user_activity")

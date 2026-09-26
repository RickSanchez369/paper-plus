# path: apps/shared/urls.py

"""Dashboard, plus the two cross-cutting report modules (REDESIGN_VISION 4.8, 4.9)."""

from django.urls import path

from .views import (
    DashboardView,
    DatePickerMonthView,
    ReportsView,
    UserActivityDetailView,
    UserActivityView,
)

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
    path("", UserActivityView.as_view(), name="index"),
    path("<uuid:pk>/", UserActivityDetailView.as_view(), name="detail"),
], "user_activity")

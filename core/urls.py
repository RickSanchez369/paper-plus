"""
URL configuration for core project.

One path per module in REDESIGN_VISION 4, in that document's order, so the
sidebar and this file read the same way. `/admin/` is a superuser-only
technical backend, not a user-facing surface (2.1); the gate lives on
PaperPlusAdminSite.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.payments.urls import (
    bank_accounts_patterns,
    cheques_patterns,
    expenses_patterns,
    payables_patterns,
    receivables_patterns,
)
from apps.shared.urls import reports_patterns, user_activity_patterns

urlpatterns = [
    path("", include("apps.shared.urls")),
    path("sales/", include("apps.sales.urls")),
    path("purchasing/", include("apps.purchasing.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("receivables/", include(receivables_patterns)),
    path("payables/", include(payables_patterns)),
    path("cheques/", include(cheques_patterns)),
    path("bank-accounts/", include(bank_accounts_patterns)),
    path("expenses/", include(expenses_patterns)),
    path("customers/", include("apps.partners.urls")),
    path("reports/", include(reports_patterns)),
    path("user-activity/", include(user_activity_patterns)),
    path("", include("apps.users.urls")),
    path("admin/", admin.site.urls),
]

# Uploaded files (expense receipts) are served by Django only in DEBUG.
# In production a real web server serves MEDIA_ROOT; static() is a no-op
# when DEBUG is off, so this line is safe to leave in place.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""
URL configuration for core project.

`/admin/` is a superuser-only technical backend, not a user-facing surface
(REDESIGN_VISION 2.1); the gate lives on PaperPlusAdminSite. The real
frontend's routes land here in Phase B.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]

# Uploaded files (expense receipts) are served by Django only in DEBUG.
# In production a real web server serves MEDIA_ROOT; static() is a no-op
# when DEBUG is off, so this line is safe to leave in place.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

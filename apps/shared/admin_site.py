# path: apps/shared/admin_site.py

"""
Superuser-only admin site (REDESIGN_VISION §2.1).

WHY this exists now: until this rebuild, `/admin/` was safe for a staff
user because every page was business-scoped (`BusinessScopedAdminMixin`)
and role-gated through the Owner/Seller auth Groups. Both are gone, so
`is_staff` alone would hand any logged-in staff user raw write access to
every financial model. `/admin/` is a technical backend for the person
maintaining the system, not a user-facing surface — end users get the real
frontend instead.

`AdminSite.has_permission` is the single gate Django checks for every
admin view, including the login page, so overriding it here is enough.
"""

from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


class PaperPlusAdminSite(AdminSite):
    """Django admin, reachable by active superusers only."""

    site_header = "مدیریت پیپر پلاس"
    site_title = "پیپر پلاس"
    index_title = "پنل فنی"

    def has_permission(self, request):
        user = request.user
        return user.is_active and user.is_superuser


class PaperPlusAdminConfig(AdminConfig):
    """Replaces `django.contrib.admin` in INSTALLED_APPS."""

    default_site = "apps.shared.admin_site.PaperPlusAdminSite"

# apps/shared/admin.py
"""
Admin registration for the shared app.

Business and BusinessMembership are gone, so this
module is down to the AuditLog browser. Site-wide Persian titles live on
PaperPlusAdminSite (apps/shared/admin_site.py) now, not here.
"""
from django.contrib import admin

from .models import AuditLog

# Fields inherited from BaseModel. Shown read-only so they are visible
# for debugging but can never be edited by hand.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only view of AuditLog rows (D-029).

    No add/change/delete: rows are written only by log_event() from inside
    services, inside the same atomic transaction as the event itself.
    """

    list_display = ("event_type", "target_type", "target_id", "actor", "created_at")
    list_filter = ("event_type",)
    search_fields = ("target_id", "actor__phone")
    list_select_related = ("actor",)
    readonly_fields = SYSTEM_FIELDS + ("actor", "event_type", "target_type", "target_id", "payload")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

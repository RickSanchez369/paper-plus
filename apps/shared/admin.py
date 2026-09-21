# apps/shared/admin.py
"""
Admin registration for the shared app: Business and BusinessMembership.

The admin is the data-entry tool for business owners. Neither model here
touches stock or money, so plain ModelAdmin saves are safe. Records are
deactivated with `is_active`, never deleted: every business record is
referenced by products, partners and invoices through PROTECT foreign keys,
and deleting a membership erases who had access and when.
"""
from django.contrib import admin

from .admin_mixins import BusinessScopedAdminMixin
from .models import Business, BusinessMembership

# Site-wide Persian titles. Set here because `shared` is the base app
# every other app depends on, so this module is always loaded.
admin.site.site_header = "مدیریت پیپر پلاس"
admin.site.site_title = "پیپر پلاس"
admin.site.index_title = "پنل مدیریت"

# Fields inherited from BaseModel. Shown read-only so they are visible
# for debugging but can never be edited by hand.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")


class BusinessMembershipInline(BusinessScopedAdminMixin, admin.TabularInline):
    """
    Members of one business, edited inside the Business change page.

    Kept inline because a membership has no meaning without its business;
    a separate page would force the owner to jump between screens.
    """

    model = BusinessMembership
    # No blank rows by default; the owner clicks "add another" when needed.
    extra = 0
    fields = ("user", "role", "is_active")
    # Deactivate instead of delete, so access history is preserved.
    can_delete = False
    # Search by phone or name instead of loading every user into a
    # dropdown. Requires UserAdmin.search_fields (admin.E039).
    autocomplete_fields = ("user",)


@admin.register(Business)
class BusinessAdmin(BusinessScopedAdminMixin, admin.ModelAdmin):
    """Admin for the tenant root. Every business-data row points here."""

    # The model IS Business, so the scope path is its own primary key.
    business_lookup = "pk"

    list_display = ("name", "legal_name", "phone", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "legal_name", "registration_number", "phone")
    readonly_fields = SYSTEM_FIELDS
    fieldsets = (
        ("اطلاعات اصلی", {"fields": ("name", "legal_name", "registration_number")}),
        ("اطلاعات تماس", {"fields": ("phone", "address")}),
        ("وضعیت", {"fields": ("is_active",)}),
        # Collapsed: useful for debugging, noise for daily use.
        ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
    )
    inlines = (BusinessMembershipInline,)

    def has_delete_permission(self, request, obj=None):
        # A business is deactivated, never deleted (see module docstring).
        return False


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(BusinessScopedAdminMixin, admin.ModelAdmin):
    """
    Cross-business view of memberships: answers "who has access where".

    Editing normally happens in the Business inline; this list exists
    for searching and filtering across all businesses.
    """

    list_display = ("user", "business", "role", "is_active", "created_at")
    list_filter = ("business", "role", "is_active")
    search_fields = ("user__phone", "business__name")
    # One JOIN instead of one extra query per row for user and business.
    list_select_related = ("user", "business")
    # Same search boxes on the standalone membership page.
    autocomplete_fields = ("business", "user")
    readonly_fields = SYSTEM_FIELDS
    fields = ("business", "user", "role", "is_active") + SYSTEM_FIELDS

    def has_delete_permission(self, request, obj=None):
        # Deactivate instead of delete, so access history is preserved.
        return False
"""
Admin for the custom User model (D-007: phone is the USERNAME_FIELD).

Django's stock UserAdmin and its forms assume a `username` field, so both
forms and all fieldsets are redefined here against the real fields.
Users are deactivated, never deleted: `created_by`/`actor` on movements,
invoices, payments and audit rows are PROTECT foreign keys, and the audit
trail depends on them.

Creating and deactivating logins stays an admin-only task for now, and
`/admin/` is superuser-only (D-035), so the
old per-business scoping, the Owner/Seller role field, and the
self-deactivation carve-out a Seller needed are all gone with the roles
themselves.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from simple_history.admin import SimpleHistoryAdmin

from .models import User


class UserCreateForm(BaseUserCreationForm):
    """
    Form for the "add user" page: phone + name + password twice.

    Based on BaseUserCreationForm, not UserCreationForm: the latter adds a
    case-insensitive uniqueness check hard-coded to `username`. Uniqueness
    and the ^09\\d{9}$ format of `phone` are enforced by the model field.
    """

    class Meta:
        model = User
        fields = ("phone", "first_name", "last_name")


class UserEditForm(UserChangeForm):
    """
    Form for the "change user" page.

    Only Meta is replaced; the parent keeps the read-only password hash
    field with its link to the "change password" form.
    """

    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(SimpleHistoryAdmin, DjangoUserAdmin):
    """User admin keyed on phone instead of username."""

    form = UserEditForm
    add_form = UserCreateForm
    list_display = ("phone", "first_name", "last_name", "is_active", "is_staff", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser", "groups")
    # Also required by autocomplete_fields in other admins (admin.E039).
    search_fields = ("phone", "first_name", "last_name")
    # Stock UserAdmin orders by `username`, which does not exist here (admin.E033).
    ordering = ("phone",)
    readonly_fields = ("id", "last_login", "created_at", "updated_at")

    # Change page.
    fieldsets = (
        ("ورود", {"fields": ("phone", "password")}),
        ("اطلاعات شخصی", {"fields": ("first_name", "last_name")}),
        ("دسترسی‌ها", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("اطلاعات سیستمی", {
            "fields": ("id", "last_login", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # Add page. DjangoUserAdmin switches to these automatically when obj is None.
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "first_name", "last_name", "password1", "password2"),
        }),
    )

    def has_delete_permission(self, request, obj=None):
        # Deactivate with is_active instead (see module docstring).
        return False

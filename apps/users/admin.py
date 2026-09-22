"""
Admin for the custom User model (D-007: phone is the USERNAME_FIELD).

Django's stock UserAdmin and its forms assume a `username` field, so both
forms and all fieldsets are redefined here against the real fields.
Users are deactivated, never deleted: `created_by` on inventory movements
and invoices is a PROTECT foreign key, and the audit trail depends on it.
"""
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.db import transaction

from apps.shared.admin_mixins import BusinessScopedAdminMixin
from apps.shared.models import Business, BusinessMembership
from apps.shared.permissions import get_business_ids
from .models import User

# Fields a non-superuser must never edit. Without this, any staff user with
# "change user" permission could grant themselves superuser access.
PRIVILEGE_FIELDS = ("is_superuser", "groups", "user_permissions")

# D-029: a Seller reaching their own record may only view it and flip
# is_active off. Everything else, including this list itself, stays locked.
SELF_DEACTIVATION_READONLY = (
    ("phone", "password", "first_name", "last_name", "is_staff")
    + PRIVILEGE_FIELDS
    + ("id", "last_login", "created_at", "updated_at")
)


class UserCreateForm(BaseUserCreationForm):
    """
    Form for the "add user" page: phone + name + password twice, plus the
    new user's first business and role (D-028). A User has no meaning
    without at least one membership, so both are required; a user with no
    business (e.g. a second superuser) is created via `createsuperuser`,
    not this form.

    Based on BaseUserCreationForm, not UserCreationForm: the latter adds a
    case-insensitive uniqueness check hard-coded to `username`. Uniqueness
    and the ^09\\d{9}$ format of `phone` are enforced by the model field.
    """

    business = forms.ModelChoiceField(
        queryset=Business.objects.none(),  # narrowed per-request in get_form
        label="کسب‌وکار",
    )
    role = forms.ChoiceField(
        choices=BusinessMembership._meta.get_field("role").choices,
        label="نقش",
    )

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
class UserAdmin(BusinessScopedAdminMixin, DjangoUserAdmin):
    """User admin keyed on phone instead of username."""

    # User has no business FK (D-008); the link is through memberships.
    # To-many path: distinct() stops a user shared across two of the
    # viewer's businesses from appearing twice. Users with no membership
    # are invisible to non-superusers until ROADMAP 1.3.
    business_lookup = "memberships__business"
    scope_distinct = True
    form = UserEditForm
    add_form = UserCreateForm
    list_display = ("phone", "first_name", "last_name", "is_active", "is_staff", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser", "groups")
    # Also required later by autocomplete_fields in other admins (admin.E039).
    search_fields = ("phone", "first_name", "last_name")
    # Stock UserAdmin orders by `username`, which does not exist here (admin.E033).
    ordering = ("phone",)
    readonly_fields = ("id", "last_login", "created_at", "updated_at")

    # Change page.
    fieldsets = (
        ("ورود", {"fields": ("phone", "password")}),
        ("اطلاعات شخصی", {"fields": ("first_name", "last_name")}),
        ("دسترسی‌ها", {"fields": ("is_active", "is_staff") + PRIVILEGE_FIELDS}),
        ("اطلاعات سیستمی", {
            "fields": ("id", "last_login", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # Add page. DjangoUserAdmin switches to these automatically when obj is None.
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "first_name", "last_name", "password1", "password2", "business", "role"),
        }),
    )

    def _is_self_seller_edit(self, request, obj):
        """True when a Seller (not Owner, not superuser) is on their own record (D-029)."""
        return (
            obj is not None
            and obj.pk == request.user.pk
            and not request.user.is_superuser
            and request.user.groups.filter(name="Seller").exists()
            and not request.user.groups.filter(name="Owner").exists()
        )

    def has_view_permission(self, request, obj=None):
        if self._is_self_seller_edit(request, obj):
            return True
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if self._is_self_seller_edit(request, obj):
            return True
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if self._is_self_seller_edit(request, obj):
            return SELF_DEACTIVATION_READONLY
        # Lock privilege fields for everyone except superusers.
        readonly = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser:
            readonly = tuple(readonly) + PRIVILEGE_FIELDS
        return readonly

    def get_form(self, request, obj=None, **kwargs):
        # Scope the add-form "business" choices to the viewer (D-028): an
        # Owner may only attach a new user to their own business.
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            ids = get_business_ids(request.user)
            qs = Business.objects.all() if request.user.is_superuser else Business.objects.filter(pk__in=ids)
            form.base_fields["business"].queryset = qs.filter(is_active=True)
        return form

    def save_model(self, request, obj, form, change):
        """
        Create the user and, on the add page, its first membership (D-028)
        in one transaction: a User row must never exist without a way in.
        Self-service Seller edits may only turn is_active off, never back
        on (D-029); readonly_fields already blocks every other field.
        """
        if change and self._is_self_seller_edit(request, obj) and not User.objects.get(pk=obj.pk).is_active:
            obj.is_active = False
        if not change:
            obj.is_staff = True
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if not change:
                BusinessMembership.objects.create(
                    business=form.cleaned_data["business"],
                    user=obj,
                    role=form.cleaned_data["role"],
                    is_active=True,
                )

    def has_delete_permission(self, request, obj=None):
        # Deactivate with is_active instead (see module docstring).
        return False
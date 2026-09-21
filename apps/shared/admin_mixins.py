"""
Business scoping for every admin (D-026).

Non-superusers see and choose only rows of the businesses they are active
members of. Superuser is never scoped. Scoping happens in two places:

- get_queryset: the changelist, and also change/delete views, because
  ModelAdmin.get_object reads through get_queryset. A foreign row opened by
  URL behaves as if it does not exist.
- formfield_for_foreignkey: dropdown choices and their validation, so a
  foreign Business or Product cannot be submitted even with a crafted POST.
  Autocomplete widgets are covered by the target model's own admin, which
  also uses this mixin.

The mixin must come FIRST in the bases, before admin.ModelAdmin /
admin.TabularInline, so its methods run before Django's.
"""

from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist

from apps.shared.models import Business
from apps.shared.permissions import get_business_ids

_CACHE_ATTR = "_scoped_business_ids"


def _get_ids(request):
    """
    Business ids for request.user, computed once per request.

    One changelist page calls this for the queryset and for every FK field;
    caching on the request avoids one query per call.
    """
    if not hasattr(request, _CACHE_ATTR):
        setattr(request, _CACHE_ATTR, get_business_ids(request.user))
    return getattr(request, _CACHE_ATTR)


def _has_business_fk(model):
    """True if ``model`` has a ``business`` FK pointing to Business."""
    try:
        field = model._meta.get_field("business")
    except FieldDoesNotExist:
        return False
    return field.many_to_one and field.related_model is Business


class BusinessScopedAdminMixin:
    """
    Scope an admin (ModelAdmin or inline) to the user's businesses.

    ``business_lookup`` is the ORM path from this admin's model to Business:
    - "business" for models with a direct FK (default)
    - "pk" for Business itself
    - "invoice__business" for invoice items
    Set ``scope_distinct = True`` when the path crosses a to-many relation
    (e.g. User via memberships), or the changelist shows duplicate rows.
    """

    business_lookup = "business"
    scope_distinct = False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        qs = qs.filter(**{f"{self.business_lookup}__in": _get_ids(request)})
        return qs.distinct() if self.scope_distinct else qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            related = db_field.related_model
            ids = _get_ids(request)
            # Respect a queryset a subclass already set; only narrow it.
            base = kwargs.get("queryset", related._default_manager.all())
            if related is Business:
                kwargs["queryset"] = base.filter(pk__in=ids)
            elif _has_business_fk(related):
                kwargs["queryset"] = base.filter(business_id__in=ids)
            # FKs to models without a business (e.g. User) are not narrowed
            # here; the user FK on memberships is handled in ROADMAP 1.3.
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    
    def get_list_filter(self, request):
        """
        Scope the "business" sidebar filter for non-superusers.

        The default RelatedFieldListFilter lists every Business in the
        database without going through get_queryset, which leaks other
        tenants' names. RelatedOnlyFieldListFilter lists only values present
        in this admin's (already scoped) queryset.
        """
        filters = super().get_list_filter(request)
        if request.user.is_superuser:
            return filters
        return tuple(
            ("business", admin.RelatedOnlyFieldListFilter) if f == "business" else f
            for f in filters
        )
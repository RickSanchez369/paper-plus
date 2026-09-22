"""Signal handlers for the shared app.

WHY: BusinessMembership.role is the single source of truth for what a
user can do (D-009). Keeping Django's auth Group in sync here means
admin permissions always match the role field, instead of requiring
manual Group assignment in the admin that can drift out of sync.
"""
from django.contrib.auth.models import Group
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import BusinessMembership

ROLE_GROUP_MAP = {
    "owner": "Owner",
    "salesperson": "Seller",
}


def _remove_group_if_unneeded(user, role):
    """Drop the role's Group unless another active membership still needs it."""
    group_name = ROLE_GROUP_MAP.get(role)
    if not group_name:
        return
    still_needs = BusinessMembership.objects.filter(
        user=user, role=role, is_active=True
    ).exists()
    if not still_needs:
        Group.objects.filter(name=group_name).first()
        user.groups.remove(*Group.objects.filter(name=group_name))


@receiver(post_save, sender=BusinessMembership)
def sync_group_on_membership_save(sender, instance, **kwargs):
    """Add the user to the Group matching their current role.

    Does not touch groups from the user's OTHER role/business
    memberships: a user Owner in one business and Seller in another
    ends up with both groups. Per-business scoping is handled by
    BusinessScopedAdminMixin, not by Group membership.
    """
    group_name = ROLE_GROUP_MAP.get(instance.role)
    if not group_name:
        return
    if instance.is_active:
        group, _ = Group.objects.get_or_create(name=group_name)
        instance.user.groups.add(group)
    else:
        _remove_group_if_unneeded(instance.user, instance.role)


@receiver(post_delete, sender=BusinessMembership)
def sync_group_on_membership_delete(sender, instance, **kwargs):
    """Remove the role's Group if no other active membership needs it."""
    _remove_group_if_unneeded(instance.user, instance.role)
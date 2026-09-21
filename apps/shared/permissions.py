"""
Role checks for business-scoped actions (D-021, D-023, D-026).

Services call these helpers so a permission is enforced even when the call
does not come through the admin. A hidden admin button is never the only
barrier (D-026).

Rules:
- Superuser passes every role check and is never scoped to a business.
- A membership counts only if the membership, the user and the business are
  all active. An inactive link is treated exactly like no link.
- Role values are the stored choice values of BusinessMembership.role.
"""

from django.core.exceptions import PermissionDenied

from apps.shared.models import BusinessMembership

# Stored values of BusinessMembership.role. Plain strings so callers do not
# depend on the name of the choices class.
ROLE_OWNER = "owner"
ROLE_SALESPERSON = "salesperson"
ALL_ROLES = frozenset({ROLE_OWNER, ROLE_SALESPERSON})


def _is_active_user(user):
    """True for an authenticated, active user. None and AnonymousUser fail."""
    return (
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    )


def _validate_roles(roles):
    """
    Reject an empty or misspelled role list.

    A typo such as "ownr" would otherwise deny everyone silently and look
    like a permission bug. This is a programmer error, so the message is
    English and the exception is ValueError, not PermissionDenied.
    """
    if not roles:
        raise ValueError("At least one role is required.")
    unknown = set(roles) - ALL_ROLES
    if unknown:
        raise ValueError(f"Unknown role(s): {sorted(unknown)}")


def get_membership(user, business):
    """
    Return the user's active membership in ``business``, or None.

    None also covers: missing/anonymous/inactive user, inactive business,
    inactive membership. Superuser status is NOT considered here: a
    superuser without a membership gets None. Use ``has_role`` for checks.
    """
    if not _is_active_user(user) or business is None:
        return None
    return BusinessMembership.objects.filter(
        user=user,
        business=business,
        is_active=True,
        business__is_active=True,
    ).first()


def has_role(user, business, *roles):
    """
    True if ``user`` may act in ``business`` with one of ``roles``.

    An active superuser always passes (D-021, D-023: "Owner and superuser").
    """
    _validate_roles(roles)
    if not _is_active_user(user):
        return False
    if user.is_superuser:
        return True
    membership = get_membership(user, business)
    return membership is not None and membership.role in roles


def is_owner(user, business):
    """True for an active Owner of ``business`` or an active superuser."""
    return has_role(user, business, ROLE_OWNER)


def require_role(user, business, *roles):
    """
    Raise PermissionDenied unless ``has_role`` passes.

    Call at the top of a service, before any lock or write, so a rejected
    call touches nothing.
    """
    if not has_role(user, business, *roles):
        raise PermissionDenied("شما اجازه‌ی انجام این کار را در این کسب‌وکار ندارید.")
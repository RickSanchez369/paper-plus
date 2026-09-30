"""
The one permission concept left after the single-business rebuild.

Business/BusinessMembership and the Owner/Seller roles are gone, so
`get_membership`, `has_role`, `is_owner`, `require_role` and
`get_business_ids` are gone with them. Any authenticated user may do
anything in the app, with one exception that used to be role-gated and is
now gated on Django's own builtin `is_superuser`: cancelling a document.
(Confirming a sale that drives stock negative was the second, until D-052
made that impossible for everyone.)

Services call this helper themselves, so the rule holds even when the
call does not come from a view (D-026's reasoning, unchanged).
"""

from django.core.exceptions import PermissionDenied


def is_privileged(user):
    """
    True for an authenticated, active superuser.

    None and AnonymousUser fail, same as before: a missing user is never
    treated as permission.
    """
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_superuser", False)
    )


def require_privileged(user):
    """
    Raise PermissionDenied unless ``is_privileged`` passes.

    Call at the top of a service, before any lock or write, so a rejected
    call touches nothing.
    """
    if not is_privileged(user):
        raise PermissionDenied("فقط ابرکاربر اجازه‌ی انجام این کار را دارد.")

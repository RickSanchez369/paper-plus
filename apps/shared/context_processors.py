# path: apps/shared/context_processors.py

"""Context every page of the frontend needs, so no view has to remember it."""

from django.conf import settings

from .navigation import NAVIGATION
from .permissions import is_privileged


def company(request):
    """Who issues printed documents (settings.COMPANY, filled from .env)."""
    return {"company": settings.COMPANY}


def navigation(request):
    """
    The sidebar, plus which section the current page belongs to.

    The active section is derived from the resolved URL's namespace rather
    than from the path, so a detail page like `sales:detail` keeps "فروش"
    highlighted without every view having to declare where it lives.
    """
    match = getattr(request, "resolver_match", None)
    current = ""
    if match is not None:
        current = match.namespace or (match.url_name or "")

    user = getattr(request, "user", None)
    visible = tuple(
        group for group in NAVIGATION
        if not group.superuser_only or is_privileged(user)
    )

    return {
        "navigation": visible,
        "current_section": current,
    }

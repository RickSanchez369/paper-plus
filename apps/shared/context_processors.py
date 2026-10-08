# path: apps/shared/context_processors.py

"""Context every page of the frontend needs, so no view has to remember it."""

from django.conf import settings

from .navigation import NAVIGATION


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

    # The folded group (receivables/payables/cheques, expenses) that holds the current page
    # starts open, so the active child is visible without a click.
    open_group = next(
        (g.label for g in NAVIGATION if any(i.match_prefix == current for i in g.items)), ""
    )
    return {
        "navigation": NAVIGATION,
        "current_section": current,
        "open_nav_group": open_group,
    }

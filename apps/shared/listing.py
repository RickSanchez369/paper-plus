# path: apps/shared/listing.py

"""
Sorting and paging for list pages, one way everywhere.

`?sort=<key>&dir=asc|desc` is matched against a whitelist the view passes
in, so a query string can never name a column the view did not offer.
Rows may be queryset objects or the dicts/lists views build in Python.
"""

from django.core.paginator import Paginator

PER_PAGE = 25


def sort_rows(request, rows, sort_keys, default=None):
    """Sort `rows` by the whitelisted `?sort=`; return (rows, active key, direction).

    `sort_keys` maps a key name to a callable that returns the sort value of
    a row. Unknown keys fall back to `default` (or the incoming order).
    """
    key = request.GET.get("sort")
    if key not in sort_keys:
        key = default if default in sort_keys else None
    direction = "desc" if request.GET.get("dir") == "desc" else "asc"
    if key is None:
        return rows, None, direction
    return sorted(rows, key=sort_keys[key], reverse=(direction == "desc")), key, direction


def paginate(request, rows, per_page=PER_PAGE):
    """The requested page of `rows` (a bad page number falls back safely)."""
    return Paginator(rows, per_page).get_page(request.GET.get("page"))

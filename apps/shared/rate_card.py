# path: apps/shared/rate_card.py

"""
Display context for the «نرخ دلار» stat card (D-080). Read-only: it only reads the stored
`ExchangeRate` rows, so the template tag (full page) and the refresh view (htmx fragment)
render the very same card from one place.
"""

from django.middleware.csrf import get_token

from apps.shared import exchange
from apps.shared.models import ExchangeRate


def usd_rate_context(request, just_updated=False, next_url=None):
    """Context for shared/_usd_rate_card.html: newest valid rate, the move against the one
    before it, whether it is stale, and why the last try failed (first line of the stored error)."""
    valid = list(ExchangeRate.objects.filter(status=ExchangeRate.Status.OK).order_by("-fetched_at")[:2])
    row = valid[0] if valid else None
    previous = valid[1] if len(valid) > 1 else None
    attempt = exchange.latest_attempt()
    failed = bool(attempt and attempt.status == ExchangeRate.Status.FAILED)

    delta = (row.rate - previous.rate) if row and previous else None
    return {
        "row": row,
        "stale": exchange.is_stale(row),
        "delta_dir": (delta > 0) - (delta < 0) if delta is not None else 0,
        "delta_abs": abs(delta) if delta else None,
        "delta_pct": round(abs(delta) * 100 / previous.rate, 1) if delta else None,
        "last_failed": failed,
        "fail_reason": attempt.error.splitlines()[0] if failed and attempt.error else "",
        "just_updated": just_updated,
        "csrf_token": get_token(request) if request is not None else "",
        "next": next_url if next_url is not None else (request.get_full_path() if request is not None else ""),
    }

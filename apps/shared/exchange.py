# path: apps/shared/exchange.py

"""
USD rate in Toman, read from an Iranian price site (D-080).

`fetch_usd_rate` is the only writer of `ExchangeRate`. It never touches an
invoice and invoice confirmation never calls it: confirmation only reads the
latest stored valid row (`latest_valid_rate`), so a slow or broken source
cannot hold up a sale. A failed attempt is stored without a number.

Sources are small parsers registered by name; the one in use comes from
`settings.USD_RATE_SOURCE` (and `USD_RATE_URL` to point it elsewhere), the
others are tried after it when it fails.
"""

import datetime
import json
import re
import urllib.request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ExchangeRate

USER_AGENT = "Mozilla/5.0 (paper-plus rate reader)"
TIMEOUT_SECONDS = 8
# A new rate further than this from the last valid one is more likely a
# mis-parse than a real move; it is stored as a failure instead.
MAX_JUMP_FACTOR = 2


class RateError(Exception):
    """The source answered, but not with a usable rate."""


def _http_get(url):
    """The only network call; tests replace it."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", "replace")


def _digits(text):
    return int(text.replace(",", "").replace("٬", ""))


def parse_tgju_profile(body):
    """The live price on the tgju dollar page, Rial -> Toman."""
    found = re.search(r'data-col="info\.last_trade\.PDrCotVal"[^>]*>\s*([\d,]+)\s*<', body)
    if not found:
        raise RateError("قیمت در صفحهٔ منبع پیدا نشد (ساختار صفحه عوض شده؟).")
    return _digits(found.group(1)) // 10


def parse_tgju_api(body):
    """The latest daily row of the tgju history table (close price), Rial -> Toman."""
    try:
        return _digits(json.loads(body)["data"][0][3]) // 10
    except (ValueError, KeyError, IndexError, TypeError):
        raise RateError("پاسخ منبع قابل خواندن نبود.")


# name -> (default URL, parser)
SOURCES = {
    "tgju": ("https://www.tgju.org/profile/price_dollar_rl", parse_tgju_profile),
    "tgju_api": ("https://api.tgju.org/v1/market/indicator/summary-table-data/price_dollar_rl", parse_tgju_api),
}


def latest_valid_rate():
    """The newest successful row, or None when nothing was ever read."""
    return ExchangeRate.objects.filter(status=ExchangeRate.Status.OK).order_by("-fetched_at").first()


def latest_attempt():
    """The newest row of any status, to show whether the last try failed."""
    return ExchangeRate.objects.order_by("-fetched_at").first()


def is_stale(row, hours=None):
    """True when there is no valid rate or it is older than ``hours`` (default: the setting)."""
    hours = hours if hours is not None else settings.USD_RATE_STALE_HOURS
    return row is None or timezone.now() - row.fetched_at > datetime.timedelta(hours=hours)


def _try_source(name, url):
    default_url, parser = SOURCES[name]
    rate = parser(_http_get(url or default_url))
    if rate <= 0:
        raise RateError("نرخ خوانده‌شده معتبر نیست.")
    last = latest_valid_rate()
    if last and not (last.rate / MAX_JUMP_FACTOR <= rate <= last.rate * MAX_JUMP_FACTOR):
        raise RateError(f"نرخ {rate} با آخرین نرخ معتبر ({last.rate}) فاصلهٔ غیرعادی دارد.")
    return rate


@transaction.atomic
def fetch_usd_rate():
    """
    Read the rate once and store one row: ``ok`` with the number, or
    ``failed`` with the reasons and no number. The configured source goes
    first, the other registered sources follow if it fails. Returns the row.
    """
    now = timezone.now()
    configured = settings.USD_RATE_SOURCE
    order = [configured] + [name for name in SOURCES if name != configured]
    errors = []
    for name in order:
        if name not in SOURCES:
            errors.append(f"{name}: منبع ناشناخته")
            continue
        url = settings.USD_RATE_URL if name == configured else ""
        try:
            rate = _try_source(name, url)
        except RateError as exc:
            errors.append(f"{name}: {exc}")
        except Exception as exc:  # network down, DNS, timeout, bad TLS ...
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
        else:
            return ExchangeRate.objects.create(
                rate=rate, rate_date=timezone.localdate(now), fetched_at=now,
                source=name, status=ExchangeRate.Status.OK,
            )
    return ExchangeRate.objects.create(
        rate=None, rate_date=timezone.localdate(now), fetched_at=now,
        source=configured, status=ExchangeRate.Status.FAILED, error="\n".join(errors)[:2000],
    )

# path: apps/shared/templatetags/paper.py

"""
Display filters for templates. These never change how a value is stored.

Money formatting already lived in apps/shared/utils.py; the date filters
wrap apps/shared/dates.py so no template ever converts a calendar itself.
"""

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import Resolver404, resolve
from django.utils.html import format_html

from apps.products.units import split_units, units_phrase
from apps.shared import dates
from apps.shared.utils import format_number, format_toman
from apps.shared.words import number_to_words

register = template.Library()


@register.inclusion_tag("shared/_usd_rate_card.html", takes_context=True)
def usd_rate_card(context):
    """The «نرخ دلار» stat card: newest valid rate, its age, and a failed-last-try warning (D-080)."""
    from apps.shared import exchange

    row = exchange.latest_valid_rate()
    attempt = exchange.latest_attempt()
    request = context.get("request")
    return {
        "row": row,
        "stale": exchange.is_stale(row),
        "last_failed": bool(attempt and attempt.status == "failed"),
        "csrf_token": context.get("csrf_token"),
        "next": request.get_full_path() if request else "",
    }


@register.simple_tag
def parent_url(path):
    """The page one level up from `path`: drop the last URL segment, and keep
    dropping while the result is not a real page (e.g. `/inventory/products/`
    does not exist, so `/inventory/products/new/` goes up to `/inventory/`).
    Empty for the home page. Used by the header's "بازگشت" button, which
    deliberately never means history.back() -- the previous page may be a
    validation error."""
    parts = [p for p in path.split("/") if p]
    while parts:
        parts.pop()
        candidate = "/" + "/".join(parts) + "/" if parts else "/"
        try:
            resolve(candidate)
        except Resolver404:
            continue
        return candidate
    return ""


@register.simple_tag
def static_v(path):
    """`{% static %}` plus the file's modification time, so a browser never
    keeps serving a stale CSS/JS file after it was edited."""
    url = static(path)
    found = finders.find(path)
    return f"{url}?v={int(os.path.getmtime(found))}" if found else url


@register.filter(name="jalali")
def jalali(value):
    """"۱۴۰۵/۰۷/۰۳" — the everyday form, for table cells."""
    return dates.format_date(value)


@register.filter(name="jalali_long")
def jalali_long(value):
    """"۳ مهر ۱۴۰۵" — for headings and invoice bodies, where it reads as prose."""
    return dates.format_date(value, with_month_name=True)


@register.filter(name="jalali_at")
def jalali_at(value):
    """"۱۴۰۵/۰۷/۰۳ ساعت ۱۴:۳۰" — for audit rows, where the time is the point."""
    return dates.format_datetime(value)


def _keep_sign_left(text):
    """Isolate a leading minus with its digits so an RTL run keeps «-۵۰» and not «۵۰-»."""
    if text.startswith("-"):
        figure, _, rest = text.partition(" ")
        return f"⁦{figure}⁩ {rest}".rstrip()
    return text


@register.filter(name="toman")
def toman(value):
    """"۲۵۰٬۰۰۰ تومان" with Persian digits -- the one money filter (D-043)."""
    if value is None:
        return ""
    return _keep_sign_left(dates.to_persian_digits(format_toman(value)).replace(",", "٬"))


@register.filter(name="toman_words")
def toman_words(value):
    """"یک هزار و دویست تومان" -- the amount in words for a printed invoice."""
    if value is None:
        return ""
    return f"{number_to_words(value)} تومان"


@register.filter(name="fa_number")
def fa_number(value):
    """A plain count in Persian digits: quantities, invoice counts, page numbers."""
    if value is None:
        return ""
    return _keep_sign_left(dates.to_persian_digits(format_number(value)).replace(",", "٬"))


@register.filter(name="units")
def units(quantity, pack_per_carton):
    """A stock/quantity in packs as «۶ کارتن + ۴ بسته», plus «(۳۴ بسته)» once cartons are involved (D-081)."""
    if quantity is None:
        return ""
    cartons, packs = split_units(quantity, pack_per_carton)
    text = units_phrase(cartons, packs)
    if cartons:
        text += f" ({quantity} بسته)"
    return dates.to_persian_digits(text)


@register.filter(name="line_units")
def line_units(item):
    """An invoice line's quantity exactly as it was entered: cartons + loose packs, plus the pack total (D-081)."""
    cartons = item.cartons
    packs = item.loose_packs
    text = units_phrase(cartons, packs)
    if cartons:
        text += f" ({item.quantity} بسته)"
    return dates.to_persian_digits(text)


@register.filter(name="fa_digits")
def fa_digits(value):
    """Persian digits with NO grouping: document numbers (invoice, cheque),
    which are identifiers, not quantities -- 9956001, never 9,956,001."""
    if value in (None, ""):
        return ""
    return dates.to_persian_digits(str(value))


@register.filter(name="dict_get")
def dict_get(mapping, key):
    """`{{ mapping|dict_get:key }}` -- a template's `.` lookup only reads a
    literal attribute name, never a loop variable's value; User Activity's
    per-bucket columns are built from one shared `bucket_order` loop, so
    this is the one place that needs it."""
    return mapping.get(key)


# One place decides which colour a business state wears, so a status never
# changes look between a list, a detail page and the dashboard.
_STATUS_TONES = {
    "payment": {"paid": "good", "partial": "pending", "unpaid": "bad"},
    "invoice": {"draft": "pending", "confirmed": "neutral", "cancelled": "muted"},
    "cheque": {"pending": "info", "cleared": "good", "bounced": "bad-solid", "cancelled": "muted"},
    "direction": {"in": "good", "out": "neutral"},
}


@register.simple_tag
def status_badge(kind, value, label):
    """A status chip whose tone comes from `_STATUS_TONES`; unknown values stay neutral."""
    tone = _STATUS_TONES.get(kind, {}).get(str(value), "neutral")
    return format_html('<span class="badge badge--{}">{}</span>', tone, label)


@register.simple_tag
def flag_badge(tone, label):
    """A chip for a flag that is not a document status (overdue, stale rate, inactive...)."""
    return format_html('<span class="badge badge--{}">{}</span>', tone, label)


def _query_without(request, *drop):
    """The current query string minus `drop`, ending in "&" when not empty."""
    params = request.GET.copy()
    for name in drop:
        params.pop(name, None)
    encoded = params.urlencode()
    return f"{encoded}&" if encoded else ""


@register.inclusion_tag("shared/_pagination.html", takes_context=True)
def pager(context, page_obj):
    """The shared pager; keeps every active filter and sort in its links."""
    return {"page_obj": page_obj, "query": _query_without(context["request"], "page")}


@register.inclusion_tag("shared/_sort_th.html", takes_context=True)
def sort_th(context, label, key):
    """A sortable column header: click toggles asc/desc and returns to page 1."""
    request = context["request"]
    active = context.get("sort_key") == key
    direction = context.get("sort_dir", "asc")
    return {
        "label": label, "key": key, "active": active, "direction": direction,
        "next_dir": "desc" if active and direction == "asc" else "asc",
        "query": _query_without(request, "sort", "dir", "page"),
    }

# path: apps/shared/templatetags/paper.py

"""
Display filters for templates. These never change how a value is stored.

Money formatting already lived in apps/shared/utils.py; the date filters
wrap apps/shared/dates.py so no template ever converts a calendar itself.
"""

import os
from uuid import uuid4

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import Resolver404, resolve
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.products.units import split_units, units_phrase
from apps.shared import dates
from apps.shared.utils import format_number, format_toman
from apps.shared.words import number_to_words

register = template.Library()


@register.simple_tag(takes_context=True)
def financial_submission(context):
    request = context.get("request")
    previous = request.POST.get("submission_id") if request and request.method == "POST" else None
    return format_html('<input type="hidden" name="submission_id" value="{}">', previous or uuid4())


@register.inclusion_tag("shared/_usd_rate_card.html", takes_context=True)
def usd_rate_card(context):
    """The «نرخ دلار» stat card: newest valid rate, its age, and a failed-last-try warning (D-080)."""
    from apps.shared.rate_card import usd_rate_context

    # One builder for the page tag and the htmx refresh view, so both render the same card.
    return usd_rate_context(context.get("request"))


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


@register.filter(name="toman_bare")
def toman_bare(value):
    """The `toman` figure without its unit, for table columns whose header already says «تومان»."""
    return toman(value).removesuffix(" تومان")


@register.simple_tag
def party_link(party):
    """A Customer/Supplier name as a link to its account page, so a name is never a dead end; "—" when empty."""
    from django.urls import reverse

    if not party:
        return "—"
    route = "customers:detail" if party._meta.model_name == "customer" else "purchasing:supplier_detail"
    return format_html('<a class="party-link" href="{}">{}</a>', reverse(route, args=[party.pk]), party.name)


@register.filter(name="toman_split")
def toman_split(value):
    """The `toman` figure and its unit as two spans, so a large tile can set the unit small (dashboard)."""
    if value is None:
        return ""
    figure = toman(value).removesuffix(" تومان")
    return format_html('<span class="money__fig">{}</span> <span class="money__unit">تومان</span>', figure)


@register.filter(name="money")
def money(value):
    """Money for table cells and prose: same text as `toman`, but the figure and the unit are two nodes
    and the sign / zero state is a class, so every amount can be styled once (figure strong, unit quiet,
    negative red, zero muted). Use `toman` for attributes, JS, toasts and print."""
    if value is None:
        return ""
    figure = toman(value).removesuffix(" تومان")
    try:
        negative = value < 0
    except TypeError:
        negative = str(value).strip().startswith("-")
    # A zero amount reads as "nothing", not as a balance (no non-zero digit anywhere in the figure).
    zero = not negative and not any(ch in "123456789۱۲۳۴۵۶۷۸۹" for ch in figure)
    cls = "money" + (" is-neg" if negative else "") + (" is-zero" if zero else "")
    return format_html('<span class="{}"><span class="money__fig">{}</span> <span class="money__unit">تومان</span></span>', cls, figure)


@register.filter(name="toman_words")
def toman_words(value):
    """"یک هزار و دویست تومان" -- the amount in words for a printed invoice."""
    if value is None:
        return ""
    return f"{number_to_words(value)} تومان"


@register.filter(name="fa_percent")
def fa_percent(value):
    """A percentage with at most one decimal, «+۱۲٫۹٪»; `fa_number` truncates to an int, which turned +12.9% into +12
    and -0.6% into 0."""
    if value is None:
        return ""
    rounded = round(float(value), 1)
    text = f"{abs(rounded):.1f}".removesuffix(".0").replace(".", "٫")
    figure = dates.to_persian_digits(text)
    if rounded < 0:
        return _keep_sign_left(f"-{figure}٪")
    return f"{figure}٪"


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
    # Oversold stock reads «منفی ۲ کارتن + ۴ بسته»: a minus before each part flips in an RTL run.
    prefix = "منفی " if quantity < 0 else ""
    quantity = abs(quantity)
    cartons, packs = split_units(quantity, pack_per_carton)
    text = units_phrase(cartons, packs)
    if cartons:
        text += f" ({quantity} بسته)"
    return dates.to_persian_digits(prefix + text)


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
    from apps.shared.services import display_document_number

    return display_document_number(str(value))


@register.filter(name="ident")
def ident(value):
    """A phone, SKU, cheque or supplier-invoice number: Persian digits, laid out as ONE
    left-to-right run isolated from the Persian around it, so «0912 345 6789» or
    «INV-12/3» never reorder next to a colon or a « · » separator."""
    if value in (None, ""):
        return ""
    return format_html('<bdi dir="ltr" class="ident">{}</bdi>', dates.to_persian_digits(str(value)))


@register.filter(name="dash")
def dash(value, label="ثبت نشده"):
    """One look for «no value»: a muted dash that screen readers voice as `label`.
    Falsy values behave like `default`, so a template can swap `|default:"—"` for `|dash`."""
    if not value:
        return format_html(
            '<span class="nil" title="{0}"><span aria-hidden="true">—</span><span class="sr-only">{0}</span></span>',
            label,
        )
    return value


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


# One icon set for actions, the same hand-drawn language as the drawer's nav glyphs:
# 24x24 grid, stroke only, so every glyph inherits currentColor. One name = one meaning app-wide.
_ICONS = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "print": '<path d="M7 9V4h10v5"/><path d="M7 17H5a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2"/><path d="M7 14h10v6H7z"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "filter": '<path d="M4 6h16l-6 7.5V19l-4-2v-3.5z"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    "pay": '<rect x="3.5" y="6" width="17" height="12" rx="2"/><path d="M3.5 10h17"/><path d="M7 14.5h3"/>',
    "invoice": '<path d="M6 4h9l4 4v12H6z"/><path d="M15 4v4h4"/><path d="M9.5 13h6"/><path d="M9.5 16.5h4"/>',
    "undo": '<path d="M9 8 5 12l4 4"/><path d="M5 12h9a4 4 0 0 1 0 8h-2"/>',
    "ban": '<circle cx="12" cy="12" r="8"/><path d="m6.5 17.5 11-11"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
    "alert": '<path d="M12 4.5 21 19H3z"/><path d="M12 10v4"/><path d="M12 16.8v.2"/>',
    "arrow_in": '<path d="M17 7 7 17"/><path d="M7 9v8h8"/>',
    "arrow_out": '<path d="M7 17 17 7"/><path d="M9 7h8v8"/>',
}


@register.simple_tag
def icon(name, extra=""):
    """Inline decorative SVG from the shared action set; the Persian label always stays next to it.
    Unknown names render nothing, so a typo never breaks a page."""
    body = _ICONS.get(name)
    if not body:
        return ""
    return format_html('<svg class="icon {}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{}</svg>', extra, mark_safe(body))


@register.filter(name="peak")
def peak(rows, attr):
    """Largest |value| of `attr` across a list of dicts or objects: the 100% mark for `{% meter %}`."""
    best = 0
    for row in rows or []:
        try:
            raw = row[attr] if isinstance(row, dict) else getattr(row, attr)
            best = max(best, abs(int(raw)))
        except (KeyError, AttributeError, TypeError, ValueError):
            continue
    return best


@register.simple_tag
def meter(value, peak_value, tone="", signed=False):
    """A decorative magnitude bar sized value/peak (the figure beside it carries the real value).
    `tone` is "pos", "neg" or "quiet"; `signed` draws a zero-centred bar for profit / balance."""
    try:
        v = int(value)
        p = int(peak_value)
    except (TypeError, ValueError):
        return ""
    pct = min(100, abs(v) * 100 // p) if p else 0
    cls = ["meter"]
    if signed:
        cls += ["meter--signed", "meter--neg" if v < 0 else "meter--pos"]
    elif tone in ("pos", "neg", "quiet"):
        cls.append(f"meter--{tone}")
    elif v < 0:
        cls.append("meter--neg")
    if not pct:
        cls.append("meter--empty")
    return format_html('<span class="{}" style="--v:{}" aria-hidden="true"></span>', " ".join(cls), pct)


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


@register.inclusion_tag("shared/_sort_chips.html", takes_context=True)
def sort_chips(context, *pairs):
    """Sort links as chips ("label:key" each) for phones, where card layouts hide the sortable table header (D-095)."""
    request = context["request"]
    direction = context.get("sort_dir", "asc")
    chips = []
    for pair in pairs:
        label, key = pair.rsplit(":", 1)
        active = context.get("sort_key") == key
        chips.append({
            "label": label, "key": key, "active": active, "direction": direction,
            "next_dir": "desc" if active and direction == "asc" else "asc",
        })
    return {"chips": chips, "query": _query_without(request, "sort", "dir", "page")}


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

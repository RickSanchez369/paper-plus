# path: apps/shared/templatetags/paper.py

"""
Display filters for templates. These never change how a value is stored.

Money formatting already lived in apps/shared/utils.py; the date filters
wrap apps/shared/dates.py so no template ever converts a calendar itself.
"""

from django import template

from apps.shared import dates
from apps.shared.utils import format_number, format_toman

register = template.Library()


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


@register.filter(name="toman")
def toman(value):
    """"۲۵۰٬۰۰۰ تومان" with Persian digits -- the one money filter (D-043)."""
    if value is None:
        return ""
    return dates.to_persian_digits(format_toman(value)).replace(",", "٬")


@register.filter(name="fa_number")
def fa_number(value):
    """A plain count in Persian digits: quantities, invoice counts, page numbers."""
    if value is None:
        return ""
    return dates.to_persian_digits(format_number(value)).replace(",", "٬")


@register.filter(name="dict_get")
def dict_get(mapping, key):
    """`{{ mapping|dict_get:key }}` -- a template's `.` lookup only reads a
    literal attribute name, never a loop variable's value; User Activity's
    per-bucket columns are built from one shared `bucket_order` loop, so
    this is the one place that needs it."""
    return mapping.get(key)

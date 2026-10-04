# path: apps/payments/templatetags/dues_ui.py

"""
Display helpers for the dues pages and the cheque pages (G044): one graded
"how soon" chip instead of a binary overdue badge. Pure presentation -- the
day counts come from dates the views already hold.
"""

from django import template
from django.utils.html import format_html

from apps.shared.templatetags.paper import fa_number

register = template.Library()


@register.filter(name="days_from")
def days_from(due_date, today):
    """Whole days from `today` to `due_date` (negative = late); None when either is missing."""
    if due_date is None or today is None:
        return None
    return (due_date - today).days


@register.filter(name="due_tier")
def due_tier(days_left):
    """late / today / soon / later for a day count -- the row-tint class suffix; "" when unknown."""
    if days_left is None or days_left == "":
        return ""
    if days_left < 0:
        return "late"
    if days_left == 0:
        return "today"
    return "soon" if days_left <= 7 else "later"


@register.simple_tag
def due_chip(days_left, soon_days=7):
    """Graded chip: N days late / today / N days left. Words and a dot, never colour alone."""
    if days_left is None or days_left == "":
        return ""
    if days_left < 0:
        tone, text = "late", f"{fa_number(-days_left)} روز تأخیر"
    elif days_left == 0:
        tone, text = "today", "امروز"
    elif days_left <= soon_days:
        tone, text = "soon", f"{fa_number(days_left)} روز دیگر"
    else:
        tone, text = "later", f"{fa_number(days_left)} روز دیگر"
    return format_html('<span class="badge badge--due-{}">{}</span>', tone, text)

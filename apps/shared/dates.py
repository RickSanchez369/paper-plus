# path: apps/shared/dates.py

"""
Jalali is the calendar this business works in; Gregorian/UTC is what the
database stores (D-004, now actually implemented).

Everything that turns a stored date into something a user reads, or a
typed date into something the database accepts, goes through this module.
No view, template or form does its own conversion — otherwise "which
calendar is this number in" becomes a question you have to answer per call
site, which is exactly how off-by-one date bugs get in.

Digits: users type Persian (۱۴۰۵/۰۷/۰۳), and sometimes Arabic-Indic
(١٤٠٥/٠٧/٠٣) when their keyboard layout differs, and sometimes ASCII when
pasting. All three are accepted on input; output is always Persian.
"""

import datetime
import re

import jdatetime

# Persian (U+06F0..U+06F9) and Arabic-Indic (U+0660..U+0669) digits, mapped
# to ASCII so one parser handles every keyboard.
_TO_ASCII = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_TO_PERSIAN = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# Accepts 1405/7/3, 1405-07-03 and 1405.07.03 — people type all three.
_DATE_PATTERN = re.compile(r"^\s*(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*$")

MONTH_NAMES = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)

# jdatetime weekday(): 0 is Saturday, matching how a Persian calendar reads.
WEEKDAY_NAMES = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه")


def to_ascii_digits(value):
    """Normalise Persian/Arabic-Indic digits to ASCII for parsing."""
    return str(value).translate(_TO_ASCII)


def to_persian_digits(value):
    """Turn ASCII digits into Persian ones for display."""
    return str(value).translate(_TO_PERSIAN)


def to_jalali(value):
    """
    A stored date (or datetime) as a `jdatetime.date`.

    A datetime is converted in the active timezone first: a sale confirmed
    at 01:00 Tehran belongs to that Jalali day, not to the UTC one before it.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        from django.utils import timezone

        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return jdatetime.date.fromgregorian(date=value)


def format_date(value, with_month_name=False):
    """
    "۱۴۰۵/۰۷/۰۳", or "۳ مهر ۱۴۰۵" when a sentence reads better than a code.

    Returns "" for None so a template never prints "None".
    """
    jalali = to_jalali(value)
    if jalali is None:
        return ""
    if with_month_name:
        return to_persian_digits(f"{jalali.day} {MONTH_NAMES[jalali.month - 1]} {jalali.year}")
    return to_persian_digits(f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}")


def format_datetime(value):
    """"۱۴۰۵/۰۷/۰۳ ساعت ۱۴:۳۰" — for audit rows, where the time matters."""
    if value is None:
        return ""
    from django.utils import timezone

    local = timezone.localtime(value) if timezone.is_aware(value) else value
    return f"{format_date(local)} ساعت {to_persian_digits(local.strftime('%H:%M'))}"


def parse_jalali(text):
    """
    Parse a typed Jalali date into a Gregorian `datetime.date`.

    Returns None when the text is not a date at all, and raises ValueError
    when it looks like one but is not real (1405/13/01, or 1405/12/30 in a
    year that has no such day). The two cases get different messages in the
    form field: one is "fill this in", the other is "that day does not exist".
    """
    if text is None:
        return None
    match = _DATE_PATTERN.match(to_ascii_digits(text))
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    # jdatetime raises for an out-of-range month/day, including the leap-year
    # case for 30 Esfand, which a plain range check would let through.
    return jdatetime.date(year, month, day).togregorian()


def today():
    """Today as a `jdatetime.date`, in the active (Tehran) timezone."""
    from django.utils import timezone

    return to_jalali(timezone.localdate())


def month_bounds(jalali_year, jalali_month):
    """
    First and last Gregorian dates of a Jalali month.

    Used by the date-range picker's "this month", which must mean the
    Jalali month the user is looking at, not the Gregorian one.
    """
    first = jdatetime.date(jalali_year, jalali_month, 1)
    if jalali_month == 12:
        next_first = jdatetime.date(jalali_year + 1, 1, 1)
    else:
        next_first = jdatetime.date(jalali_year, jalali_month + 1, 1)
    return first.togregorian(), next_first.togregorian() - datetime.timedelta(days=1)


def week_bounds(gregorian_date):
    """
    First and last Gregorian dates of the Jalali week containing a date.

    The Persian week starts on Saturday, which `jdatetime.date.weekday()`
    already numbers as 0 — using Python's own weekday() here would silently
    start the week on Monday and quietly shift every weekly total.
    """
    jalali = to_jalali(gregorian_date)
    start = gregorian_date - datetime.timedelta(days=jalali.weekday())
    return start, start + datetime.timedelta(days=6)


def month_grid(jalali_year, jalali_month):
    """
    One month laid out for the date picker: leading blanks, then each day.

    Lives here, not in JavaScript. An earlier version of the picker carried
    its own copy of the Jalali conversion, and the two implementations
    disagreed about which years are leap (they use different approximations
    of the 33-year cycle) -- so the calendar offered a day the server then
    refused to parse. There is one calendar in this app, and it is this
    module.

    Each day carries the exact string `JalaliDateField` would parse, so
    clicking a cell cannot produce something the form rejects.
    """
    first = jdatetime.date(jalali_year, jalali_month, 1)
    if jalali_month == 12:
        next_first = jdatetime.date(jalali_year + 1, 1, 1)
    else:
        next_first = jdatetime.date(jalali_year, jalali_month + 1, 1)
    day_count = (next_first.togregorian() - first.togregorian()).days

    current = today()
    days = []
    for day in range(1, day_count + 1):
        jalali = jdatetime.date(jalali_year, jalali_month, day)
        days.append({
            "day": to_persian_digits(day),
            "value": to_persian_digits(f"{jalali_year:04d}/{jalali_month:02d}/{day:02d}"),
            "is_today": jalali == current,
        })

    return {
        "year": jalali_year,
        "month": jalali_month,
        # weekday(): 0 is Saturday, which is where a Persian week starts.
        "leading_blanks": range(first.weekday()),
        "title": f"{MONTH_NAMES[jalali_month - 1]} {to_persian_digits(jalali_year)}",
        "days": days,
    }


def clamp_month(year, month):
    """
    Normalise a year/month the client asked for, rolling over at the edges.

    The picker moves a month at a time with plain integer arithmetic, so it
    can hand us month 0 or 13; turning those into the neighbouring year here
    keeps that arithmetic out of the JavaScript, where it would be a second
    place to get the calendar wrong.
    """
    year, month = int(year), int(month)
    if month < 1:
        year, month = year - 1, 12
    elif month > 12:
        year, month = year + 1, 1
    # jdatetime supports a wide range; these bounds are simply the years a
    # trading business could plausibly file a document in.
    year = max(1300, min(year, 1500))
    return year, month

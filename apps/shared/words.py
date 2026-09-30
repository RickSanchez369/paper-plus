# path: apps/shared/words.py

"""A whole number spelled out in Persian, for the printed invoice's
"amount in words" line (the line a stamp-and-sign invoice is expected to have)."""

_ONES = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده",
         "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
_TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
_HUNDREDS = ["", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]
_SCALES = ["", "هزار", "میلیون", "میلیارد", "هزار میلیارد"]


def _below_thousand(n):
    parts = []
    if n >= 100:
        parts.append(_HUNDREDS[n // 100])
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10])
        n %= 10
    if n:
        parts.append(_ONES[n])
    return " و ".join(parts)


def number_to_words(value):
    """0 -> "صفر", 1250 -> "یک هزار و دویست و پنجاه". Negative gets "منفی"."""
    n = int(value)
    if n == 0:
        return "صفر"
    if n < 0:
        return "منفی " + number_to_words(-n)
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000
    if len(groups) > len(_SCALES):
        return str(value)           # beyond what an invoice can hold: show digits
    parts = []
    for index in range(len(groups) - 1, -1, -1):
        chunk = groups[index]
        if not chunk:
            continue
        text = _below_thousand(chunk)
        parts.append(f"{text} {_SCALES[index]}".strip())
    return " و ".join(parts)

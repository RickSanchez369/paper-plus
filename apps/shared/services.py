# path: apps/shared/services.py

from django.db import transaction

from apps.shared import dates
from apps.shared.models import DocumentSequence


# The 32 letters of the Persian alphabet, in dictionary order (D-086).
PERSIAN_LETTERS = (
    "الف", "ب", "پ", "ت", "ث", "ج", "چ", "ح", "خ", "د", "ذ", "ر", "ز", "ژ", "س", "ش",
    "ص", "ض", "ط", "ظ", "ع", "غ", "ف", "ق", "ک", "گ", "ل", "م", "ن", "و", "ه", "ی",
)
# Arabic letter mark: keeps a round digit ("الف2") on the letter's side of the
# slash when the number is laid out right-to-left; display only, never stored.
_ALM = "؜"


def format_document_number(year, number):
    """1405, 42 -> "1405/0042": Jalali year, then the running number of that year."""
    return f"{year}/{number:04d}"


def format_sale_number(jalali_date, number):
    """
    The n-th sale of a Jalali day (D-086): 12 Mehr 1405, 2 -> "ب/14050712".

    After the 32nd letter the alphabet starts again with a round number:
    33 -> "الف2/14050712", 65 -> "الف3/...". Digits are stored ASCII, like
    every other document number; templates show them in Persian.
    """
    rnd, index = divmod(number - 1, len(PERSIAN_LETTERS))
    letter = PERSIAN_LETTERS[index] + (str(rnd + 1) if rnd else "")
    return f"{letter}/{jalali_date.year:04d}{jalali_date.month:02d}{jalali_date.day:02d}"


def display_document_number(value):
    """A stored number in Persian digits, with the bidi mark a lettered round needs."""
    text = dates.to_persian_digits(value)
    head, sep, tail = text.partition("/")
    if sep and head[-1:].isdigit() and not head.isdigit():
        return f"{head}{_ALM}{sep}{tail}"
    return text


def get_next_document_number(doc_type, on_date=None):
    """
    Atomically issue the next invoice number for ``doc_type`` (D-064).

    The number is "<Jalali year>/<running number>", e.g. "1405/0042"; the
    running number restarts at 1 every Farvardin, like a paper invoice book.
    The year's DocumentSequence row is created on first use, then locked with
    select_for_update() so two invoices confirmed at the same instant (two
    users, two tabs) can never receive the same number. .get() is used, not
    .filter().first(): select_for_update() on an un-evaluated queryset locks
    nothing, only a fetched row does.

    Sales are numbered per Jalali day of the invoice's own date instead
    (D-086): "الف/14050712", "ب/14050712", ... one counter row per day.

    Args:
        doc_type: one of DocumentSequence.DocType values ("sale"/"purchase").
        on_date: the invoice date (a Gregorian date) that a sale number is
            built from; today when omitted. Purchases ignore it.

    Returns:
        str: the number to assign to this document.
    """
    is_sale = doc_type == DocumentSequence.DocType.SALE
    when = dates.to_jalali(on_date) if (is_sale and on_date) else dates.today()
    day = when.month * 100 + when.day if is_sale else 0
    with transaction.atomic():
        row, _ = DocumentSequence.objects.get_or_create(doc_type=doc_type, year=when.year, day=day)
        seq = DocumentSequence.objects.select_for_update().get(pk=row.pk)
        issued_number = seq.next_number
        seq.next_number += 1
        seq.save(update_fields=["next_number"])
        if is_sale:
            return format_sale_number(when, issued_number)
        return format_document_number(when.year, issued_number)

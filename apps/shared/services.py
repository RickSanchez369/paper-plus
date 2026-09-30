# path: apps/shared/services.py

from django.db import transaction

from apps.shared import dates
from apps.shared.models import DocumentSequence


def format_document_number(year, number):
    """1405, 42 -> "1405/0042": Jalali year, then the running number of that year."""
    return f"{year}/{number:04d}"


def get_next_document_number(doc_type):
    """
    Atomically issue the next invoice number for ``doc_type`` (D-064).

    The number is "<Jalali year>/<running number>", e.g. "1405/0042"; the
    running number restarts at 1 every Farvardin, like a paper invoice book.
    The year's DocumentSequence row is created on first use, then locked with
    select_for_update() so two invoices confirmed at the same instant (two
    users, two tabs) can never receive the same number. .get() is used, not
    .filter().first(): select_for_update() on an un-evaluated queryset locks
    nothing, only a fetched row does.

    Args:
        doc_type: one of DocumentSequence.DocType values ("sale"/"purchase").

    Returns:
        str: the number to assign to this document.
    """
    year = dates.today().year
    with transaction.atomic():
        row, _ = DocumentSequence.objects.get_or_create(doc_type=doc_type, year=year)
        seq = DocumentSequence.objects.select_for_update().get(pk=row.pk)
        issued_number = seq.next_number
        seq.next_number += 1
        seq.save(update_fields=["next_number"])
        return format_document_number(year, issued_number)

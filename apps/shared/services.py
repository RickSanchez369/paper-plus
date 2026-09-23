# path: apps/shared/services.py

from django.db import transaction

from apps.shared.models import DocumentSequence


def get_next_document_number(business, doc_type):
    """
    Atomically issue the next invoice number for (business, doc_type).

    The DocumentSequence row for this business+doc_type is locked with
    select_for_update() so two invoices confirmed at the same instant
    (e.g. two sellers, two browser tabs) can never receive the same
    number. .get() is used, not .filter().first(): select_for_update()
    on an un-evaluated queryset locks nothing, only a fetched row does.

    Does not create the sequence row — DocumentSequence rows are
    created once per business at onboarding (roadmap 3.2), with a
    configurable starting number. Calling this before that row exists
    is a bug, not a case to silently patch over.

    Args:
        business: shared.Business instance.
        doc_type: one of DocumentSequence.DocType values ("sale"/"purchase").

    Returns:
        int: the number to assign to this document.

    Raises:
        DocumentSequence.DoesNotExist: no sequence row for this
            business+doc_type yet.
    """
    with transaction.atomic():
        seq = DocumentSequence.objects.select_for_update().get(
            business=business,
            doc_type=doc_type,
        )
        issued_number = seq.next_number
        seq.next_number += 1
        seq.save(update_fields=["next_number"])
        return issued_number
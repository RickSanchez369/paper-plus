# path: apps/shared/audit.py

"""Helper for writing AuditLog rows from inside services (D-029)."""

from apps.shared.models import AuditLog


def log_event(*, business, actor, event_type, target, payload=None):
    """
    Record one AuditLog row for a service-level event.

    `target` is any model instance with a `pk`; its class label
    (e.g. "purchasing.purchaseinvoice") and pk are stored so the
    log stays a plain FK-free reference (D-029).
    """
    AuditLog.objects.create(
        business=business,
        actor=actor,
        event_type=event_type,
        target_type=target._meta.label_lower,
        target_id=target.pk,
        payload=payload or {},
    )
# path: apps/payments/selectors.py

"""Read-only queries over payments (ROADMAP 4.3). Selectors never write."""

from django.db.models import BigIntegerField, Case, F, Sum, When

from .models import Payment


def get_bank_account_balance(bank_account):
    """Net money moved through this account: IN payments minus OUT payments."""
    result = Payment.objects.filter(bank_account=bank_account).aggregate(
        balance=Sum(
            Case(
                When(direction=Payment.Direction.IN, then=F("amount")),
                default=-F("amount"),
                output_field=BigIntegerField(),
            )
        )
    )
    return result["balance"] or 0


def get_supplier_outstanding(supplier):
    """
    Accounts payable: this supplier's unpaid balance across its confirmed
    purchase invoices (REDESIGN_VISION 4.2's Suppliers sub-section, and
    the Payables page later -- one selector, so the two can never disagree).

    Summed per-invoice (total minus paid, clamped at 0) rather than one
    supplier-wide total minus total paid, so an overpayment on one invoice
    never offsets what is still genuinely owed on another (D-025: derived,
    never stored).
    """
    from apps.purchasing.models import PurchaseInvoice

    invoices = PurchaseInvoice.objects.filter(
        supplier=supplier, status=PurchaseInvoice.Status.CONFIRMED,
    ).prefetch_related("payment_allocations")
    return sum(max(invoice.total_amount - invoice.paid_amount, 0) for invoice in invoices)

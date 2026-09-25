# path: apps/payments/selectors.py

"""Read-only queries over payments (ROADMAP 4.3). Selectors never write."""

from django.db.models import BigIntegerField, Case, F, Sum, When

from .models import Payment


def get_bank_account_balance(bank_account, as_of=None):
    """
    Net money moved through this account: IN payments minus OUT payments.

    `as_of` (a date) restricts the ledger to payments on or before that
    day, for the Bank Accounts comparison cards (REDESIGN_VISION 4.5) --
    "the balance as it stood then", not a separate stored snapshot.
    """
    qs = Payment.objects.filter(bank_account=bank_account)
    if as_of is not None:
        qs = qs.filter(payment_date__lte=as_of)
    result = qs.aggregate(
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
    the Payables page -- one selector, so the two can never disagree).

    Summed per-invoice (`invoice.outstanding`, already clamped at 0) rather
    than one supplier-wide total minus total paid, so an overpayment on one
    invoice never offsets what is still genuinely owed on another
    (D-025: derived, never stored).
    """
    from apps.purchasing.models import PurchaseInvoice

    invoices = PurchaseInvoice.objects.filter(
        supplier=supplier, status=PurchaseInvoice.Status.CONFIRMED,
    ).prefetch_related("payment_allocations")
    return sum(invoice.outstanding for invoice in invoices)


def get_customer_outstanding(customer):
    """
    Accounts receivable: this customer's unpaid balance across its
    confirmed sales invoices (REDESIGN_VISION 4.4/4.7) -- the exact mirror
    of `get_supplier_outstanding`, shared by the Receivables page and the
    Customer-detail statement so the two can never disagree.
    """
    from apps.sales.models import SalesInvoice

    invoices = SalesInvoice.objects.filter(
        customer=customer, status=SalesInvoice.Status.CONFIRMED,
    ).prefetch_related("payment_allocations")
    return sum(invoice.outstanding for invoice in invoices)


def get_open_invoices(model, **party_filter):
    """
    This party's confirmed invoices that still owe something, oldest
    first -- the order a payment should settle them in by default. Shared
    by Receivables/Payables and the Customer/Supplier detail pages so the
    "record payment" form always offers the same invoice list, however the
    page got there.
    """
    invoices = (
        model.objects.filter(status=model.Status.CONFIRMED, **party_filter)
        .prefetch_related("payment_allocations")
        .order_by("invoice_date")
    )
    return [invoice for invoice in invoices if invoice.outstanding > 0]

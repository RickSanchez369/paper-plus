# path: apps/payments/selectors.py

"""Read-only queries over payments (ROADMAP 4.3). Selectors never write."""

import datetime

from django.db.models import BigIntegerField, Case, F, Sum, When

from .models import Payment


def get_bank_account_balance(bank_account, as_of=None):
    """
    Net money moved through this account: IN payments minus OUT payments.

    `as_of` (a date) restricts the ledger to payments on or before that
    day, for the Bank Accounts comparison cards --
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
    purchase invoices.

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
    confirmed sales invoices -- the exact mirror
    of `get_supplier_outstanding`, shared by the Receivables page and the
    Customer-detail statement so the two can never disagree.
    """
    from apps.sales.models import SalesInvoice

    invoices = SalesInvoice.objects.filter(
        customer=customer, status=SalesInvoice.Status.CONFIRMED,
    ).prefetch_related("payment_allocations")
    return sum(invoice.outstanding for invoice in invoices)


def get_total_receivables_as_of(as_of):
    """
    Business-wide accounts receivable as of a past date: confirmed sales invoices dated on or before
    `as_of`, minus only the allocations whose own payment happened by then
    -- a payment made after `as_of` must not retroactively shrink a past
    report's outstanding figure.
    """
    from apps.sales.models import SalesInvoice

    invoices = SalesInvoice.objects.filter(
        status=SalesInvoice.Status.CONFIRMED, invoice_date__lte=as_of,
    ).prefetch_related("payment_allocations__payment")
    total = 0
    for invoice in invoices:
        paid = sum(
            allocation.amount
            for allocation in invoice.payment_allocations.all()
            if allocation.payment.payment_date <= as_of
        )
        total += max(invoice.total - paid, 0)
    return total


def get_total_payables_as_of(as_of):
    """Exact mirror of `get_total_receivables_as_of`, Supplier/PurchaseInvoice side."""
    from apps.purchasing.models import PurchaseInvoice

    invoices = PurchaseInvoice.objects.filter(
        status=PurchaseInvoice.Status.CONFIRMED, invoice_date__lte=as_of,
    ).prefetch_related("payment_allocations__payment")
    total = 0
    for invoice in invoices:
        paid = sum(
            allocation.amount
            for allocation in invoice.payment_allocations.all()
            if allocation.payment.payment_date <= as_of
        )
        total += max(invoice.total_amount - paid, 0)
    return total


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


def _pending_cheque_sum(invoice_field, invoice):
    from .models import Cheque

    return sum(
        c.amount
        for c in Cheque.objects.filter(**{invoice_field: invoice}, status=Cheque.Status.PENDING)
    )


def get_credit_items(model):
    """
    The unpaid, not-yet-chequed part of each open invoice -- the نسیه a party
    still owes on account (D-071). ``[{"invoice", "amount", "due_date"}]``,
    soonest due first, undated ones last.

    An invoice's outstanding includes cheques still pending (they are not
    money yet, D-039), but those are listed on their own with their own due
    dates; this is only what is left after taking them out. Derived on every
    read, never stored (D-025).
    """
    invoice_field = "sales_invoice" if model.__name__ == "SalesInvoice" else "purchase_invoice"
    items = []
    invoices = model.objects.filter(status=model.Status.CONFIRMED).select_related(
        "customer" if invoice_field == "sales_invoice" else "supplier"
    ).prefetch_related("payment_allocations")
    for invoice in invoices:
        outstanding = invoice.outstanding
        if outstanding <= 0:
            continue
        credit = outstanding - _pending_cheque_sum(invoice_field, invoice)
        if credit > 0:
            items.append({"invoice": invoice, "amount": credit, "due_date": invoice.credit_due_date})
    items.sort(key=lambda i: (i["due_date"] is None, i["due_date"] or datetime.date.max, i["invoice"].invoice_date))
    return items


def get_pending_cheques(direction):
    """Pending cheques of one direction (in = from customers, out = to suppliers), soonest due first."""
    from .models import Cheque

    return list(
        Cheque.objects.filter(status=Cheque.Status.PENDING, direction=direction)
        .select_related("customer", "supplier", "bank_account", "sales_invoice", "purchase_invoice")
        .order_by("due_date", "created_at")
    )


def get_expense_reminders(today=None, window_days=7):
    """
    Expense payments that are due soon or already overdue (D-073, D-074),
    soonest first: fixed costs whose reminder window has opened, and unpaid
    نسیه expenses with a due date inside ``window_days``.

    ``[{"kind", "label", "amount", "due_date", "days_left", "overdue", "url_name", "url_args"}]``.
    Cheques are not here -- a pending cheque already has its own due date and
    row (see `get_upcoming_payments`).
    """
    from .models import Expense, RecurringExpense

    today = today or datetime.date.today()
    items = []
    for item in RecurringExpense.objects.filter(is_active=True):
        days_left = (item.next_due_date - today).days
        if days_left <= item.remind_days_before:
            items.append({
                "kind": "recurring", "label": item.reason, "amount": item.amount,
                "due_date": item.next_due_date, "days_left": days_left, "overdue": days_left < 0,
                "obj": item,
            })
    for expense in Expense.objects.filter(
        cancelled_at__isnull=True, payment__isnull=True, due_date__isnull=False,
        payment_method=Expense.PaymentMethod.CREDIT,
    ):
        days_left = (expense.due_date - today).days
        if days_left <= window_days:
            items.append({
                "kind": "expense", "label": expense.reason, "amount": expense.amount,
                "due_date": expense.due_date, "days_left": days_left, "overdue": days_left < 0,
                "obj": expense,
            })
    items.sort(key=lambda i: i["due_date"])
    return items


def get_upcoming_payments(today=None, window_days=7):
    """
    Everything the business has to PAY in the next ``window_days`` days, and
    whatever is already late (D-074), as one date-ordered list for the
    dashboard: cheques we issued (to suppliers or for expenses), unpaid
    expenses, fixed costs about to fall due, and supplier credit coming due.

    ``[{"kind", "label", "amount", "due_date", "days_left", "overdue", "obj"}]``
    with ``kind`` in cheque / expense / recurring / supplier_credit.
    """
    from apps.purchasing.models import PurchaseInvoice

    from .models import Cheque

    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=window_days)
    items = list(get_expense_reminders(today, window_days))

    for cheque in Cheque.objects.filter(
        status=Cheque.Status.PENDING, direction=Payment.Direction.OUT,
        due_date__isnull=False, due_date__lte=horizon,
    ).select_related("supplier", "expense"):
        who = cheque.supplier.name if cheque.supplier_id else (cheque.expense.reason if cheque.expense_id else "")
        items.append({
            "kind": "cheque", "label": f"چک {cheque.cheque_number or '(بدون شماره)'} — {who}",
            "amount": cheque.amount, "due_date": cheque.due_date,
            "days_left": (cheque.due_date - today).days, "overdue": cheque.due_date < today, "obj": cheque,
        })

    for item in get_credit_items(PurchaseInvoice):
        due = item["due_date"]
        if due is not None and due <= horizon:
            items.append({
                "kind": "supplier_credit",
                "label": f"نسیهٔ فاکتور {item['invoice'].invoice_number} — {item['invoice'].supplier.name}",
                "amount": item["amount"], "due_date": due,
                "days_left": (due - today).days, "overdue": due < today, "obj": item["invoice"],
            })

    items.sort(key=lambda i: i["due_date"])
    return items


def get_upcoming_receivables(today=None, window_days=10):
    """
    Everything customers owe the business that falls due within
    ``window_days`` days, plus whatever is already late (D-079): cheques we
    hold (direction IN) and sale credit (نسیه). The mirror of
    `get_upcoming_payments`, same row shape, ``kind`` is cheque / customer_credit.
    Settled invoices never appear: money taken by card or transfer is not owed.
    """
    from apps.sales.models import SalesInvoice

    from .models import Cheque

    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=window_days)
    items = []

    for cheque in Cheque.objects.filter(
        status=Cheque.Status.PENDING, direction=Payment.Direction.IN,
        due_date__isnull=False, due_date__lte=horizon,
    ).select_related("customer"):
        who = cheque.customer.name if cheque.customer_id else ""
        items.append({
            "kind": "cheque", "label": f"چک {cheque.cheque_number or '(بدون شماره)'} — {who}",
            "amount": cheque.amount, "due_date": cheque.due_date,
            "days_left": (cheque.due_date - today).days, "overdue": cheque.due_date < today, "obj": cheque,
        })

    for item in get_credit_items(SalesInvoice):
        due = item["due_date"]
        if due is not None and due <= horizon:
            items.append({
                "kind": "customer_credit",
                "label": f"نسیهٔ فاکتور {item['invoice'].invoice_number} — {item['invoice'].customer.name}",
                "amount": item["amount"], "due_date": due,
                "days_left": (due - today).days, "overdue": due < today, "obj": item["invoice"],
            })

    items.sort(key=lambda i: i["due_date"])
    return items

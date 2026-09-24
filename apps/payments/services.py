# path: apps/payments/services.py

"""Write services for payments, their allocation to invoices, and cheques (ROADMAP 4.3, 4.4)."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared.audit import log_event

from .models import Cheque, Expense, Payment, PaymentAllocation


@transaction.atomic
def record_payment(payment, user):
    """
    Validate and save a new Payment (D-012-style: amount always positive,
    `direction` carries the sign). Does not touch any invoice -- see
    `allocate_payment` for that.

    Args:
        payment: an unsaved Payment with direction, amount,
            payment_date, and optionally bank_account/note already set.
        user: the user performing the action; recorded as `created_by`.

    Raises:
        ValidationError: payment already exists, or amount is not positive.
    """
    if not payment._state.adding:
        # pk is never None here (BaseModel.id defaults to uuid4() on
        # construction, before save) -- _state.adding is the real signal.
        raise ValidationError("پرداخت قابل ویرایش نیست.")
    if payment.amount is None or payment.amount <= 0:
        raise ValidationError("مبلغ پرداخت باید بزرگ‌تر از صفر باشد.")
    # A friendly message before payment_party_matches_direction would
    # otherwise surface as a raw IntegrityError.
    if payment.customer_id and payment.supplier_id:
        raise ValidationError("یک پرداخت نمی‌تواند هم‌زمان مشتری و تأمین‌کننده داشته باشد.")
    if payment.customer_id and payment.direction != Payment.Direction.IN:
        raise ValidationError("فقط دریافتی می‌تواند به مشتری نسبت داده شود.")
    if payment.supplier_id and payment.direction != Payment.Direction.OUT:
        raise ValidationError("فقط پرداختی می‌تواند به تأمین‌کننده نسبت داده شود.")
    payment.created_by = user
    payment.save()
    log_event(
        actor=user,
        event_type="record_payment",
        target=payment,
        payload={"direction": payment.direction, "amount": payment.amount},
    )
    return payment


@transaction.atomic
def allocate_payment(allocation, user):
    """
    Validate and save a new PaymentAllocation (D-025).

    Locks the payment and the target invoice so two concurrent allocations
    can never together exceed either one's remaining balance -- the same
    reasoning confirm_sale uses to lock Product rows (D-015).

    Args:
        allocation: an unsaved PaymentAllocation with `payment`, exactly
            one of `sales_invoice`/`purchase_invoice`, and `amount` set.
        user: the user performing the action.

    Returns:
        The same allocation, now saved.

    Raises:
        ValidationError: allocation already exists; not exactly one
            invoice side is set; the invoice is not confirmed; the
            payment's direction does not match the invoice side (IN -> sales,
            OUT -> purchase); amount exceeds the payment's or the
            invoice's remaining balance.
    """
    if not allocation._state.adding:
        # pk is never None here (BaseModel.id defaults to uuid4() on
        # construction, before save) -- _state.adding is the real signal.
        raise ValidationError("تخصیص پرداخت قابل ویرایش نیست.")

    if bool(allocation.sales_invoice_id) == bool(allocation.purchase_invoice_id):
        raise ValidationError("دقیقاً یکی از فاکتور فروش یا خرید باید انتخاب شود.")

    if allocation.amount is None or allocation.amount <= 0:
        raise ValidationError("مبلغ تخصیص باید بزرگ‌تر از صفر باشد.")

    payment = Payment.objects.select_for_update().get(pk=allocation.payment_id)

    if allocation.sales_invoice_id:
        if payment.direction != Payment.Direction.IN:
            raise ValidationError("پرداخت خروجی («پرداخت») به فاکتور فروش تخصیص نمی‌یابد.")
        invoice = SalesInvoice.objects.select_for_update().get(pk=allocation.sales_invoice_id)
        remaining_on_invoice = invoice.total - invoice.paid_amount
    else:
        if payment.direction != Payment.Direction.OUT:
            raise ValidationError("پرداخت ورودی («دریافت») به فاکتور خرید تخصیص نمی‌یابد.")
        invoice = PurchaseInvoice.objects.select_for_update().get(pk=allocation.purchase_invoice_id)
        remaining_on_invoice = invoice.total_amount - invoice.paid_amount

    if invoice.status != invoice.Status.CONFIRMED:
        raise ValidationError("فقط فاکتور تأییدشده قابل تخصیص پرداخت است.")

    if allocation.amount > payment.unallocated_amount:
        raise ValidationError("مبلغ تخصیص از باقیماندهٔ پرداخت بیشتر است.")

    if allocation.amount > remaining_on_invoice:
        raise ValidationError("مبلغ تخصیص از باقیماندهٔ فاکتور بیشتر است.")

    allocation.save()
    log_event(
        actor=user,
        event_type="allocate_payment",
        target=allocation,
        payload={"amount": allocation.amount},
    )
    return allocation


@transaction.atomic
def record_cheque(cheque, user):
    """
    Validate and save a new Cheque, status always PENDING at creation.

    A pending cheque is not yet money (Sina's call, 2026-09-24): no Payment
    is created here. See `clear_cheque`/`bounce_cheque` for the two ways
    a pending cheque is closed out.

    Args:
        cheque: an unsaved Cheque with direction, exactly one of
            customer/supplier, cheque_number, due_date, amount, and
            optionally bank_account/bank_name/note already set.
        user: the user performing the action.

    Raises:
        ValidationError: cheque already exists; amount is not positive; or
            the direction/party pair is invalid.
    """
    if not cheque._state.adding:
        raise ValidationError("چک قابل ویرایش نیست.")
    if cheque.amount is None or cheque.amount <= 0:
        raise ValidationError("مبلغ چک باید بزرگ‌تر از صفر باشد.")
    # A friendly Persian message before the DB CHECK (cheque_direction_matches_party)
    # would otherwise surface a raw IntegrityError.
    if cheque.direction == Payment.Direction.IN:
        if not cheque.customer_id or cheque.supplier_id:
            raise ValidationError("چک دریافتی باید دقیقاً یک مشتری داشته باشد، بدون تأمین‌کننده.")
    elif cheque.direction == Payment.Direction.OUT:
        if not cheque.supplier_id or cheque.customer_id:
            raise ValidationError("چک پرداختی باید دقیقاً یک تأمین‌کننده داشته باشد، بدون مشتری.")
    else:
        raise ValidationError("جهت چک نامعتبر است.")
    cheque.status = Cheque.Status.PENDING
    cheque.save()
    log_event(
        actor=user,
        event_type="record_cheque",
        target=cheque,
        payload={"direction": cheque.direction, "amount": cheque.amount},
    )
    return cheque


@transaction.atomic
def clear_cheque(cheque, user, bank_account=None):
    """
    Mark a pending cheque cleared and create the Payment it represents.

    The cheque's amount and direction become a new Payment (D-025); the
    caller still allocates that Payment to an invoice separately via
    `allocate_payment`, same as any other payment.

    Args:
        cheque: the Cheque to clear (any status; only PENDING succeeds).
        user: the user performing the action.
        bank_account: optional BankAccount to attribute the Payment to;
            defaults to the cheque's own `bank_account`.

    Raises:
        ValidationError: cheque is not pending.
    """
    locked = Cheque.objects.select_for_update().get(pk=cheque.pk)
    if locked.status != Cheque.Status.PENDING:
        raise ValidationError("فقط چک در انتظار وصول قابل وصول‌شدن است.")

    payment = record_payment(
        Payment(
            bank_account=bank_account or locked.bank_account,
            direction=locked.direction,
            # Carry the cheque's own party across, so the money this cheque
            # became is still traceable to a person (REDESIGN_VISION 3).
            customer=locked.customer,
            supplier=locked.supplier,
            amount=locked.amount,
            payment_date=timezone.localdate(),
            note=f"وصول چک {locked.cheque_number}",
        ),
        user,
    )
    locked.payment = payment
    locked.status = Cheque.Status.CLEARED
    locked.save(update_fields=["payment", "status", "updated_at"])

    # Entered from an invoice (4.3b): allocate automatically, no manual
    # second step. A rejection here (e.g. the invoice is already fully
    # paid some other way) rolls back the whole clear -- the cheque stays
    # pending until someone resolves it, instead of clearing with money
    # that has nowhere valid to go.
    if locked.sales_invoice_id:
        allocate_payment(
            PaymentAllocation(payment=payment, sales_invoice_id=locked.sales_invoice_id, amount=locked.amount),
            user,
        )
    elif locked.purchase_invoice_id:
        allocate_payment(
            PaymentAllocation(payment=payment, purchase_invoice_id=locked.purchase_invoice_id, amount=locked.amount),
            user,
        )

    log_event(
        actor=user,
        event_type="clear_cheque",
        target=locked,
        payload={"amount": locked.amount},
    )
    return locked


@transaction.atomic
def bounce_cheque(cheque, user):
    """
    Mark a pending cheque bounced. No Payment is ever created for it --
    the cheque simply stays as history (never deleted, D-024 philosophy).

    Raises:
        ValidationError: cheque is not pending.
    """
    locked = Cheque.objects.select_for_update().get(pk=cheque.pk)
    if locked.status != Cheque.Status.PENDING:
        raise ValidationError("فقط چک در انتظار وصول قابل برگشت‌خوردن است.")

    locked.status = Cheque.Status.BOUNCED
    locked.save(update_fields=["status", "updated_at"])
    log_event(
        actor=user,
        event_type="bounce_cheque",
        target=locked,
        payload={"amount": locked.amount},
    )
    return locked

@transaction.atomic
def cancel_cheque(cheque, user):
    """
    Withdraw a cheque that should never have been entered.

    Reachable only from PENDING, one-way, and financially a no-op: a
    pending cheque was never counted toward any invoice's payment_status
    (ROADMAP 4.4), so there is nothing to reverse and no Payment is
    involved either way. Mirrors `bounce_cheque`'s shape; the row survives
    as history rather than being deleted (REDESIGN_VISION 2.7).

    Raises:
        ValidationError: cheque is not pending.
    """
    locked = Cheque.objects.select_for_update().get(pk=cheque.pk)
    if locked.status != Cheque.Status.PENDING:
        raise ValidationError("فقط چک در انتظار وصول قابل لغو است.")

    locked.status = Cheque.Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    log_event(
        actor=user,
        event_type="cancel_cheque",
        target=locked,
        payload={"amount": locked.amount},
    )
    return locked


@transaction.atomic
def record_expense(expense, user):
    """
    Record a business expense and the money that left with it, together.

    Creates the Payment (direction OUT, no allocations -- an expense
    settles no invoice) and links it to the Expense in one transaction, so
    the two can never exist apart. Reusing the Payment ledger is the whole
    point: bank balances and every cash-flow figure already read from it,
    so an expense needs no parallel accounting path
    (REDESIGN_VISION 3, vision doc 27).

    Args:
        expense: an unsaved Expense with expense_date, amount, reason and
            optionally related_person/bank_account/document/note set.
            `payment` must NOT be set -- this creates it.
        user: the user performing the action; recorded on both rows.

    Raises:
        ValidationError: expense already exists, amount is not positive,
            reason is blank, or a payment was pre-attached.
    """
    if not expense._state.adding:
        raise ValidationError("هزینه قابل ویرایش نیست.")
    if expense.amount is None or expense.amount <= 0:
        raise ValidationError("مبلغ هزینه باید بزرگ‌تر از صفر باشد.")
    if not (expense.reason or "").strip():
        raise ValidationError("ثبت «بابت» برای هزینه الزامی است.")
    if expense.payment_id is not None:
        raise ValidationError("پرداخت هزینه را خود سرویس می‌سازد.")

    expense.payment = record_payment(
        Payment(
            bank_account=expense.bank_account,
            direction=Payment.Direction.OUT,
            amount=expense.amount,
            payment_date=expense.expense_date,
            note=f"هزینه: {expense.reason}",
        ),
        user,
    )
    expense.created_by = user
    expense.save()

    log_event(
        actor=user,
        event_type="record_expense",
        target=expense,
        payload={"amount": expense.amount, "reason": expense.reason},
    )
    return expense


@transaction.atomic
def cancel_expense(expense, user):
    """
    Undo an expense with an opposite entry, never by deleting it.

    Books a Payment of the same amount in the opposite direction against
    the same account, so the bank balance returns to where it was and the
    ledger keeps both halves of the story (REDESIGN_VISION 2.7). The
    Expense row itself stays, flagged cancelled, and stops counting toward
    any total (`counts_toward_totals`).

    Raises:
        ValidationError: expense is already cancelled.
    """
    locked = Expense.objects.select_for_update().get(pk=expense.pk)
    if locked.is_cancelled:
        raise ValidationError("این هزینه قبلاً لغو شده است.")

    locked.reversal_payment = record_payment(
        Payment(
            bank_account=locked.bank_account,
            direction=Payment.Direction.IN,
            amount=locked.amount,
            payment_date=timezone.localdate(),
            note=f"لغو هزینه: {locked.reason}",
        ),
        user,
    )
    locked.cancelled_at = timezone.now()
    locked.cancelled_by = user
    locked.save(update_fields=["reversal_payment", "cancelled_at", "cancelled_by", "updated_at"])

    log_event(
        actor=user,
        event_type="cancel_expense",
        target=locked,
        payload={"amount": locked.amount},
    )
    return locked

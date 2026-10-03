# path: apps/payments/services.py

"""Write services for payments, their allocation to invoices, and cheques (ROADMAP 4.3, 4.4)."""

import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.shared import dates

from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared.audit import log_event
from apps.shared.permissions import is_privileged

from .models import BankAccount, Cheque, Expense, Payment, PaymentAllocation, RecurringExpense

# Which kind of account each way of paying goes through (D-067, D-069). Cash
# is not a way of paying any more; a cheque is always drawn on / deposited
# into a current account.
METHOD_ACCOUNT_TYPE = {
    "card": BankAccount.AccountType.POS,
    "bank_transfer": BankAccount.AccountType.CURRENT,
    "cheque": BankAccount.AccountType.CURRENT,
}


def validate_entry_account(method, bank_account):
    """
    Check one payment row's method against its account (D-069).

    card -> a card-reader account (required); bank_transfer -> a current
    account (required); cheque -> a current account if one is known yet.
    Anything else (including the retired cash method) is refused.

    Raises:
        ValidationError: with a Persian message saying what is wrong.
    """
    if method not in METHOD_ACCOUNT_TYPE:
        raise ValidationError("روش پرداخت نامعتبر است (پرداخت نقدی پشتیبانی نمی‌شود).")
    if bank_account is None:
        if method != "cheque":
            raise ValidationError("برای کارت‌خوان و حواله بانکی انتخاب حساب الزامی است.")
        return
    if bank_account.account_type != METHOD_ACCOUNT_TYPE[method]:
        label = BankAccount.AccountType(METHOD_ACCOUNT_TYPE[method]).label
        raise ValidationError(f"این روش پرداخت فقط با حساب «{label}» ممکن است.")


def resolve_full_payment_amounts(total, parts):
    """
    Turn the full-settlement choices into ``[(method, account, amount)]``
    that add up to exactly ``total`` (D-069).

    ``parts`` is ``[(method, account, amount_or_None)]``, one per method the
    user picked (one or both of card/transfer). One part takes the whole
    total; two parts need one amount (the other is the rest) or both, adding
    up to the total. The browser's idea of the total is never trusted.

    Raises:
        ValidationError: no part, a missing/zero amount, or a sum that is not the total.
    """
    if not parts:
        raise ValidationError("حداقل یک روش پرداخت (کارت‌خوان یا حواله بانکی) را انتخاب کنید.")
    for method, account, _ in parts:
        validate_entry_account(method, account)
    if len(parts) == 1:
        method, account, amount = parts[0]
        if amount not in (None, total):
            raise ValidationError("مبلغ پرداخت با مبلغ نهایی فاکتور برابر نیست.")
        return [(method, account, total)]
    (m1, a1, x1), (m2, a2, x2) = parts
    if x1 is None and x2 is None:
        raise ValidationError("مبلغ حداقل یکی از دو روش پرداخت را وارد کنید.")
    if x1 is None:
        x1 = total - x2
    elif x2 is None:
        x2 = total - x1
    if x1 <= 0 or x2 <= 0 or x1 + x2 != total:
        raise ValidationError("جمع مبلغ کارت‌خوان و حواله باید دقیقاً برابر مبلغ نهایی فاکتور باشد.")
    return [(m1, a1, x1), (m2, a2, x2)]


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
def refund_invoice_payments(invoice, user):
    """
    Give back the money of a cancelled invoice (D-055).

    For every payment allocation still standing on the invoice, books ONE
    refund Payment in the opposite direction, for exactly the allocated
    amount, from/to the same account and party, and links it on the
    allocation (`reversal_payment`) -- the original payment and allocation
    stay untouched, the correction is a new, opposite entry (D-014/D-023).
    A payment shared with other invoices is only refunded for this
    invoice's part. Pending cheques of the invoice never became money, so
    they are simply cancelled.

    Called by cancel_sale/cancel_purchase inside their own transaction, once
    the invoice is known to be cancellable. Returns the total refunded.
    """
    if isinstance(invoice, SalesInvoice):
        allocations = PaymentAllocation.objects.filter(sales_invoice=invoice)
    else:
        allocations = PaymentAllocation.objects.filter(purchase_invoice=invoice)
    allocations = list(
        allocations.filter(reversal_payment__isnull=True)
        .select_related("payment")
        .select_for_update()
        .order_by("created_at", "pk")
    )
    refunded = 0
    for allocation in allocations:
        original = allocation.payment
        opposite = (
            Payment.Direction.OUT if original.direction == Payment.Direction.IN else Payment.Direction.IN
        )
        refund = Payment.objects.create(
            bank_account=original.bank_account,
            customer=original.customer,
            supplier=original.supplier,
            direction=opposite,
            amount=allocation.amount,
            payment_date=timezone.localdate(),
            note=f"برگشت پرداخت بابت لغو فاکتور {invoice.invoice_number}",
            is_reversal=True,
            created_by=user,
        )
        allocation.reversal_payment = refund
        allocation.save(update_fields=["reversal_payment", "updated_at"])
        log_event(
            actor=user,
            event_type="reverse_payment",
            target=refund,
            payload={"amount": refund.amount, "direction": refund.direction, "invoice": invoice.invoice_number},
        )
        refunded += allocation.amount

    for cheque in Cheque.objects.select_for_update().filter(
        **({"sales_invoice": invoice} if isinstance(invoice, SalesInvoice) else {"purchase_invoice": invoice}),
        status=Cheque.Status.PENDING,
    ):
        cancel_cheque(cheque, user)
    return refunded


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
        if cheque.customer_id or (not cheque.supplier_id and not cheque.expense_id):
            raise ValidationError("چک پرداختی باید یک تأمین‌کننده (یا یک هزینه) داشته باشد، بدون مشتری.")
        if cheque.supplier_id and cheque.expense_id:
            raise ValidationError("چک پرداختی نمی‌تواند هم‌زمان تأمین‌کننده و هزینه داشته باشد.")
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


# "Use the account the cheque already carries" -- distinct from None, which
# means cash chosen on purpose (D-045: never cash by omission).
USE_CHEQUE_ACCOUNT = object()


@transaction.atomic
def clear_cheque(cheque, user, bank_account=USE_CHEQUE_ACCOUNT):
    """
    Mark a pending cheque cleared and create the Payment it represents.

    The cheque's amount and direction become a new Payment (D-025); the
    caller still allocates that Payment to an invoice separately via
    `allocate_payment`, same as any other payment.

    Args:
        cheque: the Cheque to clear (any status; only PENDING succeeds).
        user: the user performing the action.
        bank_account: the BankAccount the money moved through, or None for
            cash chosen on purpose. Left out, the cheque's own account is
            used -- and if it has none, clearing is refused instead of
            silently booking cash.

    Raises:
        ValidationError: cheque is not pending, or no account was given and
            the cheque carries none.
    """
    locked = Cheque.objects.select_for_update().get(pk=cheque.pk)
    if locked.status != Cheque.Status.PENDING:
        raise ValidationError("فقط چک در انتظار وصول قابل وصول‌شدن است.")
    if bank_account is USE_CHEQUE_ACCOUNT:
        bank_account = locked.bank_account
        if bank_account is None:
            raise ValidationError("حساب این چک مشخص نیست؛ هنگام وصول یک حساب انتخاب کنید.")
    if bank_account is None or bank_account.account_type != BankAccount.AccountType.CURRENT:
        raise ValidationError("چک فقط به/از «حساب جاری» وصول می‌شود.")

    payment = record_payment(
        Payment(
            bank_account=bank_account,
            direction=locked.direction,
            # Carry the cheque's own party across, so the money this cheque
            # became is still traceable to a person.
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

    # A cheque that pays an expense (D-072): once it clears, that payment IS
    # the expense's payment, so the expense shows as paid.
    if locked.expense_id:
        paid_expense = Expense.objects.select_for_update().get(pk=locked.expense_id)
        paid_expense.payment = payment
        paid_expense.save(update_fields=["payment", "updated_at"])

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
    as history rather than being deleted.

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


def add_months_jalali(day, months):
    """``day`` moved ``months`` Jalali months ahead, keeping the day number where the month allows it
    (a 31st lands on the last day of a shorter month). Used for "every month" fixed costs (D-073)."""
    jalali = dates.to_jalali(day)
    index = jalali.year * 12 + (jalali.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last_day = 31 if month <= 6 else 30 if month <= 11 else (30 if dates.jdatetime.date(year, 1, 1).isleap() else 29)
    return dates.jdatetime.date(year, month, min(jalali.day, last_day)).togregorian()


def next_due_after(recurring):
    """The due date one period after ``recurring.next_due_date``."""
    if recurring.repeat_unit == RecurringExpense.Unit.DAY:
        return recurring.next_due_date + datetime.timedelta(days=recurring.repeat_every)
    return add_months_jalali(recurring.next_due_date, recurring.repeat_every)


@transaction.atomic
def advance_recurring(recurring, user, skipped=False):
    """
    Move a fixed cost's reminder on to its next period (D-073). Called when
    the instalment has been recorded as an Expense, or when this period is
    deliberately skipped (``skipped=True``, logged so it is traceable).
    """
    locked = RecurringExpense.objects.select_for_update().get(pk=recurring.pk)
    old = locked.next_due_date
    locked.next_due_date = next_due_after(locked)
    locked.save(update_fields=["next_due_date", "updated_at"])
    if skipped:
        log_event(
            actor=user,
            event_type="skip_recurring_expense",
            target=locked,
            payload={"reason": locked.reason, "skipped_due": old.isoformat()},
        )
    return locked


@transaction.atomic
def record_expense(expense, user, cheque=None):
    """
    Record a business expense and, depending on how it is paid, the money
    that left with it (D-072).

    * transfer: books the Payment(OUT) from the chosen current account and
      links it, in one transaction, so the two can never exist apart. Reusing
      the Payment ledger is the whole point: bank balances and every cash-flow
      figure already read from it.
    * cheque: saves a pending OUT Cheque (no customer/supplier, linked to this
      expense); no money moves until it is cleared, and `clear_cheque` then
      links the payment here.
    * credit (نسیه): nothing is booked; the expense waits for `pay_expense`.
      A due date is required so the dashboard can remind.

    If ``expense.recurring`` is set the fixed cost's reminder advances one
    period (D-073).

    Args:
        expense: an unsaved Expense with expense_date, amount, reason,
            payment_method and, as the method needs, bank_account / due_date.
            `payment` must NOT be set.
        user: the user performing the action; recorded on every row.
        cheque: for method=cheque, an unsaved Cheque carrying cheque_number /
            bank_name / issuer / due_date (direction, expense and status are
            set here).

    Raises:
        ValidationError: expense already exists, amount not positive, reason
            blank, a payment pre-attached, or the method's own requirements unmet.
    """
    if not expense._state.adding:
        raise ValidationError("هزینه قابل ویرایش نیست.")
    if expense.amount is None or expense.amount <= 0:
        raise ValidationError("مبلغ هزینه باید بزرگ‌تر از صفر باشد.")
    if not (expense.reason or "").strip():
        raise ValidationError("ثبت «بابت» برای هزینه الزامی است.")
    if expense.payment_id is not None:
        raise ValidationError("پرداخت هزینه را خود سرویس می‌سازد.")

    method = expense.payment_method
    if method == Expense.PaymentMethod.TRANSFER:
        account = expense.bank_account
        if account is None or account.account_type != BankAccount.AccountType.CURRENT:
            raise ValidationError("هزینه با حواله بانکی باید از یک «حساب جاری» پرداخت شود.")
        expense.payment = record_payment(
            Payment(
                bank_account=account,
                direction=Payment.Direction.OUT,
                amount=expense.amount,
                payment_date=expense.expense_date,
                note=f"هزینه: {expense.reason}",
            ),
            user,
        )
    elif method == Expense.PaymentMethod.CREDIT:
        if expense.due_date is None:
            raise ValidationError("برای هزینهٔ نسیه، تاریخ سررسید پرداخت را وارد کنید.")
        expense.bank_account = None
    elif method == Expense.PaymentMethod.CHEQUE:
        if cheque is None or cheque.due_date is None:
            raise ValidationError("برای هزینهٔ چکی، تاریخ سررسید چک را وارد کنید.")
        if expense.bank_account is not None and expense.bank_account.account_type != BankAccount.AccountType.CURRENT:
            raise ValidationError("چک هزینه باید روی یک «حساب جاری» باشد.")
    else:
        raise ValidationError("روش پرداخت هزینه نامعتبر است.")

    expense.created_by = user
    expense.save()

    if method == Expense.PaymentMethod.CHEQUE:
        cheque.direction = Payment.Direction.OUT
        cheque.expense = expense
        cheque.amount = expense.amount
        cheque.bank_account = expense.bank_account
        record_cheque(cheque, user)

    if expense.recurring_id:
        advance_recurring(expense.recurring, user)

    log_event(
        actor=user,
        event_type="record_expense",
        target=expense,
        payload={"amount": expense.amount, "reason": expense.reason, "method": method},
    )
    return expense


@transaction.atomic
def pay_expense(expense, bank_account, user, payment_date=None):
    """
    Pay an expense that is still owed (D-072): a نسیه expense when its due
    date comes, or one whose cheque bounced. Books the Payment(OUT) from the
    chosen current account and links it.

    Raises:
        ValidationError: already paid or cancelled, a cheque for it is still
            pending (clear that instead), or the account is not a current account.
    """
    locked = Expense.objects.select_for_update().get(pk=expense.pk)
    if locked.is_cancelled:
        raise ValidationError("این هزینه لغو شده است.")
    if locked.payment_id is not None:
        raise ValidationError("این هزینه قبلاً پرداخت شده است.")
    if Cheque.objects.filter(expense=locked, status=Cheque.Status.PENDING).exists():
        raise ValidationError("چک این هزینه هنوز در انتظار وصول است؛ آن را پاس کنید.")
    if bank_account is None or bank_account.account_type != BankAccount.AccountType.CURRENT:
        raise ValidationError("هزینه از یک «حساب جاری» پرداخت می‌شود.")

    locked.payment = record_payment(
        Payment(
            bank_account=bank_account,
            direction=Payment.Direction.OUT,
            amount=locked.amount,
            payment_date=payment_date or timezone.localdate(),
            note=f"پرداخت هزینه: {locked.reason}",
        ),
        user,
    )
    locked.save(update_fields=["payment", "updated_at"])
    log_event(
        actor=user,
        event_type="pay_expense",
        target=locked,
        payload={"amount": locked.amount, "reason": locked.reason},
    )
    return locked


@transaction.atomic
def cancel_expense(expense, user):
    """
    Undo an expense, never by deleting it.

    If money already left, books a Payment of the same amount in the opposite
    direction against the same account, so the bank balance returns to where
    it was and the ledger keeps both halves of the story. If it was never
    paid, any pending cheque for it is withdrawn and nothing else moves. The
    Expense row stays, flagged cancelled, and stops counting toward any total
    (`counts_toward_totals`).

    Superuser-only, same risk tier as cancel_sale/cancel_purchase (D-023).

    Raises:
        ValidationError: expense is already cancelled, or ``user`` is not
            a superuser.
    """
    locked = Expense.objects.select_for_update().get(pk=expense.pk)
    if locked.is_cancelled:
        raise ValidationError("این هزینه قبلاً لغو شده است.")
    if not is_privileged(user):
        raise ValidationError("فقط ابرکاربر می‌تواند هزینه را لغو کند.")

    for pending in Cheque.objects.select_for_update().filter(expense=locked, status=Cheque.Status.PENDING):
        cancel_cheque(pending, user)

    if locked.payment_id is not None:
        locked.reversal_payment = record_payment(
            Payment(
                bank_account=locked.payment.bank_account,
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

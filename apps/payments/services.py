# path: apps/payments/services.py

"""Write services for payments, their allocation to invoices, and cheques (ROADMAP 4.3, 4.4)."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared.audit import log_event

from .models import Cheque, Payment, PaymentAllocation


@transaction.atomic
def record_payment(payment, user):
    """
    Validate and save a new Payment (D-012-style: amount always positive,
    `direction` carries the sign). Does not touch any invoice -- see
    `allocate_payment` for that.

    Args:
        payment: an unsaved Payment with business, direction, amount,
            payment_date, and optionally bank_account/note already set.
        user: the user performing the action; recorded as `created_by`.

    Raises:
        ValidationError: payment already exists, amount is not positive,
            or bank_account belongs to a different business.
    """
    if not payment._state.adding:
        # pk is never None here (BaseModel.id defaults to uuid4() on
        # construction, before save) -- _state.adding is the real signal.
        raise ValidationError("پرداخت قابل ویرایش نیست.")
    if payment.amount is None or payment.amount <= 0:
        raise ValidationError("مبلغ پرداخت باید بزرگ‌تر از صفر باشد.")
    if payment.bank_account_id is not None and payment.bank_account.business_id != payment.business_id:
        raise ValidationError("حساب بانکی متعلق به کسب‌وکار دیگری است.")

    payment.created_by = user
    payment.save()
    log_event(
        business=payment.business,
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
            invoice side is set; the invoice is not confirmed; invoice and
            payment belong to different businesses; the payment's
            direction does not match the invoice side (IN -> sales,
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

    if invoice.business_id != payment.business_id:
        raise ValidationError("فاکتور و پرداخت متعلق به یک کسب‌وکار نیستند.")

    if invoice.status != invoice.Status.CONFIRMED:
        raise ValidationError("فقط فاکتور تأییدشده قابل تخصیص پرداخت است.")

    if allocation.amount > payment.unallocated_amount:
        raise ValidationError("مبلغ تخصیص از باقیماندهٔ پرداخت بیشتر است.")

    if allocation.amount > remaining_on_invoice:
        raise ValidationError("مبلغ تخصیص از باقیماندهٔ فاکتور بیشتر است.")

    allocation.save()
    log_event(
        business=payment.business,
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
        cheque: an unsaved Cheque with business, direction, exactly one of
            customer/supplier, cheque_number, due_date, amount, and
            optionally bank_account/bank_name/note already set.
        user: the user performing the action.

    Raises:
        ValidationError: cheque already exists; amount is not positive;
            customer/supplier or bank_account belongs to another business.
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
    if cheque.customer_id is not None and cheque.customer.business_id != cheque.business_id:
        raise ValidationError("مشتری متعلق به کسب‌وکار دیگری است.")
    if cheque.supplier_id is not None and cheque.supplier.business_id != cheque.business_id:
        raise ValidationError("تأمین‌کننده متعلق به کسب‌وکار دیگری است.")
    if cheque.bank_account_id is not None and cheque.bank_account.business_id != cheque.business_id:
        raise ValidationError("حساب بانکی متعلق به کسب‌وکار دیگری است.")

    cheque.status = Cheque.Status.PENDING
    cheque.save()
    log_event(
        business=cheque.business,
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
            business=locked.business,
            bank_account=bank_account or locked.bank_account,
            direction=locked.direction,
            amount=locked.amount,
            payment_date=timezone.now().date(),
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
        business=locked.business,
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
        business=locked.business,
        actor=user,
        event_type="bounce_cheque",
        target=locked,
        payload={"amount": locked.amount},
    )
    return locked

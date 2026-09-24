# path: apps/payments/services.py

"""Write services for payments and their allocation to invoices (ROADMAP 4.3)."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared.audit import log_event

from .models import Payment


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

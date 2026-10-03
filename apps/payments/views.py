# path: apps/payments/views.py

"""
Receivables / Payables / Cheques: one conceptual
module, three views, each with its own namespace so a page can link
straight to the view it means (apps/payments/urls.py's own docstring).

Views never write -- money and stock go through apps/*/services.py inside
transaction.atomic, same rule as every other module.
"""

import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.partners.models import Customer, Supplier
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared import dates
from apps.shared.forms import DateRangeForm
from apps.shared.permissions import is_privileged
from apps.shared.utils import format_toman

from .forms import (
    PayInvoiceForm,
    ClearChequeForm,
    BankAccountForm,
    ChequeCompletionForm,
    ChequeFilterForm,
    ExpenseFilterForm,
    ExpenseForm,
    PayExpenseForm,
    RecordPaymentForm,
    RecurringExpenseForm,
)
from .models import BankAccount, Cheque, Expense, Payment, PaymentAllocation, RecurringExpense
from .selectors import (
    get_bank_account_balance,
    get_customer_outstanding,
    get_credit_items,
    get_expense_reminders,
    get_open_invoices,
    get_pending_cheques,
    get_supplier_outstanding,
)
from .services import (
    advance_recurring,
    allocate_payment,
    bounce_cheque,
    cancel_cheque,
    cancel_expense,
    clear_cheque,
    pay_expense,
    record_expense,
    record_payment,
)


class _DuesListView(LoginRequiredMixin, TemplateView):
    """
    Shared body of Receivables and Payables (D-071): what is owed, split by
    HOW it will be settled -- pending cheques (each with its own due date and
    pass/bounce buttons) and credit on account (نسیه, per invoice, with its
    due date and a pay-all-or-part form) -- plus the per-party summary with
    the general "ثبت پرداخت" form. Mirrors one side to the other: only the
    direction, models and wording differ.
    """

    direction = None            # Payment.Direction.IN (receivables) / OUT (payables)
    party_model = None
    invoice_model = None
    party_field = ""            # "customer" / "supplier"
    outstanding_of = None
    record_url_name = ""
    pay_url_name = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paying_supplier = self.direction == Payment.Direction.OUT
        today = timezone.localdate()

        cheques = []
        for cheque in get_pending_cheques(self.direction):
            cheques.append({
                "cheque": cheque,
                "party": cheque.customer or cheque.supplier,
                "overdue": cheque.due_date is not None and cheque.due_date < today,
                "clear_form": ClearChequeForm(
                    initial={"bank_account": cheque.bank_account_id},
                    auto_id=f"clr_{cheque.pk.hex[:8]}_%s",
                ),
            })

        credit = []
        for item in get_credit_items(self.invoice_model):
            invoice = item["invoice"]
            credit.append({
                **item,
                "party": getattr(invoice, self.party_field),
                "overdue": item["due_date"] is not None and item["due_date"] < today,
                "form": PayInvoiceForm(
                    invoice=invoice, credit_amount=item["amount"], paying_supplier=paying_supplier,
                    initial={"payment_date": today},
                ),
                "post_url": reverse(self.pay_url_name, args=[invoice.pk]),
            })

        rows = []
        # Deactivated parties stay: a balance they still owe must not
        # vanish from the page that collects it.
        for party in self.party_model.objects.order_by("name"):
            outstanding = self.outstanding_of(party)
            if outstanding <= 0:
                continue
            open_invoices = get_open_invoices(self.invoice_model, **{self.party_field: party})
            rows.append({
                self.party_field: party,
                "party": party,
                "outstanding": outstanding,
                "form": RecordPaymentForm(**{self.party_field: party}, open_invoices=open_invoices),
                "post_url": reverse(self.record_url_name, args=[party.pk]),
            })
        rows.sort(key=lambda r: -r["outstanding"])

        context.update({
            "cheques": cheques,
            "cheques_total": sum(c["cheque"].amount for c in cheques),
            "credit": credit,
            "credit_total": sum(i["amount"] for i in credit),
            "rows": rows,
            "next_url": self.request.path,
        })
        return context


class ReceivablesListView(_DuesListView):
    """Money owed to the business, by cheque and by credit on account."""

    template_name = "payments/receivables_list.html"
    direction = Payment.Direction.IN
    party_model = Customer
    invoice_model = SalesInvoice
    party_field = "customer"
    outstanding_of = staticmethod(get_customer_outstanding)
    record_url_name = "receivables:record_payment"
    pay_url_name = "receivables:pay_invoice"


class PayablesListView(_DuesListView):
    """Exact mirror of Receivables, Supplier/PurchaseInvoice side -- reads the
    same `get_supplier_outstanding` the
    Suppliers sub-section (4.2) already uses, so the two can never disagree."""

    template_name = "payments/payables_list.html"
    direction = Payment.Direction.OUT
    party_model = Supplier
    invoice_model = PurchaseInvoice
    party_field = "supplier"
    outstanding_of = staticmethod(get_supplier_outstanding)
    record_url_name = "payables:record_payment"
    pay_url_name = "payables:pay_invoice"


class _PayInvoiceView(LoginRequiredMixin, View):
    """
    POST: settle all or part of one invoice's credit part (D-071) -- books
    the Payment (customer money in / supplier money out) and allocates
    exactly that amount to this invoice, in one transaction, via the same
    services as every other payment. Redirects back to the list with a flash
    message; a refusal comes back as a message too.
    """

    invoice_model = None
    direction = None
    party_field = ""
    invoice_fk = ""
    back_url_name = ""

    def post(self, request, pk):
        invoice = get_object_or_404(self.invoice_model, pk=pk)
        credit = next((i["amount"] for i in get_credit_items(self.invoice_model) if i["invoice"].pk == invoice.pk), 0)
        form = PayInvoiceForm(
            request.POST, invoice=invoice, credit_amount=credit,
            paying_supplier=self.direction == Payment.Direction.OUT,
        )
        if not form.is_valid():
            messages.error(request, "؛ ".join(e for errors in form.errors.values() for e in errors))
            return redirect(self.back_url_name)
        data = form.cleaned_data
        try:
            with transaction.atomic():
                payment = record_payment(
                    Payment(
                        bank_account=data["bank_account"],
                        direction=self.direction,
                        amount=data["amount"],
                        payment_date=data["payment_date"],
                        note=data["note"] or f"تسویهٔ فاکتور {invoice.invoice_number}",
                        **{self.party_field: getattr(invoice, self.party_field)},
                    ),
                    request.user,
                )
                allocate_payment(
                    PaymentAllocation(payment=payment, amount=data["amount"], **{self.invoice_fk: invoice.pk}),
                    request.user,
                )
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            amount_text = format_toman(data["amount"])
            messages.success(request, f"پرداخت {amount_text} برای فاکتور {invoice.invoice_number} ثبت شد.")
        return redirect(self.back_url_name)


class PayCustomerInvoiceView(_PayInvoiceView):
    invoice_model = SalesInvoice
    direction = Payment.Direction.IN
    party_field = "customer"
    invoice_fk = "sales_invoice_id"
    back_url_name = "receivables:list"


class PaySupplierInvoiceView(_PayInvoiceView):
    invoice_model = PurchaseInvoice
    direction = Payment.Direction.OUT
    party_field = "supplier"
    invoice_fk = "purchase_invoice_id"
    back_url_name = "payables:list"


class _RecordPaymentView(LoginRequiredMixin, View):
    """
    Shared POST handler behind the one "ثبت پرداخت" component: books the Payment, then allocates it
    across whichever open invoices were checked, oldest first, until the
    amount runs out -- any leftover stays an unallocated payment on that
    party's account (a prepayment, same as the form's own hint says).
    """

    party_model = None
    invoice_model = None
    invoice_fk = ""  # "sales_invoice_id" or "purchase_invoice_id"

    def party_kwargs(self, party):
        field = "customer" if self.party_model is Customer else "supplier"
        return {field: party}

    def post(self, request, pk):
        party = get_object_or_404(self.party_model, pk=pk)
        open_invoices = get_open_invoices(self.invoice_model, **self.party_kwargs(party))
        form = RecordPaymentForm(request.POST, open_invoices=open_invoices, **self.party_kwargs(party))

        if form.is_valid():
            data = form.cleaned_data
            by_id = {str(invoice.pk): invoice for invoice in open_invoices}
            chosen = sorted(
                (by_id[pk_str] for pk_str in data.get("invoices") or [] if pk_str in by_id),
                key=lambda invoice: invoice.invoice_date,
            )
            try:
                with transaction.atomic():
                    payment = record_payment(
                        Payment(
                            bank_account=data["bank_account"],
                            direction=form.direction,
                            amount=data["amount"],
                            payment_date=data["payment_date"],
                            note=data["note"],
                            **self.party_kwargs(party),
                        ),
                        request.user,
                    )
                    remaining = data["amount"]
                    for invoice in chosen:
                        if remaining <= 0:
                            break
                        take = min(invoice.outstanding, remaining)
                        allocate_payment(
                            PaymentAllocation(payment=payment, amount=take, **{self.invoice_fk: invoice.pk}),
                            request.user,
                        )
                        remaining -= take
            except ValidationError as exc:
                form.add_error(None, "؛ ".join(exc.messages))
            else:
                html = render_to_string(
                    "payments/_record_payment_success.html", {"party": party}, request=request,
                )
                return HttpResponse(html)

        html = render_to_string(
            "payments/_record_payment_form.html",
            {"form": form, "post_url": request.path},
            request=request,
        )
        return HttpResponse(html, status=422)


class RecordCustomerPaymentView(_RecordPaymentView):
    party_model = Customer
    invoice_model = SalesInvoice
    invoice_fk = "sales_invoice_id"


class RecordSupplierPaymentView(_RecordPaymentView):
    party_model = Supplier
    invoice_model = PurchaseInvoice
    invoice_fk = "purchase_invoice_id"


class ChequesListView(LoginRequiredMixin, TemplateView):
    """Status/direction/due-date-range filters, one
    table covering both received and issued cheques."""

    template_name = "payments/cheques_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = ChequeFilterForm(self.request.GET or None)
        qs = Cheque.objects.select_related(
            "customer", "supplier", "bank_account", "sales_invoice", "purchase_invoice",
        ).order_by("due_date")

        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("status"):
                qs = qs.filter(status=data["status"])
            if data.get("direction"):
                qs = qs.filter(direction=data["direction"])
            if data.get("due_start"):
                qs = qs.filter(due_date__gte=data["due_start"])
            if data.get("due_end"):
                qs = qs.filter(due_date__lte=data["due_end"])

        context["filter_form"] = filter_form
        context["cheques"] = qs
        return context


class ChequeDetailView(LoginRequiredMixin, DetailView):
    """Full lifecycle trace: party, linked invoice
    (or "general/unattached"), and, once cleared, the Payment it became."""

    model = Cheque
    template_name = "payments/cheque_detail.html"
    context_object_name = "cheque"

    def get_queryset(self):
        return Cheque.objects.select_related(
            "customer", "supplier", "bank_account", "payment__bank_account",
            "sales_invoice", "purchase_invoice",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["completion_form"] = ChequeCompletionForm(instance=self.object)
        context["clear_form"] = ClearChequeForm(
            initial={"bank_account": str(self.object.bank_account_id) if self.object.bank_account_id else ""},
        )
        return context


class ChequeCompleteView(LoginRequiredMixin, View):
    """"تکمیل مشخصات" for a cheque entered incomplete from an invoice
    (4.3b) -- a plain save on the descriptive fields only, same as
    ChequeAdmin.save_model's `change` branch (status/payment stay
    untouchable; only a service ever sets those)."""

    def post(self, request, pk):
        cheque = get_object_or_404(Cheque, pk=pk)
        if cheque.status != Cheque.Status.PENDING:
            messages.error(request, "فقط چک در انتظار وصول قابل ویرایش است.")
            return redirect("cheques:detail", pk=pk)

        form = ChequeCompletionForm(request.POST, instance=cheque)
        if form.is_valid():
            form.save()
            messages.success(request, "مشخصات چک بروزرسانی شد.")
        else:
            messages.error(request, "؛ ".join(error for errors in form.errors.values() for error in errors))
        return redirect("cheques:detail", pk=pk)


class ChequeActionView(LoginRequiredMixin, View):
    """POST-only door to clear_cheque/bounce_cheque/cancel_cheque -- the
    services are the only real guard (must be PENDING)."""

    action = None  # set per URL: "clear", "bounce", or "cancel"
    _services = {"clear": clear_cheque, "bounce": bounce_cheque, "cancel": cancel_cheque}
    _labels = {"clear": "وصول", "bounce": "برگشت", "cancel": "لغو"}

    @staticmethod
    def _back(request, pk):
        back = request.POST.get("next", "")
        if back in (reverse("receivables:list"), reverse("payables:list"), reverse("cheques:list")):
            return back
        return reverse("cheques:detail", args=[pk])

    def post(self, request, pk):
        cheque = get_object_or_404(Cheque, pk=pk)
        service = self._services[self.action]
        kwargs = {}
        if self.action == "clear":
            form = ClearChequeForm(request.POST)
            if not form.is_valid():
                messages.error(request, "؛ ".join(e for errors in form.errors.values() for e in errors))
                return redirect(self._back(request, pk))
            kwargs["bank_account"] = form.cleaned_data["bank_account"]
        try:
            service(cheque, request.user, **kwargs)
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            messages.success(request, f"چک {self._labels[self.action]} شد.")
        # The Receivables/Payables page posts here too and wants to land back
        # on itself; only a known local path is honoured.
        return redirect(self._back(request, pk))


class BankAccountListView(LoginRequiredMixin, TemplateView):
    """
    Bank Accounts: one card per account -- name,
    owner, account number, live balance, and the three comparison deltas
    (vs. yesterday/last week/last month), all read straight off the
    Payment ledger via `get_bank_account_balance(as_of=...)`. No
    independent "cash" row here -- cash payments
    (bank_account left blank) never belong to any BankAccount.
    """

    template_name = "payments/bank_accounts_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        rows = []
        for account in BankAccount.objects.filter(is_active=True).order_by("name"):
            balance = get_bank_account_balance(account)
            rows.append({
                "account": account,
                "balance": balance,
                "deltas": [
                    {"label": "نسبت به دیروز", "value": balance - get_bank_account_balance(
                        account, as_of=today - datetime.timedelta(days=1),
                    )},
                    {"label": "نسبت به هفتهٔ گذشته", "value": balance - get_bank_account_balance(
                        account, as_of=today - datetime.timedelta(days=7),
                    )},
                    {"label": "نسبت به ماه گذشته", "value": balance - get_bank_account_balance(
                        account, as_of=today - datetime.timedelta(days=30),
                    )},
                ],
            })
        # Card readers and current accounts are shown as two sections (D-067).
        context["groups"] = [
            {"title": label, "rows": [r for r in rows if r["account"].account_type == value]}
            for value, label in BankAccount.AccountType.choices
        ]
        context["rows"] = rows
        return context


class BankAccountCreateView(LoginRequiredMixin, View):
    """"+ حساب بانکی جدید" -- a full page, like Inventory's new product:
    not mid-transaction, so nothing to keep alive around it. An account
    is descriptive data, not money, so a plain save is enough; its
    balance only ever comes from the Payment ledger."""

    template_name = "payments/bank_account_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": BankAccountForm()})

    def post(self, request):
        form = BankAccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            messages.success(request, f"حساب «{account.name}» ثبت شد.")
            return redirect("bank_accounts:list")
        return render(request, self.template_name, {"form": form})


class BankAccountUpdateView(LoginRequiredMixin, View):
    """Fix a name/owner/number typo. Same form as create; the ledger is
    untouched -- every Payment keeps pointing at the same row."""

    template_name = "payments/bank_account_form.html"

    def get(self, request, pk):
        account = get_object_or_404(BankAccount, pk=pk)
        return render(request, self.template_name, {"form": BankAccountForm(instance=account), "account": account})

    def post(self, request, pk):
        account = get_object_or_404(BankAccount, pk=pk)
        form = BankAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, "مشخصات حساب بروزرسانی شد.")
            return redirect("bank_accounts:detail", pk=pk)
        return render(request, self.template_name, {"form": form, "account": account})


class BankAccountDetailView(LoginRequiredMixin, DetailView):
    """
    Full ledger for one account: every Payment
    against it, each resolved to what it actually was -- a cheque
    clearing, an expense (or its cancellation reversal), or money
    allocated to one or more invoices -- all already derivable from
    Payment/PaymentAllocation/Expense.payment, no new model needed.
    """

    model = BankAccount
    template_name = "payments/bank_account_detail.html"
    context_object_name = "account"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["balance"] = get_bank_account_balance(self.object)
        payments = Payment.objects.filter(bank_account=self.object).select_related(
            "customer", "supplier", "created_by", "cheque", "expense", "reversed_expense",
        ).prefetch_related(
            "allocations__sales_invoice", "allocations__purchase_invoice",
            "reversed_allocation__sales_invoice", "reversed_allocation__purchase_invoice",
        ).order_by("-payment_date", "-created_at")
        context["ledger_rows"] = [_describe_payment(payment) for payment in payments]
        return context


def _describe_payment(payment):
    """One bank-ledger row's source/destination text and link, if any."""
    if hasattr(payment, "expense"):
        source, url = f"هزینه: {payment.expense.reason}", None
    elif hasattr(payment, "reversed_expense"):
        source, url = f"لغو هزینه: {payment.reversed_expense.reason}", None
    elif payment.is_reversal:
        allocation = getattr(payment, "reversed_allocation", None)
        invoice = (allocation.sales_invoice or allocation.purchase_invoice) if allocation else None
        if invoice is not None:
            page = "sales:detail" if allocation.sales_invoice_id else "purchasing:detail"
            source, url = f"برگشت پرداخت بابت لغو فاکتور {invoice.invoice_number}", reverse(page, args=[invoice.pk])
        else:
            source, url = "برگشت پرداخت", None
    elif hasattr(payment, "cheque"):
        source, url = f"وصول چک {payment.cheque.cheque_number or '(بدون شماره)'}", reverse("cheques:detail", args=[payment.cheque.pk])
    else:
        allocations = list(payment.allocations.all())
        if allocations:
            parts = []
            for allocation in allocations:
                if allocation.sales_invoice_id:
                    parts.append((allocation.sales_invoice.invoice_number or "(تأیید نشده)", reverse("sales:detail", args=[allocation.sales_invoice_id])))
                else:
                    parts.append((allocation.purchase_invoice.invoice_number or "(تأیید نشده)", reverse("purchasing:detail", args=[allocation.purchase_invoice_id])))
            source, url = "، ".join(number for number, _ in parts), parts[0][1] if len(parts) == 1 else None
        elif payment.party:
            source, url = str(payment.party), None
        else:
            source, url = "بدون تخصیص", None
    return {
        "payment": payment,
        "source": source,
        "url": url,
        "party": payment.party,
    }


class ExpensesListView(LoginRequiredMixin, TemplateView):
    """
    Expenses: newest-first, cards for today's and
    this month's totals (cancelled expenses excluded from both --
    `Expense.counts_toward_totals`), free-text search over reason/note,
    plus the shared date-range picker and structured filters (bank
    account, amount range, paid/owed). The table itself still lists a
    cancelled expense, same "history, not hidden" rule as a cancelled invoice.

    An expense can still be owed (D-072): a نسیه one until it is paid, a
    cheque one until the cheque clears. Those show a "پرداخت" form here and
    an "owed" card on top.
    """

    template_name = "payments/expenses_list.html"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_form = DateRangeForm(self.request.GET or None)
        filter_form = ExpenseFilterForm(self.request.GET or None)
        date_range = range_form.range

        qs = Expense.objects.select_related("bank_account", "created_by", "payment").filter(
            expense_date__gte=date_range[0], expense_date__lte=date_range[1],
        )

        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("q"):
                qs = qs.filter(Q(reason__icontains=data["q"]) | Q(note__icontains=data["q"]))
            if data.get("bank_account"):
                qs = qs.filter(bank_account=data["bank_account"])
            if data.get("amount_min") is not None:
                qs = qs.filter(amount__gte=data["amount_min"])
            if data.get("amount_max") is not None:
                qs = qs.filter(amount__lte=data["amount_max"])
            if data.get("status") == "owed":
                qs = qs.filter(payment__isnull=True, cancelled_at__isnull=True)
            elif data.get("status") == "paid":
                qs = qs.filter(payment__isnull=False)

        expenses = qs.order_by("-expense_date", "-created_at")
        paginator = Paginator(expenses, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        rows = [
            {
                "expense": expense,
                "pay_form": PayExpenseForm(expense=expense, initial={"payment_date": timezone.localdate()})
                if not expense.is_paid and not expense.is_cancelled else None,
            }
            for expense in page_obj.object_list
        ]
        context.update({
            "range_form": range_form,
            "date_range": date_range,
            "filter_form": filter_form,
            "page_obj": page_obj,
            "rows": rows,
            "cards": self._cards(),
            "can_cancel": is_privileged(self.request.user),
            "due_reminders": get_expense_reminders(),
        })
        return context

    @staticmethod
    def _cards():
        today = timezone.localdate()
        jalali_today = dates.today()
        month_start, month_end = dates.month_bounds(jalali_today.year, jalali_today.month)

        not_cancelled = Q(cancelled_at__isnull=True)
        month_total = Expense.objects.filter(
            not_cancelled, expense_date__gte=month_start, expense_date__lte=month_end,
        ).aggregate(total=models.Sum("amount"))["total"] or 0
        today_total = Expense.objects.filter(not_cancelled, expense_date=today).aggregate(
            total=models.Sum("amount"),
        )["total"] or 0
        owed_total = Expense.objects.filter(not_cancelled, payment__isnull=True).aggregate(
            total=models.Sum("amount"),
        )["total"] or 0

        return {"today_total": today_total, "month_total": month_total, "owed_total": owed_total}


class ExpenseCreateView(LoginRequiredMixin, View):
    """New-expense one-shot form: atomic create of the Expense (and, for a
    transfer, its Payment(OUT); for a cheque, its pending Cheque) via
    record_expense -- no edit/delete after. `?recurring=<id>` pre-fills it
    from a fixed cost (D-073)."""

    template_name = "payments/expense_new.html"

    def get(self, request):
        initial = {"expense_date": timezone.localdate()}
        recurring = RecurringExpense.objects.filter(pk=_uuid_or_none(request.GET.get("recurring")), is_active=True).first()
        if recurring is not None:
            initial.update({
                "reason": recurring.reason, "amount": recurring.amount, "recurring": recurring.pk,
                "note": recurring.note,
            })
        return render(request, self.template_name, {"form": ExpenseForm(initial=initial), "recurring": recurring})

    def post(self, request):
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    expense = record_expense(form.save(commit=False), request.user, cheque=form.build_cheque())
            except ValidationError as exc:
                form.add_error(None, "؛ ".join(exc.messages))
            else:
                messages.success(request, "هزینه ثبت شد.")
                return redirect("expenses:list")
        return render(request, self.template_name, {"form": form, "recurring": form.cleaned_data.get("recurring") if hasattr(form, "cleaned_data") else None})


def _uuid_or_none(value):
    """A UUID from a query string, or None when it is missing or malformed."""
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


class ExpensePayView(LoginRequiredMixin, View):
    """POST-only door to pay_expense (a نسیه expense, or one whose cheque bounced)."""

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = PayExpenseForm(request.POST, expense=expense)
        if not form.is_valid():
            messages.error(request, "؛ ".join(e for errors in form.errors.values() for e in errors))
            return redirect("expenses:list")
        try:
            pay_expense(expense, form.cleaned_data["bank_account"], request.user, form.cleaned_data["payment_date"])
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            messages.success(request, "پرداخت هزینه ثبت شد.")
        return redirect("expenses:list")


class ExpenseCancelView(LoginRequiredMixin, View):
    """POST-only: cancel_expense itself is the only real guard (superuser
    + not already cancelled); this view is just the HTTP door to it."""

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        try:
            cancel_expense(expense, request.user)
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            messages.success(request, "هزینه لغو شد.")
        return redirect("expenses:list")


class RecurringExpenseListView(LoginRequiredMixin, TemplateView):
    """Fixed, repeating costs (D-073): when each is next due, with the
    "ثبت پرداخت" shortcut (opens the expense form pre-filled) and "رد کردن
    این نوبت". Anything inside its reminder window is flagged."""

    template_name = "payments/recurring_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        rows = []
        for item in RecurringExpense.objects.order_by("-is_active", "next_due_date", "reason"):
            days_left = (item.next_due_date - today).days
            rows.append({
                "item": item,
                "days_left": days_left,
                "overdue": days_left < 0,
                "due_soon": item.is_active and days_left <= item.remind_days_before,
            })
        context["rows"] = rows
        return context


class RecurringExpenseCreateView(LoginRequiredMixin, View):
    """Add a fixed cost."""

    template_name = "payments/recurring_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": RecurringExpenseForm(initial={"repeat_every": 1, "remind_days_before": 7})})

    def post(self, request):
        form = RecurringExpenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "هزینهٔ ثابت ثبت شد.")
            return redirect("recurring_expenses:list")
        return render(request, self.template_name, {"form": form})


class RecurringExpenseUpdateView(LoginRequiredMixin, View):
    """Change a fixed cost's amount, period, next date or reminder lead time."""

    template_name = "payments/recurring_form.html"

    def get(self, request, pk):
        item = get_object_or_404(RecurringExpense, pk=pk)
        return render(request, self.template_name, {"form": RecurringExpenseForm(instance=item), "item": item})

    def post(self, request, pk):
        item = get_object_or_404(RecurringExpense, pk=pk)
        form = RecurringExpenseForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "هزینهٔ ثابت بروزرسانی شد.")
            return redirect("recurring_expenses:list")
        return render(request, self.template_name, {"form": form, "item": item})


class RecurringExpenseSkipView(LoginRequiredMixin, View):
    """POST: skip this period without recording an expense (advances the reminder, logged)."""

    def post(self, request, pk):
        item = get_object_or_404(RecurringExpense, pk=pk, is_active=True)
        advance_recurring(item, request.user, skipped=True)
        messages.success(request, f"نوبت «{item.reason}» رد شد.")
        return redirect(request.POST.get("next") if request.POST.get("next") == reverse("dashboard") else "recurring_expenses:list")


class RecurringExpenseToggleView(LoginRequiredMixin, View):
    """POST: switch a fixed cost off (no more reminders) or back on. Never deleted: past expenses point to it."""

    def post(self, request, pk):
        item = get_object_or_404(RecurringExpense, pk=pk)
        item.is_active = not item.is_active
        item.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "هزینهٔ ثابت فعال شد." if item.is_active else "هزینهٔ ثابت غیرفعال شد.")
        return redirect("recurring_expenses:list")

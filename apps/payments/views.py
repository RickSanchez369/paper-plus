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

from .forms import (
    ClearChequeForm,
    BankAccountForm,
    ChequeCompletionForm,
    ChequeFilterForm,
    ExpenseFilterForm,
    ExpenseForm,
    RecordPaymentForm,
)
from .models import BankAccount, Cheque, Expense, Payment, PaymentAllocation
from .selectors import (
    get_bank_account_balance,
    get_customer_outstanding,
    get_open_invoices,
    get_supplier_outstanding,
)
from .services import (
    allocate_payment,
    bounce_cheque,
    cancel_cheque,
    cancel_expense,
    clear_cheque,
    record_expense,
    record_payment,
)


class ReceivablesListView(LoginRequiredMixin, TemplateView):
    """Customers with an open balance, each row
    carrying its own ready-to-open "ثبت پرداخت" form -- the party is
    already fixed by the row, so no second page is needed to record one."""

    template_name = "payments/receivables_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        # Deactivated customers stay: a balance they still owe must not
        # vanish from the page that collects it.
        for customer in Customer.objects.order_by("name"):
            outstanding = get_customer_outstanding(customer)
            if outstanding <= 0:
                continue
            open_invoices = get_open_invoices(SalesInvoice, customer=customer)
            rows.append({
                "customer": customer,
                "outstanding": outstanding,
                "form": RecordPaymentForm(customer=customer, open_invoices=open_invoices),
                "post_url": reverse("receivables:record_payment", args=[customer.pk]),
            })
        rows.sort(key=lambda r: -r["outstanding"])
        context["rows"] = rows
        return context


class PayablesListView(LoginRequiredMixin, TemplateView):
    """Exact mirror of Receivables, Supplier/PurchaseInvoice side -- reads the
    same `get_supplier_outstanding` the
    Suppliers sub-section (4.2) already uses, so the two can never disagree."""

    template_name = "payments/payables_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for supplier in Supplier.objects.order_by("name"):
            outstanding = get_supplier_outstanding(supplier)
            if outstanding <= 0:
                continue
            open_invoices = get_open_invoices(PurchaseInvoice, supplier=supplier)
            rows.append({
                "supplier": supplier,
                "outstanding": outstanding,
                "form": RecordPaymentForm(supplier=supplier, open_invoices=open_invoices),
                "post_url": reverse("payables:record_payment", args=[supplier.pk]),
            })
        rows.sort(key=lambda r: -r["outstanding"])
        context["rows"] = rows
        return context


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

    def post(self, request, pk):
        cheque = get_object_or_404(Cheque, pk=pk)
        service = self._services[self.action]
        kwargs = {}
        if self.action == "clear":
            form = ClearChequeForm(request.POST)
            if not form.is_valid():
                messages.error(request, "؛ ".join(e for errors in form.errors.values() for e in errors))
                return redirect("cheques:detail", pk=pk)
            kwargs["bank_account"] = form.cleaned_data["bank_account"]   # None = cash, chosen
        try:
            service(cheque, request.user, **kwargs)
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            messages.success(request, f"چک {self._labels[self.action]} شد.")
        return redirect("cheques:detail", pk=pk)


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
    account, amount range). The table itself still lists a cancelled
    expense, same "history, not hidden" rule as a cancelled invoice.
    """

    template_name = "payments/expenses_list.html"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_form = DateRangeForm(self.request.GET or None)
        filter_form = ExpenseFilterForm(self.request.GET or None)
        date_range = range_form.range

        qs = Expense.objects.select_related("bank_account", "created_by").filter(
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

        expenses = qs.order_by("-expense_date", "-created_at")
        paginator = Paginator(expenses, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        context.update({
            "range_form": range_form,
            "date_range": date_range,
            "filter_form": filter_form,
            "page_obj": page_obj,
            "expenses": page_obj.object_list,
            "cards": self._cards(),
            "can_cancel": is_privileged(self.request.user),
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

        return {"today_total": today_total, "month_total": month_total}


class ExpenseCreateView(LoginRequiredMixin, View):
    """New-expense one-shot form: atomic create of
    Expense + Payment(OUT), via record_expense -- no edit/delete after."""

    template_name = "payments/expense_new.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ExpenseForm()})

    def post(self, request):
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    expense = record_expense(form.save(commit=False), request.user)
            except ValidationError as exc:
                form.add_error(None, "؛ ".join(exc.messages))
            else:
                messages.success(request, "هزینه ثبت شد.")
                return redirect("expenses:list")
        return render(request, self.template_name, {"form": form})


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

# path: apps/payments/views.py

"""
Receivables / Payables / Cheques (REDESIGN_VISION 4.4): one conceptual
module, three views, each with its own namespace so a page can link
straight to the view it means (apps/payments/urls.py's own docstring).

Views never write -- money and stock go through apps/*/services.py inside
transaction.atomic, same rule as every other module.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.partners.models import Customer, Supplier
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice

from .forms import ChequeCompletionForm, ChequeFilterForm, RecordPaymentForm
from .models import Cheque, Payment, PaymentAllocation
from .selectors import get_customer_outstanding, get_supplier_outstanding
from .services import allocate_payment, bounce_cheque, cancel_cheque, clear_cheque, record_payment


class ReceivablesListView(LoginRequiredMixin, TemplateView):
    """Customers with an open balance (REDESIGN_VISION 4.4), each row
    carrying its own ready-to-open "ثبت پرداخت" form -- the party is
    already fixed by the row, so no second page is needed to record one."""

    template_name = "payments/receivables_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for customer in Customer.objects.filter(is_active=True).order_by("name"):
            outstanding = get_customer_outstanding(customer)
            if outstanding <= 0:
                continue
            open_invoices = _open_invoices(SalesInvoice, customer=customer)
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
    """Exact mirror of Receivables, Supplier/PurchaseInvoice side
    (REDESIGN_VISION 4.4) -- reads the same `get_supplier_outstanding` the
    Suppliers sub-section (4.2) already uses, so the two can never disagree."""

    template_name = "payments/payables_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for supplier in Supplier.objects.filter(is_active=True).order_by("name"):
            outstanding = get_supplier_outstanding(supplier)
            if outstanding <= 0:
                continue
            open_invoices = _open_invoices(PurchaseInvoice, supplier=supplier)
            rows.append({
                "supplier": supplier,
                "outstanding": outstanding,
                "form": RecordPaymentForm(supplier=supplier, open_invoices=open_invoices),
                "post_url": reverse("payables:record_payment", args=[supplier.pk]),
            })
        rows.sort(key=lambda r: -r["outstanding"])
        context["rows"] = rows
        return context


def _open_invoices(model, **party_filter):
    """This party's confirmed invoices that still owe something, oldest
    first -- the order a payment should settle them in by default."""
    invoices = (
        model.objects.filter(status=model.Status.CONFIRMED, **party_filter)
        .prefetch_related("payment_allocations")
        .order_by("invoice_date")
    )
    return [invoice for invoice in invoices if invoice.outstanding > 0]


class _RecordPaymentView(LoginRequiredMixin, View):
    """
    Shared POST handler behind the one "ثبت پرداخت" component
    (REDESIGN_VISION 8 item 2): books the Payment, then allocates it
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
        open_invoices = _open_invoices(self.invoice_model, **self.party_kwargs(party))
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
    """REDESIGN_VISION 4.4: status/direction/due-date-range filters, one
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
    """Full lifecycle trace (REDESIGN_VISION 4.4): party, linked invoice
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
        try:
            service(cheque, request.user)
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            messages.success(request, f"چک {self._labels[self.action]} شد.")
        return redirect("cheques:detail", pk=pk)

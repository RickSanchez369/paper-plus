# path: apps/partners/views.py

"""
The Customers module plus the inline "new customer"
component shared with Sales/Purchasing.

Views never write directly -- editing a Customer is a plain field update
(no money/stock involved), but "record payment" on the detail page still
goes through apps.payments.services via the existing receivables_patterns
route (RecordCustomerPaymentView), reused as-is rather than duplicated.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.payments.forms import RecordPaymentForm
from apps.payments.models import Payment
from apps.payments.selectors import get_customer_outstanding, get_open_invoices
from apps.sales.models import SalesInvoice

from .forms import CustomerForm, CustomerFilterForm, QuickCustomerForm
from .models import Customer


class QuickCustomerCreateView(LoginRequiredMixin, View):
    """
    Creates a Customer from the inline mini-form (htmx POST).

    On success, returns the form's own htmx target replaced with a small
    confirmation, plus an out-of-band swap of `#id_customer` -- the id
    Django gives any form whose field is literally named `customer`
    (SaleInvoiceForm included) -- with the new party selected. The page
    that embedded this component needs no JS of its own to pick it up.
    """

    def post(self, request):
        form = QuickCustomerForm(request.POST)
        if not form.is_valid():
            html = render_to_string(
                "partners/_quick_party_form.html",
                {
                    "form": form,
                    "post_url": request.path,
                    "title": "مشتری جدید",
                    "compact": bool(request.POST.get("compact")),
                },
                request=request,
            )
            return HttpResponse(html, status=422)

        customer = form.save()
        success_html = render_to_string(
            "partners/_quick_party_create_success.html",
            {"customer": customer},
            request=request,
        )
        select_html = render_to_string(
            "partners/_customer_select_oob.html",
            {
                "customers": Customer.objects.filter(is_active=True).order_by("name"),
                "selected": customer,
            },
            request=request,
        )
        return HttpResponse(success_html + select_html)


def _customer_row(customer):
    """One list-page row: badge, open balance, invoice count, last
    purchase date -- all derived, never stored (D-025)."""
    confirmed = SalesInvoice.objects.filter(customer=customer, status=SalesInvoice.Status.CONFIRMED)
    outstanding = get_customer_outstanding(customer)
    last_purchase = confirmed.aggregate(last=Max("invoice_date"))["last"]
    return {
        "customer": customer,
        "outstanding": outstanding,
        "owes": outstanding > 0,
        "invoice_count": confirmed.count(),
        "last_purchase": last_purchase,
    }


class CustomerListView(LoginRequiredMixin, TemplateView):
    """
    List: name, phone, account status badge, open
    balance, invoice count, last purchase date. Search over name/phone,
    filter by account status (owes/settled) and active/inactive -- shows
    active customers only until the filter says otherwise, same default
    every other list in this app uses.
    """

    template_name = "partners/customers_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = CustomerFilterForm(self.request.GET or None)

        qs = Customer.objects.all()
        # "" (the "همه" option) must mean everyone; only a missing or unknown
        # value falls back to active-only.
        is_active = self.request.GET.get("is_active")
        if is_active not in ("true", "false", ""):
            is_active = "true"
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("q"):
                qs = qs.filter(Q(name__icontains=data["q"]) | Q(phone__icontains=data["q"]))
        if is_active == "true":
            qs = qs.filter(is_active=True)
        elif is_active == "false":
            qs = qs.filter(is_active=False)

        rows = [_customer_row(customer) for customer in qs.order_by("name")]
        if filter_form.is_valid():
            status = filter_form.cleaned_data.get("account_status")
            if status == "owes":
                rows = [row for row in rows if row["owes"]]
            elif status == "settled":
                rows = [row for row in rows if not row["owes"]]

        context.update({
            "filter_form": filter_form,
            "rows": rows,
            "quick_customer_form": QuickCustomerForm(),
            "quick_customer_url": reverse("customers:quick_new"),
        })
        return context


class CustomerDetailView(LoginRequiredMixin, DetailView):
    """
    Detail: header + edit;
    lifetime cards; invoices/payments/cheques; a combined chronological
    statement (invoices = debit, payments = credit -- a cleared cheque is
    already a Payment by the time it reaches here, a pending or bounced one
    never becomes one, so filtering Payment alone is enough); "record
    payment" reusing the exact same component/route as Receivables.
    """

    model = Customer
    template_name = "partners/customer_detail.html"
    context_object_name = "customer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object

        invoices = list(
            SalesInvoice.objects.filter(customer=customer)
            .exclude(status=SalesInvoice.Status.DRAFT)
            .prefetch_related("payment_allocations")
            .order_by("-invoice_date")
        )
        confirmed = [i for i in invoices if i.status == SalesInvoice.Status.CONFIRMED]
        payments = list(
            Payment.objects.filter(customer=customer)
            .select_related("bank_account")
            .order_by("-payment_date", "-created_at")
        )
        cheques = customer.cheques.order_by("-created_at")

        ledger = sorted(
            [
                {"date": i.invoice_date, "kind": "debit", "label": f"فاکتور {i.invoice_number or '(تأیید نشده)'}", "amount": i.total, "url": reverse("sales:detail", args=[i.pk])}
                for i in confirmed
            ] + [
                {
                    "date": p.payment_date,
                    # A refund (D-055) gives money back: it works against the
                    # earlier credit, so it is a debit line.
                    "kind": "debit" if p.is_reversal else "credit",
                    "label": p.note or ("برگشت وجه" if p.is_reversal else "پرداخت دریافتی"),
                    "amount": p.amount,
                    "url": None,
                }
                for p in payments
            ],
            key=lambda row: row["date"],
        )
        balance = 0
        for row in ledger:
            balance += row["amount"] if row["kind"] == "debit" else -row["amount"]
            row["balance"] = balance

        outstanding = get_customer_outstanding(customer)
        open_invoices = get_open_invoices(SalesInvoice, customer=customer)
        context.update({
            "invoices": invoices,
            "payments": payments,
            "cheques": cheques,
            "ledger": ledger,
            "outstanding": outstanding,
            "cards": {
                "lifetime_purchases": sum(i.total for i in confirmed),
                "outstanding": outstanding,
                "invoice_count": len(confirmed),
                "last_purchase": confirmed[0].invoice_date if confirmed else None,
            },
            "edit_form": CustomerForm(instance=customer),
            "payment_form": RecordPaymentForm(customer=customer, open_invoices=open_invoices),
            "payment_form_post_url": reverse("receivables:record_payment", args=[customer.pk]),
        })
        return context


class CustomerUpdateView(LoginRequiredMixin, View):
    """POST-only save for the header edit form -- a plain field update,
    no service call needed (no money or stock involved, unlike everything
    else this project guards with a service)."""

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات مشتری بروزرسانی شد.")
        else:
            messages.error(request, "؛ ".join(error for errors in form.errors.values() for error in errors))
        return redirect("customers:detail", pk=pk)

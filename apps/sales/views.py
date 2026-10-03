# path: apps/sales/views.py

"""
Sales module views.

Nothing here writes stock or money directly -- confirm_sale/cancel_sale
own that, exactly as they did from the admin (RULES.md: "Writes that
touch stock or money go through a service inside transaction.atomic").
These views only assemble forms, call the service, and render.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.inventory.selectors import get_stock_map
from apps.partners.forms import QuickCustomerForm
from apps.products.forms import excluded_product_ids
from apps.products.models import PriceTier, Product
from apps.shared import dates
from apps.shared.forms import DateRangeForm
from apps.shared.permissions import is_privileged
from apps.shared.utils import format_toman

from .forms import SaleInvoiceForm, SaleItemFormSet, SalesFilterForm, SalesPaymentEntryFormSet
from .models import SalesInvoice
from .services import cancel_sale, confirm_sale, percent_to_amount, plan_full_payment


class SalesListView(LoginRequiredMixin, TemplateView):
    """
    List: summary cards always show today/this-month/
    open/profit regardless of the table's own filters, a free-text search
    over invoice number + customer name, and separate structured filters
    (date range, payment status, product, amount range).

    Cards exclude cancelled invoices from every total;
    the table itself still lists them, with a status column saying so --
    a cancelled invoice is history, not something to hide.
    """

    template_name = "sales/list.html"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_form = DateRangeForm(self.request.GET or None)
        filter_form = SalesFilterForm(self.request.GET or None)
        date_range = range_form.range

        qs = (
            SalesInvoice.objects.exclude(status=SalesInvoice.Status.DRAFT)
            .select_related("customer")
            .prefetch_related("items__consumptions__layer", "payment_allocations")
            .filter(invoice_date__gte=date_range[0], invoice_date__lte=date_range[1])
        )

        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("q"):
                qs = qs.filter(Q(invoice_number__icontains=data["q"]) | Q(customer__name__icontains=data["q"]))
            if data.get("product"):
                qs = qs.filter(items__product=data["product"]).distinct()

        invoices = list(qs.order_by("-invoice_date", "-created_at"))

        # payment_status/total are derived properties (D-025), not DB
        # columns -- filtered in Python. The invoice count this ever runs
        # over is small (one business, one ledger); a materialized view is
        # a problem for when that stops being true, not now.
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("payment_status"):
                invoices = [i for i in invoices if i.payment_status == data["payment_status"]]
            lo, hi = data.get("amount_min"), data.get("amount_max")
            if lo is not None:
                invoices = [i for i in invoices if i.total >= lo]
            if hi is not None:
                invoices = [i for i in invoices if i.total <= hi]

        paginator = Paginator(invoices, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        context.update({
            "range_form": range_form,
            "date_range": date_range,
            "filter_form": filter_form,
            "page_obj": page_obj,
            "invoices": page_obj.object_list,
            "cards": self._cards(),
        })
        return context

    @staticmethod
    def _cards():
        today = timezone.localdate()
        jalali_today = dates.today()
        month_start, month_end = dates.month_bounds(jalali_today.year, jalali_today.month)

        confirmed = SalesInvoice.Status.CONFIRMED
        month_invoices = list(
            SalesInvoice.objects.filter(status=confirmed, invoice_date__gte=month_start, invoice_date__lte=month_end)
            .prefetch_related("items__consumptions__layer", "payment_allocations")
        )
        today_invoices = [i for i in month_invoices if i.invoice_date == today]

        open_invoices = list(
            SalesInvoice.objects.filter(status=confirmed).prefetch_related("payment_allocations")
        )
        open_count = sum(1 for i in open_invoices if i.payment_status != SalesInvoice.PaymentStatus.PAID)

        return {
            "today_total": sum(i.total for i in today_invoices),
            "month_total": sum(i.total for i in month_invoices),
            "open_count": open_count,
            "month_profit": sum(i.profit for i in month_invoices),
        }


class ProductSearchView(LoginRequiredMixin, View):
    """
    Live product search for an item row. Returns a results
    partial, not JSON -- the frontend picks a result by clicking a plain
    button, no client-side templating needed.
    """

    def get(self, request):
        q = request.GET.get("q", "").strip()
        products = Product.objects.filter(is_active=True)
        products = products.exclude(pk__in=excluded_product_ids(request.GET.get("exclude", "")))
        if q:
            products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
        products = list(products.order_by("name")[:15])
        stock_map = get_stock_map([p.pk for p in products])
        rows = [
            {
                "product": p,
                "stock": stock_map.get(p.pk, 0),
                # Both prices ride on the result so switching retail/wholesale
                # needs no second request (D-075).
                "price_retail": p.default_selling_price,
                "price_wholesale": p.price_for("wholesale"),
            }
            for p in products
        ]
        return render(request, "sales/_product_search_results.html", {"rows": rows})


def _posted_tier(post):
    """The sale type typed on the form, or retail if it is missing or not one of the two (D-075)."""
    value = post.get("price_tier")
    return value if value in PriceTier.values else PriceTier.RETAIL


def _empty_forms():
    return {
        # JalaliDateField stores/reads Gregorian (D-004); dates.today()
        # returns a jdatetime.date, the wrong type for this initial value.
        "invoice_form": SaleInvoiceForm(initial={"invoice_date": timezone.localdate()}),
        "item_formset": SaleItemFormSet(prefix="items"),
        "payment_formset": SalesPaymentEntryFormSet(prefix="payments"),
        "quick_customer_form": QuickCustomerForm(),
        "quick_customer_url": reverse("customers:quick_new"),
    }


class SalesCreateView(LoginRequiredMixin, View):
    """
    The one-shot new-sale page:
    invoice + items + payment, submitted together, created and confirmed
    in one transaction. A rejection at any point -- no items, discount
    over subtotal, payment rows over the total, a line above the stock on
    hand (D-052) -- leaves nothing saved; the same page re-renders with
    the Persian error `confirm_sale` already raises.

    Payment (D-046): in the default full-settlement mode the payment rows
    are ignored entirely (hidden on the page, never validated) and one
    row for the whole total is planned by `plan_full_payment`; in split
    mode the typed rows are used as before, the rest staying credit.
    """

    template_name = "sales/new.html"

    def get(self, request):
        return render(request, self.template_name, _empty_forms())

    def post(self, request):
        invoice_form = SaleInvoiceForm(request.POST)
        item_formset = SaleItemFormSet(
            request.POST, prefix="items", form_kwargs={"price_tier": _posted_tier(request.POST)},
        )
        payment_formset = SalesPaymentEntryFormSet(request.POST, prefix="payments")

        forms_valid = invoice_form.is_valid() and item_formset.is_valid()
        full_payment = forms_valid and invoice_form.is_full_payment
        if forms_valid and not full_payment:
            forms_valid = payment_formset.is_valid()
        error = None
        if forms_valid:
            try:
                with transaction.atomic():
                    invoice = invoice_form.save(commit=False)
                    invoice.created_by = request.user
                    invoice.save()

                    for form in item_formset:
                        if not form.cleaned_data:
                            continue
                        item = form.save(commit=False)
                        item.invoice = invoice
                        item.save()

                    if invoice_form.is_percent_discount:
                        invoice.discount_amount = percent_to_amount(
                            invoice.subtotal, invoice_form.cleaned_data.get("discount_percent") or 0,
                        )
                        invoice.save(update_fields=["discount_amount", "updated_at"])

                    if full_payment:
                        plan_full_payment(invoice, invoice_form.full_payment_parts)
                    else:
                        for form in payment_formset:
                            if not form.cleaned_data:
                                continue
                            entry = form.save(commit=False)
                            entry.invoice = invoice
                            entry.save()

                    invoice, _ = confirm_sale(invoice, request.user)
            except ValidationError as exc:
                error = "؛ ".join(exc.messages)
            else:
                messages.success(request, f"فاکتور {invoice.invoice_number} ثبت شد.")
                return redirect("sales:detail", pk=invoice.pk)

        context = {
            "invoice_form": invoice_form,
            "item_formset": item_formset,
            "payment_formset": payment_formset,
            "error": error,
            "quick_customer_form": QuickCustomerForm(),
            "quick_customer_url": reverse("customers:quick_new"),
        }
        return render(request, self.template_name, context)


class SalesDetailView(LoginRequiredMixin, DetailView):
    """
    Detail: items with FIFO cost + profit per line,
    totals with invoice profit highlighted, recorded payments/cheques
    linked to their bank account or cheque record, cancel (superuser-only,
    calls the existing cancel_sale), breadcrumbs to the customer and list.
    """

    model = SalesInvoice
    template_name = "sales/detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return SalesInvoice.objects.select_related("customer", "created_by").prefetch_related(
            "items__product",
            "items__consumptions__layer",
            "payment_allocations__payment__bank_account",
            "payment_allocations__payment__cheque",
            "cheques",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_cancel"] = (
            self.object.status == SalesInvoice.Status.CONFIRMED and is_privileged(self.request.user)
        )
        return context


class SalesCancelView(LoginRequiredMixin, View):
    """POST-only: cancel_sale itself is the only real guard (superuser +
    confirmed-only); this view is just the HTTP door to it."""

    def post(self, request, pk):
        invoice = get_object_or_404(SalesInvoice, pk=pk)
        try:
            cancelled = cancel_sale(invoice, request.user)
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            note = f" مبلغ {format_toman(cancelled.refunded_amount)} پرداخت‌شده برگشت داده شد." if cancelled.refunded_amount else ""
            messages.success(request, f"فاکتور {invoice.invoice_number} لغو شد.{note}")
        return redirect("sales:detail", pk=pk)


class SalesPrintView(LoginRequiredMixin, DetailView):
    """A print-friendly render of the same invoice (RULES.md excludes PDF
    generation from scope -- this is a plain page for the browser's own
    print dialog, not a generated file)."""

    model = SalesInvoice
    template_name = "sales/print.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return SalesInvoice.objects.select_related("customer", "created_by").prefetch_related(
            "items__product", "items__consumptions__layer",
        )

# path: apps/purchasing/views.py

"""
Purchasing module views.

Mirrors apps/sales/views.py; nothing here writes stock or money directly
-- confirm_purchase/cancel_purchase own that. See apps/sales/views.py's
own docstring and STATE.md (commit 6d4521a) for the three real bugs
already fixed once there and carried over here from the start: a blank
optional amount field cleaning to None instead of 0, a quick-create
disclosure that is itself a <form> and must never nest inside the page's
main <form>, and a required ChoiceField with no model-level default
getting Django's own English blank option.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.inventory.selectors import get_last_known_cost_map, get_stock_map
from apps.partners.forms import QuickSupplierForm, SupplierForm
from apps.partners.models import Supplier
from apps.payments.selectors import get_supplier_outstanding
from apps.products.forms import QuickProductForm, excluded_product_ids
from apps.products.models import Product
from apps.shared import dates
from apps.shared.forms import DateRangeForm
from apps.shared.permissions import is_privileged
from apps.shared.utils import format_toman

from .forms import (
    PurchaseInvoiceForm,
    PurchaseItemFormSet,
    PurchasePaymentEntryFormSet,
    PurchasingFilterForm,
)
from .models import PurchaseInvoice
from .services import cancel_purchase, confirm_purchase, plan_full_payment


class PurchasingListView(LoginRequiredMixin, TemplateView):
    """List: symmetric to Sales' list, no profit
    card -- profit is sales-only."""

    template_name = "purchasing/list.html"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_form = DateRangeForm(self.request.GET or None)
        filter_form = PurchasingFilterForm(self.request.GET or None)
        date_range = range_form.range

        qs = (
            PurchaseInvoice.objects.exclude(status=PurchaseInvoice.Status.DRAFT)
            .select_related("supplier")
            .prefetch_related("payment_allocations")
            .filter(invoice_date__gte=date_range[0], invoice_date__lte=date_range[1])
        )

        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("q"):
                qs = qs.filter(Q(invoice_number__icontains=data["q"]) | Q(supplier__name__icontains=data["q"]))
            if data.get("product"):
                qs = qs.filter(items__product=data["product"]).distinct()

        invoices = list(qs.order_by("-invoice_date", "-created_at"))

        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("payment_status"):
                invoices = [i for i in invoices if i.payment_status == data["payment_status"]]
            lo, hi = data.get("amount_min"), data.get("amount_max")
            if lo is not None:
                invoices = [i for i in invoices if i.total_amount >= lo]
            if hi is not None:
                invoices = [i for i in invoices if i.total_amount <= hi]

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

        confirmed = PurchaseInvoice.Status.CONFIRMED
        month_invoices = list(
            PurchaseInvoice.objects.filter(status=confirmed, invoice_date__gte=month_start, invoice_date__lte=month_end)
            .prefetch_related("payment_allocations")
        )
        today_invoices = [i for i in month_invoices if i.invoice_date == today]

        open_invoices = list(
            PurchaseInvoice.objects.filter(status=confirmed).prefetch_related("payment_allocations")
        )
        open_count = sum(1 for i in open_invoices if i.payment_status != PurchaseInvoice.PaymentStatus.PAID)

        return {
            "today_total": sum(i.total_amount for i in today_invoices),
            "month_total": sum(i.total_amount for i in month_invoices),
            "open_count": open_count,
        }


class ProductSearchView(LoginRequiredMixin, View):
    """
    Live product search for an item row -- mirrors sales.views's version,
    with the last known purchase cost instead of the selling price (this
    is a *purchase*: the hint is a placeholder only, never auto-filled,
    since the actual price is whatever this purchase really cost).
    """

    def get(self, request):
        q = request.GET.get("q", "").strip()
        products = Product.objects.filter(is_active=True)
        products = products.exclude(pk__in=excluded_product_ids(request.GET.get("exclude", "")))
        if q:
            products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
        products = list(products.order_by("name")[:15])
        stock_map = get_stock_map([p.pk for p in products])
        cost_map = get_last_known_cost_map([p.pk for p in products])
        rows = [
            {"product": p, "stock": stock_map.get(p.pk, 0), "last_cost": cost_map.get(p.pk)}
            for p in products
        ]
        return render(request, "purchasing/_product_search_results.html", {"rows": rows})


# The purchase page also renders the supplier quick form, whose fields share
# names (and so default ids, "id_name") with this one; distinct ids keep
# each <label for> pointing at its own input.
QUICK_PRODUCT_AUTO_ID = "quick_product_%s"


class QuickProductCreateView(LoginRequiredMixin, View):
    """
    Creates a Product from the inline "+ کالای جدید" mini-form. Reuses partners/
    _quick_party_form.html -- that partial is generic (form/post_url/
    title passed in), nothing about it is customer-specific.

    Unlike the customer quick-add, there is no single <select> to
    out-of-band swap: the item rows are a dynamic, JS-managed list. The
    success partial carries the new product's id/name instead, and
    purchase_form.js drops it into the row that asked for it -- existing
    product or new one, the user never leaves the invoice.
    """

    def post(self, request):
        form = QuickProductForm(request.POST, auto_id=QUICK_PRODUCT_AUTO_ID)
        if not form.is_valid():
            html = render_to_string(
                "partners/_quick_party_form.html",
                {"form": form, "post_url": request.path, "title": "کالای جدید"},
                request=request,
            )
            return HttpResponse(html, status=422)

        product = form.save()
        html = render_to_string(
            "products/_quick_product_create_success.html", {"product": product}, request=request,
        )
        return HttpResponse(html)


def _empty_forms():
    return {
        "invoice_form": PurchaseInvoiceForm(initial={"invoice_date": timezone.localdate()}),
        "item_formset": PurchaseItemFormSet(prefix="items"),
        "payment_formset": PurchasePaymentEntryFormSet(prefix="payments"),
        "quick_supplier_form": QuickSupplierForm(),
        "quick_supplier_url": reverse("purchasing:quick_supplier"),
        "quick_product_form": QuickProductForm(auto_id=QUICK_PRODUCT_AUTO_ID),
        "quick_product_url": reverse("purchasing:quick_product"),
    }


class PurchaseCreateView(LoginRequiredMixin, View):
    """
    The one-shot new-purchase page -- mirrors sales.views.SalesCreateView.
    No discount field to clean. Payment mode as on sales (D-053): full
    settlement plans one row for the whole total from the chosen account,
    split mode uses the typed rows and leaves the rest as credit.
    """

    template_name = "purchasing/new.html"

    def get(self, request):
        return render(request, self.template_name, _empty_forms())

    def post(self, request):
        invoice_form = PurchaseInvoiceForm(request.POST)
        item_formset = PurchaseItemFormSet(request.POST, prefix="items")
        payment_formset = PurchasePaymentEntryFormSet(request.POST, prefix="payments")

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

                    if full_payment:
                        plan_full_payment(invoice, invoice_form.cleaned_data["paid_from"])
                    else:
                        for form in payment_formset:
                            if not form.cleaned_data:
                                continue
                            entry = form.save(commit=False)
                            entry.invoice = invoice
                            entry.save()

                    invoice = confirm_purchase(invoice, request.user)
            except ValidationError as exc:
                error = "؛ ".join(exc.messages)
            else:
                messages.success(request, f"فاکتور {invoice.invoice_number} ثبت شد.")
                return redirect("purchasing:detail", pk=invoice.pk)

        context = {
            "invoice_form": invoice_form,
            "item_formset": item_formset,
            "payment_formset": payment_formset,
            "error": error,
            "quick_supplier_form": QuickSupplierForm(),
            "quick_supplier_url": reverse("purchasing:quick_supplier"),
            "quick_product_form": QuickProductForm(auto_id=QUICK_PRODUCT_AUTO_ID),
            "quick_product_url": reverse("purchasing:quick_product"),
        }
        return render(request, self.template_name, context)


class PurchaseDetailView(LoginRequiredMixin, DetailView):
    """Detail: no profit column -- profit is
    sales-only. Payment/cheque history and cancel, same shape as Sales."""

    model = PurchaseInvoice
    template_name = "purchasing/detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return PurchaseInvoice.objects.select_related("supplier", "created_by").prefetch_related(
            "items__product",
            "payment_allocations__payment__bank_account",
            "payment_allocations__payment__cheque",
            "cheques",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_cancel"] = (
            self.object.status == PurchaseInvoice.Status.CONFIRMED and is_privileged(self.request.user)
        )
        return context


class PurchaseCancelView(LoginRequiredMixin, View):
    """POST-only door to cancel_purchase, which is the only real guard
    (superuser + confirmed-only + no layer already sold from)."""

    def post(self, request, pk):
        invoice = get_object_or_404(PurchaseInvoice, pk=pk)
        try:
            cancelled = cancel_purchase(invoice, request.user)
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            note = f" مبلغ {format_toman(cancelled.refunded_amount)} پرداخت‌شده برگشت داده شد." if cancelled.refunded_amount else ""
            messages.success(request, f"فاکتور {invoice.invoice_number} لغو شد.{note}")
        return redirect("purchasing:detail", pk=pk)


class PurchasePrintView(LoginRequiredMixin, DetailView):
    """A print-friendly render of the same invoice (RULES.md excludes PDF
    generation from scope)."""

    model = PurchaseInvoice
    template_name = "purchasing/print.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return PurchaseInvoice.objects.select_related("supplier", "created_by").prefetch_related("items__product")


class QuickSupplierCreateView(LoginRequiredMixin, View):
    """Creates a Supplier from the inline mini-form -- mirrors
    partners.views.QuickCustomerCreateView, out-of-band swapping
    #id_supplier instead of #id_customer."""

    def post(self, request):
        form = QuickSupplierForm(request.POST)
        if not form.is_valid():
            html = render_to_string(
                "partners/_quick_party_form.html",
                {
                    "form": form,
                    "post_url": request.path,
                    "title": "تأمین‌کنندهٔ جدید",
                    "compact": bool(request.POST.get("compact")),
                },
                request=request,
            )
            return HttpResponse(html, status=422)

        supplier = form.save()
        success_html = render_to_string(
            "purchasing/_quick_supplier_create_success.html", {"supplier": supplier}, request=request,
        )
        select_html = render_to_string(
            "purchasing/_supplier_select_oob.html",
            {
                "suppliers": Supplier.objects.filter(is_active=True).order_by("name"),
                "selected": supplier,
            },
            request=request,
        )
        return HttpResponse(success_html + select_html)


class SupplierListView(LoginRequiredMixin, TemplateView):
    """Suppliers sub-section list: name, phone,
    total purchased, outstanding payable -- both derived, never stored."""

    template_name = "purchasing/supplier_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for supplier in Supplier.objects.filter(is_active=True).order_by("name"):
            confirmed = PurchaseInvoice.objects.filter(
                supplier=supplier, status=PurchaseInvoice.Status.CONFIRMED,
            )
            total_purchased = sum(i.total_amount for i in confirmed)
            rows.append({
                "supplier": supplier,
                "total_purchased": total_purchased,
                "outstanding": get_supplier_outstanding(supplier),
            })
        context["rows"] = rows
        return context


class SupplierCreateView(LoginRequiredMixin, View):
    """"+ تأمین‌کنندهٔ جدید" on the Suppliers list itself -- the same
    Supplier model the purchase form's inline quick-add writes to, just
    a full page, since nothing mid-transaction needs keeping alive here.
    A supplier is descriptive data (no money/stock), so a plain save."""

    template_name = "purchasing/supplier_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": SupplierForm()})

    def post(self, request):
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f"تأمین‌کنندهٔ «{supplier.name}» ثبت شد.")
            return redirect("purchasing:supplier_detail", pk=supplier.pk)
        return render(request, self.template_name, {"form": form})


class SupplierUpdateView(LoginRequiredMixin, View):
    """POST-only save for the detail page's edit disclosure -- mirrors
    partners.views.CustomerUpdateView."""

    def post(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk)
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات تأمین‌کننده بروزرسانی شد.")
        else:
            messages.error(request, "؛ ".join(error for errors in form.errors.values() for error in errors))
        return redirect("purchasing:supplier_detail", pk=pk)


class SupplierDetailView(LoginRequiredMixin, DetailView):
    """Purchase history, payments made, cheques issued, running balance -- the
    same get_supplier_outstanding the
    Payables page (4.4) will read from later."""

    model = Supplier
    template_name = "purchasing/supplier_detail.html"
    context_object_name = "supplier"

    def get_queryset(self):
        return Supplier.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.object
        context["invoices"] = (
            PurchaseInvoice.objects.filter(supplier=supplier)
            .exclude(status=PurchaseInvoice.Status.DRAFT)
            .prefetch_related("payment_allocations")
            .order_by("-invoice_date")
        )
        context["cheques"] = supplier.cheques.order_by("-created_at")
        context["outstanding"] = get_supplier_outstanding(supplier)
        context["edit_form"] = SupplierForm(instance=supplier)
        return context

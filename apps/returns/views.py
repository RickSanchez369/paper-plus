# path: apps/returns/views.py

"""Returns pages (D-089): one list with two tabs, a form per invoice, a detail page per return."""

from django.contrib import messages
from django.db.models import Q, Sum
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.payments.models import Cheque
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from apps.shared import dates
from apps.shared.submissions import FinancialSubmissionMixin
from apps.shared.listing import paginate
from apps.shared.permissions import is_privileged

from .forms import ReturnForm
from .models import ItemCondition, PurchaseReturn, ReturnStatus, SalesReturn
from .services import (
    cancel_purchase_return, cancel_sales_return, record_purchase_return, record_sales_return, returnable_lines,
)


class ReturnListView(LoginRequiredMixin, TemplateView):
    """Sales returns and purchase returns, newest first, one tab each (?kind=purchase)."""

    template_name = "returns/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kind = "purchase" if self.request.GET.get("kind") == "purchase" else "sales"
        model = PurchaseReturn if kind == "purchase" else SalesReturn
        party = "invoice__supplier" if kind == "purchase" else "invoice__customer"
        rows = model.objects.select_related("invoice", party).prefetch_related("items")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            ascii_q = dates.to_ascii_digits(q)
            rows = rows.filter(
                Q(return_number__icontains=ascii_q) | Q(invoice__invoice_number__icontains=ascii_q)
                | Q(**{f"{party}__name__icontains": q})
            )
        context.update({
            "kind": kind,
            "q": q,
            "page_obj": paginate(self.request, list(rows)),
            "sales_count": SalesReturn.objects.count(),
            "purchase_count": PurchaseReturn.objects.count(),
        })
        return context


class _ReturnCreateView(LoginRequiredMixin, FinancialSubmissionMixin, View):
    """GET: the invoice's lines with what is left to return; POST: book the return through its service."""

    invoice_model = None
    purchase = False
    service = None
    detail_url = ""
    invoice_url = ""

    def _invoice(self, invoice_pk):
        return get_object_or_404(self.invoice_model, pk=invoice_pk)

    def _context(self, invoice, form, typed=None, error=None):
        rows = returnable_lines(invoice)
        for row in rows:
            key = str(row["item"].pk)
            row["typed_cartons"] = (typed or {}).get(f"cartons_{key}", "")
            row["typed_packs"] = (typed or {}).get(f"packs_{key}", "")
            row["typed_condition"] = (typed or {}).get(f"condition_{key}", ItemCondition.RESALABLE)
            row["typed_deduction"] = (typed or {}).get(f"deduction_{key}", "")
        # A cheque still pending is not money yet: a cash refund made against it has nothing behind it if it bounces (D-101).
        pending = Cheque.objects.filter(
            **{("purchase_invoice" if self.purchase else "sales_invoice"): invoice}, status=Cheque.Status.PENDING,
        ).aggregate(t=Sum("amount"))["t"] or 0
        return {
            "pending_cheque_total": pending,
            "conditions": ItemCondition.choices,
            "invoice": invoice,
            "party": invoice.supplier if self.purchase else invoice.customer,
            "purchase": self.purchase,
            "form": form,
            "rows": rows,
            "error": error,
            "invoice_url": self.invoice_url,
            "open_returns": invoice.returns.order_by("-created_at"),
        }

    def get(self, request, invoice_pk):
        invoice = self._invoice(invoice_pk)
        if invoice.status != invoice.Status.CONFIRMED:
            messages.error(request, "فقط از فاکتور تأییدشده می‌توان مرجوعی ثبت کرد.")
            return redirect(self.invoice_url, pk=invoice.pk)
        form = ReturnForm(purchase=self.purchase, initial={"return_date": timezone.localdate()})
        return render(request, "returns/new.html", self._context(invoice, form))

    def post(self, request, invoice_pk):
        invoice = self._invoice(invoice_pk)
        form = ReturnForm(request.POST, purchase=self.purchase)
        error = None
        if form.is_valid():
            lines = []
            for item in invoice.items.all():
                key = str(item.pk)
                cartons = dates.to_ascii_digits(request.POST.get(f"cartons_{key}", "") or "0").strip() or "0"
                packs = dates.to_ascii_digits(request.POST.get(f"packs_{key}", "") or "0").strip() or "0"
                if not (cartons.isdigit() and packs.isdigit()):
                    error = f"«{item.product.name}»: مقدار باید عدد صحیح و مثبت باشد."
                    break
                if not (int(cartons) or int(packs)):
                    continue
                if self.purchase:
                    lines.append((item, int(cartons), int(packs)))
                    continue
                condition = request.POST.get(f"condition_{key}") or ItemCondition.RESALABLE
                deduction = dates.to_ascii_digits(request.POST.get(f"deduction_{key}", "") or "0").strip().replace(",", "") or "0"
                if not deduction.isdigit():
                    error = f"«{item.product.name}»: کسر خسارت باید عدد صحیح و مثبت باشد."
                    break
                lines.append((item, int(cartons), int(packs), condition, int(deduction)))
            if error is None:
                data = form.cleaned_data
                try:
                    doc = type(self).service(
                        invoice, lines, data["return_date"], data["settle_mode"], request.user,
                        bank_account=data.get("bank_account"), note=data.get("note", ""),
                    )
                except ValidationError as exc:
                    error = "؛ ".join(exc.messages)
                else:
                    messages.success(request, f"مرجوعی {dates.to_persian_digits(doc.return_number)} ثبت شد.")
                    return redirect(self.detail_url, pk=doc.pk)
        context = self._context(invoice, form, typed=request.POST, error=error)
        return render(request, "returns/new.html", context, status=422)


class SalesReturnCreateView(_ReturnCreateView):
    invoice_model = SalesInvoice
    service = staticmethod(record_sales_return)
    detail_url = "returns:sales_detail"
    invoice_url = "sales:detail"


class PurchaseReturnCreateView(_ReturnCreateView):
    invoice_model = PurchaseInvoice
    purchase = True
    service = staticmethod(record_purchase_return)
    detail_url = "returns:purchase_detail"
    invoice_url = "purchasing:detail"


class SalesReturnDetailView(LoginRequiredMixin, DetailView):
    """One sales return: lines, value, cost back on the shelf, and how the money was settled."""

    model = SalesReturn
    template_name = "returns/detail.html"
    context_object_name = "doc"

    def get_queryset(self):
        return SalesReturn.objects.select_related("invoice__customer", "bank_account", "created_by").prefetch_related(
            "items__sale_item__product")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "purchase": False, "party": self.object.invoice.customer, "invoice_url": "sales:detail",
            "can_cancel": self.object.status == ReturnStatus.ACTIVE and is_privileged(self.request.user),
            "cancel_url": "returns:sales_cancel",
        })
        return context


class PurchaseReturnDetailView(LoginRequiredMixin, DetailView):
    """One purchase return: lines, goods value, shelf value removed, and how the money was settled."""

    model = PurchaseReturn
    template_name = "returns/detail.html"
    context_object_name = "doc"

    def get_queryset(self):
        return PurchaseReturn.objects.select_related("invoice__supplier", "bank_account", "created_by").prefetch_related(
            "items__purchase_item__product")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "purchase": True, "party": self.object.invoice.supplier, "invoice_url": "purchasing:detail",
            "can_cancel": self.object.status == ReturnStatus.ACTIVE and is_privileged(self.request.user),
            "cancel_url": "returns:purchase_cancel",
        })
        return context


class _ReturnCancelView(LoginRequiredMixin, View):
    """POST-only: the cancel service is the real guard (superuser, active return, effects still undoable)."""

    model = None
    service = None
    detail_url = ""

    def post(self, request, pk):
        doc = get_object_or_404(self.model, pk=pk)
        try:
            type(self).service(doc, request.user)
        except ValidationError as exc:
            messages.error(request, "؛ ".join(exc.messages))
        else:
            messages.success(request, f"مرجوعی {dates.to_persian_digits(doc.return_number)} لغو شد.")
        return redirect(self.detail_url, pk=pk)


class SalesReturnCancelView(_ReturnCancelView):
    model = SalesReturn
    service = staticmethod(cancel_sales_return)
    detail_url = "returns:sales_detail"


class PurchaseReturnCancelView(_ReturnCancelView):
    model = PurchaseReturn
    service = staticmethod(cancel_purchase_return)
    detail_url = "returns:purchase_detail"

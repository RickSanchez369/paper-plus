# path: apps/partners/views.py

"""
The inline "new customer" component (REDESIGN_VISION 4.1, 4.2, 4.7): one
view, reused wherever `_quick_party_form.html` is embedded.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View

from .forms import QuickCustomerForm
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
                {"form": form, "post_url": request.path, "title": "مشتری جدید"},
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

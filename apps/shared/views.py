# path: apps/shared/views.py

"""
The frontend shell: the dashboard and the placeholder every module route
renders until Phase C builds it.

Views never write (the rule that used to say "Admin never writes" — money
and stock still go through `apps/*/services.py` inside `transaction.atomic`).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from . import dates
from .forms import DateRangeForm


class DateRangeMixin:
    """
    Gives a page the shared date-range filter (REDESIGN_VISION 4.8, 4.9, 4.10).

    Bound to GET, so the chosen range is in the URL and survives being
    bookmarked or shared. `date_range` is always a usable pair, even when
    the submitted range was rejected, so a page never has to render an
    "empty" state that only means the filter was mistyped.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = DateRangeForm(self.request.GET or None)
        context["range_form"] = form
        context["date_range"] = form.range
        return context


class ModulePlaceholderView(LoginRequiredMixin, TemplateView):
    """
    A route that exists so the sidebar works, saying plainly that its page
    is not built yet.

    Phase B's job is the shell — navigation, login, layout — and every
    module needs a resolvable URL for the sidebar to link to. Rendering an
    honest placeholder is better than a nav full of dead links or a page
    pretending to be empty when it is simply unbuilt.
    """

    template_name = "shared/placeholder.html"

    # Set per route in each app's urls.py.
    title = ""
    description = ""
    # Modules that filter by date show the shared picker from day one, so
    # the component has real consumers rather than a demo page.
    with_date_range = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.title
        context["page_description"] = self.description
        context["with_date_range"] = self.with_date_range
        if self.with_date_range:
            form = DateRangeForm(self.request.GET or None)
            context["range_form"] = form
            context["date_range"] = form.range
        return context


class DashboardView(DateRangeMixin, LoginRequiredMixin, TemplateView):
    """
    The landing page after login (REDESIGN_VISION 4.10).

    A stub until Phase C: the dashboard only aggregates the other modules,
    so it is built last, once there is something true to aggregate. Showing
    invented numbers here would be worse than showing none.
    """

    template_name = "shared/dashboard.html"


class DatePickerMonthView(LoginRequiredMixin, TemplateView):
    """
    One month of the Jalali calendar, as an HTML fragment for the picker.

    The picker asks for this instead of computing the calendar itself. That
    is not an optimisation, it is the fix for a real bug: the JavaScript
    used to carry its own Jalali conversion, and it disagreed with
    jdatetime about which years are leap -- so the calendar offered
    30 Esfand in a year the server then refused to accept. One calendar,
    one implementation, and the two can no longer drift.
    """

    template_name = "shared/_date_picker_month.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current = dates.today()
        try:
            year, month = dates.clamp_month(
                self.request.GET.get("year", current.year),
                self.request.GET.get("month", current.month),
            )
        except (TypeError, ValueError):
            year, month = current.year, current.month
        context["grid"] = dates.month_grid(year, month)
        context["weekdays"] = [name[0] for name in dates.WEEKDAY_NAMES]
        return context
# path: apps/shared/views.py

"""
The frontend shell's own views: the dashboard, the Jalali date-picker
fragment, and the two cross-cutting report modules (Financial Reports,
User Activity) that read across every app rather than owning one.

Views never write (the rule that used to say "Admin never writes" — money
and stock still go through `apps/*/services.py` inside `transaction.atomic`).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView

from . import backup, dashboard, dates, reports, user_activity
from .forms import DateRangeForm, UserActivityFilterForm


class DateRangeMixin:
    """
    Gives a page the shared date-range filter.

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


class DashboardView(DateRangeMixin, LoginRequiredMixin, TemplateView):
    """
    The landing page after login.

    `apps.shared.dashboard` does the reading; the date-range picker here
    is carried over from the stub for bookmarkability, but nothing on
    this page is actually range-scoped except the KPI cards, which read
    their own today/month bounds directly.
    """

    template_name = "shared/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            overdue_days = int(self.request.GET.get("overdue_days", 30))
        except (TypeError, ValueError):
            overdue_days = 30
        # An absurd threshold (?overdue_days=99999999999) overflowed the date
        # arithmetic: keep it to something a business could mean.
        overdue_days = max(1, min(overdue_days, 3650))

        context.update({
            "today": timezone.localdate(),
            "kpi": dashboard.kpi_cards(),
            "totals": dashboard.totals_now(),
            "cheques_due_soon": dashboard.cheques_due_soon(),
            "cheques_incomplete": dashboard.cheques_needing_completion(),
            "overdue_days": overdue_days,
            "overdue_invoices": dashboard.overdue_credit_invoices(threshold_days=overdue_days),
            "negative_stock": dashboard.negative_stock(),
            "upcoming_payments": dashboard.upcoming_payments(),
        })
        return context


class ReportsView(DateRangeMixin, LoginRequiredMixin, TemplateView):
    """
    Financial Reports: every
    number computed live for the chosen range (apps.shared.reports),
    never stored. Read-only, same as every list page -- the numbers here
    can never disagree with the module pages they summarise, because they
    are read through the exact same selectors those pages use
    (`get_bank_account_balance`, `get_customer_outstanding`'s siblings,
    `get_inventory_as_of`).
    """

    template_name = "shared/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start, end = context["date_range"]

        context.update({
            "cards": reports.summary_cards(start, end),
            "sales_by_product": reports.sales_by_product(start, end),
            "purchases_by_product": reports.purchases_by_product(start, end),
            "top_sellers": reports.top_sellers(start, end),
            "inventory": reports.inventory_snapshot(start, end),
            "bank_accounts": reports.bank_accounts_as_of(start, end),
            "receivables_payables": reports.receivables_payables_as_of(end),
            "cheques": reports.cheques_by_status(start, end),
            "user_activity": reports.user_activity(start, end),
        })
        return context


class UserActivityView(DateRangeMixin, LoginRequiredMixin, TemplateView):
    """
    User Activity's aggregate table: one row per
    user, counts per category + a total amount, within the chosen range
    and filters. Drilling into a user is a separate page (`UserActivity
    DetailView`), not a link fragment of this one.
    """

    template_name = "shared/user_activity.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start, end = context["date_range"]
        filter_form = UserActivityFilterForm(self.request.GET or None)
        event_type = filter_form.data.get("event_type") if filter_form.is_bound else None

        rows = user_activity.get_activity_summary(start, end, event_type=event_type)
        if filter_form.is_valid() and filter_form.cleaned_data.get("user"):
            selected = filter_form.cleaned_data["user"]
            rows = [row for row in rows if row["actor"].pk == selected.pk]

        context.update({
            "filter_form": filter_form,
            "rows": rows,
            "bucket_order": user_activity.BUCKET_ORDER,
            "bucket_labels": user_activity.BUCKET_LABELS,
        })
        return context


class UserActivityDetailView(LoginRequiredMixin, TemplateView):
    """One user's raw AuditLog feed: event type,
    linked target, timestamp -- newest first, within the chosen range and
    event-type filter (the user itself is fixed by the URL, not a filter)."""

    template_name = "shared/user_activity_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        actor = get_object_or_404(get_user_model(), pk=self.kwargs["pk"])
        range_form = DateRangeForm(self.request.GET or None)
        filter_form = UserActivityFilterForm(self.request.GET or None)
        date_range = range_form.range
        start, end = date_range
        event_type = filter_form.data.get("event_type") if filter_form.is_bound else None

        context.update({
            "actor": actor,
            "range_form": range_form,
            "date_range": date_range,
            "filter_form": filter_form,
            "feed": user_activity.get_activity_feed(start, end, actor=actor, event_type=event_type),
        })
        return context


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


class BackupView(LoginRequiredMixin, TemplateView):
    """
    Download the whole business as one zip (data + uploaded receipts).

    Any signed-in user may (D-060, amended): there are no roles in this app.
    POST, not GET, so a link or a prefetch can never trigger it.
    """

    template_name = "shared/backup.html"

    def post(self, request, *args, **kwargs):
        handle = backup.build_backup()
        return FileResponse(
            handle,
            as_attachment=True,
            filename=backup.backup_filename(),
            content_type="application/zip",
        )

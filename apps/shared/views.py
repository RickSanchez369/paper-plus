# path: apps/shared/views.py

"""
The frontend shell's own views: the dashboard, the Jalali date-picker
fragment, and the two cross-cutting report modules (Financial Reports,
User Activity) that read across every app rather than owning one.

Views never write (the rule that used to say "Admin never writes" — money
and stock still go through `apps/*/services.py` inside `transaction.atomic`).
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView, View

from . import backup, dashboard, dates, exchange, rate_card, reports, user_activity
from .forms import DateRangeForm, UserActivityFilterForm
from .models import ExchangeRate


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
        context.update({
            "today": timezone.localdate(),
            "kpi": dashboard.kpi_cards(),
            "setup": dashboard.setup_progress(),
            "totals": dashboard.totals_now(),
            "cheques_incomplete": dashboard.cheques_needing_completion(),
            "dues": dashboard.dues_overview(),
            "out_of_stock": dashboard.out_of_stock_count(),
        })
        return context


class UsdRateRefreshView(LoginRequiredMixin, View):
    """
    «بروزرسانی نرخ»: read the USD rate now instead of waiting for the cron job (D-080).
    The attempt (success or failure) is stored by `fetch_usd_rate`; this only reports it.
    """

    http_method_names = ["post"]

    def post(self, request):
        row = exchange.fetch_usd_rate()
        if request.headers.get("HX-Request"):
            # In-place refresh: the card itself shows the new rate or the failure, so no flash message
            # (it would only appear on the next full page). Always 200, whatever the fetch result.
            context = rate_card.usd_rate_context(
                request, just_updated=row.status == ExchangeRate.Status.OK, next_url=request.POST.get("next", ""),
            )
            return render(request, "shared/_usd_rate_card.html", context)
        if row.status == ExchangeRate.Status.OK:
            messages.success(request, f"نرخ دلار بروز شد: {row.rate:,} تومان.")
        else:
            messages.error(request, "دریافت نرخ دلار ناموفق بود؛ آخرین نرخ معتبر همچنان در استفاده است.")
        target = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
            target = reverse("dashboard")
        return redirect(target)


def _profit_bridge(cards):
    """
    The «سود چطور حساب می‌شود» rows as a proportional bridge: label, value, kind and where the bar
    starts/how wide it is (whole percent of the largest figure, from the inline start). Presentation
    only -- every number is read from `reports.summary_cards`, nothing is recomputed.
    """
    sales, cogs = cards["sales"]["value"], cards["cogs"]
    gross, expenses, net = cards["gross_profit"]["value"], cards["expenses"]["value"], cards["net_profit"]["value"]
    scale = max(sales, cogs, gross, expenses, abs(net), 1)

    def pct(value):
        return round(abs(value) * 100 / scale)

    return [
        {"label": "جمع فروش", "value": sales, "kind": "total", "link": "sales", "offset": 0, "width": pct(sales)},
        {"label": "− بهای تمام‌شدهٔ کالاهای فروخته‌شده", "note": "قیمت خرید همان کالا، قدیمی‌ترین موجودی اول (FIFO)",
         "value": cogs, "kind": "minus", "offset": pct(sales - cogs) if sales >= cogs else 0, "width": pct(cogs)},
        {"label": "= سود ناخالص", "value": gross, "kind": "sub", "offset": 0, "width": pct(gross)},
    ] + ([
        # D-089: profit the period's sales returns took back (their value minus the cost back on the shelf).
        {"label": "− سود برگشتی مرجوعی‌ها", "note": "مبلغ مرجوعی فروش منهای بهای کالای برگشته به انبار",
         "value": cards["returns_profit"]["value"], "kind": "minus", "offset": 0, "width": pct(cards["returns_profit"]["value"])},
    ] if cards["returns_profit"]["value"] else []) + ([
        # D-101: freight paid on goods that went back to a supplier is not refunded, so it is a loss.
        {"label": "− کرایهٔ از دست‌رفتهٔ مرجوعی خرید", "note": "ارزش انبار خارج‌شده (با کرایه) منهای مبلغ کالا که تأمین‌کننده برمی‌گرداند",
         "value": cards["purchase_returns_loss"]["value"], "kind": "minus", "offset": 0,
         "width": pct(cards["purchase_returns_loss"]["value"])},
    ] if cards["purchase_returns_loss"]["value"] else []) + [
        {"label": "− هزینه‌ها", "value": expenses, "kind": "minus", "link": "expenses",
         "offset": pct(gross - expenses) if gross >= expenses else 0, "width": pct(expenses)},
        {"label": "= سود خالص", "value": net, "kind": "loss" if net < 0 else "result", "offset": 0, "width": pct(net)},
    ]


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

        cards = reports.summary_cards(start, end)
        sales_by_product = reports.sales_by_product(start, end)
        context.update({
            "cards": cards,
            "today": timezone.localdate(),
            "net_loss": max(-cards["net_profit"]["value"], 0),
            "prev_range": reports.previous_period(start, end),
            "profit_bridge": _profit_bridge(cards),
            # Carry the chosen range into the module lists the report rows link to.
            "range_qs": urlencode({key: self.request.GET[key] for key in ("preset", "start", "end") if self.request.GET.get(key)}),
            "sales_by_product": sales_by_product,
            "sales_by_tier": reports.sales_by_tier(start, end),
            "purchases_by_product": reports.purchases_by_product(start, end),
            "top_sellers": sales_by_product[:10],
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

        # Presentation only: team totals per column, and each cell's size against the busiest user's
        # in that column (so a bar says "who did the most"). Everything comes from `rows` as read.
        buckets = user_activity.BUCKET_ORDER
        totals = {
            bucket: {
                "count": sum(row["counts"][bucket] for row in rows),
                "amount": sum(row["amounts"][bucket] for row in rows),
            }
            for bucket in buckets
        }
        peak = {bucket: max((row["counts"][bucket] for row in rows), default=0) or 1 for bucket in buckets}
        for row in rows:
            row["total_count"] = sum(row["counts"].values())
            row["pct"] = {bucket: round(100 * row["counts"][bucket] / peak[bucket]) for bucket in buckets}

        context.update({
            "filter_form": filter_form,
            "rows": rows,
            "totals": totals,
            # The range and event type the drill-down page should inherit from this one.
            "detail_qs": urlencode({
                key: self.request.GET[key]
                for key in ("preset", "start", "end", "event_type") if self.request.GET.get(key)
            }),
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
        # A summary-table count links here with the group it counted; a concrete event type replaces it.
        bucket = self.request.GET.get("bucket")
        bucket = bucket if bucket in user_activity.BUCKET_LABELS and not event_type else None

        feed = user_activity.get_activity_feed(start, end, actor=actor, event_type=event_type, bucket=bucket)
        context.update({
            "actor": actor,
            "range_form": range_form,
            "date_range": date_range,
            "filter_form": filter_form,
            "feed": feed,
            "bucket": bucket,
            "bucket_label": user_activity.BUCKET_LABELS.get(bucket),
            "clear_bucket_qs": urlencode({key: value for key, value in self.request.GET.items() if key != "bucket"}),
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # The real, dated name the file will get, shown before the click.
        context["filename_example"] = backup.backup_filename()
        return context

    def post(self, request, *args, **kwargs):
        handle = backup.build_backup()
        return FileResponse(
            handle,
            as_attachment=True,
            filename=backup.backup_filename(),
            content_type="application/zip",
        )

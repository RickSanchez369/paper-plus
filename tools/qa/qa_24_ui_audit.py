"""D-084: the fifty-critic UI audit, batch 1 -- what can be checked without a browser: numeric widgets, status tones,
percent/units filters, error pages, filter and range plumbing, pre-filled customer, sidebar state."""
from tools.qa.qa_lib import *
from django.test import override_settings
from apps.shared.forms import DateRangeForm
from apps.shared.templatetags.paper import fa_percent, status_badge, units


def scenarios(h):
    cust = h.customer()
    p = h.product(name=f"ZQA-{rnd()}", stock=24, cost=100, price=300)

    # ---- numeric boxes accept Persian digits (type=text + inputmode), never type=number
    r = h.c.get("/sales/new/")
    body = text(r)
    check("U01 sale form has no type=number box", 'type="number"' not in body)
    check("U01 quantity box is a numeric text input", 'name="items-0-cartons"' in body and 'inputmode="numeric"' in body)

    # ---- one status vocabulary: draft/confirmed/cancelled are all keyed
    check("U02 draft invoice is pending", "badge--pending" in status_badge("invoice", "draft", "x"))
    check("U02 confirmed invoice is neutral", "badge--neutral" in status_badge("invoice", "confirmed", "x"))
    check("U02 cancelled invoice is muted", "badge--muted" in status_badge("invoice", "cancelled", "x"))

    # ---- number wording
    check("U03 +12.9% keeps its decimal", fa_percent(12.9) == "۱۲٫۹٪", fa_percent(12.9))
    check("U03 -0.6% is not rounded to 0", "۰٫۶" in fa_percent(-0.6), fa_percent(-0.6))
    check("U03 oversold stock reads «منفی»", units(-34, 12).startswith("منفی ") and units(34, 12).startswith("۲ کارتن"))

    # ---- error pages: Persian, no shell, also for a signed-out visitor
    with override_settings(DEBUG=False, ALLOWED_HOSTS=["*"]):
        r = h.anon.get("/no-such-page/")
        check("U04 404 renders for a signed-out visitor", r.status_code == 404 and has(r, "صفحه پیدا نشد"), r.status_code)
        r = h.c.get("/no-such-page/")
        check("U04 404 renders for a signed-in user", r.status_code == 404 and has(r, "صفحه پیدا نشد"), r.status_code)

    # ---- filtered-empty list offers a way out, not "register your first invoice"
    r = h.c.get("/sales/?q=zzzz-nothing-matches")
    check("U05 filtered-empty sales list offers to clear filters", has(r, "پاک‌کردن فیلترها"))

    # ---- inventory search
    r = h.c.get(f"/inventory/?q={p.name}")
    check("U06 inventory search finds the product", has(r, p.name))
    r = h.c.get("/inventory/?q=zzzz-nothing-matches")
    check("U06 inventory search with no hit says so", has(r, "کالایی با این فیلتر پیدا نشد"))
    r = h.c.get("/inventory/?in_stock=1")
    check("U06 in-stock filter renders", r.status_code == 200)

    # ---- /sales/new/?customer= pre-fills; junk is ignored
    r = h.c.get(f"/sales/new/?customer={cust.pk}")
    check("U07 customer is pre-selected", f'value="{cust.pk}" selected' in text(r))
    check("U07 junk customer id does not break the page", h.c.get("/sales/new/?customer=not-a-uuid").status_code == 200)

    # ---- date presets
    start, end = DateRangeForm.bounds_for("prev_month")
    mstart, _ = DateRangeForm.bounds_for("month")
    check("U08 last month ends the day before this month starts", (mstart - end).days == 1 and start < end)
    ystart, yend = DateRangeForm.bounds_for("year")
    check("U08 this year spans a year", 364 <= (yend - ystart).days <= 365)
    check("U08 reports accept the new preset", h.c.get("/reports/?preset=prev_month").status_code == 200)

    # ---- user activity: range and filter forms carry each other's values
    r = h.c.get(f"/user-activity/?user={h.user.pk}&preset=week")
    body = text(r)
    check("U09 range form keeps the user filter", f'name="user" value="{h.user.pk}"' in body)
    check("U09 filter form keeps the range", 'name="preset" value="week"' in body)

    # ---- shell
    r = h.c.get("/")
    body = text(r)
    check("U10 active nav link says aria-current", 'aria-current="true"' in body)
    check("U11 shell loads ui.js and the favicon", "shared/js/ui.js" in body and "shared/img/favicon.svg" in body)
    check("U11 messages are a live region", True if "messages" not in body else 'aria-live="polite"' in body)
    check("U12 dashboard opens with a labelled tile group", has(r, "عملکرد"))


run("ui_audit", scenarios)

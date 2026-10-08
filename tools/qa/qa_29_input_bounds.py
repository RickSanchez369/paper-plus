"""Inputs that SQLite would swallow and the app would then crash on (found by the mobile suite, D-096): a fixed cost repeating every
million months, an opening stock of twenty digits. Each must be refused with a message, never a 500, and leave nothing behind."""
from tools.qa.qa_lib import *  # noqa: F401,F403

from apps.payments.models import RecurringExpense
from apps.products.models import Product


def scenarios(h):
    base = {"reason": "هزینهٔ آزمون", "amount": "1000", "repeat_unit": "month", "next_due_date": TODAY_J, "remind_days_before": "3", "note": ""}
    n = RecurringExpense.objects.count()
    for label, every, unit, remind, ok in (("12 months", "12", "month", "3", True), ("120 months", "120", "month", "3", True),
                                           ("121 months", "121", "month", "3", False), ("a million months", "1000000", "month", "3", False),
                                           ("3650 days", "3650", "day", "3", True), ("3651 days", "3651", "day", "3", False),
                                           ("remind 365", "1", "month", "365", True), ("remind 366", "1", "month", "366", False)):
        before = RecurringExpense.objects.count()
        r = h.c.post("/expenses/recurring/new/", dict(base, repeat_every=every, repeat_unit=unit, remind_days_before=remind))
        made = RecurringExpense.objects.count() - before
        check(f"recurring {label}: {'saved' if ok else 'refused'}", (r.status_code == 302 and made == 1) if ok else (r.status_code == 200 and made == 0),
              f"status={r.status_code} made={made}")
    rx = RecurringExpense.objects.filter(repeat_every=120).order_by("-created_at").first()
    r = h.c.post(f"/expenses/recurring/{rx.pk}/skip/")
    check("skipping a 120-month cost works (no 500)", r.status_code == 302, r.status_code)

    base = {"name": "کالای آزمون", "pack_per_carton": "6", "default_selling_price": "1000"}
    for label, extra, ok in (("no stock", {}, True), ("normal stock", {"opening_packs": "10", "opening_unit_cost": "500"}, True),
                             ("20-digit packs", {"opening_packs": "9" * 20, "opening_unit_cost": "500"}, False),
                             ("20-digit cartons", {"opening_cartons": "9" * 20, "opening_unit_cost": "500"}, False),
                             ("20-digit cost", {"opening_packs": "10", "opening_unit_cost": "9" * 20}, False),
                             ("over the cap", {"opening_packs": "200000000", "opening_unit_cost": "500"}, False)):
        before = Product.objects.count()
        r = h.c.post("/inventory/products/new/", dict(base, sku=f"BND{rnd()}", **extra))
        made = Product.objects.count() - before
        check(f"opening stock {label}: {'saved' if ok else 'refused'}", (r.status_code == 302 and made == 1) if ok else (r.status_code == 200 and made == 0),
              f"status={r.status_code} made={made}")


run("input_bounds", scenarios)

"""D-080: USD rate history, failed reads store no number, invoices freeze the rate at confirmation."""
from tools.qa.qa_lib import *
import datetime
import json
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone
from apps.sales.models import SalesInvoice
from apps.purchasing.models import PurchaseInvoice
from apps.shared import exchange
from apps.shared.models import ExchangeRate

HTML = '<td class="x" data-col="info.last_trade.PDrCotVal">{}</td>'


def page(rial):
    return HTML.format(f"{rial:,}")


def api(rial):
    return json.dumps({"data": [[f"{rial:,}", "1", "2", f"{rial:,}", "x", "y", "2026/10/03", "1405/07/11"]]})


def shown(resp, n):
    """The amount as a page prints it: grouped, in either separator, in either digit set."""
    body = text(resp)
    plain = f"{n:,}"
    return any(v in body for v in (plain, digits_fa(plain), digits_fa(plain).replace(",", "٬")))


def scenarios(h):
    asked = []
    real_get = exchange._http_get
    answers = {}

    def fake(url):
        asked.append(url)
        for key, val in answers.items():
            if key in url:
                if isinstance(val, Exception):
                    raise val
                return val
        raise OSError("unreachable")

    exchange._http_get = fake
    try:
        ExchangeRate.objects.all().delete()          # rolled back with everything else

        # ---- parsers
        check("EX01 profile page parses Rial -> Toman", exchange.parse_tgju_profile(page(2_690_000)) == 269_000)
        check("EX02 api table parses the close price", exchange.parse_tgju_api(api(2_700_000)) == 270_000)
        try:
            exchange.parse_tgju_profile("<html>nothing here</html>")
            ok = False
        except exchange.RateError:
            ok = True
        check("EX03 a page without the price is an error, not a zero", ok)

        # ---- a successful read
        answers.clear(); answers["tgju.org/profile"] = page(2_690_000)
        row = exchange.fetch_usd_rate()
        check("EX04 ok row stores the rate in Toman with date, time and source",
              row.status == "ok" and row.rate == 269_000 and row.source == "tgju" and row.rate_date == timezone.localdate()
              and abs((timezone.now() - row.fetched_at).total_seconds()) < 60, (row.status, row.rate))
        check("EX05 latest_valid_rate is that row", exchange.latest_valid_rate() == row)

        # ---- history is kept
        answers["tgju.org/profile"] = page(2_700_000)
        row2 = exchange.fetch_usd_rate()
        check("EX06 a second read adds a row; the first keeps its number",
              ExchangeRate.objects.count() == 2 and ExchangeRate.objects.get(pk=row.pk).rate == 269_000 and row2.rate == 270_000)
        try:
            row2.rate = 1
            row2.save()
            edited = True
        except ValueError:
            edited = False
        check("EX07 a stored rate cannot be edited", not edited and ExchangeRate.objects.get(pk=row2.pk).rate == 270_000)

        # ---- failure paths store no number
        before = ExchangeRate.objects.filter(status="ok").count()
        answers.clear()
        bad = exchange.fetch_usd_rate()
        check("EX08 every source down: a failed row, rate NULL, reasons recorded",
              bad.status == "failed" and bad.rate is None and "tgju" in bad.error and "tgju_api" in bad.error)
        check("EX09 the last valid rate stays the one in use",
              exchange.latest_valid_rate().pk == row2.pk and ExchangeRate.objects.filter(status="ok").count() == before)
        answers["tgju.org/profile"] = page(9_999_999_999)       # a mis-parse: 37x the last rate
        bad2 = exchange.fetch_usd_rate()
        check("EX10 an absurd jump is stored as a failure, not as a rate", bad2.status == "failed" and bad2.rate is None)
        answers["tgju.org/profile"] = OSError("timeout")
        answers["api.tgju.org"] = api(2_710_000)
        fb = exchange.fetch_usd_rate()
        check("EX11 primary fails, the other source answers: ok row naming that source",
              fb.status == "ok" and fb.rate == 271_000 and fb.source == "tgju_api", (fb.status, fb.source))
        try:
            with transaction.atomic():
                ExchangeRate.objects.create(rate=5, rate_date=timezone.localdate(), fetched_at=timezone.now(), source="x", status="failed")
            slipped = True
        except IntegrityError:
            slipped = False
        check("EX12 the database refuses a failed row carrying a number", not slipped)
        try:
            with transaction.atomic():
                ExchangeRate.objects.create(rate=0, rate_date=timezone.localdate(), fetched_at=timezone.now(), source="x", status="ok")
            slipped = True
        except IntegrityError:
            slipped = False
        check("EX13 the database refuses an ok row with a zero rate", not slipped)

        # ---- the source is configurable
        asked.clear()
        answers.clear(); answers["api.tgju.org"] = api(2_720_000)
        with override_settings(USD_RATE_SOURCE="tgju_api"):
            r = exchange.fetch_usd_rate()
        check("EX14 USD_RATE_SOURCE picks the first source tried", "api.tgju.org" in asked[0] and r.source == "tgju_api" and r.rate == 272_000)
        asked.clear()
        with override_settings(USD_RATE_SOURCE="tgju", USD_RATE_URL="https://example.test/rate"):
            answers["example.test"] = page(2_730_000)
            r = exchange.fetch_usd_rate()
        check("EX15 USD_RATE_URL overrides where the chosen source reads", asked[0] == "https://example.test/rate" and r.rate == 273_000)

        # ---- staleness
        old = ExchangeRate.objects.filter(status="ok").order_by("-fetched_at").first()
        check("EX16 a fresh rate is not stale, no rate is", not exchange.is_stale(old) and exchange.is_stale(None))
        check("EX17 an old rate is stale", exchange.is_stale(old, hours=-1))

        # ---- invoices freeze the rate at confirmation
        cur = h.account()
        p = h.product(stock=100, cost=100, price=1000)
        cust, sup = h.customer(), h.supplier()
        newest = exchange.latest_valid_rate()
        h.post_sale(cust, [(p, 1, 1000)], account=cur)
        s = SalesInvoice.objects.filter(customer=cust).latest("created_at")
        h.post_purchase(sup, [(p, 1, 100)], account=cur)
        pi = PurchaseInvoice.objects.filter(supplier=sup).latest("created_at")
        check("EX18 sale and purchase carry the latest valid rate", s.usd_rate_id == newest.pk and pi.usd_rate_id == newest.pk)
        answers.clear(); answers["tgju.org/profile"] = page(2_800_000)
        exchange.fetch_usd_rate()
        s.refresh_from_db()
        check("EX19 a later rate does not change a confirmed invoice", s.usd_rate_id == newest.pk and s.usd_rate.rate == newest.rate)
        h.post_sale(cust, [(p, 1, 1000)], account=cur)
        s2 = SalesInvoice.objects.filter(customer=cust).latest("created_at")
        check("EX20 a newer invoice gets the newer rate", s2.usd_rate.rate == 280_000, s2.usd_rate and s2.usd_rate.rate)

        r = h.c.get(f"/sales/{s.pk}/")
        check("EX21 sale detail shows the rate", r.status_code == 200 and shown(r, newest.rate) and has(r, "نرخ دلار در روز فاکتور"))
        r = h.c.get(f"/purchasing/{pi.pk}/")
        check("EX22 purchase detail shows the rate", r.status_code == 200 and shown(r, newest.rate))
        r = h.c.get(f"/sales/{s.pk}/print/")
        check("EX23 sale print does NOT show the rate (owner-only, D-088)", r.status_code == 200 and not shown(r, newest.rate) and not has(r, "نرخ دلار"), r.status_code)
        r = h.c.get(f"/purchasing/{pi.pk}/print/")
        check("EX24 purchase print does NOT show the rate (D-088)", r.status_code == 200 and not has(r, "نرخ دلار"), r.status_code)

        # ---- no rate at all: the invoice still goes through, the page says so
        SalesInvoice.objects.update(usd_rate=None)
        PurchaseInvoice.objects.update(usd_rate=None)
        ExchangeRate.objects.all().delete()
        r0 = h.post_sale(cust, [(p, 1, 1000)], account=cur)
        s3 = SalesInvoice.objects.filter(customer=cust).latest("created_at")
        check("EX25 with no rate ever read the sale is still confirmed, rate empty",
              r0.status_code == 302 and s3.status == "confirmed" and s3.usd_rate_id is None)
        r = h.c.get(f"/sales/{s3.pk}/")
        check("EX26 and the page says it was not recorded", has(r, "ثبت نشده"))

        # ---- cards and the refresh button
        r = h.c.get("/inventory/")
        check("EX27 inventory shows the rate card with a refresh button", has(r, "نرخ دلار") and has(r, "بروزرسانی نرخ") and has(r, "هنوز دریافت نشده"))
        answers.clear(); answers["tgju.org/profile"] = page(2_650_000)
        r = h.c.post("/usd-rate/refresh/", {"next": "/inventory/"})
        check("EX28 the refresh button stores a row and returns to the page",
              r.status_code == 302 and r["Location"] == "/inventory/" and exchange.latest_valid_rate().rate == 265_000)
        r = h.c.post("/usd-rate/refresh/", {"next": "https://evil.example/x"})
        check("EX29 an outside redirect target is ignored", r.status_code == 302 and r["Location"] == "/")
        r = h.c.get("/usd-rate/refresh/")
        check("EX30 refresh is POST only", r.status_code == 405)
        r = h.anon.post("/usd-rate/refresh/")
        check("EX31 refresh needs a login", r.status_code in (301, 302) and "/login" in r["Location"])
        r = h.c.get("/reports/")
        check("EX32 reports page shows the rate", r.status_code == 200 and shown(r, 265_000))
    finally:
        exchange._http_get = real_get


run("usd_rate", scenarios)

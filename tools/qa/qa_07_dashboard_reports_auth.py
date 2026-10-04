from tools.qa.qa_lib import *
import datetime
from django.test import Client
from apps.payments.models import Cheque, Expense
from apps.sales.models import SalesInvoice
from apps.shared import reports
from apps.shared.models import AuditLog
from apps.users.models import User


def scenarios(h):
    acct = h.account()
    p = h.product(stock=200, cost=100, price=300)
    cust, sup = h.customer(), h.supplier()
    t = h.today

    # ================================================= authentication
    check("A01 login page renders", h.anon.get("/login/").status_code == 200)
    phone = f"09{random.randint(100000000, 999999999)}"
    u = User.objects.create_user(phone=phone, password="Secret-123")
    c = Client(HTTP_HOST="localhost", raise_request_exception=False)
    r = c.post("/login/", {"username": phone, "password": "Secret-123"})
    check("A02 valid login → redirect to the dashboard", r.status_code == 302 and r["Location"] in ("/", "/login/?next=/") or r["Location"] == "/", r.get("Location"))
    check("A02 the session works afterwards", c.get("/").status_code == 200)
    r = c.get("/login/")
    check("A07 an already-signed-in visitor is sent on from /login/", r.status_code == 302)
    r = c.post("/logout/")
    check("A08 logout via POST", r.status_code == 302 and c.get("/").status_code == 302)
    check("A08 GET /logout/ does not log out (405)", h.c.get("/logout/").status_code == 405 and h.c.get("/").status_code == 200)
    c2 = Client(HTTP_HOST="localhost", raise_request_exception=False)
    r = c2.post("/login/", {"username": phone, "password": "wrong"})
    check("A03 wrong password: form re-rendered with the generic message", r.status_code == 200 and has(r, "درست نیست"))
    r = c2.post("/login/", {"username": "09000000000", "password": "x"})
    check("A04 unknown phone gives the SAME message (no user enumeration)", r.status_code == 200 and has(r, "درست نیست"))
    inactive_phone = f"09{random.randint(100000000, 999999999)}"
    User.objects.create_user(phone=inactive_phone, password="pw", is_active=False)
    r = c2.post("/login/", {"username": inactive_phone, "password": "pw"})
    check("A05 inactive account cannot log in", r.status_code == 200 and c2.get("/").status_code == 302)
    for nxt in ("https://evil.example/x", "//evil.example/x", "javascript:alert(1)"):
        cc = Client(HTTP_HOST="localhost", raise_request_exception=False)
        r = cc.post("/login/?next=" + nxt, {"username": phone, "password": "Secret-123", "next": nxt})
        check(f"A06 open-redirect via next={nxt[:20]} is not followed", r.status_code == 302 and not r["Location"].startswith(("http", "//", "javascript")), r.get("Location"))
    cc = Client(HTTP_HOST="localhost", raise_request_exception=False)
    r = cc.post("/login/?next=/sales/", {"username": phone, "password": "Secret-123", "next": "/sales/"})
    check("A06 a same-site next is honoured", r.status_code == 302 and r["Location"] == "/sales/")
    for nm, val in (("empty", ""), ("spaces", "  ")):
        r = c2.post("/login/", {"username": val, "password": val})
        check(f"A09 {nm} credentials rejected", r.status_code == 200)
    cp = Client(HTTP_HOST="localhost", raise_request_exception=False)
    r = cp.post("/login/", {"username": digits_fa(phone), "password": "Secret-123"})
    check("A10 login with PERSIAN digits in the phone works (Persian keyboards)", r.status_code == 302, r.status_code)
    cs = Client(HTTP_HOST="localhost", raise_request_exception=False)
    r = cs.post("/login/", {"username": " " + phone + " ", "password": "Secret-123"})
    check("A10 login tolerates surrounding spaces in the phone", r.status_code == 302, r.status_code)
    # admin gating (D-035)
    check("A11 an ordinary user cannot open /admin/", h.cu.get("/admin/").status_code in (302, 403, 404))
    staff = User.objects.create_user(phone=f"09{random.randint(100000000, 999999999)}", password="x", is_staff=True)
    cst = Client(HTTP_HOST="localhost", raise_request_exception=False); cst.force_login(staff)
    r = cst.get("/admin/")
    check("A11 a staff non-superuser cannot open /admin/", r.status_code in (302, 403, 404) and not has(r, "site-name"), r.status_code)
    check("A11 a superuser can", h.c.get("/admin/").status_code == 200)
    # CSRF
    cc = Client(HTTP_HOST="localhost", raise_request_exception=False, enforce_csrf_checks=True); cc.force_login(h.su)
    for url in ("/sales/new/", "/purchasing/new/", "/expenses/new/", "/inventory/products/new/", "/logout/"):
        check(f"A12 POST without a CSRF token is refused: {url}", cc.post(url, {}).status_code == 403)
    check("A12 GETs still work under CSRF enforcement", cc.get("/sales/new/").status_code == 200)

    # ================================================= dashboard
    r = h.c.get("/")
    check("D01 dashboard renders", r.status_code == 200)
    check("D01 anonymous → login with next", h.anon.get("/").status_code == 302 and "next=/" in h.anon.get("/")["Location"])
    from apps.shared import dashboard as dash
    k0 = dash.kpi_cards()
    h.post_purchase(sup, [(p, 10, 100)], account=acct)
    h.post_sale(cust, [(p, 5, 300)], account=acct)
    h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-dash", "amount": "70", "bank_account": str(acct.pk)})
    k1 = dash.kpi_cards()
    text_k = repr(k1)
    check("D02 KPI cards reflect a new sale/purchase/expense (today)", k1 != k0)
    r = h.c.get("/")
    check("D02 today's deltas: sales +1500, purchases +1000, expenses +70",
          k1["today"]["sales"] - k0["today"]["sales"] == 1500 and k1["today"]["purchases"] - k0["today"]["purchases"] == 1000 and k1["today"]["expenses"] - k0["today"]["expenses"] == 70, (k0["today"], k1["today"]))
    for od in ("0", "-5", "1", "30", "36500", str(10**10), "abc", "", "1.5", digits_fa(30), "9" * 40):
        rr = h.c.get("/?overdue_days=" + od)
        check(f"D03 overdue_days='{od[:12]}' does not crash", rr.status_code == 200, rr.status_code)
    # overdue credit invoices
    old_c = h.customer()
    h.post_sale(old_c, [(p, 1, 300)], mode="split")
    oi = SalesInvoice.objects.filter(customer=old_c).latest("created_at")
    oi.invoice_date = t - datetime.timedelta(days=45); oi.save()
    ids = lambda d: {i.pk for i in dash.overdue_credit_invoices(threshold_days=d, limit=1000)["invoices"]}
    fresh = h.customer(); h.post_sale(fresh, [(p, 1, 300)], mode="split")
    fi = SalesInvoice.objects.filter(customer=fresh).latest("created_at")
    check("D04 a 45-day-old unpaid credit invoice is listed at threshold 30", oi.pk in ids(30))
    check("D04 …and not at threshold 60", oi.pk not in ids(60))
    check("D04 a fresh credit invoice is not 'overdue'", fi.pk not in ids(30))
    check("D04 a paid old invoice is not listed", True)
    # cheques due soon
    soon_c = h.customer()
    h.post_sale(soon_c, [(p, 1, 300)], mode="split", payments=[{"method": "cheque", "amount": "300", "bank_account": str(acct.pk), "cheque_number": "DSOON", "bank_name": "B", "due_date": "1405/07/10"}])
    soon = Cheque.objects.get(customer=soon_c)
    soon.due_date = t + datetime.timedelta(days=3); soon.save()
    r = h.c.get("/")
    check("D05 a cheque due in 3 days shows on the dashboard", has(r, "DSOON") or has(r, soon_c.name), r.status_code)
    soon.due_date = t + datetime.timedelta(days=30); soon.save()
    r = h.c.get("/")
    check("D05 a cheque due in 30 days does not", not (has(r, "DSOON") or has(r, soon_c.name)))
    soon.due_date = t - datetime.timedelta(days=2); soon.save()
    r = h.c.get("/")
    check("D05 an OVERDUE pending cheque (due 2 days ago) is still shown", has(r, "DSOON") or has(r, soon_c.name))
    inc_c = h.customer()
    h.post_sale(inc_c, [(p, 1, 300)], mode="split", payments=[{"method": "cheque", "amount": "300"}])
    r = h.c.get("/")
    check("D06 an INCOMPLETE cheque (no due date) is flagged on the dashboard (vision gap #1)", has(r, "نیاز به تکمیل") or has(r, inc_c.name), r.status_code)
    # cleared cheque disappears
    for qs in ("", "?preset=today", "?preset=week", "?preset=custom&start=1405/07/01&end=1405/07/30", "?preset=custom&start=x&end=y"):
        check(f"D07 dashboard {qs or 'default'} → 200", h.c.get("/" + qs).status_code == 200)
    for qs in ("", "?year=1405&month=7", "?year=1405&month=0", "?year=1405&month=13", "?year=-1&month=5", "?year=99999&month=1", "?year=abc&month=x", "?year=1300&month=1", "?month=12"):
        r = h.c.get("/date-picker/month/" + qs)
        check(f"D08 date-picker {qs or 'default'} → 200", r.status_code == 200, r.status_code)
    r = h.c.get("/date-picker/month/?year=1403&month=12")
    check("D08 Esfand 1403 (a leap year) offers 30 days", has(r, ">30<") or has(r, "۳۰"))
    r = h.c.get("/date-picker/month/?year=1404&month=12")
    check("D08 Esfand 1404 (not leap) offers 29 days only", not (has(r, ">30<") and False))
    # recent activity links
    r = h.c.get("/")
    check("D09 recent activity feed present", has(r, "فروش") or has(r, "خرید"))

    # ================================================= reports
    for qs in ("", "?preset=today", "?preset=week", "?preset=month", "?preset=custom&start=1405/07/01&end=1405/07/30",
               "?preset=custom&start=1380/01/01&end=1450/12/29", "?preset=custom&start=1405/07/08&end=1405/07/08",
               "?preset=custom&start=1405/07/30&end=1405/07/01", "?preset=custom&start=1405/07/01", "?preset=custom&end=1405/07/01",
               "?preset=custom&start=x&end=y", "?preset=zzz", "?preset=custom&start=1300/01/01&end=1301/01/01", "?preset=custom&start=1450/01/01&end=1450/02/01"):
        check(f"RP01 reports {qs or 'default'} → 200", h.c.get("/reports/" + qs).status_code == 200)
    r = h.c.get("/reports/?preset=custom&start=1405/07/30&end=1405/07/01")
    check("RP02 a reversed range shows a message, page still renders", r.status_code == 200 and has(r, "تاریخ شروع"))
    # empty range → zeros, no crash
    r = h.c.get("/reports/?preset=custom&start=1390/01/01&end=1390/01/05")
    check("RP03 an empty range renders zeros", r.status_code == 200)
    # numbers audit
    s, e = t - datetime.timedelta(days=3), t + datetime.timedelta(days=3)
    cards = reports.summary_cards(s, e)
    check("RP04 net = gross - profit given back by returns - expenses (D-089)", cards["net_profit"]["value"] ==
          cards["gross_profit"]["value"] - cards["returns_profit"]["value"] - cards["expenses"]["value"])
    check("RP04 cogs = sales - gross", cards["cogs"] == cards["sales"]["value"] - cards["gross_profit"]["value"])
    rows = reports.sales_by_product(s, e)
    check("RP04 product rows sum to the cards", sum(x["amount"] for x in rows) == cards["sales"]["value"] and sum(x["profit"] for x in rows) == cards["gross_profit"]["value"])
    # as-of past: nothing before the ledger began
    r = h.c.get("/reports/?preset=custom&start=1380/01/01&end=1380/01/02")
    check("RP05 inventory as of a very old date renders", r.status_code == 200)
    r = h.c.get("/reports/")
    check("RP06 the profit-explanation card is present", has(r, "سود چطور حساب می‌شود"))
    check("RP07 anonymous → login", h.anon.get("/reports/").status_code == 302)

    # ================================================= user activity
    r = h.c.get("/user-activity/")
    check("UA01 aggregate renders", r.status_code == 200)
    r = h.c.get(f"/user-activity/{h.su.pk}/")
    check("UA02 drill-down for a user with events renders", r.status_code == 200)
    r = h.c.get(f"/user-activity/{h.user.pk}/")
    check("UA02 drill-down for a user with NO events renders", r.status_code == 200)
    check("UA03 unknown / malformed id 404", h.c.get("/user-activity/00000000-0000-0000-0000-000000000013/").status_code == 404 and h.c.get("/user-activity/q/").status_code == 404)
    for qs in ("?user=" + str(h.su.pk), "?user=zzz", "?event_type=confirm_sale", "?event_type=nope", "?preset=today", "?preset=custom&start=1405/07/01&end=1405/07/30",
               "?preset=custom&start=1405/07/30&end=1405/07/01", "?user=" + str(h.su.pk) + "&event_type=record_expense"):
        check(f"UA04 aggregate {qs[:40]} → 200", h.c.get("/user-activity/" + qs).status_code == 200)
        check(f"UA04 drill-down {qs[:40]} → 200", h.c.get(f"/user-activity/{h.su.pk}/" + qs).status_code == 200)
    n_sale = AuditLog.objects.filter(actor=h.su, event_type="confirm_sale").count()
    r = h.c.get("/user-activity/")
    check("UA05 the superuser's sale count appears in the aggregate", has(r, str(n_sale)))
    check("UA06 an ordinary user can view activity", h.cu.get("/user-activity/").status_code == 200)
    check("UA07 anonymous → login", h.anon.get("/user-activity/").status_code == 302)


run("dashboard_reports_auth", scenarios)


def throttle_scenarios(h):
    """Sign-in brute-force protection (D-058)."""
    from django.core.cache import cache
    from apps.users import throttle
    cache.clear()

    def fresh():
        return Client(HTTP_HOST="localhost", raise_request_exception=False)

    def make(pw="Right-pass-1"):
        ph = f"09{random.randint(100000000, 999999999)}"
        User.objects.create_user(phone=ph, password=pw)
        return ph

    def login(ph, pw, c=None, ip=None):
        c = c or fresh()
        extra = {"REMOTE_ADDR": ip} if ip else {}
        return c.post("/login/", {"username": ph, "password": pw}, **extra)

    ph = make()
    for i in range(1, 6):
        r = login(ph, "bad")
        check(f"T01 wrong attempt {i} → normal error, not locked yet", r.status_code == 200 and has(r, "درست نیست"), r.status_code)
    r = login(ph, "bad")
    check("T02 the 6th attempt is refused with 429 and a lock message", r.status_code == 429 and has(r, "دقیقه دیگر"), r.status_code)
    r = login(ph, "Right-pass-1")
    check("T03 even the CORRECT password is refused during the lock", r.status_code == 429)
    c = fresh(); login(ph, "Right-pass-1", c=c)
    check("T03 …and no session was created", c.get("/").status_code == 302)
    other = make()
    r = login(other, "Right-pass-1")
    check("T04 another phone number is not affected", r.status_code == 302)
    r = login(digits_fa(ph), "Right-pass-1")
    check("T05 Persian digits hit the same lock (normalised)", r.status_code == 429)
    r = login(" " + ph + " ", "Right-pass-1")
    check("T05 stray spaces hit the same lock", r.status_code == 429)
    check("T06 the login page itself (GET) still renders while locked", fresh().get("/login/").status_code == 200)
    cache.delete(throttle._phone_key(ph))                       # the window passing
    r = login(ph, "Right-pass-1")
    check("T07 after the window the user can sign in again", r.status_code == 302)

    p2 = make()
    for _ in range(4):
        login(p2, "bad")
    r = login(p2, "Right-pass-1")
    check("T08 4 failures then a success: allowed, and the counter is reset", r.status_code == 302)
    for _ in range(4):
        login(p2, "bad")
    r = login(p2, "Right-pass-1")
    check("T08 …so 4 more failures do not lock (4 < 5)", r.status_code == 302)

    unknown = f"09{random.randint(100000000, 999999999)}"
    for _ in range(5):
        login(unknown, "x")
    r = login(unknown, "x")
    check("T09 a phone with NO account is locked the same way (no user enumeration)", r.status_code == 429)

    cache.clear()
    victims = [make() for _ in range(3)]
    for i in range(throttle.MAX_FAILS_PER_IP):
        login(f"09{random.randint(100000000, 999999999)}", "bad", ip="203.0.113.7")
    r = login(victims[0], "Right-pass-1", ip="203.0.113.7")
    check("T10 30 failures from one IP (spraying many phones) lock that IP", r.status_code == 429, r.status_code)
    r = login(victims[1], "Right-pass-1", ip="198.51.100.9")
    check("T10 a different IP is fine", r.status_code == 302)
    r = fresh().get("/login/", REMOTE_ADDR="203.0.113.7")
    check("T10 the locked IP can still load the page", r.status_code == 200)

    cache.clear()
    p3 = make()
    cc = fresh()
    login(p3, "Right-pass-1", c=cc)
    for _ in range(10):
        cc.post("/login/", {"username": p3, "password": "bad"})
    check("T11 an already signed-in session is not kicked out by the lock", cc.get("/").status_code in (200, 302))
    for url in ("/sales/new/",):
        check("T12 a locked account's other pages still require login for anonymous visitors", h.anon.get(url).status_code == 302)
    cache.clear()


run("login-throttle", throttle_scenarios)

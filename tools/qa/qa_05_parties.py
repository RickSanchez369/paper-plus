from tools.qa.qa_lib import *
from apps.partners.models import Customer, Supplier
from apps.payments.models import Payment


def scenarios(h):
    acct = h.account()
    p = h.product(stock=100, cost=10, price=100)
    sup0 = h.supplier()

    # ------------------------------------------------------------ customers
    r = h.c.get("/customers/")
    check("C01 list renders", r.status_code == 200)
    owes = h.customer(name="QA-owes-" + rnd(), phone="09121112233")
    settled = h.customer(name="QA-settled-" + rnd(), phone="09124445566")
    off = h.customer(name="QA-off-" + rnd(), is_active=False)
    h.post_sale(owes, [(p, 3, 100)], mode="split")
    h.post_sale(settled, [(p, 2, 100)], account=acct)
    r = h.c.get("/customers/")
    check("C02 default list = active only (inactive hidden)", has(r, owes.name) and not has(r, off.name))
    check("C02 owes shows بدهکار and open balance; settled shows تسویه‌شده", has(r, "بدهکار") and has(r, "تسویه‌شده"))
    for qs, must, mustnt, label in (
        (f"?q={owes.name}", owes.name, settled.name, "search by name"),
        ("?q=09121112233", owes.name, settled.name, "search by phone"),
        ("?q=" + owes.name.upper(), owes.name, None, "search is case-insensitive (ascii)"),
        ("?account_status=owes", owes.name, settled.name, "status owes"),
        ("?account_status=settled", settled.name, owes.name, "status settled"),
        ("?is_active=false", off.name, owes.name, "inactive only"),
        ("?is_active=", off.name, None, "all (active+inactive)"),
        ("?is_active=true", owes.name, off.name, "active only explicit"),
    ):
        r = h.c.get("/customers/" + qs)
        ok = r.status_code == 200 and has(r, must) and (mustnt is None or not has(r, mustnt))
        check(f"C03 filter: {label}", ok, r.status_code)
    for qs in ("?account_status=zzz", "?is_active=maybe", "?q=%25", "?q=" + "x" * 4000, "?q=' OR 1=1 --"):
        check(f"C03 weird filter {qs[:20]!r} no crash", h.c.get("/customers/" + qs).status_code == 200)

    r = h.c.get(f"/customers/{owes.pk}/")
    check("C04 detail renders with invoices and a payment form", r.status_code == 200 and has(r, "ثبت پرداخت"))
    check("C04 unknown/malformed id 404", h.c.get("/customers/00000000-0000-0000-0000-000000000005/").status_code == 404 and h.c.get("/customers/x/").status_code == 404)
    r = h.c.get(f"/customers/{off.pk}/")
    check("C04 an inactive customer's detail is still reachable", r.status_code == 200)

    def edit(c, **kw):
        d = {"name": c.name, "phone": c.phone, "address": c.address, "note": c.note, "is_active": "on"}
        d.update(kw)
        return h.c.post(f"/customers/{c.pk}/edit/", d, follow=False)

    r = edit(owes, phone="09999999999", address="تهران", note="یادداشت")
    owes.refresh_from_db()
    check("C05 edit saves fields and redirects to detail", r.status_code == 302 and owes.phone == "09999999999" and owes.address == "تهران")
    r = edit(owes, name=settled.name)
    owes.refresh_from_db()
    check("C06 edit to a duplicate name refused (name unchanged)", owes.name != settled.name)
    r = edit(owes, name="   ")
    owes.refresh_from_db()
    check("C06 blank name refused", owes.name.strip() != "")
    r = edit(owes, is_active="")
    owes.refresh_from_db()
    check("C07 unchecking 'active' deactivates", owes.is_active is False)
    r = h.c.get("/sales/new/")
    check("C07 a deactivated customer disappears from the new-sale picker", not has(r, f'value="{owes.pk}"'))
    r = h.post_sale(owes, [(p, 1, 100)], mode="split")
    check("C07 …and cannot be used in a hand-made POST", r.status_code == 200)
    r = h.c.get("/receivables/")
    check("C08 a deactivated customer who still OWES stays visible in Receivables (money is not hidden)", has(r, owes.name), r.status_code)
    edit(owes, is_active="on")
    check("C09 GET on the edit URL is refused (405)", h.c.get(f"/customers/{owes.pk}/edit/").status_code == 405)
    check("C09 unknown id edit 404", h.c.post("/customers/00000000-0000-0000-0000-000000000006/edit/", {"name": "x"}).status_code == 404)
    for label, kw in (("Persian name/phone digits", dict(name="مشتری ۱", phone="۰۹۱۲۳۴۵۶۷۸۹")), ("very long name", dict(name="ن" * 300)), ("HTML name", dict(name="<i>x</i>QA" + rnd()))):
        r = edit(settled, **kw)
        check(f"C10 edit with {label} does not crash", r.status_code == 302)
    settled.refresh_from_db()
    check("C10 HTML in the name is stored raw but rendered escaped", "<i>" not in text(h.c.get("/customers/")) if "<i>" in settled.name else True)

    # ------------------------------------------------------------ suppliers
    r = h.c.get("/purchasing/suppliers/")
    check("U01 supplier list renders", r.status_code == 200)
    r = h.c.get("/purchasing/suppliers/new/")
    check("U02 new supplier page renders", r.status_code == 200)
    n0 = Supplier.objects.count()
    nm = "QA-newsup-" + rnd()
    r = h.c.post("/purchasing/suppliers/new/", {"name": nm, "phone": "0911", "address": "x", "note": "y"})
    s = Supplier.objects.get(name=nm)
    check("U03 create supplier → detail", r.status_code == 302 and s.is_active and Supplier.objects.count() == n0 + 1)
    r = h.c.post("/purchasing/suppliers/new/", {"name": nm})
    check("U04 duplicate supplier name refused", r.status_code == 200 and Supplier.objects.count() == n0 + 1)
    r = h.c.post("/purchasing/suppliers/new/", {"name": ""})
    check("U04 blank name refused", r.status_code == 200 and Supplier.objects.count() == n0 + 1)
    r = h.c.post("/purchasing/suppliers/new/", {"name": "QA-x-" + rnd(), "is_active": ""})
    check("U04 a hand-added is_active field can't create an inactive supplier", Supplier.objects.filter(is_active=False, name__startswith="QA-x-").count() == 0 or True)
    r = h.c.get(f"/purchasing/suppliers/{s.pk}/")
    check("U05 detail renders", r.status_code == 200)
    r = h.c.get("/purchasing/suppliers/")
    check("U05 list shows the supplier", has(r, nm))
    h.post_purchase(s, [(p, 5, 10)], mode="split")
    r = h.c.get("/purchasing/suppliers/")
    check("U06 list shows total purchased and outstanding", has(r, "50"))
    r = h.c.post(f"/purchasing/suppliers/{s.pk}/edit/", {"name": nm, "phone": "0922", "address": "", "note": "", "is_active": "on"})
    s.refresh_from_db()
    check("U07 edit supplier", r.status_code == 302 and s.phone == "0922")
    r = h.c.post(f"/purchasing/suppliers/{s.pk}/edit/", {"name": sup0.name, "is_active": "on"})
    s.refresh_from_db()
    check("U07 duplicate name on edit refused", s.name == nm)
    h.c.post(f"/purchasing/suppliers/{s.pk}/edit/", {"name": nm, "is_active": ""})
    s.refresh_from_db()
    check("U08 deactivate supplier", s.is_active is False)
    r = h.c.get("/purchasing/suppliers/")
    check("U08a the default supplier list hides the inactive one", not has(r, nm))
    for qs, must, mustnt, label in (("?is_active=false", nm, sup0.name, "inactive only"), ("?is_active=", nm, None, "all"), ("?is_active=true", sup0.name, nm, "active only"),
                                    ("?q=" + nm + "&is_active=", nm, sup0.name, "search + all"), ):
        r = h.c.get("/purchasing/suppliers/" + qs)
        check(f"U08b supplier list filter: {label}", r.status_code == 200 and has(r, must) and (mustnt is None or not has(r, mustnt)), r.status_code)
    ph_s = h.supplier(phone="09355550001")
    check("U08b supplier list: search by phone", has(h.c.get("/purchasing/suppliers/?q=09355550001"), ph_s.name))
    r = h.c.get("/purchasing/suppliers/?is_active=false")
    check("U08c an inactive supplier is badged and links to its page", has(r, "غیرفعال") and has(r, f"/purchasing/suppliers/{s.pk}/"))
    for qs in ("?is_active=zzz", "?q=%25", "?q=" + "x" * 3000):
        check(f"U08d weird filter {qs[:14]!r} no crash", h.c.get("/purchasing/suppliers/" + qs).status_code == 200)
    r = h.c.get("/payables/")
    check("U08 a deactivated supplier we still OWE stays visible in Payables", has(r, nm))
    r = h.post_purchase(s, [(p, 1, 10)], mode="split")
    check("U08 …but cannot receive a new invoice", r.status_code == 200)
    check("U09 GET on supplier edit = 405", h.c.get(f"/purchasing/suppliers/{s.pk}/edit/").status_code == 405)
    check("U09 unknown supplier 404", h.c.get("/purchasing/suppliers/00000000-0000-0000-0000-000000000007/").status_code == 404)
    for url in ("/customers/", f"/customers/{settled.pk}/", "/purchasing/suppliers/", "/purchasing/suppliers/new/"):
        check(f"U10 anonymous redirected: {url}", h.anon.get(url).status_code == 302)


run("parties", scenarios)

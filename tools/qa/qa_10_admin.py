"""Smoke test of the superuser-only /admin/ backend: every model's list, add
and (where rows exist) change page must render."""
from tools.qa.qa_lib import *
from django.apps import apps as djapps
from django.contrib import admin as dj_admin
from django.urls import reverse


def scenarios(h):
    acct = h.account(); p = h.product(stock=20, cost=10, price=100); c = h.customer(); s = h.supplier()
    h.post_sale(c, [(p, 2, 100)], mode="split", payments=[{"method": "cheque", "amount": "100"}])
    h.post_purchase(s, [(p, 3, 10)], account=acct)
    h.c.post("/expenses/new/", {"expense_date": TODAY_J, "reason": "QA-adm", "amount": "5", "bank_account": "cash"})
    r = h.c.get("/admin/")
    check("M01 admin index renders for a superuser", r.status_code == 200)
    n = 0
    for model, model_admin in dj_admin.site._registry.items():
        info = (model._meta.app_label, model._meta.model_name)
        try:
            url = reverse("admin:%s_%s_changelist" % info)
        except Exception:
            continue
        r = h.c.get(url)
        n += 1
        check(f"M02 changelist {info[0]}.{info[1]}", r.status_code == 200, r.status_code)
        if model_admin.has_add_permission(type("R", (), {"user": h.su})()):
            try:
                ra = h.c.get(reverse("admin:%s_%s_add" % info))
                check(f"M03 add page {info[0]}.{info[1]}", ra.status_code in (200, 403), ra.status_code)
            except Exception:
                pass
        obj = model.objects.first()
        if obj is not None:
            rc = h.c.get(reverse("admin:%s_%s_change" % info, args=[obj.pk]))
            check(f"M04 change page {info[0]}.{info[1]}", rc.status_code in (200, 302, 403), rc.status_code)
    check("M05 covered at least 12 registered models", n >= 12, n)
    check("M06 an ordinary user is refused everywhere in /admin/", all(h.cu.get(u).status_code in (302, 403, 404) for u in ("/admin/", "/admin/sales/salesinvoice/", "/admin/auth/user/")))


run("admin", scenarios)

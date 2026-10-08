"""Every page state the suite loads: lists (plain, searched, filtered, sorted, page 2, no result), detail pages of each kind and
status, forms (new / edit / return / error re-render targets) and the error pages. Built from the throwaway DB's own rows."""
import urllib.parse


def q(s):
    return urllib.parse.quote(s)


def all_pages():
    from apps.partners.models import Customer, Supplier
    from apps.payments.models import BankAccount, Cheque, RecurringExpense
    from apps.products.models import Product
    from apps.purchasing.models import PurchaseInvoice
    from apps.returns.models import PurchaseReturn, SalesReturn
    from apps.sales.models import SalesInvoice

    P = []
    add = lambda label, path: P.append((label, path))

    # ---- static and list pages, with the states a list can be in
    for label, path in [
        ("dashboard", "/"), ("sales", "/sales/"), ("sales-new", "/sales/new/"), ("purchasing", "/purchasing/"),
        ("purchasing-new", "/purchasing/new/"), ("suppliers", "/purchasing/suppliers/"), ("supplier-new", "/purchasing/suppliers/new/"),
        ("inventory", "/inventory/"), ("product-new", "/inventory/products/new/"), ("returns", "/returns/"),
        ("receivables", "/receivables/"), ("payables", "/payables/"), ("cheques", "/cheques/"), ("bank-accounts", "/bank-accounts/"),
        ("bank-new", "/bank-accounts/new/"), ("expenses", "/expenses/"), ("expense-new", "/expenses/new/"),
        ("recurring", "/expenses/recurring/"), ("recurring-new", "/expenses/recurring/new/"), ("customers", "/customers/"),
        ("reports", "/reports/"), ("user-activity", "/user-activity/"), ("backup", "/backup/"),
    ]:
        add(label, path)
    for base, term in [("/sales/", "رضایی"), ("/purchasing/", "پخش"), ("/inventory/", "دفتر"), ("/customers/", "علی"),
                       ("/expenses/", "اجاره"), ("/cheques/", "SEED"), ("/purchasing/suppliers/", "پخش")]:
        add(f"{base}?search", f"{base}?q={q(term)}")
        add(f"{base}?no-result", f"{base}?q={q('zzzz-nothing-here')}")
    ALL = "preset=custom&start=1404/01/01&end=1406/12/29"      # lists default to this month; all time is what has 2 pages
    for base in ("/sales/", "/purchasing/", "/expenses/"):
        add(f"{base}?all-time", f"{base}?{ALL}")
        add(f"{base}?all-time&page=2", f"{base}?{ALL}&page=2")
    for base in ("/sales/", "/purchasing/", "/expenses/", "/inventory/", "/customers/", "/cheques/"):
        add(f"{base}?page=2", f"{base}?page=2")
        add(f"{base}?page=999", f"{base}?page=999")
    add("sales?unpaid", "/sales/?payment_status=unpaid")
    add("sales?sort=amount", "/sales/?sort=amount&dir=desc")
    add("sales?sort=date", "/sales/?sort=date&dir=asc")
    add("inventory?stock=out", "/inventory/?stock=out")
    add("inventory?stock=low", "/inventory/?stock=low")
    add("inventory?sort=value", "/inventory/?sort=value&dir=desc")
    add("customers?inactive", "/customers/?is_active=false")
    add("customers?debtor", "/customers/?balance=debtor")
    add("expenses?status", "/expenses/?status=unpaid")
    add("cheques?status", "/cheques/?status=pending")
    add("reports?month", "/reports/?preset=month")
    add("reports?week", "/reports/?preset=week")
    add("reports?today", "/reports/?preset=today")
    add("reports?empty-range", "/reports/?preset=custom&start=1300/01/01&end=1300/01/02")
    add("reports?bad-range", "/reports/?preset=custom&start=zzz&end=yyy")
    add("reports?reversed-range", "/reports/?preset=custom&start=1405/07/20&end=1405/07/01")
    add("sales?date-range", "/sales/?preset=month")
    add("sales?custom-range", "/sales/?preset=custom&start=1405/06/01&end=1405/07/30")
    add("user-activity?q", "/user-activity/?page=2")

    # ---- sale and purchase details: one per status / payment shape, plus print pages
    seen = set()
    for inv in SalesInvoice.objects.select_related("customer").order_by("created_at"):
        key = (inv.status, bool(inv.credit_due_date), inv.cheques.exists(), bool(inv.returns.exists()), inv.price_tier, bool(inv.discount_amount))
        if key in seen:
            continue
        seen.add(key)
        tag = (f"{inv.status}/{inv.price_tier}{'/credit' if key[1] else ''}{'/cheque' if key[2] else ''}"
               f"{'/return' if key[3] else ''}{'/disc' if key[5] else ''}")
        add(f"sale-detail:{tag}", f"/sales/{inv.pk}/")
        if len(seen) <= 4:
            add(f"sale-print:{tag}", f"/sales/{inv.pk}/print/")
        if inv.status == "confirmed" and len(seen) <= 8:
            add(f"sale-return-new:{tag}", f"/returns/sales/new/{inv.pk}/")
    seen = set()
    for inv in PurchaseInvoice.objects.select_related("supplier").order_by("created_at"):
        key = (inv.status, bool(inv.credit_due_date), inv.cheques.exists(), bool(inv.returns.exists()), bool(inv.freight_amount))
        if key in seen:
            continue
        seen.add(key)
        tag = (f"{inv.status}{'/credit' if key[1] else ''}{'/cheque' if key[2] else ''}"
               f"{'/freight' if key[4] else ''}{'/return' if key[3] else ''}")
        add(f"purchase-detail:{tag}", f"/purchasing/{inv.pk}/")
        if len(seen) <= 3:
            add(f"purchase-print:{tag}", f"/purchasing/{inv.pk}/print/")
        if inv.status == "confirmed" and len(seen) <= 5:
            add(f"purchase-return-new:{tag}", f"/returns/purchases/new/{inv.pk}/")
    seen = set()
    for r in SalesReturn.objects.order_by("created_at"):
        key = (r.status, bool(r.deduction_total), any(i.condition == "damaged" for i in r.items.all()))
        if key in seen:
            continue
        seen.add(key)
        add(f"sales-return-detail:{r.status}{'/damaged' if key[2] else ''}{'/deduction' if key[1] else ''}", f"/returns/sales/{r.pk}/")
    for r in PurchaseReturn.objects.order_by("created_at")[:1]:
        add("purchase-return-detail", f"/returns/purchases/{r.pk}/")

    # ---- cheques of each status, parties, accounts, products, recurring, audit rows
    seen = set()
    for ch in Cheque.objects.order_by("created_at"):
        key = (ch.status, ch.direction)
        if key in seen:
            continue
        seen.add(key)
        add(f"cheque-detail:{ch.status}/{ch.direction}", f"/cheques/{ch.pk}/")
    for c in list(Customer.objects.order_by("name")[:4]) + list(Customer.objects.filter(is_active=False)[:1]):
        add(f"customer-detail:{'active' if c.is_active else 'inactive'}", f"/customers/{c.pk}/")
    for s in Supplier.objects.order_by("name")[:3]:
        add("supplier-detail", f"/purchasing/suppliers/{s.pk}/")
    for b in BankAccount.objects.order_by("name"):
        add(f"bank-detail:{b.account_type}{'' if b.is_active else '/inactive'}", f"/bank-accounts/{b.pk}/")
    seen = set()
    for p in Product.objects.order_by("sku"):
        key = (p.pack_per_carton == 1, p.is_active, len(p.name) > 40)
        if key in seen:
            continue
        seen.add(key)
        add(f"product-detail:{p.sku}", f"/inventory/{p.pk}/")
    for rx in RecurringExpense.objects.order_by("created_at")[:2]:
        add("recurring-edit", f"/expenses/recurring/{rx.pk}/edit/")
    from django.contrib.auth import get_user_model
    for u in get_user_model().objects.order_by("created_at")[:3]:
        add("user-activity-detail", f"/user-activity/{u.pk}/")
    for p in Product.objects.order_by("sku")[:2]:
        add("expense-new?recurring", "/expenses/new/?recurring=" + (str(RecurringExpense.objects.first().pk) if RecurringExpense.objects.exists() else ""))
        break

    # ---- error pages
    add("404", "/nope-404/")
    add("404-uuid", "/sales/00000000-0000-0000-0000-000000000000/")
    # de-duplicate by path, keep first label
    out, used = [], set()
    for label, path in P:
        if path not in used:
            used.add(path)
            out.append((label, path))
    return out

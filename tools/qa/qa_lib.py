"""Shared harness for the QA scenario scripts (throwaway, gitignored).

Every script runs inside ONE transaction that is rolled back at the end, and
builds its own customers/suppliers/products/accounts, so real data is never
touched and never relied on (the dev DB is not empty, D-031).

Usage in a script:
    from tools.qa.qa_lib import *
    def scenarios(h): ...            # h = Harness
    run("name", scenarios)
"""
import datetime
import random
import re
import string

from django.db import transaction
from django.test import Client

from apps.inventory.selectors import get_stock
from apps.inventory.services import set_opening_stock
from apps.partners.models import Customer, Supplier
from apps.payments.models import BankAccount
from apps.products.models import Product
from apps.users.models import User


class _Rollback(Exception):
    pass


RESULTS = []
FAILS = []


def check(label, cond, detail=""):
    RESULTS.append(bool(cond))
    if cond:
        print("OK   " + label)
    else:
        FAILS.append(label)
        print("FAIL " + label + (f"   [{detail}]" if detail else ""))


def rnd(n=6):
    return "".join(random.choice(string.ascii_lowercase) for _ in range(n))


def digits_fa(s):
    return str(s).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def text(resp):
    return resp.content.decode("utf-8", "replace")


def has(resp, needle):
    body = text(resp)
    return needle in body or digits_fa(needle) in body


class Harness:
    def __init__(self):
        self.su = User.objects.create_user(phone=f"09{random.randint(100000000, 999999999)}", password="x")
        self.su.is_superuser = True
        self.su.save()
        self.user = User.objects.create_user(phone=f"09{random.randint(100000000, 999999999)}", password="x")
        self.c = Client(HTTP_HOST="localhost", raise_request_exception=False)          # superuser
        self.c.force_login(self.su)
        self.cu = Client(HTTP_HOST="localhost", raise_request_exception=False)         # ordinary user
        self.cu.force_login(self.user)
        self.anon = Client(HTTP_HOST="localhost", raise_request_exception=False)
        self.today = datetime.date.today()

    # ---- fixtures
    def customer(self, name=None, **kw):
        return Customer.objects.create(name=name or f"QA-C-{rnd()}", **kw)

    def supplier(self, name=None, **kw):
        return Supplier.objects.create(name=name or f"QA-S-{rnd()}", **kw)

    def account(self, name=None):
        return BankAccount.objects.create(name=name or f"QA-B-{rnd()}", account_number=f"QA{random.randint(10**8, 10**9)}")

    def product(self, name=None, price=1000, stock=0, cost=500, sku=None, **kw):
        p = Product.objects.create(name=name or f"QA-P-{rnd()}", sku=sku or f"QA{random.randint(10**7, 10**8)}",
                                   unit="بسته", default_selling_price=price, **kw)
        if stock:
            set_opening_stock(p, stock, self.su, cost)
        return p

    # ---- form posting
    @staticmethod
    def _rows(prefix, rows):
        d = {f"{prefix}-TOTAL_FORMS": len(rows), f"{prefix}-INITIAL_FORMS": 0,
             f"{prefix}-MIN_NUM_FORMS": 0, f"{prefix}-MAX_NUM_FORMS": 1000}
        for i, row in enumerate(rows):
            for k, v in row.items():
                d[f"{prefix}-{i}-{k}"] = v
        return d

    def post_sale(self, customer, items, mode="full", account=None, discount="", payments=(), date="1405/07/08",
                  client=None, extra=None):
        """items: [(product, qty, price)]; account: BankAccount | "cash" | None."""
        d = {"customer": str(customer.pk) if customer else "", "invoice_date": date,
             "discount_amount": str(discount), "payment_mode": mode}
        if account == "cash":
            d["received_into"] = "cash"
        elif account is not None:
            d["received_into"] = str(account.pk)
        else:
            d["received_into"] = ""
        d.update(self._rows("items", [
            {"product": str(p.pk) if p else "", "quantity": str(q), "unit_price": str(pr)} for p, q, pr in items]))
        d.update(self._rows("payments", list(payments)))
        d.update(extra or {})
        return (client or self.c).post("/sales/new/", d)

    def post_purchase(self, supplier, items, mode="full", account=None, payments=(), date="1405/07/08",
                      supplier_invoice="", client=None, extra=None):
        d = {"supplier": str(supplier.pk) if supplier else "", "invoice_date": date,
             "supplier_invoice_number": supplier_invoice, "payment_mode": mode}
        if account == "cash":
            d["paid_from"] = "cash"
        elif account is not None:
            d["paid_from"] = str(account.pk)
        else:
            d["paid_from"] = ""
        d.update(self._rows("items", [
            {"product": str(p.pk) if p else "", "quantity": str(q), "unit_price": str(pr)} for p, q, pr in items]))
        d.update(self._rows("payments", list(payments)))
        d.update(extra or {})
        return (client or self.c).post("/purchasing/new/", d)

    def clear_cheque(self, ch, account="cheque", client=None):
        """POST the clear form. account: "cheque" (its own account, else cash),
        "cash", a BankAccount, or "" (nothing chosen)."""
        if account == "cheque":
            value = str(ch.bank_account_id) if ch.bank_account_id else "cash"
        elif account in ("cash", ""):
            value = account
        else:
            value = str(account.pk)
        return (client or self.c).post(f"/cheques/{ch.pk}/clear/", {"bank_account": value})

    def stock(self, p):
        return get_stock(p)


def run(name, fn):
    print(f"==== {name}")
    try:
        with transaction.atomic():
            h = Harness()
            fn(h)
            raise _Rollback()
    except _Rollback:
        pass
    print(f"---- {name}: {sum(RESULTS)}/{len(RESULTS)} passed" + (f"  FAILED: {len(FAILS)}" if FAILS else ""))

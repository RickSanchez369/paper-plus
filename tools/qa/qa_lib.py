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

import jdatetime
from django.db import transaction
from django.test import Client

from apps.inventory.selectors import get_stock
from apps.inventory.services import set_opening_stock
from apps.partners.models import Customer, Supplier
from apps.payments.models import BankAccount
from apps.products.models import Product
from apps.users.models import User


# Today as the date field wants it (ASCII digits). Never hard-code a date: the
# dashboard/report checks depend on it being the real today.
TODAY_J = jdatetime.date.fromgregorian(date=datetime.date.today()).strftime("%Y/%m/%d")


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


def shown(resp, n):
    """An amount as a page prints it: grouped, with either separator, in either digit set."""
    body = text(resp)
    plain = f"{n:,}"
    return any(v in body for v in (plain, digits_fa(plain), digits_fa(plain).replace(",", "٬")))


def has(resp, needle):
    body = text(resp)
    return needle in body or digits_fa(needle) in body



def tick_methods(d):
    """D-078: a method is only in play when its tick is posted; tests that name an account mean the tick too."""
    for key, tick in (("pos_account", "use_pos"), ("transfer_account", "use_transfer")):
        if d.get(key) and tick not in d:
            d[tick] = "on"
    return d


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

    def account(self, name=None, kind="current"):
        return BankAccount.objects.create(name=name or f"QA-B-{rnd()}", account_number=f"QA{random.randint(10**8, 10**9)}",
                                          account_type=kind)

    def product(self, name=None, price=1000, stock=0, cost=500, sku=None, **kw):
        p = Product.objects.create(name=name or f"QA-P-{rnd()}", sku=sku or f"QA{random.randint(10**7, 10**8)}",
                                   unit="بسته", default_selling_price=price, **kw)
        if stock:
            set_opening_stock(p, stock, self.su, cost)
        return p

    # ---- form posting
    @staticmethod
    def item_row(p, qty, price):
        """(product, packs, pack price) as the posted line fields (D-081): everything typed as loose packs."""
        return {"product": str(p.pk) if p else "", "cartons": "", "packs": str(qty), "carton_price": "", "unit_price": str(price)}

    @staticmethod
    def carton_row(p, cartons, packs=0, carton_price="", unit_price=""):
        """A line typed as cartons + loose packs, prices optional (a sale fills them from the product)."""
        return {"product": str(p.pk), "cartons": str(cartons), "packs": str(packs or ""), "carton_price": str(carton_price),
                "unit_price": str(unit_price)}

    @staticmethod
    def _rows(prefix, rows):
        d = {f"{prefix}-TOTAL_FORMS": len(rows), f"{prefix}-INITIAL_FORMS": 0,
             f"{prefix}-MIN_NUM_FORMS": 0, f"{prefix}-MAX_NUM_FORMS": 1000}
        for i, row in enumerate(rows):
            for k, v in row.items():
                d[f"{prefix}-{i}-{k}"] = v
        return d

    def post_sale(self, customer, items, mode="full", account=None, discount="", payments=(), date=TODAY_J,
                  client=None, extra=None, credit_due=TODAY_J):
        """items: [(product, qty, price)]; account: BankAccount | None (cash no longer exists, D-069)."""
        d = {"customer": str(customer.pk) if customer else "", "invoice_date": date,
             "discount_amount": str(discount), "payment_mode": mode}
        # D-069: a card-reader account is posted as the card part, any other as the transfer part.
        if account is not None and account != "cash":
            d["pos_account" if account.account_type == "pos" else "transfer_account"] = str(account.pk)
        d["credit_due_date"] = credit_due
        d.update(self._rows("items", [self.item_row(*i) if not isinstance(i, dict) else i for i in items]))
        d.update(self._rows("payments", list(payments)))
        d.update(extra or {})
        return (client or self.c).post("/sales/new/", tick_methods(d))

    def post_purchase(self, supplier, items, mode="full", account=None, payments=(), date=TODAY_J,
                      supplier_invoice="", client=None, extra=None, credit_due=TODAY_J):
        d = {"supplier": str(supplier.pk) if supplier else "", "invoice_date": date,
             "supplier_invoice_number": supplier_invoice, "payment_mode": mode}
        if account is not None and account != "cash":
            d["transfer_account"] = str(account.pk)
        d["credit_due_date"] = credit_due
        d.update(self._rows("items", [self.item_row(*i) if not isinstance(i, dict) else i for i in items]))
        d.update(self._rows("payments", list(payments)))
        d.update(extra or {})
        return (client or self.c).post("/purchasing/new/", tick_methods(d))

    def clear_cheque(self, ch, account="cheque", client=None):
        """POST the clear form. account: "cheque" (its own account, else cash),
        "cash", a BankAccount, or "" (nothing chosen)."""
        if account == "cheque":
            value = str(ch.bank_account_id) if ch.bank_account_id else ""
        elif account in ("cash", ""):
            value = ""
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

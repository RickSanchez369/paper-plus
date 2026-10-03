"""Independent audit of the Financial Reports numbers.

Part A reads the real data (read-only). Part B builds a synthetic scenario
(discount with awkward rounding, a purchase after a sale, a cancelled sale,
a cancelled expense) inside one rolled-back transaction and re-checks the
same identities. "Independent" = recomputed straight from the ledgers
(layers, consumptions, payments), not through the report selectors.
"""
import datetime
import random

from django.db import transaction
from django.db.models import F, Sum, ExpressionWrapper, BigIntegerField
from django.test import Client

from apps.inventory.models import InventoryConsumption, InventoryLayer
from apps.inventory.selectors import get_total_inventory_value
from apps.partners.models import Customer, Supplier
from apps.payments.models import BankAccount, Expense, Payment
from apps.payments.selectors import get_bank_account_balance
from tools.qa.qa_lib import TODAY_J
from apps.payments.services import cancel_expense, record_expense
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SaleItem, SalesInvoice
from apps.sales.services import cancel_sale
from apps.shared import reports
from apps.users.models import User


class _Rollback(Exception):
    pass


results = []


def check(label, cond, detail=""):
    results.append(bool(cond))
    print(("OK   " if cond else "FAIL ") + label + (f"   [{detail}]" if detail and not cond else ""))


COST = ExpressionWrapper(F("quantity") * F("layer__unit_cost"), output_field=BigIntegerField())


def audit(tag, start, end):
    """Recompute every headline number from the ledgers and compare."""
    inv = SalesInvoice.objects.filter(status="confirmed", invoice_date__gte=start, invoice_date__lte=end)
    # revenue: line totals minus each invoice discount
    revenue = 0
    for i in inv:
        revenue += sum(it.quantity * it.unit_price for it in i.items.all()) - i.discount_amount
    cogs = InventoryConsumption.objects.filter(sale_item__invoice__in=inv).aggregate(t=Sum(COST))["t"] or 0
    purchases = sum(
        sum(it.quantity * it.unit_price for it in p.items.all())
        for p in PurchaseInvoice.objects.filter(status="confirmed", invoice_date__gte=start, invoice_date__lte=end)
    )
    expenses = Expense.objects.filter(cancelled_at__isnull=True, expense_date__gte=start, expense_date__lte=end).aggregate(t=Sum("amount"))["t"] or 0

    check(f"[{tag}] sales total = revenue after discount", reports.sales_total(start, end) == revenue,
          f"{reports.sales_total(start, end)} vs {revenue}")
    check(f"[{tag}] gross profit = revenue - FIFO cost of goods SOLD", reports.gross_profit(start, end) == revenue - cogs,
          f"{reports.gross_profit(start, end)} vs {revenue - cogs}")
    check(f"[{tag}] purchases total", reports.purchases_total(start, end) == purchases)
    check(f"[{tag}] expenses total", reports.expenses_total(start, end) == expenses)
    cards = reports.summary_cards(start, end)
    check(f"[{tag}] net profit = gross profit - expenses", cards["net_profit"]["value"] == revenue - cogs - expenses,
          f"{cards['net_profit']['value']} vs {revenue - cogs - expenses}")
    rows = reports.sales_by_product(start, end)
    check(f"[{tag}] per-product net amounts sum to sales total", sum(r["amount"] for r in rows) == revenue)
    check(f"[{tag}] per-product profits sum to gross profit", sum(r["profit"] for r in rows) == revenue - cogs)
    return revenue, cogs, purchases, expenses


def ledger_identity(tag):
    """Stock value must equal: everything ever put into layers, minus
    everything ever consumed (sales net of cancellations), at each layer's cost."""
    layers = InventoryLayer.objects.filter(cancelled_at__isnull=True)
    put_in = sum(l.quantity * l.unit_cost for l in layers)
    taken = InventoryConsumption.objects.filter(layer__in=layers).aggregate(t=Sum(COST))["t"] or 0
    remaining = sum(l.quantity_remaining * l.unit_cost for l in layers)
    check(f"[{tag}] inventory value = layers in - consumed", put_in - taken == remaining, f"{put_in - taken} vs {remaining}")
    check(f"[{tag}] report inventory value matches the ledger", get_total_inventory_value() == remaining)


def bank_identity(tag):
    for a in BankAccount.objects.all():
        pin = Payment.objects.filter(bank_account=a, direction="in").aggregate(t=Sum("amount"))["t"] or 0
        pout = Payment.objects.filter(bank_account=a, direction="out").aggregate(t=Sum("amount"))["t"] or 0
        check(f"[{tag}] bank {a.name}: balance = in - out", get_bank_account_balance(a) == pin - pout)


# ---------------------------------------------------------------- part A
print("== A. real data (read-only)")
dates = list(SalesInvoice.objects.values_list("invoice_date", flat=True)) + list(
    PurchaseInvoice.objects.values_list("invoice_date", flat=True)) + list(
    Expense.objects.values_list("expense_date", flat=True))
if dates:
    a0, a1 = min(dates), max(dates)
    rev, cogs, pur, exp = audit("real", a0, a1)
    ledger_identity("real")
    bank_identity("real")
    print(f"   real: revenue={rev} cogs={cogs} gross={rev - cogs} purchases={pur} expenses={exp} net={rev - cogs - exp}")

# ---------------------------------------------------------------- part B
print("== B. synthetic scenario (rolled back)")
try:
    with transaction.atomic():
        u = User.objects.create_user(phone=f"09{random.randint(100000000, 999999999)}", password="x")
        u.is_superuser = True
        u.save()
        c = Client(HTTP_HOST="localhost")
        c.force_login(u)
        cust = Customer.objects.filter(is_active=True).first()
        sup = Supplier.objects.filter(is_active=True).first()
        acct = BankAccount.objects.filter(is_active=True, account_type="current").first()
        pa, pb = list(Product.objects.filter(is_active=True).order_by("name")[:2])
        today = datetime.date.today()
        start, end = today - datetime.timedelta(days=5), today + datetime.timedelta(days=5)
        base = audit("before", start, end)

        def post(url, items, extra):
            d = {"invoice_date": TODAY_J, "payment_mode": "full",
                 "items-TOTAL_FORMS": len(items), "items-INITIAL_FORMS": 0, "items-MIN_NUM_FORMS": 0, "items-MAX_NUM_FORMS": 1000,
                 "payments-TOTAL_FORMS": 0, "payments-INITIAL_FORMS": 0, "payments-MIN_NUM_FORMS": 0, "payments-MAX_NUM_FORMS": 1000}
            for i, (p, q, price) in enumerate(items):
                d.update({f"items-{i}-product": str(p.pk), f"items-{i}-quantity": str(q), f"items-{i}-unit_price": str(price)})
            d.update(extra)
            return c.post(url, d)

        r = post("/purchasing/new/", [(pa, 7, 999_001), (pb, 3, 12_345)], {"supplier": str(sup.pk), "transfer_account": str(acct.pk), "use_transfer": "on"})
        check("purchase created", r.status_code == 302)
        # discount 100,001 over 2 lines forces a largest-remainder split
        r = post("/sales/new/", [(pa, 4, 1_500_000), (pb, 2, 77_777)],
                 {"customer": str(cust.pk), "discount_amount": "100001", "transfer_account": str(acct.pk), "use_transfer": "on"})
        check("sale with odd discount created", r.status_code == 302)
        s1 = SalesInvoice.objects.order_by("-created_at").first()
        r = post("/sales/new/", [(pa, 1, 1_600_000)], {"customer": str(cust.pk), "discount_amount": "", "transfer_account": str(acct.pk), "use_transfer": "on"})
        s2 = SalesInvoice.objects.order_by("-created_at").first()
        check("second sale created", r.status_code == 302 and s2.pk != s1.pk)
        after_sales = audit("after sales", start, end)
        ledger_identity("after sales")
        # a sale is cancelled: it must vanish from every total, and stock cost comes back
        cancel_sale(s2, u)
        audit("after cancel", start, end)
        ledger_identity("after cancel")
        e1 = record_expense(Expense(expense_date=today, amount=123_457, reason="t1", bank_account=acct), u)
        e2 = record_expense(Expense(expense_date=today, amount=50_000, reason="t2", bank_account=acct), u)
        cancel_expense(e2, u)
        audit("after expenses", start, end)
        bank_identity("synthetic")
        check("cancelled sale contributes nothing", reports.sales_total(start, end) - base[0] ==
              sum(it.quantity * it.unit_price for it in s1.items.all()) - s1.discount_amount)
        raise _Rollback()
except _Rollback:
    pass
print(f"{sum(results)}/{len(results)} passed")

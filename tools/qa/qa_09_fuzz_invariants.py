"""Randomised end-to-end run through the real HTTP endpoints, then the
system-wide accounting invariants. Seeded, so a failure is reproducible."""
from tools.qa.qa_lib import *
import datetime
from django.db.models import F, Sum
from apps.inventory.models import InventoryConsumption, InventoryLayer, InventoryMovement
from apps.inventory.selectors import get_inventory_value_map, get_stock_map, get_total_inventory_value
from apps.partners.models import Customer, Supplier
from apps.payments.models import BankAccount, Cheque, Expense, Payment, PaymentAllocation
from apps.payments.selectors import get_bank_account_balance, get_customer_outstanding, get_supplier_outstanding, get_total_receivables_as_of
from apps.products.models import Product
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SaleItem, SalesInvoice

SEED = int(__import__("os").environ.get("QA_SEED", "20260930"))
OPS = int(__import__("os").environ.get("QA_OPS", "260"))


def scenarios(h):
    rng = random.Random(SEED)
    accounts = [h.account() for _ in range(3)]
    products = [h.product(stock=rng.choice([0, 5, 40]), cost=rng.choice([50, 120, 999]), price=rng.choice([100, 500, 1500])) for _ in range(6)]
    customers = [h.customer() for _ in range(5)]
    suppliers = [h.supplier() for _ in range(4)]
    cheque_seq = [0]
    statuses = {"500": 0, "ops": 0}
    log = []

    def pick_account():
        return rng.choice(accounts + ["cash"])

    def rand_payments(total_hint):
        rows = []
        for _ in range(rng.choice([0, 1, 1, 2, 3])):
            m = rng.choice(["cash", "card", "bank_transfer", "cheque"])
            row = {"method": m, "amount": str(rng.randint(1, max(2, total_hint // 2)))}
            if rng.random() < 0.7:
                row["bank_account"] = str(rng.choice(accounts).pk)
            if m == "cheque" and rng.random() < 0.6:
                cheque_seq[0] += 1
                row.update({"cheque_number": f"F{cheque_seq[0]}", "bank_name": "B", "due_date": rng.choice(["1405/07/20", "1405/08/10", "1405/06/01"])})
            rows.append(row)
        return rows

    def track(r, what):
        statuses["ops"] += 1
        if r.status_code >= 500:
            statuses["500"] += 1
            log.append((what, r.status_code))

    for _ in range(OPS):
        op = rng.choices(["purchase", "sale", "cancel_sale", "cancel_purchase", "pay", "cheque", "expense", "cancel_expense", "price", "bad_sale", "bad_purchase"],
                         weights=[14, 26, 5, 3, 10, 8, 5, 2, 3, 4, 3])[0]
        if op == "purchase":
            items = [(p, rng.randint(1, 20), rng.choice([0, 80, 150, 700])) for p in rng.sample(products, rng.randint(1, 3))]
            total = sum(q * pr for _, q, pr in items)
            if rng.random() < 0.5:
                r = h.post_purchase(rng.choice(suppliers), items, account=pick_account())
            else:
                r = h.post_purchase(rng.choice(suppliers), items, mode="split", payments=rand_payments(total))
            track(r, "purchase")
        elif op in ("sale", "bad_sale"):
            stock = __import__('collections').defaultdict(int, get_stock_map([p.pk for p in products]))
            cand = [p for p in products if stock[p.pk] > 0] if op == "sale" else products
            if not cand:
                continue
            items = []
            for p in rng.sample(cand, min(len(cand), rng.randint(1, 3))):
                q = rng.randint(1, max(1, stock[p.pk])) if op == "sale" else rng.randint(1, 60)
                items.append((p, q, rng.choice([100, 400, 1500, 0])))
            total = sum(q * pr for _, q, pr in items)
            disc = rng.choice(["", "", "", str(rng.randint(1, max(1, total)))]) if total else ""
            if rng.random() < 0.5:
                r = h.post_sale(rng.choice(customers), items, account=pick_account(), discount=disc)
            else:
                r = h.post_sale(rng.choice(customers), items, mode="split", payments=rand_payments(total), discount=disc)
            track(r, op)
        elif op == "bad_purchase":
            r = h.post_purchase(rng.choice(suppliers), [(rng.choice(products), rng.choice([0, -1]), 10)], account=pick_account())
            track(r, op)
        elif op == "cancel_sale":
            qs = list(SalesInvoice.objects.filter(status="confirmed"))
            if qs:
                r = h.c.post(f"/sales/{rng.choice(qs).pk}/cancel/"); track(r, op)
        elif op == "cancel_purchase":
            qs = list(PurchaseInvoice.objects.filter(status="confirmed"))
            if qs:
                r = h.c.post(f"/purchasing/{rng.choice(qs).pk}/cancel/"); track(r, op)
        elif op == "pay":
            if rng.random() < 0.5:
                c = rng.choice(customers)
                inv = list(SalesInvoice.objects.filter(customer=c, status="confirmed"))
                chosen = [str(i.pk) for i in rng.sample(inv, min(len(inv), rng.randint(0, 2)))]
                d = {"amount": str(rng.randint(1, 3000)), "payment_date": "1405/07/08", "bank_account": rng.choice(["", str(rng.choice(accounts).pk)])}
                if chosen:
                    d["invoices"] = chosen
                r = h.c.post(f"/receivables/{c.pk}/record-payment/", d)
            else:
                s = rng.choice(suppliers)
                inv = list(PurchaseInvoice.objects.filter(supplier=s, status="confirmed"))
                chosen = [str(i.pk) for i in rng.sample(inv, min(len(inv), rng.randint(0, 2)))]
                d = {"amount": str(rng.randint(1, 3000)), "payment_date": "1405/07/08", "bank_account": rng.choice(["", str(rng.choice(accounts).pk)])}
                if chosen:
                    d["invoices"] = chosen
                r = h.c.post(f"/payables/{s.pk}/record-payment/", d)
            track(r, op)
        elif op == "cheque":
            chs = list(Cheque.objects.all())
            if chs:
                ch = rng.choice(chs)
                r = h.c.post(f"/cheques/{ch.pk}/{rng.choice(['clear', 'clear', 'bounce', 'cancel'])}/"); track(r, op)
        elif op == "expense":
            r = h.c.post("/expenses/new/", {"expense_date": "1405/07/08", "reason": "QA-fz", "amount": str(rng.randint(1, 900)), "bank_account": rng.choice(["cash", str(rng.choice(accounts).pk)])})
            track(r, op)
        elif op == "cancel_expense":
            es = list(Expense.objects.all())
            if es:
                r = h.c.post(f"/expenses/{rng.choice(es).pk}/cancel/"); track(r, op)
        elif op == "price":
            r = h.c.post(f"/inventory/{rng.choice(products).pk}/selling-price/", {"default_selling_price": str(rng.randint(0, 3000))}); track(r, op)

    check(f"Z00 {statuses['ops']} random operations ran with ZERO server errors (seed {SEED})", statuses["500"] == 0, log[:5])
    counts = dict(sales=SalesInvoice.objects.count(), purchases=PurchaseInvoice.objects.count(), cheques=Cheque.objects.count(), expenses=Expense.objects.count(), payments=Payment.objects.count())
    print("   dataset:", counts)
    check("Z00b the run produced a meaningful dataset", counts["sales"] > 15 and counts["purchases"] > 8, counts)

    # ---------------- invariants (over the products/parties of THIS run)
    pids = [p.pk for p in products]
    stock = __import__('collections').defaultdict(int, get_stock_map(pids))
    IN = {"opening", "purchase", "adjustment_in"}
    for p in products:
        ms = InventoryMovement.objects.filter(product=p)
        net = sum(m.quantity if m.movement_type in IN else -m.quantity for m in ms)
        check(f"Z01 stock = movement ledger for {p.name[-4:]}", stock[p.pk] == net, (stock[p.pk], net))
        check(f"Z01b stock never negative for {p.name[-4:]}", stock[p.pk] >= 0)
    layers = InventoryLayer.objects.filter(product__in=products)
    bad = []
    for l in layers:
        used = l.consumptions.aggregate(t=Sum("quantity"))["t"] or 0
        if l.quantity - used != l.quantity_remaining or not 0 <= l.quantity_remaining <= l.quantity:
            bad.append((l.pk, l.quantity, used, l.quantity_remaining))
    check("Z02 every layer: remaining = quantity − Σ consumption, within 0..quantity", not bad, bad[:3])
    active_rem = {p.pk: sum(l.quantity_remaining for l in layers if l.product_id == p.pk and l.cancelled_at is None) for p in products}
    check("Z03 Σ active layer remaining = stock (per product)", all(active_rem[p.pk] == stock[p.pk] for p in products), [(p.name[-4:], active_rem[p.pk], stock[p.pk]) for p in products if active_rem[p.pk] != stock[p.pk]])
    vmap = __import__('collections').defaultdict(int, get_inventory_value_map(pids))
    check("Z04 inventory value = Σ remaining × cost", all(vmap[p.pk] == sum(l.quantity_remaining * l.unit_cost for l in layers if l.product_id == p.pk and l.cancelled_at is None) for p in products))
    # sales
    sales = SalesInvoice.objects.filter(customer__in=customers)
    bad = []
    for inv in sales:
        for it in inv.items.all():
            used = it.consumptions.aggregate(t=Sum("quantity"))["t"] or 0
            expect = it.quantity if inv.status == "confirmed" else 0
            if used != expect:
                bad.append((inv.invoice_number, inv.status, it.quantity, used))
    check("Z05 every sale line consumed exactly its quantity (0 when cancelled)", not bad, bad[:3])
    check("Z06 invoice profit = Σ line profits; cancelled profit 0", all(inv.profit == sum(i.profit for i in inv.items.all()) and (inv.status == "confirmed" or inv.profit == 0) for inv in sales))
    check("Z07 discount never exceeds subtotal", all(inv.discount_amount <= inv.subtotal for inv in sales))
    # allocations
    over = []
    for pay in Payment.objects.filter(created_by=h.su):
        tot = pay.allocations.aggregate(t=Sum("amount"))["t"] or 0
        if tot > pay.amount:
            over.append((pay.pk, tot, pay.amount))
    check("Z08 no payment is allocated for more than its amount", not over, over[:3])
    over = []
    for inv in list(sales) + list(PurchaseInvoice.objects.filter(supplier__in=suppliers)):
        paid = inv.payment_allocations.aggregate(t=Sum("amount"))["t"] or 0
        total = inv.total if hasattr(inv, "total") and not isinstance(inv, PurchaseInvoice) else inv.total_amount
        if paid > total:
            over.append((inv.invoice_number, paid, total))
    check("Z09 no invoice is paid for more than its total", not over, over[:3])
    check("Z10 payment_status agrees with allocations", all(
        (i.payment_status == "paid") == (i.paid_amount >= (i.total if not isinstance(i, PurchaseInvoice) else i.total_amount) and (i.total if not isinstance(i, PurchaseInvoice) else i.total_amount) > 0)
        or (i.total if not isinstance(i, PurchaseInvoice) else i.total_amount) == 0
        for i in list(sales.filter(status="confirmed")) + list(PurchaseInvoice.objects.filter(supplier__in=suppliers, status="confirmed"))))
    # cheques
    bad = []
    for ch in Cheque.objects.filter(created_by=None) if False else Cheque.objects.all():
        if not (ch.customer_id in [c.pk for c in customers] or ch.supplier_id in [s.pk for s in suppliers]):
            continue
        if ch.status == "cleared":
            if ch.payment is None or ch.payment.amount != ch.amount or ch.payment.direction != ch.direction:
                bad.append(("cleared-mismatch", ch.pk))
        elif ch.payment is not None:
            bad.append(("payment-on-non-cleared", ch.pk, ch.status))
    check("Z11 cheques: cleared ⇒ matching payment; any other status ⇒ no payment", not bad, bad[:3])
    # expenses
    bad = []
    for e in Expense.objects.filter(created_by=h.su):
        if e.payment.direction != "out" or e.payment.amount != e.amount:
            bad.append(("payment", e.pk))
        if e.cancelled_at:
            if e.reversal_payment is None or e.reversal_payment.direction != "in" or e.reversal_payment.amount != e.amount or e.reversal_payment.bank_account_id != e.payment.bank_account_id:
                bad.append(("reversal", e.pk))
        elif e.reversal_payment is not None:
            bad.append(("reversal-on-live", e.pk))
    check("Z12 expenses: payment OUT for the amount; cancelled ⇒ exact opposite payment", not bad, bad[:3])
    # bank
    for a in accounts:
        pin = Payment.objects.filter(bank_account=a, direction="in").aggregate(t=Sum("amount"))["t"] or 0
        pout = Payment.objects.filter(bank_account=a, direction="out").aggregate(t=Sum("amount"))["t"] or 0
        check(f"Z13 bank balance = in − out ({a.name[-4:]})", get_bank_account_balance(a) == pin - pout)
    # party balances
    for c in customers:
        conf = SalesInvoice.objects.filter(customer=c, status="confirmed")
        exp = sum(i.total for i in conf) - sum((i.payment_allocations.aggregate(t=Sum("amount"))["t"] or 0) for i in conf)
        check(f"Z14 customer outstanding = Σ(total − paid) ({c.name[-4:]})", get_customer_outstanding(c) == exp, (get_customer_outstanding(c), exp))
    for s in suppliers:
        conf = PurchaseInvoice.objects.filter(supplier=s, status="confirmed")
        exp = sum(i.total_amount for i in conf) - sum((i.payment_allocations.aggregate(t=Sum("amount"))["t"] or 0) for i in conf)
        check(f"Z14 supplier outstanding = Σ(total − paid) ({s.name[-4:]})", get_supplier_outstanding(s) == exp, (get_supplier_outstanding(s), exp))
    # numbering
    nums = list(SalesInvoice.objects.exclude(invoice_number="").values_list("invoice_number", flat=True))
    check("Z15 sale invoice numbers unique", len(nums) == len(set(nums)))
    pn = list(PurchaseInvoice.objects.exclude(invoice_number="").values_list("invoice_number", flat=True))
    check("Z15 purchase invoice numbers unique", len(pn) == len(set(pn)))
    check("Z16 no draft invoices left behind by any rejected submission", not SalesInvoice.objects.filter(status="draft").exists() and not PurchaseInvoice.objects.filter(status="draft").exists())
    check("Z17 no orphan payment entries (rows of non-confirmed invoices)", not SalesInvoice.objects.filter(status="draft", payment_entries__isnull=False).exists())
    # reports agree with the ledger over the whole run
    from apps.shared import reports
    s0, s1 = datetime.date.today() - datetime.timedelta(days=400), datetime.date.today() + datetime.timedelta(days=400)
    cards = reports.summary_cards(s0, s1)
    check("Z18 report: net = gross − expenses", cards["net_profit"]["value"] == cards["gross_profit"]["value"] - cards["expenses"]["value"])
    check("Z18 report: product rows add up to the cards", sum(r["amount"] for r in reports.sales_by_product(s0, s1)) == cards["sales"]["value"])
    check("Z19 receivables total = Σ customers' outstanding (all customers)", get_total_receivables_as_of(datetime.date.today()) == sum(get_customer_outstanding(c) for c in Customer.objects.all()))
    for url in ("/", "/reports/", "/receivables/", "/payables/", "/cheques/", "/bank-accounts/", "/inventory/", "/sales/", "/purchasing/", "/expenses/", "/user-activity/"):
        check(f"Z20 {url} still renders after the run", h.c.get(url).status_code == 200)


run("fuzz+invariants", scenarios)

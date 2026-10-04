"""D-078: card reader / bank transfer are ticked on the full-settlement panel, and a single card
reader is the default account."""
from tools.qa.qa_lib import *
from apps.payments.forms import InvoicePaymentFields
from apps.payments.models import BankAccount, Payment
from apps.sales.models import SalesInvoice


def last_sale(c):
    return SalesInvoice.objects.filter(customer=c).latest("created_at")


def scenarios(h):
    # The dev DB may hold real accounts: park every other card reader inside this rolled-back transaction.
    BankAccount.objects.filter(account_type="pos").update(is_active=False)
    pos = h.account(kind="pos")
    cur = h.account()
    p = h.product(stock=500, cost=100, price=1000)
    cust = h.customer()

    # ---- single card reader is the default
    check("PT01 exactly one active card reader is found", InvoicePaymentFields.single_pos_account() == pos)
    form = InvoicePaymentFields()
    check("PT02 the form preselects it", form.pos_default == pos and form.fields["pos_account"].initial == pos.pk)
    r = h.c.get("/sales/new/")
    check("PT03 the page shows its name and a hidden value, not a list",
          has(r, pos.name) and f'type="hidden" name="pos_account" id="id_pos_account" value="{pos.pk}"' in text(r))

    # ---- ticks
    n = SalesInvoice.objects.filter(customer=cust).count()
    r = h.post_sale(cust, [(p, 2, 1000)], extra={"use_pos": "on", "pos_amount": "2000"})
    check("PT04 card ticked, account left out: the single reader is used",
          r.status_code == 302 and Payment.objects.filter(customer=cust, bank_account=pos, amount=2000).exists(), r.status_code)
    r = h.post_sale(cust, [(p, 1, 1000)], extra={"pos_account": str(pos.pk), "pos_amount": "1000", "use_pos": ""})
    check("PT05 nothing ticked is refused even if an account and amount were sent",
          r.status_code == 200 and SalesInvoice.objects.filter(customer=cust).count() == n + 1)
    r = h.post_sale(cust, [(p, 1, 1000)], extra={"use_transfer": "on", "transfer_account": str(cur.pk),
                                                 "pos_account": str(pos.pk), "pos_amount": "400", "use_pos": ""})
    check("PT06 unticked card is ignored: transfer takes the whole total",
          r.status_code == 302 and Payment.objects.filter(customer=cust, bank_account=cur, amount=1000).exists()
          and not Payment.objects.filter(customer=cust, bank_account=pos, amount=400).exists())
    r = h.post_sale(cust, [(p, 1, 1000)], extra={"use_transfer": "on", "transfer_account": ""})
    check("PT07 transfer ticked without an account is refused", r.status_code == 200)
    r = h.post_sale(cust, [(p, 10, 1000)], extra={"use_pos": "on", "use_transfer": "on", "transfer_account": str(cur.pk), "pos_amount": "3000"})
    check("PT08 both ticked: card 3000 + transfer takes the rest",
          r.status_code == 302 and Payment.objects.filter(customer=cust, bank_account=pos, amount=3000).exists()
          and Payment.objects.filter(customer=cust, bank_account=cur, amount=7000).exists())

    # ---- several card readers: the choice comes back
    pos2 = h.account(kind="pos")
    check("PT09 two card readers: no default", InvoicePaymentFields.single_pos_account() is None)
    r = h.c.get("/sales/new/")
    check("PT10 the page offers a list again", 'name="pos_account"' in text(r) and "<select" in text(r) and f'value="{pos2.pk}"' in text(r))
    r = h.post_sale(cust, [(p, 1, 1000)], extra={"use_pos": "on", "pos_amount": "1000"})
    check("PT11 card ticked with no account and two readers is refused", r.status_code == 200)

    # ---- purchases keep transfer only
    r = h.c.get("/purchasing/new/")
    check("PT12 purchase page has no card tick", 'name="use_pos"' not in text(r) and 'name="use_transfer"' in text(r))


run("payment_ticks", scenarios)

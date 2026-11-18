from uuid import uuid4

from django.test import TestCase

from apps.payments.models import Expense, Payment
from apps.purchasing.models import PurchaseInvoice
from apps.sales.models import SalesInvoice
from tools.qa.qa_lib import Harness, TODAY_J


class FinancialSubmissionTests(TestCase):
    def setUp(self):
        self.h = Harness()
        self.account = self.h.account()
        self.product = self.h.product(stock=10)

    def test_purchase_form_replays_the_same_purchase(self):
        self.assertContains(self.h.c.get("/purchasing/new/"), 'name="submission_id"')
        supplier = self.h.supplier()
        key = {"submission_id": str(uuid4())}
        responses = [self.h.post_purchase(supplier, [(self.product, 2, 500)], account=self.account, extra=key)
                     for _ in range(2)]
        self.assertEqual([r.status_code for r in responses], [302, 302])
        self.assertEqual(responses[0]["Location"], responses[1]["Location"])
        self.assertEqual(PurchaseInvoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.h.stock(self.product), 12)

    def test_return_replays_the_same_document(self):
        self.h.post_sale(self.h.customer(), [(self.product, 4, 1000)], mode="split")
        invoice = SalesInvoice.objects.get()
        item = invoice.items.get()
        url = f"/returns/sales/new/{invoice.pk}/"
        self.assertContains(self.h.c.get(url), 'name="submission_id"')
        data = {"submission_id": str(uuid4()), "return_date": TODAY_J, "settle_mode": "credit",
                f"packs_{item.pk}": "1"}
        first = self.h.c.post(url, data)
        second = self.h.c.post(url, data)
        self.assertEqual((first.status_code, second.status_code), (302, 302))
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(invoice.returns.count(), 1)
        self.assertEqual(self.h.stock(self.product), 7)

    def test_expense_validation_releases_the_operation_key(self):
        url = "/expenses/new/"
        self.assertContains(self.h.c.get(url), 'name="submission_id"')
        data = {"submission_id": str(uuid4()), "expense_date": TODAY_J, "reason": "Test expense",
                "amount": "0", "bank_account": str(self.account.pk)}
        invalid = self.h.c.post(url, data)
        self.assertContains(invalid, data["submission_id"])
        self.assertFalse(Expense.objects.exists())
        data["amount"] = "500"
        first = self.h.c.post(url, data)
        second = self.h.c.post(url, data)
        self.assertEqual((first.status_code, second.status_code), (302, 302))
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(Expense.objects.count(), 1)

    def test_party_payment_replay_has_one_payment(self):
        customer = self.h.customer()
        self.h.post_sale(customer, [(self.product, 4, 1000)], mode="split")
        url = f"/receivables/{customer.pk}/record-payment/"
        data = {"submission_id": str(uuid4()), "payment_date": TODAY_J, "amount": "500",
                "bank_account": str(self.account.pk)}
        first = self.h.c.post(url, data)
        second = self.h.c.post(url, data)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(Payment.objects.filter(customer=customer, amount=500).count(), 1)

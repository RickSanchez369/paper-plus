from django.test import TestCase
from django.urls import reverse

from apps.payments.models import Payment
from apps.sales.models import SalesInvoice
from tools.qa.qa_lib import Harness


class SalesSubmissionTests(TestCase):
    def setUp(self):
        self.h = Harness()
        self.customer = self.h.customer()
        self.product = self.h.product(stock=10, cost=500)
        self.account = self.h.account(kind="pos")
        self.url = reverse("sales:new")

    def new_submission(self):
        return str(self.h.c.get(self.url).context["submission_id"])

    def submit(self, submission_id, quantity=2):
        return self.h.post_sale(
            self.customer,
            [(self.product, quantity, 1000)],
            account=self.account,
            extra={"submission_id": submission_id},
        )

    def test_replaying_sale_has_one_financial_and_stock_effect(self):
        submission_id = self.new_submission()
        first = self.submit(submission_id)
        second = self.submit(submission_id)
        invoice = SalesInvoice.objects.get()

        expected = reverse("sales:detail", kwargs={"pk": invoice.pk})
        self.assertRedirects(first, expected, fetch_redirect_response=False)
        self.assertRedirects(second, expected, fetch_redirect_response=False)
        self.assertEqual(self.h.stock(self.product), 8)
        self.assertEqual(list(Payment.objects.values_list("amount", flat=True)), [2000])

    def test_independent_identical_sales_have_different_invoices(self):
        first = self.submit(self.new_submission())
        second = self.submit(self.new_submission())

        self.assertEqual((first.status_code, second.status_code), (302, 302))
        self.assertNotEqual(first["Location"], second["Location"])
        self.assertEqual(SalesInvoice.objects.count(), 2)
        self.assertEqual(self.h.stock(self.product), 6)

    def test_failed_submission_can_be_corrected_with_the_same_id(self):
        submission_id = self.new_submission()
        bad = self.submit(submission_id, quantity=11)

        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, f'value="{submission_id}"')
        self.assertFalse(SalesInvoice.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.h.stock(self.product), 10)
        self.assertEqual(self.submit(submission_id).status_code, 302)

    def test_invalid_submission_id_is_rejected(self):
        self.assertEqual(self.submit("invalid").status_code, 400)
        self.assertFalse(SalesInvoice.objects.exists())

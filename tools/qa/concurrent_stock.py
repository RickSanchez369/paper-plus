"""Concurrency checks for a disposable, file-backed SQLite database."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from django.db import connections
from django.test import Client

from apps.payments.models import Payment
from apps.sales.models import SalesInvoice
from tools.qa.qa_lib import Harness, check


def check_concurrent_stock():
    h = Harness()
    account = h.account(kind="pos")
    customer = h.customer()
    product = h.product(stock=1)
    clients = [Client(HTTP_HOST="localhost") for _ in range(2)]
    for client in clients:
        client.force_login(h.su)
    start = Barrier(2, timeout=10)

    def submit(client):
        try:
            start.wait()
            response = h.post_sale(
                customer, [(product, 1, 1000)], account=account, client=client,
                extra={"submission_id": str(uuid4())},
            )
            return response.status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(submit, clients))
    check("Concurrent independent sales reject one attempt at the last pack", statuses == [200, 302], statuses)
    check("Concurrent sales create exactly one invoice and one payment",
          SalesInvoice.objects.filter(customer=customer).count() == 1
          and Payment.objects.filter(customer=customer).count() == 1)
    check("Concurrent sales do not oversell stock", h.stock(product) == 0)

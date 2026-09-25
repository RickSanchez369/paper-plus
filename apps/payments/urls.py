# path: apps/payments/urls.py

"""
Routes for the five modules whose models live in this app.

Receivables, Payables and Cheques are one conceptual module with three
views (REDESIGN_VISION 4.4) and share a sidebar group, but each still gets
its own namespace so a page can link straight to the view it means.
Each pattern list is exported separately and mounted from core/urls.py,
rather than declaring a single `app_name` here, because one app owning
several top-level modules is exactly the case `include((patterns, ns))`
exists for.
"""

from django.urls import path

from .views import (
    BankAccountDetailView,
    BankAccountListView,
    ChequeActionView,
    ChequeCompleteView,
    ChequeDetailView,
    ChequesListView,
    ExpenseCancelView,
    ExpenseCreateView,
    ExpensesListView,
    PayablesListView,
    ReceivablesListView,
    RecordCustomerPaymentView,
    RecordSupplierPaymentView,
)

receivables_patterns = ([
    path("", ReceivablesListView.as_view(), name="list"),
    path("<uuid:pk>/record-payment/", RecordCustomerPaymentView.as_view(), name="record_payment"),
], "receivables")

payables_patterns = ([
    path("", PayablesListView.as_view(), name="list"),
    path("<uuid:pk>/record-payment/", RecordSupplierPaymentView.as_view(), name="record_payment"),
], "payables")

cheques_patterns = ([
    path("", ChequesListView.as_view(), name="list"),
    path("<uuid:pk>/", ChequeDetailView.as_view(), name="detail"),
    path("<uuid:pk>/complete/", ChequeCompleteView.as_view(), name="complete"),
    path("<uuid:pk>/clear/", ChequeActionView.as_view(action="clear"), name="clear"),
    path("<uuid:pk>/bounce/", ChequeActionView.as_view(action="bounce"), name="bounce"),
    path("<uuid:pk>/cancel/", ChequeActionView.as_view(action="cancel"), name="cancel"),
], "cheques")

bank_accounts_patterns = ([
    path("", BankAccountListView.as_view(), name="list"),
    path("<uuid:pk>/", BankAccountDetailView.as_view(), name="detail"),
], "bank_accounts")

expenses_patterns = ([
    path("", ExpensesListView.as_view(), name="list"),
    path("new/", ExpenseCreateView.as_view(), name="new"),
    path("<uuid:pk>/cancel/", ExpenseCancelView.as_view(), name="cancel"),
], "expenses")

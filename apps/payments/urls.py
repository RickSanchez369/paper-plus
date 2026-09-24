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

from apps.shared.views import ModulePlaceholderView

receivables_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="مطالبات",
            description="مشتریانی که حساب باز دارند، با امکان ثبت پرداخت روی چند فاکتور.",
        ),
        name="list",
    ),
], "receivables")

payables_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="بدهی‌ها",
            description="تأمین‌کنندگانی که به آن‌ها بدهکاریم — قرینهٔ مطالبات.",
        ),
        name="list",
    ),
], "payables")

cheques_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="چک‌ها",
            description="چک‌های دریافتی و پرداختی، وضعیت و سررسیدشان.",
        ),
        name="list",
    ),
], "cheques")

bank_accounts_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="حساب‌های بانکی",
            description="حساب‌ها با صاحب حساب و موجودی زنده، و دفتر هر حساب.",
        ),
        name="list",
    ),
], "bank_accounts")

expenses_patterns = ([
    path(
        "",
        ModulePlaceholderView.as_view(
            title="هزینه‌ها",
            description="هزینه‌های ثبت‌شده با طرف حساب، بابت و سند پیوست.",
        ),
        name="list",
    ),
], "expenses")

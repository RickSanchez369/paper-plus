# path: apps/payments/selectors.py

"""Read-only queries over payments (ROADMAP 4.3). Selectors never write."""

from django.db.models import BigIntegerField, Case, F, Sum, When

from .models import Payment


def get_bank_account_balance(bank_account):
    """Net money moved through this account: IN payments minus OUT payments."""
    result = Payment.objects.filter(bank_account=bank_account).aggregate(
        balance=Sum(
            Case(
                When(direction=Payment.Direction.IN, then=F("amount")),
                default=-F("amount"),
                output_field=BigIntegerField(),
            )
        )
    )
    return result["balance"] or 0

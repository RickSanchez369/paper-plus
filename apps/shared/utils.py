# path: apps/shared/utils.py

"""Presentation helpers. These never change how values are stored."""


def format_number(value):
    """Group digits in threes: 1234567 -> '1,234,567'."""
    if value is None:
        return ""
    return f"{int(value):,}"


def format_toman(value):
    """'250,000 تومان' -- every stored amount is already whole Toman (D-043)."""
    if value is None:
        return ""
    return f"{format_number(value)} تومان"

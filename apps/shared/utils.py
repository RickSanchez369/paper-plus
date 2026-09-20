# path: apps/shared/utils.py

"""Presentation helpers. These never change how values are stored."""

RIAL_PER_TOMAN = 10


def format_number(value):
    """Group digits in threes: 1234567 -> '1,234,567'."""
    if value is None:
        return ""
    return f"{int(value):,}"


def rial_to_toman(rial):
    """Convert stored Rial to Toman for display only."""
    if rial is None:
        return None
    return rial / RIAL_PER_TOMAN


def format_rial(rial):
    """'2,500,000 ریال (250,000 تومان)'"""
    if rial is None:
        return ""
    toman = int(rial) // RIAL_PER_TOMAN
    remainder = int(rial) % RIAL_PER_TOMAN
    toman_text = format_number(toman) if remainder == 0 else f"{toman + remainder / RIAL_PER_TOMAN:,.1f}"
    return f"{format_number(rial)} ریال ({toman_text} تومان)"
"""Shared form widgets."""
from django import forms


class NumericInput(forms.TextInput):
    """A numeric box that accepts Persian digits.

    `<input type=number>` silently drops «۱۲» typed on a Persian keyboard, so a
    clerk sees a dead field. A text box with `inputmode=numeric` opens the numeric
    keypad all the same, and `ui.js` turns Persian digits into Latin ones as they
    are typed; the server-side IntegerField/DecimalField validation is unchanged.
    """

    def __init__(self, attrs=None):
        merged = {"inputmode": "numeric", "autocomplete": "off"}
        merged.update(attrs or {})
        super().__init__(merged)

"""Small text helpers shared by search boxes."""
import re

# Persian (U+06F0..) and Arabic-Indic (U+0660..) digits, Arabic letters typed on Arabic keyboards, and the
# invisible joiners that Persian text carries (ZWNJ / ZWJ / RLM / LRM / tatweel).
_DIGITS = {ord(d): str(i) for i, d in enumerate("۰۱۲۳۴۵۶۷۸۹")}
_DIGITS.update({ord(d): str(i) for i, d in enumerate("٠١٢٣٤٥٦٧٨٩")})
_LETTERS = {ord("ك"): "ک", ord("ي"): "ی", ord("ى"): "ی", ord("ة"): "ه"}
_INVISIBLE = re.compile("[‌‍‎‏ـ]")


def search_key(text):
    """Fold a name, code or query to one comparable form: ASCII digits, Persian letters, no joiners, lower case.

    A shop owner types «دفتر ۱۰۰» or «دفتر 100» or «كاغذ» on whatever keyboard is at hand while a customer waits;
    all of them must find the same product. Compare words with ``all(term in search_key(name) for term in
    search_key(query).split())`` so word order does not matter either.
    """
    folded = str(text or "").translate(_DIGITS).translate(_LETTERS)
    return " ".join(_INVISIBLE.sub("", folded).lower().split())

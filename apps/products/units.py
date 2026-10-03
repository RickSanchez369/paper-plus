# path: apps/products/units.py

"""
Carton + pack arithmetic and wording (D-081).

Stock, layers and FIFO are all counted in packs (the base unit). A carton is
`pack_per_carton` packs. These helpers only convert between the one stored
number and the carton + pack way people type and read it; they never touch
the database.
"""


def split_units(quantity, pack_per_carton):
    """``(cartons, packs)`` for a quantity in packs, e.g. 34 with 5 -> (6, 4)."""
    ratio = max(int(pack_per_carton or 1), 1)
    quantity = int(quantity or 0)
    if quantity < 0:
        cartons, packs = divmod(-quantity, ratio)
        return -cartons, -packs
    return divmod(quantity, ratio)


def to_packs(cartons, packs, pack_per_carton):
    """The base quantity of a line typed as cartons + loose packs: 6, 4, 5 -> 34."""
    return int(cartons or 0) * max(int(pack_per_carton or 1), 1) + int(packs or 0)


def units_phrase(cartons, packs, pack_word="بسته", carton_word="کارتن"):
    """
    "۶ کارتن + ۴ بسته" with the parts that are zero left out ("۶ کارتن",
    "۴ بسته"); a line with neither reads "۰ بسته". Digits stay ASCII here;
    the template filters turn them into Persian digits.
    """
    parts = []
    if cartons:
        parts.append(f"{cartons} {carton_word}")
    if packs or not cartons:
        parts.append(f"{packs} {pack_word}")
    return " + ".join(parts)

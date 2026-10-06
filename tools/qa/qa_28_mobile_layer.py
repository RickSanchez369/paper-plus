"""Phone layer pieces that live on the server side (D-095): search folding, dashboard stock alert, dues card hooks.

The CSS itself is measured in a real browser by tools/qa/mobile_audit.py; this checks what a script can: the shell links the
phone stylesheets, the totals row carries the card hook, the inventory search folds digits/letters/word order, and the
dashboard shows (and links) a stock-out.
"""
from apps.shared.text import search_key
from tools.qa.qa_lib import *


def scenarios(h):
    # ---------------------------------------------------------------- search folding
    check("ML01 Persian digits fold to ASCII", search_key("دفتر ۱۰۰ برگ") == search_key("دفتر 100 برگ"))
    check("ML02 Arabic ك/ي fold to Persian ک/ی", search_key("كاغذ يك") == search_key("کاغذ یک"))
    check("ML03 ZWNJ and tatweel vanish, case folds", search_key("A4‌ Paper") == "a4 paper" and search_key("کـاغذ") == "کاغذ")
    check("ML04 empty input is empty", search_key(None) == "" and search_key("  ") == "")

    p = h.product(name="دفتر ۱۰۰ برگ", sku="QAML100", stock=50, cost=500)
    q = h.product(name="کاغذ A4 مرغوب", sku="QAML-A4", stock=0)
    for query, expect, label in (
        ("دفتر 100", p, "ASCII digits find a name stored with Persian digits"),
        ("دفتر۱۰۰", None, "no space is a different word (still no false hit)"),
        ("100 دفتر", p, "word order does not matter"),
        ("كاغذ", q, "Arabic kaf finds a Persian-kaf name"),
        ("qaml-a4", q, "SKU matches case-insensitively"),
        ("A4 کاغذ", q, "digits/letters in any order"),
    ):
        r = h.c.get("/inventory/", {"q": query})
        found = has(r, p.name), has(r, q.name)
        if expect is p:
            ok = found == (True, False)
        elif expect is q:
            ok = found == (False, True)
        else:
            ok = found == (False, False)
        check(f"ML05 inventory search «{query}»: {label}", ok, found)

    # ---------------------------------------------------------------- dashboard stock alert
    r = h.c.get("/")
    check("ML06 a stock-out shows the amber alert strip linking to the filtered list",
          r.status_code == 200 and "alert-strip--stock" in text(r) and "/inventory/?stock=out" in text(r))
    h.product(name="QA-ML-IN", stock=5, cost=100)
    r2 = h.c.get("/inventory/", {"stock": "out"})
    check("ML07 the linked list shows the out-of-stock product", has(r2, q.name))

    # ---------------------------------------------------------------- shell + dues hooks
    body = text(h.c.get("/"))
    for css in ("mobile_tables.css", "mobile_forms.css", "mobile_shell.css", "mobile_pages.css"):
        check(f"ML08 the shell links {css}", css in body)
    check("ML09 the shell loads mobile.js", "shared/js/mobile.js" in body)
    check("ML10 the dues totals row carries data-card-skip so card mode can switch on", "data-card-skip" in body or "dues-total" not in body,
          "dues rows absent in this DB" if "dues-total" not in body else "")
    check("ML11 the dashboard month tiles open THIS month's report", "preset=prev_month" not in body and "preset=month" in body)

    # ---------------------------------------------------------------- installable on a phone
    check("ML14 the shell links a manifest, an apple-touch-icon and no service worker",
          'rel="manifest"' in body and 'rel="apple-touch-icon"' in body and "serviceWorker" not in body)
    check("ML15 the dashboard hero offers the one-tap «ثبت دریافت»", "/receivables/" in body and "ثبت دریافت از مشتری" in body)

    # ---------------------------------------------------------------- confirm buttons advertise the chord
    check("ML12 the sale confirm button names Ctrl+Enter", "Control+Enter" in text(h.c.get("/sales/new/")))
    check("ML13 the purchase confirm button names Ctrl+Enter", "Control+Enter" in text(h.c.get("/purchasing/new/")))


run("mobile_layer", scenarios)

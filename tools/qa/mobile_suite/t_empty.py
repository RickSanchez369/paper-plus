"""A brand-new install: only a user exists (no accounts, products, parties, invoices). Every page must load clean on every phone
viewport and every list must say what to do instead of drawing an empty frame."""
from tools.qa.mobile_suite import t_pages
from tools.qa.mobile_suite.lib import Watched, run_module

LISTS = ["/sales/", "/purchasing/", "/inventory/", "/returns/", "/receivables/", "/payables/", "/cheques/", "/bank-accounts/", "/expenses/",
         "/expenses/recurring/", "/customers/", "/purchasing/suppliers/", "/user-activity/"]


def body(a, rec, b):
    t_pages.body(a, rec, b)
    if a.i:
        return
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    for path in LISTS:
        w.goto(path)
        txt = w.page.evaluate("document.querySelector('main').innerText")
        has_rows = w.page.locator("table.data-table tbody tr").count()
        rec.check("empty-state", f"{path}: no rows and a sentence about it ({has_rows} rows)", has_rows == 0 and len(txt.strip()) > 20, txt[:80])
        rec.check("empty-state", f"{path}: no empty table frame is drawn", w.page.locator("table.data-table").count() == 0 or has_rows == 0)
    for path in ("/sales/new/", "/purchasing/new/", "/expenses/new/"):
        w.goto(path)
        rec.check("empty-state", f"{path}: the form opens on an empty install", w.page.locator("main form").count() >= 1)
    ctx.close()


if __name__ == "__main__":
    run_module("empty", body)

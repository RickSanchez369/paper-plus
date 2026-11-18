# QA scenario suite

Run `python tools/qa/backend_acceptance.py --all` for all numbered scenarios and
the concurrent-stock check. It migrates and seeds a temporary SQLite database,
isolates uploaded files, and exits nonzero if any check fails. Omit `--all` for
the smaller backend release suite.

End-to-end checks that drive the real URLs (Django test client) inside ONE
transaction that is rolled back, on fixtures each script builds for itself, so
real data is never touched. Run from the repo root, venv active:

```powershell
$env:PYTHONIOENCODING="utf-8"
python manage.py shell -c "exec(open('tools/qa/qa_02_purchase.py', encoding='utf-8').read())"
```

| Script | Covers |
|---|---|
| qa_02_purchase / qa_03_sales | every way to fill, break and cancel an invoice |
| qa_04_inventory | products, opening stock, selling price, detail pages |
| qa_05_parties | customers and suppliers: filters, edit, deactivate |
| qa_06_payments | record payment, cheques, bank accounts, expenses |
| qa_07_dashboard_reports_auth | login/CSRF/admin gating, dashboard, reports, activity |
| qa_08_crawler | follows every link from the dashboard, audits each page |
| qa_09_fuzz_invariants | random operations, then the accounting invariants (`QA_SEED`, `QA_OPS`) |
| qa_10_admin | /admin/ smoke test |
| qa_11_report_numbers | reports recomputed independently from the ledgers |
| (qa_06 also runs the receipt-upload rules; qa_07 also runs the login throttle) | |
| qa_12_cancel_refunds | cancelling an invoice refunds its payments and cheques (D-055) |
| qa_13_backup | backup page access rules and zip contents (D-060) |
| qa_15_numbering | invoice numbers year/running, per type, yearly reset (D-064) |
| qa_16_payment_rework | account types, issuer, percent discount, card/transfer settlement, credit due dates, Receivables/Payables split, cheque/credit expenses, fixed costs, dashboard reminders (D-067..D-074) |
| qa_17_pricing_units | pack and carton prices, blank prices filled from the product, report by sale type (D-075, D-081) |
| qa_18_payment_ticks | tick boxes for card/transfer, single card reader default (D-078) |
| qa_19_dashboard_dues | the single dues card, 10-day window, cheque/credit split (D-079) |
| qa_20_usd_rate | rate parsing, history, failures store no number, per-invoice snapshot, refresh button (D-080) |
| qa_21_units | carton + pack lines, stock in packs, average price apart from FIFO, printing (D-081) |
| qa_22_freight | freight in the total owed, split by packs, landed cost per pack/carton, cancel (D-082) |
| qa_24_ui_audit | numeric widgets, status tones, percent/units wording, error pages, filter/range plumbing, `?customer=` prefill, sidebar state (D-084) |
| qa_14_invoice_print | printed invoice: words, company header, stamp boxes, watermark (D-061) |

`OK`/`FAIL` per check and `n/N passed` at the end. JavaScript behaviour
(item rows, payment rows, date picker, htmx forms) cannot be seen from here:
that part is checked in the browser pane.

## Looking at the UI

`.\tools\qa\preview.ps1` (Windows, repo root) builds a throwaway SQLite database with demo data (`seed_qa_db.py` +
`seed_demo_data.py`: paid, part-paid and overdue sales, a cancelled invoice, a purchase with freight, cheques, expenses)
and serves it on http://localhost:8001. It never touches PostgreSQL or `.env`. On SQLite run the scripts above with
`DEBUG=True` (otherwise `ALLOWED_HOSTS` is empty and the test client gets 400).

## Mobile layer (D-095)
- `qa_31_filters_gzip`: amount filters take Persian digits, pages are gzipped, invoice number in a no-split span (D-098).
- `qa_30_zero_price_far_date`: price 0 and dates over 30 days ahead refused, purchase cancel dialog (D-097).
- `qa_27_tier_prices`: two prices by unit (carton = wholesale, pack = retail), the sale type is only a label, no customer type (D-100).
- `qa_32_returns_v2`: damaged goods and deduction, cancelling a return (stock, credit note, refund), freight loss, pending-cheque warning, return date limit (D-101).
- `python tools/qa/run_script.py qa_30_zero_price_far_date.py` runs a script on a throwaway SQLite copy of the suite's demo DB; plain `manage.py shell` would use the `.env` database.
- `qa_29_input_bounds`: huge fixed-cost periods and opening stock are refused, never a 500 (D-096).
- `qa_28_mobile_layer`: search folding (digits, ك/ي, word order), dashboard stock alert, phone stylesheets linked, dues card hook.
- `python tools/qa/mobile_env.py NAME PORT` builds a throwaway demo DB under `tools/qa/.mobile/` and serves it (several can run at once).
- `python tools/qa/mobile_audit.py --base http://localhost:PORT --login tools/qa/.mobile/NAME.sqlite3.login.txt --label X` is the phone
  scorecard (needs `pip install playwright` and Chrome; a dev tool, not in requirements.txt). Baseline and results: `docs/UI_EVOLUTION_LOG.md`.

## Mobile test suite (`tools/qa/mobile_suite/`)
A Playwright suite that drives the real pages on phone emulation (touch, 8 viewports from 320x568 to landscape and 200% text) against
throwaway SQLite databases only. `python tools/qa/mobile_suite/run.py [--only sale,forms] [--smoke] [--rebuild]` builds `base.sqlite3`
(demo data + `seed_rich.py`: 40 parties, 17 products, 40+ invoices of every shape, cheques in every status, returns, recurring costs), gives
every writing module its own DB copy and server, runs shards in parallel and prints totals (`summarize.py` groups failures).
Modules: `pages` (every page state x viewport x ~25 checks), `links` (anchors, aria, form actions, every internal link and asset),
`sale` / `purchase` (scenario matrices with DB oracles: prices from `Product.price_for`, totals, stock, payments), `forms` (every field x ~15
hostile inputs; list filters with hostile query strings), `payments` (party/invoice payments, cheques with the confirm dialogs, returns,
cancels, edit panels), `interact` (drawer, palette, filter fold, presets, date picker, keyboard over the dock, rotation, offline),
`states` (login page, lock-out, session expiry mid-form, double taps), `empty` (a fresh install). The real DB and `.env` are never read.

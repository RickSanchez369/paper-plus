# QA scenario suite

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
- `qa_28_mobile_layer`: search folding (digits, ك/ي, word order), dashboard stock alert, phone stylesheets linked, dues card hook.
- `python tools/qa/mobile_env.py NAME PORT` builds a throwaway demo DB under `tools/qa/.mobile/` and serves it (several can run at once).
- `python tools/qa/mobile_audit.py --base http://localhost:PORT --login tools/qa/.mobile/NAME.sqlite3.login.txt --label X` is the phone
  scorecard (needs `pip install playwright` and Chrome; a dev tool, not in requirements.txt). Baseline and results: `docs/UI_EVOLUTION_LOG.md`.

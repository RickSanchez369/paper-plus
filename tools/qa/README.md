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

`OK`/`FAIL` per check and `n/N passed` at the end. JavaScript behaviour
(item rows, payment rows, date picker, htmx forms) cannot be seen from here:
that part is checked in the browser pane.

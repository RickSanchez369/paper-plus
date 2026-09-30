# REDESIGN_VISION — condensed

The 2026-09-24 design spec for the full rebuild (Django-Admin multi-tenant
tool → real single-business web app). Built, merged and retired 2026-09-26.
This is a short summary. The original full spec is recoverable with
`git show 5c14525:docs/REDESIGN_VISION.md`.

Founding principle (Sina): no money, goods, cheque, debt or transaction may
be recorded without an origin, a destination, a related document, a date and
time, and the person who recorded it.

## Architecture decisions (§2)
1. Keep the services/models/selectors layer; replace only the presentation
   layer with real views + templates. `/admin/` stays superuser-only.
2. Single business, no multi-tenancy (D-033).
3. No roles; `is_superuser` is the only distinction (D-034).
4. Real FIFO costing via `InventoryLayer` + `InventoryConsumption` (D-036).
5. One-shot invoices: party, items and payment split are created and
   confirmed atomically; errors re-render the form in Persian.
6. No independent "cash account" entity: `bank_account = null` means cash.
7. No physical delete of financial records; corrections are opposite entries.
8. HTMX + Django templates (no SPA, no API layer).
9. Reports are never snapshotted; everything is derived live for the range.

## Model changes made (§3)
Removed Business/BusinessMembership and every `business` FK. Added
`InventoryLayer`, `InventoryConsumption`, `Payment.customer/supplier`,
`Cheque.CANCELLED`, `Expense`, `BankAccount.owner`, and new `AuditLog` event
types (`record_expense`, `cancel_expense`, `cancel_cheque`).

## Modules (§4)
Sales · Purchasing (+ Suppliers sub-section) · Inventory · Receivables /
Payables / Cheques · Bank Accounts · Expenses · Customers · Financial
Reports · User Activity · Dashboard. Per-module behaviour lives in the code,
its views' docstrings and `PROJECT_MAP.md`.

## Cross-page rules (§8)
- Every page that totals money excludes cancelled invoices, cheques and
  expenses.
- "Record payment" and "new customer/supplier" are single shared components.
- Incomplete cheques (no due date) get their own "needs completion" bucket.
- An inline-created product must have a real selling price.
- Inventory shows the last known cost once stock hits zero (display only).

## Still open
Visual identity (Phase D) and the USD-rate source — tracked in `STATE.md`.
Returns (ROADMAP 4.6) are out of scope by Sina's decision.

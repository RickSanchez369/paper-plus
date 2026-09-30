# STATE — paper-plus

Updated 2026-09-30. Per-module build history was dropped from this file on
purpose: `git log` is the record, `PROJECT_MAP.md` the live schema,
`DECISIONS.md` the why.

## Where we are
- The rebuild (Phases A–C) is finished, merged into `dev`/`main`, branch
  retired (2026-09-26). All 11 modules are built and browser-verified:
  Sales, Purchasing (+ Suppliers), Inventory, Receivables/Payables/Cheques,
  Bank Accounts, Expenses, Customers, Financial Reports, User Activity,
  Dashboard.
- The pre-Phase-D correction batch is done too (D-043..D-048: Toman
  everywhere, stock through documents only, expense paying account,
  full-settlement sale default, htmx 422 swap, pro-rata invoice discount).
- Last verified: 38 scripts in `scripts/`, 724/724 checks passing.
- Real data currently in the DB: 6 products with opening stock, 2 customers,
  2 suppliers, 1 bank account. `DocumentSequence` (sale, purchase) starts at
  9956001 — teardown scripts must never reset it below a number already used.

## Next
**Phase D is done (D-050):** IBM Carbon-inspired identity applied app-wide by
swapping the `app.css` tokens; three unchosen reference systems deleted, the
IBM reference kept in `docs/design/ibm/`. All 23 list/form/detail pages were
audited in the browser for leftover old-style radii, shadows and colours (none);
Carbon-style filled inputs and table headers apply app-wide. Not visually
checked (no data to render): invoice detail/print, cheque detail.

No task is queued. One candidate: tidying source comments that still cite
`REDESIGN_VISION`/`MASTER_PROMPT` section numbers.

## Open items (raise with Sina before touching)
- **USD-rate source** — undecided; Inventory and Reports show a placeholder
  card. Do not invent a source.
- **ROADMAP 4.6 returns (sales/purchase returns)** — explicitly out of scope
  (Sina, 2026-09-24). Do not design around it.
- **No write-off path** for physical loss/breakage since D-044 removed manual
  adjustment; would need a new decision (e.g. a write-off document).
- **Old `HistoricalProduct`/AuditLog rows** written before D-043 hold Rial
  figures; they describe deleted QA records and feed no calculation.

## Acceptance scenarios (ROADMAP Phase 5, not yet formally closed)
Sales/purchase numbers assigned automatically; product picker shows stock;
default price fills the line and stays a snapshot; invoice discount totals
correct; payment status derived from allocations; wrong invoice cancelled by
a superuser with history kept; stock correct after purchase and sale;
per-product history visible; selling price manageable with history;
amounts shown in Toman only (D-043); concurrent sales never oversell
uncontrolled (D-015, D-021). Most are covered by the existing scripts;
5.1–5.3 (one script per scenario, all passing, full review) remain open.

# STATE — paper-plus

Updated 2026-10-03 (third batch: D-067..D-076 — payments rework, pricing tiers, units). Per-module build history was dropped from this file on
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
  2 suppliers, 1 bank account. Invoices 9956001 (old style) exist; new ones are
  `1405/0001`-style (D-064). Teardown scripts must never delete a used
  `DocumentSequence` row.

## Next
**Phase D is done (D-050):** IBM Carbon-inspired identity applied app-wide by
swapping the `app.css` tokens; three unchosen reference systems deleted, the
IBM reference kept in `docs/design/ibm/`. All 23 list/form/detail pages were
audited in the browser for leftover old-style radii, shadows and colours (none);
Carbon-style filled inputs and table headers apply app-wide. Not visually
checked (no data to render): invoice detail/print, cheque detail.

**QA pass done (2026-09-30):** ~750 scripted checks (`tools/qa/`, see its README)
plus ~90 browser checks over every module found and fixed 14 defects (D-054).
All findings of the QA pass are now fixed (D-055..D-059): invoice cancellation refunds
payments, clearing a cheque needs an explicit account, receipt uploads are validated,
sign-in is throttled, inactive suppliers can be listed.

**Batch 2026-10-01 (D-060..D-063):** backup page/commands, A4 company invoice with
stamp boxes (company details still to come from Sina: fill `COMPANY_*` in `.env`, logo
box is a placeholder), hostiran.net visual identity, hosting-ready update path
(`deploy/UPDATING.md`). A fresh-database `migrate` bug was fixed on the way. Sina has
not picked a host yet: ask the host for Python >= 3.12 and PostgreSQL first.

**Batch 2026-10-03 (D-067..D-076), from Sina's list of ten:** bank accounts are card reader or current
account; cheques carry an issuer; sales discount can be a percent; cash is gone — card reader / bank transfer /
cheque, unpaid remainder is نسیه with a due date (full settlement = card, transfer or both); Receivables and
Payables split into cheques and credit with pass/bounce and pay-part actions; expenses by transfer, cheque or
credit; fixed repeating costs with reminders; the dashboard shows next week's payments; products are pack or
carton (separate products, separate stock); wholesale + retail prices with the sale type chosen on the
invoice. Checks: `tools/qa/qa_16_payment_rework.py` (66) and `qa_17_pricing_units.py` (30) plus the older
scripts all pass on PostgreSQL; the migrations were rehearsed on SQLite with data. Browser-checked on a
throwaway SQLite database (`tools/qa/run_qa_server.py` + `seed_qa_db.py`, port 8001): percent discount,
card+transfer settlement, split rows with account filtering, credit due date, receivables page + pass
cheque, expense method panels, fixed costs, dashboard list, sale-type switch keeping typed prices.
Live host: deploy with `manage.py update` (it backs up first); lessons learned on hostiran (nameservers set
at the registrar, cPanel shared IP differs from `hostname -i`, Secure cookies need https, certificate from the
SSL/TLS Wizard) belong in `deploy/HOSTIRAN.md` on the `deploy` branch.

**Bug-fix pass continues.** Sina reports bugs and defects page by page; each is
fixed and verified in the browser before the next. The open items below stay
open on purpose. Source comments no longer cite `REDESIGN_VISION` or
`MASTER_PROMPT` section numbers (removed 2026-09-30).

## Open items (raise with Sina before touching)
- **Real company details/logo for the printed invoice** — Sina will send them.
- **USD-rate source** — undecided; Inventory and Reports show a placeholder
  card. Do not invent a source.
- **ROADMAP 4.6 returns (sales/purchase returns)** — explicitly out of scope
  (Sina, 2026-09-24). Do not design around it.
- **No scheduled backup on the host** (Critical): the live database is one SQLite file; until a cron job
  runs `manage.py backup_db`, backups are manual. HSTS is not set yet (Major).
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
(D-015, D-052). Most are covered by the existing scripts;
5.1–5.3 (one script per scenario, all passing, full review) remain open.

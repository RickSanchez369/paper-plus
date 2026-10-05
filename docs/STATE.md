# STATE — paper-plus

Updated 2026-10-04 (sixth batch: D-086..D-091 — day/letter sale numbers, party credit, brand print, returns, four prices, SQLite host). Per-module build history was dropped from this file on
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

## TODO for the next session (start here, in this order)
1. **Daily backup cron on the host (Critical)** -- the whole business is one SQLite file. cPanel → Cron Jobs → daily 03:00:
   `cd /home/kaghazpl/paper-plus && <venv python> manage.py backup_db --keep 14`. The venv python path = the `source .../activate`
   line shown in «Setup Python App» with `activate` replaced by `python` (ask Sina for that line). Then: copy one backup off the
   host every week.
2. **USD rate on the host** -- run `python manage.py fetch_usd_rate` once in the cPanel terminal; if it reads a rate, add a cron
   every 3 hours (`0 */3 * * *`, same `cd` + venv python + `manage.py fetch_usd_rate`). If outbound HTTPS is blocked, keep the
   in-app «بروزرسانی نرخ» button only and record that here.
3. **HSTS ramp** (only once https is final): `.env` `HSTS_SECONDS=300` → restart → a few days → `86400` → weeks → `31536000`.
4. **Data entry by Sina** (after the 2026-10-05 reset): products with all four prices, customers with «نوع مشتری»
   (wholesale ones = عمده).
5. **Optional company details** in `.env`: `COMPANY_INSTAGRAM/TELEGRAM/WHATSAPP`, address, economic code, `COMPANY_TERMS`
   (Sina said "later").
6. **Drop `Product.unit`** -- no products left on the host after the reset, so it is safe once Sina agrees (new decision + migration).
7. **64 deferred UI items** in `docs/UI_AUDIT_200_DEFERRED.md` -- need Sina's choices.

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
since bought a shared host without PostgreSQL, so the live app runs SQLite (D-091).

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

**Batch 2026-10-04 (D-078..D-082), from Sina's list of five:** full settlement is ticked per method and a lone card
reader is the default account; one dashboard card for receivables and payables (cheques / credit, 10-day window); USD
rate history read from tgju (`fetch_usd_rate`, button, frozen on each confirmed invoice); one product counted in packs
with `pack_per_carton`, lines typed as cartons + packs, retail = per pack, wholesale = per carton, average purchase price
for display with FIFO still deciding profit, negative-stock card removed; freight on purchase invoices spread over the lines
into their landed cost. Checks: `qa_18`..`qa_23` (12, 11, 32, 43, 28, 19) and every older script pass on PostgreSQL;
migrations `shared.0018`, `sales.0014/0015`, `purchasing.0011..0013`, `products.0008/0009` were applied to the dev database
and the throwaway SQLite one; browser-checked on `paper-plus-qa` (ticks, single-account default, dues card, rate button,
cartons + packs row with stock left, over-stock block, freight tick, detail pages). **Before deploying:** run
`inventory_unit_report` on the real data, agree the merge map with Sina, then `convert_units --dry-run` and the real run
(see `deploy/UPDATING.md`); until then carton-counted products read wrongly. Not changed on purpose: purchase invoices
still offer no card-reader option (a card reader only receives money, D-069).

**Batch 2026-10-04 UI audit (D-083):** ten read-only agents audited the data-dense UI; accepted fixes are in: RTL numbers with units, one `status_badge`/`flag_badge` map, AA contrast tokens + focus ring, invoice summary strip, shared pager + column sort on the growing lists, two-level product search rows, mid-width invoice line layout. Checked: `qa_02..08`, `qa_14`, `qa_19`, `qa_21` pass; browser-checked at 768/1024/1440 on `paper-plus-qa`. Not done: dues boards, bank cards and fixed costs stay unpaged; `--ink-400` 11px sidebar label and input focus ring contrast not touched; Python/template changes need a restart of the `--noreload` QA server.

**Batch 2026-10-04 fifty-critic UI audit (D-084):** 50 read-only critics (one angle each) produced ~300 findings; the verified
ones are applied in two commits (see D-084 for the list and for what was left to Sina). Checked: `qa_02..24` pass on a throwaway
SQLite except `qa_13` BK12, which also fails on the commit before this batch (SQLite only, not investigated); `qa_24_ui_audit`
is new; browser-checked the invoice keyboard flow and the date picker with Playwright. QA scripts need `DEBUG=True` when run on
SQLite (empty `ALLOWED_HOSTS` otherwise gives 400). Phone width (390px) checked on dashboard and inventory; **not checked:** other pages at phone width, print preview.

**Batch 2026-10-04 two-hundred-critic UI audit (D-085):** 196 findings, 147 applied + 37 merged, 64 deferred entries
(`docs/UI_AUDIT_200_DEFERRED.md`, need Sina). Preview with `.\tools\qa\preview.ps1` (demo data on a throwaway SQLite). Checked: `qa_02..24`
pass on SQLite except `qa_13` BK12 (pre-existing); Playwright on 33 pages at 1280 and 390: no JS errors, no page-level horizontal
overflow except the A4 print page; tables scan at 1280/1024. **Not checked:** real PostgreSQL, real keyboard/touch flows beyond
the sale form, print preview, localStorage behaviour across sessions. Known: a few wide tables still scroll inside their card at 1024px.

**Batch 2026-10-04 (D-086..D-091), from Sina's list of six:** sales numbers «الف/14050712» per invoice day (after «ی»: «الف2»);
party credit fixes the "payment for a customer with nothing open disappears" bug (unticked payments settle oldest invoices,
surplus only with the «بستانکاری/پیش‌پرداخت» tick, credit shown on party pages/lists/dues and used first by the next invoice);
one-page A4 brand print («کاغذ پلاس», green/navy, B&W switch, settlement box, rotating thank-you line, contacts; USD rate no longer
printed, still on detail pages); sales and purchase returns (new app `apps.returns`, menu «مرجوعی», FIFO back/out, money off the
invoice first then refund or credit, invoices with returns cannot be cancelled); four selling prices with the sale type chosen on the
invoice and preset from `Customer.price_tier` (10 proposals compared, the recommended synthesis taken); the host DB is SQLite
(D-091). Checks: all 26 `tools/qa` scripts pass on a throwaway SQLite (new: `qa_25_party_credit` 36, `qa_26_returns` 49,
`qa_27_tier_prices` 27; `qa_13` BK12 passes again); upgrade rehearsed on SQLite: `deploy`-branch code + data, then this code's
migrations (`shared.0019..0021`, `payments.0013`, `returns.0001`, `inventory.0007/0008`, `products.0010`, `partners.0003`) --
numbers, tiers, stock and balances unchanged, key scripts pass on the upgraded copy. Browser-checked (port 8002 throwaway server):
credit tick refusal/acceptance, credit notice and reduced full-settlement amount, print at 1/22/38 lines and B&W, return form with
live over-limit and refund account, wholesale/retail switch with kept manual price, below-cost hint, customer-type preset, phone width.
**Not run:** PostgreSQL (not used on the host any more), real host. Merged into `deploy` and deployed on 2026-10-05 (see below).

**Deployed 2026-10-05:** `deploy` (`390f148`, D-086..D-092) is live on the host (SQLite). `update` ran after the D-092 fix,
then `reset_business_data` emptied all business data at Sina's request (users kept); Sina confirmed everything works. The
D-081 unit conversion is no longer needed on the host (no old products remain). Next on the host: cron jobs (`backup_db --keep 14`,
`fetch_usd_rate`), HSTS ramp, then re-entering products with the four prices and customers with their type.

**Bug-fix pass continues.** Sina reports bugs and defects page by page; each is
fixed and verified in the browser before the next. The open items below stay
open on purpose. Source comments no longer cite `REDESIGN_VISION` or
`MASTER_PROMPT` section numbers (removed 2026-09-30).

## Deployment runbooks (2026-10-04)
`deploy/CHECKLIST.md` (order, revert point, live test list), `deploy/UNIT_CONVERSION.md` (rehearse on a restored backup copy, then live),
cron lines for `backup_db --keep 14` and `fetch_usd_rate`, HSTS ramp, `COMPANY_*`. The rehearsal flow (backup, restore_db,
inventory_unit_report, convert_units --dry-run) was run end to end on the demo database. Host is cPanel without SSH and its database is SQLite
(confirmed by Sina, D-091; the shared host has no PostgreSQL). Nothing was run on the host.

## Open items (raise with Sina before touching)
- **Real company details/logo for the printed invoice** — Sina will send them.
- **USD rate on the host** — tgju is read with stdlib `urllib` (D-080); whether the shared host allows outbound HTTPS is
  untested, and the cron line `manage.py fetch_usd_rate` still has to be added there.
- **Drop `Product.unit`** — only after `convert_units` has run on every database (D-081).
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

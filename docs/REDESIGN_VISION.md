# REDESIGN_VISION — paper-plus full rebuild (branch `explore/vision-rethink`)

> **Status (2026-09-26): §1–4 and §7–9 are historical** — Phases A–C they
> describe are built, verified, merged into `dev`/`main`, and the branch is
> retired. **§5–6 are still current** — the Phase D visual-identity pick and
> the USD-rate source remain open, unresolved, and unbuilt.

Written 2026-09-24 at the end of a design-only session with Sina (no code
changed on this branch except this doc + the 4 downloaded design systems).
Purpose: let a fresh chat pick up the build with full context — this
branch's starting point is `dev` at commit `0be4bb4` (end of ROADMAP 4.4).

**Read this whole file before writing any code.** It supersedes the
multi-tenant / role-based assumptions baked into `docs/RULES.md`,
`docs/STATE.md`, and `docs/PROJECT_MAP.md` for this rebuild — those files
describe the *old* Admin-only, multi-business system, which this redesign
intentionally leaves behind. Domain logic (services/models for
sales/purchasing/inventory/payments) is reused; the multi-tenant shell and
the Django Admin UI are not.

## 1. Why this redesign exists

Sina's own words, kept verbatim because they set the tone for every
decision below: "من فکر می‌کنم مسیر رو داریم اشتباه می‌ریم ... اشتباه اصلی
از خودم بوده که توی تصویرسازی از اونچه که واقعاً می‌خواهیم کامل بیان
نکردم." He then wrote a full vision document (reproduced in spirit across
this file) describing a real, professional, connected financial/inventory
web application for a paper-products business — not a Django-Admin-based
tool. Core principle, his words: "هیچ پول، کالا، چک، بدهی یا تراکنشی نباید
بدون منشأ، مقصد، سند مرتبط، تاریخ، زمان و شخص ثبت‌کننده قابل ثبت باشد."

## 2. Non-negotiable architecture decisions (confirmed by Sina, 2026-09-24)

1. **Do not rewrite from zero.** Keep the existing services/models/selectors
   layer (`apps/sales`, `apps/purchasing`, `apps/inventory`, `apps/payments`,
   `apps/partners`, `apps/products`) — it was already built so that "Admin
   never writes movements/money directly," i.e. the business logic was
   never actually coupled to Django Admin. Replace the presentation layer
   only: real Django views + templates, navigable pages, no end-user
   operations through `/admin/` ever again. `/admin/` may remain as a
   superuser-only technical backend (see §7), not a user-facing surface.
2. **Single business, no multi-tenancy.** Sina: "یک قسمت عضویت کسب‌وکارها و
   خود کسب‌وکار رو حذف کنیم ... اگه خواستم برای کسب‌وکار جدیدی ایجاد کنم،
   یه مدل دیگه رو کپی می‌کنم یا اضافه می‌کنم." Concretely:
   - Delete `shared.Business` and `shared.BusinessMembership` models entirely.
   - Remove the `business` FK from every model that has one (Product,
     Customer, Supplier, SalesInvoice, PurchaseInvoice, InventoryMovement,
     DocumentSequence, AuditLog, BankAccount, Payment, Cheque — all of
     them, per `PROJECT_MAP.md`'s current schema).
   - Remove `BusinessScopedAdminMixin` and the per-business functions in
     `apps/shared/permissions.py` (`get_business_ids`, `has_role(user,
     business, ...)`, `is_owner(user, business)`, `require_role`).
   - A second business, if it ever happens, is a separate deployment, not
     multi-tenancy in this database.
3. **No role/permission system for now.** Sina, after being shown the
   concrete implication ("نقش Owner/Seller مستقیم روی User بمونه یا حذف
   بشه؟"), picked: "طبق بخش ۲۵ سند ... کلاً فعلاً حذفش می‌کنیم و بعداً از
   پنل ادمین اضافه می‌شه." Concretely:
   - Delete the Owner/Seller role concept entirely (no role field anywhere).
   - Any authenticated user has full access to every page/action, with two
     explicit exceptions carried over from the old role-gated behavior
     (§4.9 below): oversell blocking and cancellation are both now
     **superuser-only** (`request.user.is_superuser`, Django's own builtin
     flag — unaffected by deleting Business/Membership).
   - Multiple logins still exist (for staff attribution — `created_by`/
     `actor` fields stay everywhere, full audit trail is still required),
     just with no permission differentiation between them right now.
   - User creation/deactivation stays an Admin-panel-only task for now
     (Sina, vision doc §25) — not a page in the new frontend.
4. **Real FIFO costing, replacing today's Last-Cost approximation.**
   Sina: "این منطق‌هایی که گفتم رو باید کاملاً اجرا کنیم" — full logic,
   not a simplified version. Today's `get_cost_map` (latest purchase price)
   is not FIFO and does not support per-invoice real profit. New model
   (§3) required.
5. **One-shot invoice creation**, confirmed by Sina. No user-visible
   "draft, save, come back tomorrow" state for Sales/Purchase invoices —
   the whole invoice (party, items, payment split) is filled and submitted
   in a single page/transaction that creates-and-confirms atomically. If
   invalid, nothing is saved and the same form re-renders with Persian
   field errors (never a raw DB constraint message — lesson already learned
   from the `ChequeForm` bug in ROADMAP 4.4).
6. **No independent "cash account" entity** (vision doc §8) — `bank_account
   = null` on a Payment/Expense still means cash, exactly like today; it's
   just never listed as a row in the Bank Accounts module.
7. **No physical delete of financial records, ever** — extends the existing
   append-only philosophy (Payment/PaymentAllocation/Cheque/InventoryMovement)
   to the two new things this redesign adds: `Expense` (cancel-only, never
   edit/delete) and `Cheque` (gains a `CANCELLED` status, see §3).
8. **Frontend interactivity stack: HTMX + Django templates**, confirmed by
   Sina 2026-09-24 after being given the tradeoff directly (plain
   vanilla JS/fetch was the runner-up; a full SPA + DRF API was rejected
   as unwarranted scope for a single-business internal tool with no
   mobile/offline requirement anywhere in the vision doc). Every live-
   interaction need identified in §4 (price autofill, live remaining-
   amount calculation, repeating invoice-item rows) is a "server already
   has the data, swap a page fragment" pattern — HTMX's exact use case.
   One language (Python), no new API layer, no build tooling, reuses the
   same views/forms the rebuild is writing anyway.
9. **Financial reports are never snapshotted.** Sina confirmed: everything
   is derived live from the append-only ledgers (movements, payments,
   audit log) for whatever date range is picked, consistent with D-025
   ("never store a derived fact"). The only thing worth saving is a
   bookmarked *filter* (the date range itself), not a computed number.

## 3. Model changes required (not yet built — design only)

- **Remove:** `shared.Business`, `shared.BusinessMembership`, every
  `business` FK, `BusinessScopedAdminMixin`, per-business permission
  functions, `apps/shared/signals.py`'s group-sync signal (no more
  Owner/Seller groups).
- **`InventoryLayer`** (new, apps.inventory): `product`, `quantity_remaining`,
  `unit_cost`, `created_at`, source (`opening_stock` | `purchase_item` FK).
  One layer per opening-stock event or per confirmed purchase item.
- **`InventoryConsumption`** (new, apps.inventory): `sale_item`, `layer`,
  `quantity`. Records exactly which layer(s) a sale item drew from and how
  much — required for exact reversal on cancel and exact per-item profit.
  Selling consumes oldest layer first (true FIFO). `SaleItem.cost_of_goods
  = Σ(consumption.quantity × layer.unit_cost)`; profit = line total − that.
- **Purchase cancellation guard:** a `PurchaseItem`'s `InventoryLayer` may
  only be cancelled while untouched (`quantity_remaining == original
  quantity`); if any of it was already sold, cancellation is rejected with
  a clear Persian message — required for FIFO integrity, not optional.
- **`Payment` gains `customer` / `supplier`** (nullable FKs, mirroring the
  pattern already on `Cheque` — see `apps/payments/models.py`). Unlike
  `Cheque`, neither is required (an `Expense`'s Payment has neither).
  Constraint: if `direction=in` and `customer` is set, `supplier` must be
  null, and vice versa. `confirm_sale`/`confirm_purchase` set this
  automatically from `invoice.customer`/`invoice.supplier` when creating a
  Payment from a payment-entry row. **Why this exists:** an unallocated
  payment (e.g. a prepayment before any invoice is picked) currently has
  zero trace to a customer/supplier — violates the traceability principle
  (vision doc §4). This was found, not asked about — it's a required fix,
  not a fork.
- **`Cheque.Status` gains `CANCELLED`**, reachable only from `PENDING`
  (mirrors the existing "editable only while pending" rule from ROADMAP
  4.3b round 2). No financial effect on reversal, because a pending cheque
  was never counted toward any invoice's `payment_status` to begin with
  (ROADMAP 4.4 decision) — cancelling one is a pure "I entered this by
  mistake" correction, not a reversal.
- **`Expense`** (new app or new model in `apps.payments`): `date`, `amount`,
  `related_person` (free text — not necessarily an existing Supplier),
  `reason` (free text, "بابت"), `bank_account` (nullable FK = cash, same
  pattern as `Payment.bank_account`), `document` (optional file upload,
  receipt/proof), `note`, `created_by`, and a **`payment` OneToOne to
  `Payment`**. `record_expense(expense, user)` service creates the Expense
  **and** a `Payment(direction=OUT, no allocations)` together, atomically —
  deliberately reusing the existing Payment ledger instead of a second,
  parallel accounting path (vision doc §27, "one source of truth").
  `cancel_expense` creates a reversing `Payment(direction=IN)` and flags
  the Expense cancelled — never a physical delete (§2.7 above).
- **`AuditLog.EventType`** gains: `record_expense`, `cancel_expense`,
  `cancel_cheque`.

## 4. Final page map (11 top-level modules, confirmed order)

Suppliers is a sub-section of Purchasing, not its own nav item (Sina's
explicit call). Build order agreed: Sales → Purchasing → Inventory →
Receivables/Payables/Cheques → Bank Accounts → Expenses → Customers →
Financial Reports → User Activity → Dashboard (dashboard last, since it
only aggregates everything else).

### 4.1 Sales (`/sales/`)
- **List**: cards (today's sales, this month, open partial/credit count,
  month profit); table (invoice #, date, customer, total, payment-status
  badge, profit, document status); free-text search (invoice # + customer
  name) *plus* separate structured filters (date range, payment status,
  product, amount range) — never conflated into one box (vision doc §26).
  Pagination, empty state, print button per row.
- **New sale** (`/sales/new/`, one-shot form): customer picker + inline
  "new customer"; date; repeating item rows (product autocomplete showing
  live stock in the label, price auto-filled live from
  `default_selling_price` via a real endpoint — port the existing JS
  autofill logic, not Admin's); live subtotal/discount(%, or fixed)/total;
  split payment rows (cash/card/bank_transfer/cheque — reuse the existing
  4.3b remaining-amount auto-fill logic and "incomplete cheque allowed"
  rule); remaining after all rows = credit (نسیه), shown live. Submits as
  one atomic create+confirm; validation errors are Persian and inline,
  never a raw DB constraint (`ChequeForm.clean()` pattern already proven).
- **Detail** (`/sales/<id>/`): header (number, date, customer link,
  creator, timestamp, status); items table incl. FIFO cost + profit per
  line (from §3's `InventoryConsumption`); totals incl. **invoice profit**
  (highlighted); recorded payments/cheques with links to their bank
  account / cheque record; cancel button (**superuser-only**, confirmation
  modal, calls the existing `cancel_sale`); dedicated print route;
  breadcrumbs to customer and to the sales list.

### 4.2 Purchasing (`/purchasing/`)
Symmetric to Sales: list (cards: today/this month purchase totals, open
payable count), one-shot new-purchase form (supplier picker + inline
create; item rows can create a brand-new product inline per vision doc
§13; manual purchase price per row, with last purchase price shown as a
placeholder hint only; no discount concept — the model never had one and
the vision doc doesn't ask for it), detail page (no profit column — profit
is sales-only), cancel restricted the same way as Sales **and additionally
blocked once the resulting `InventoryLayer` has been partially consumed**
(§3's FIFO integrity guard — this is stricter than Sales' cancel rule).

**Suppliers sub-section** (inside this module, not top-level nav): list
(name, phone, total purchased, outstanding payable — derived, never
stored); detail page (purchase history, payments made, cheques issued,
running balance) — same selector the Payables page (§4.4) reads from.

### 4.3 Inventory (`/inventory/`)
Cards: total inventory value (Σ all active layers × their own cost — not
last-cost × total qty, because layers now carry different costs), item
count, negative-stock warning (defensive; should never happen under the
new oversell policy). Table: name, stock, current purchase cost (= oldest
active layer's cost, i.e. what the next sale will consume), selling price,
this item's inventory value, % share of total value. Buttons: new product,
opening stock entry, manual adjustment (in/out, mandatory reason note).
Per-product detail: active layers (cost + remaining qty each) + the
existing chronological movement history (ROADMAP 4.2) extended to show
which layer each row touched, with a link back to the source invoice.
USD/dollar rate: a placeholder card only ("not configured yet") — source
is explicitly undecided per the original vision doc §12/§30, item 8; do
not invent a source.

### 4.4 Receivables / Payables / Cheques (`/receivables/`, `/payables/`, `/cheques/`)
One conceptual module, three views, per vision doc §9 ("مطالبات و بدهی
جدا محاسبه می‌شن، ولی در یک بخش مرکزی مدیریت می‌شن"):
- **Receivables**: customers with an open balance (derived from
  `PaymentAllocation` vs `SalesInvoice.total`, never stored — existing
  D-025 pattern). "Record payment" can split across several of that
  customer's open invoices in one `Payment` (already possible today: one
  `Payment` can have many `PaymentAllocation` rows) or stay unallocated.
- **Payables**: exact mirror, Supplier/PurchaseInvoice side. Shares its
  selector with the Suppliers sub-section (§4.2) — one query, two entry
  points, never two sources of truth.
- **Cheques**: table (direction, number, amount, bank, party, due date,
  status incl. the new `CANCELLED`, linked invoice or "general/unattached"),
  filters (status, direction, due-date range — feeds the dashboard's
  "cheques due soon" widget, customer/supplier), actions per pending
  cheque (complete missing fields, clear → `clear_cheque`, bounce →
  `bounce_cheque`, cancel → new `cancel_cheque`, all one-way like today).
  Full lifecycle trace on the detail view.

### 4.5 Bank Accounts (`/bank-accounts/`)
List: bank name, **account owner** (new field — doesn't exist on
`BankAccount` today, needs adding), account number, live balance (from
`get_bank_account_balance`, already exists). Per-account comparison cards
(balance vs. yesterday / last week / last month — aggregate queries over
`Payment`, no new model). Detail: full ledger (date, amount, direction,
source/destination — invoice, expense, or cheque — creator, timestamp),
all already derivable from `Payment`/`PaymentAllocation`/`Expense.payment`.
No independent "cash" row in this list (§2.6).

### 4.6 Expenses (`/expenses/`)
List newest-first: date, related person, reason, amount, paying bank
account, creator, receipt icon if attached. Cards: today's total, this
month's total. Search (person/reason, free text) + filters (date range,
bank account, amount range). New-expense one-shot form (date, person,
reason, amount, bank account or cash, optional receipt upload, note) →
atomic create of `Expense` + `Payment(OUT)`. No edit/delete — only
`cancel_expense` (superuser-only, same risk tier as invoice cancellation).

### 4.7 Customers (`/customers/`)
List: name, phone, account status badge (owes / settled), open balance,
invoice count, last purchase date. Search (name/phone), filter (account
status, active/inactive). "New customer" button — same component reused
inline inside the Sales new-invoice form.
Detail (**this *is* ROADMAP 4.5**, fully specified now): header + edit;
cards (lifetime purchases, open balance, invoice count, last purchase);
this customer's invoices (linked), payments (`Payment.objects.filter
(customer=...)`, now directly queryable thanks to §3's fix, regardless of
allocation status), cheques (`Cheque.objects.filter(customer=...)`,
already directly queryable today), and a combined chronological
**statement/ledger** (invoices = debit, cleared payments/cheques =
credit) — the literal "running balance" ROADMAP 4.5 asked for. "Record
payment" button here too, same multi-invoice allocation as Receivables.

### 4.8 Financial Reports (`/reports/`)
Date-range picker (today/week/month/custom). Every number below is
computed live for the chosen range, never stored (§2.8):
- Summary cards: total sales, total purchases, expenses, gross profit (Σ
  real per-line FIFO profit), net profit (gross − expenses) — each with %
  change vs. the equal-length prior period (also computed live).
- Sales by product (qty, amount, profit) and purchases by product (qty,
  amount) tables.
- Top sellers (ranked by quantity, linked).
- Inventory **as of the end of the selected range** (not "right now") —
  reconstructed from the movement/layer ledger up to that date, so a
  report for last month shows last month's true stock, not today's.
- Bank account balances as of range end + period in/out totals.
- Open receivables/payables as of range end.
- Cheque counts/amounts by status within the range.
- User activity within the range (from `AuditLog`, grouped by actor).
- USD rate: placeholder only, same as §4.3 — source still undecided.
- Print button (dedicated print template, same pattern as invoices).

### 4.9 User Activity (`/user-activity/`)
Same date-range component as Reports. Aggregate table: one row per user →
counts of sales/purchases/expenses/payments/cheques recorded + cancellations
+ total amounts, within range (satisfies vision doc §25's "compare user
activity"). Drill into a user → their raw `AuditLog` feed (event type,
linked target via a small `target_type → URL` routing table built at
implementation time, timestamp). Filters: user, event type, date range.
**Not** a user-management page — creating/deactivating logins stays an
Admin-panel-only task for now (§2.3).

### 4.10 Dashboard (`/`, landing page after login)
Deliberately just a summary, not a repeat of every module's detail:
- Row 1: sales/purchases/expenses/net-profit KPI cards, each showing
  today + this month.
- Row 2: open receivables total, open payables total, total bank balance
  (all accounts summed), total inventory value — each links to its module.
- Row 3 (attention-needed): cheques due within 7 days (3-5 shown + "see
  all"), old unpaid credit invoices (default 30-day threshold — a query
  parameter, not a new field), negative-stock warning (defensive only).
- Row 4: recent activity feed, global (all users, latest N from
  `AuditLog`) + "see all" link into User Activity.
- Persistent sidebar navigation (all 11 modules) lives outside the
  dashboard's own content — the dashboard is a page, not the nav itself.

## 5. Visual design references (downloaded, not yet chosen)

Per Sina's request, 4 candidate `DESIGN.md` brand-design-system files were
pulled from `github.com/VoltAgent/awesome-design-md` for comparison before
picking (or blending) a visual identity for the new frontend:
- `docs/design/stripe/DESIGN.md` — trustworthy, data-dense, the reference
  point for financial SaaS.
- `docs/design/linear/DESIGN.md` — very minimal, sharp, precise spacing.
- `docs/design/ibm/DESIGN.md` — more formal/corporate register — chosen as
  a candidate specifically because this is a trading business, not a tech
  startup.
- `docs/design/posthog/DESIGN.md` — dashboard-heavy, card/chart/table-dense
  — relevant given how many pages here are dashboards/reports.
No pick has been made yet. The `design-taste-frontend` and
`redesign-existing-projects` Claude Code skills are available in this
environment and should be invoked when actually building frontend pages.

## 6. Open items — do not decide silently, ask Sina

- **USD/dollar rate source** (vision doc §12, §24, §30 item 8): still
  completely undecided. Do not invent a data source.
- **Which visual design system** (§5) to actually use, or how to blend them.
- Anything else vision doc §30 lists that this file doesn't explicitly
  resolve above (dashboard exact layout details, print template styling,
  full role/permission model for the *future* phase, mobile/responsive
  specifics) — those are implementation-detail decisions for the build
  phase, not resolved here on purpose (per Sina's own staged process, see
  §7).

## 7. How Sina wants to continue (his own words, vision doc §31-32)

Six stages: (1) full page/navigation map — **done, this file, §4**; (2)
each page in detail (purpose, KPIs, tables, filters, forms, financial/
inventory/audit effects, empty/error states, navigation) — **done, §4**;
(3) cross-page logic review (e.g. Sales ↔ Customer ↔ Invoice ↔ Product ↔
Inventory ↔ FIFO ↔ profit ↔ Bank ↔ Cheque ↔ Receivables ↔ Reports ↔ User
Activity) — **largely covered inline above via the explicit cross-links in
every module**, but worth a dedicated pass before finalizing; (4) final
per-page architecture, written after Sina confirms stage 3; (5) one very
precise Master Prompt for building the whole system; (6) optionally, one
prompt per page. Sina does not want a final prompt generated before he
has explicitly signed off on the architecture. Interaction rules he set:
listen first, raise architecture problems directly and plainly, ask at
most two precise questions per stage, confirm before big changes, don't
repeat things already said, don't generate the master prompt early.

**Also confirmed 2026-09-24, extending the earlier autonomy instruction
(see memory `feedback-autonomous-execution`):** no more stopping after
each checklist item to wait for a go-ahead — do the design/build work
directly and only pause to ask when there is a genuine fork or a specific
business-logic ambiguity, same standard as the git-execution autonomy
already granted.

## 8. Stage 3 — cross-page logic review (done independently, 2026-09-24)

Traced several real end-to-end chains through the §4 page designs looking
for contradictions, double-counting, or dead ends between modules.

### Chains checked and found consistent
- **Sale with split payment (cash + pending cheque + credit) → FIFO
  consumption → per-line profit → PaymentAllocation → Receivables total →
  Dashboard.** A pending cheque correctly stays outside `payment_status`
  (ROADMAP 4.4's own rule) until `clear_cheque` runs, at which point every
  downstream number (invoice status, customer balance, dashboard totals)
  updates automatically from the same underlying tables — no page caches a
  stale number.
- **Purchase cancellation guard under FIFO.** Blocking cancellation once a
  layer's `quantity_remaining != original quantity` correctly prevents
  breaking a sale that already consumed part of it — verified against both
  "fully consumed" and "partially consumed" cases.
- **Sale cancellation reversing exact FIFO layers**, even when a *later*
  sale has since drawn further from the same layer(s) — restoring by exact
  `InventoryConsumption` amount (not FIFO-order-dependent) keeps the layer
  arithmetic correct regardless of what happened in between.
- **`InventoryLayer` vs `InventoryMovement` is not a duplicate-source-of-
  truth problem.** `InventoryMovement` stays the immutable historical fact
  (never mutated, per the project's append-only invariant since D-012);
  `InventoryLayer.quantity_remaining` is a maintained *derived* running
  balance (fully reconstructable by replaying `InventoryConsumption`
  against the original quantity) — the same relationship `Payment` already
  has to `PaymentAllocation`. Keeping them separate avoids ever mutating an
  append-only ledger row.
- **Receivables/Payables lists, Customer/Supplier statements, and Sales/
  Purchasing list payment-status badges** all read the same underlying
  `PaymentAllocation`-derived properties — no page stores its own copy, so
  they cannot drift apart.
- Sina's earlier live-testing complaint ("این تخصیص پرداخت‌ها رو نمی‌فهمم
  چه تخصیصی، اصلا برای چیه") does not resurface in this redesign: payment
  allocation is never its own page anymore, it is always embedded inside a
  concrete action (recording a sale's payment split, or "ثبت پرداخت" from
  a customer/receivables page).

### Real gaps found — fixed directly in this doc (not forks, just missed detail)
1. **Incomplete cheques (no `due_date` yet, ROADMAP 4.3b's allowed case)
   are invisible to any "due soon" alert**, since a null due date can never
   fall inside a 7-day window. Both the Dashboard's warning row (§4.10) and
   the Cheques list (§4.4) must show a separate **"نیاز به تکمیل اطلاعات"**
   bucket, with equal visual urgency to "due soon" — otherwise an
   incomplete cheque can sit forgotten indefinitely.
2. **"ثبت پرداخت" appears in four places** (Receivables, Payables,
   Customer detail, Supplier detail) — this must be **one shared form/
   component**, not four separate implementations, or they will drift
   apart over time. Same treatment as "مشتری جدید" already reused between
   the Customers page and the Sales new-invoice form.
3. **Cheque entry from an invoice's payment row never mentioned letting the
   user optionally pick the destination bank account up front**, even
   though `Cheque.bank_account` already supports being set before
   clearing. Add it as an optional field on that row, alongside cheque
   number/bank/due date.
4. **Cross-cutting rule, must hold on every page that totals money:**
   dashboard cards, financial reports, customer/supplier statements, and
   every list's summary cards must all exclude **cancelled** invoices,
   cheques, and expenses from their totals. Stating it once here so no
   single page's implementation misses it and quietly disagrees with the
   others.
5. **Inventory's "قیمت خرید جاری" has nothing to show once a product's
   stock hits zero** (no active layer left). Show its last known cost
   (from the most recent, now-exhausted layer) instead of a blank, purely
   for reference — it does not feed any calculation.
6. **A product created inline mid-purchase still needs a real
   `default_selling_price`**, not the field's `0` default silently
   accepted — the inline form should require it even though the user is
   in a *purchase* flow, to avoid an accidental free sale later.
7. **ROADMAP 4.7 (purchase/selling price history) has no dedicated view**
   in the §4 page map. The underlying data already exists
   (`HistoricalProduct` via django-simple-history) — this just needs a
   small "تاریخچهٔ قیمت" tab added to the Inventory per-product detail
   page (§4.3), not a new module.

### Out of scope, explicitly deferred by Sina (2026-09-24)
8. **Sales/Purchase returns (ROADMAP 4.6) have no home anywhere** — not in
   the original vision document, not in any of the 11 modules designed in
   §4. This is different from cancelling an invoice (which voids the
   *whole* document): a return is "the invoice was correct, but the
   customer brought back 2 of the 10 items three weeks later," and it has
   real open design questions of its own (does returned stock become a
   *new* `InventoryLayer` at the original cost, or something else; does it
   need its own document type; does it retroactively touch the original
   invoice's reported profit or book a separate return/loss entry). Sina's
   call: **"فعلاً از دامنه خارجش کن، برای بعد نگهش داریم"** — explicitly
   out of scope for this redesign round. Do not design or build it without
   a fresh conversation about it later. ROADMAP 4.6 stays open/unbuilt.

## 9. Where things stand right now

This branch (`explore/vision-rethink`) contains **zero code changes** from
`dev` — only this document and the 4 design-system references (§5). No
model/service/view code for the redesign exists yet. **Stage 3 (§8) is
fully closed** — no open items remain. The next session should start by
reading this file in full, then move to stage 4 (final per-page
architecture write-up) and/or stage 5 (the Master Prompt), per whatever
Sina decides at the start of that session (see §7 for his 6-stage plan).

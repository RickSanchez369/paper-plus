# Business & technical rules — paper-plus

Invariants the running system must never violate, regardless of who or
what is developing it — as opposed to `docs/RULES.md`, which covers how
work on this repo is conducted (chat rhythm, git conventions, dev
environment). Full rationale for any `D-0xx`: [DECISIONS.md](DECISIONS.md)
(append-only, wins if this summary and it ever disagree in wording).

## Core invariants

- **Service layer only.** Writes that touch stock or money go through a
  service inside `transaction.atomic()`. Views/Admin call the service;
  neither writes movements or money directly.
- **Append-only ledger, no manual adjustment.** Stock is derived from
  `InventoryMovement`, never a stored stock field. The ledger changes only
  through documents — opening stock at product creation, purchase, sale —
  and a wrong document is cancelled, never edited; cancellation writes the
  reversing rows (D-014, D-023, D-044).
- **Opening stock is entered once**, before any other movement on that
  product, only at product creation (D-017, narrowed by D-044).
- **Money is `BigIntegerField`, whole Toman**, everywhere — storage,
  input, display, reports. One formatting helper (`format_toman`) and one
  template filter (`toman`); no other unit appears in the UI (D-043).
- **Nothing derived is stored.** Payment status, balances, every report
  number — always computed live from the ledgers, never a field that can
  drift (D-025).
- **Single business, no multi-tenancy.** No `business` FK anywhere;
  a second business would be a separate deployment (D-033).
- **No role system.** Any authenticated user may use any page/action, with
  exactly one exception, `is_superuser`-gated: cancelling a confirmed invoice
  (D-023/D-034). A sale can never take stock below zero, for anyone (D-052).
- **`/admin/` is a superuser-only technical backend**, never the end-user
  surface (D-035).
- **Real FIFO costing.** `InventoryLayer` + `InventoryConsumption` track
  which batch, at which cost, a sale drew from. A purchase's layer may be
  cancelled only while untouched; once any of it was sold, cancellation is
  rejected (D-036).
- **Profit is realised profit.** Zero unless the invoice is `CONFIRMED` —
  a draft or cancelled invoice must never contribute to a profit total
  (D-037). Oversold units have no cost basis and are surfaced as
  `uncosted`, never priced.
- **Every money movement traces to a person and a document.** A `Payment`
  carries `customer`/`supplier` even when unallocated (D-038); a `Cheque`
  is one-way pending → cleared/bounced/cancelled, never re-opened (D-039);
  an `Expense` is a `Payment(OUT)` with a reason, cancel-only, no
  counterparty field, explicit paying account (D-040, D-045).
- **A split payment settles the oldest open invoice first**, one
  `allocate_payment` call per invoice inside `record_payment`'s own
  transaction (D-042).
- **A sales invoice discount is invoice-level, whole Toman, shared across
  lines pro rata** by line total (largest remainder) so line profit and
  per-product reports sum to the invoice/report totals (D-032, D-048).
  Never touches stock, FIFO consumption or layer cost.
- **User FKs use `settings.AUTH_USER_MODEL`**; login is by phone (D-007).
- **The app connects to PostgreSQL as `paper_app`**, never `postgres`
  (D-018) — a bug or injected query must never reach superuser scope.
- **Hard delete only for unreferenced records**; `InventoryMovement` rows
  and confirmed/cancelled invoices are never deleted, by anyone (D-024).

## Decision index (full text: [DECISIONS.md](DECISIONS.md))
- D-001 Settings package `core/`; apps in `apps/`; shared app is `apps/shared`.
- D-002 Config and secrets from `.env` (django-environ); `.env.example` in git.
- D-003 UUID pk via BaseModel. Human document numbers are separate.
- D-004 Store UTC. Timezone and Jalali are presentation.
- D-005 Persian user-facing strings; English identifiers.
- D-006 Optional text fields: `blank=True`, never `null=True`.
- D-007 Login by phone (`^09\d{9}$`); custom `users.User`.
- ~~D-008~~ superseded by D-033 (no Business at all).
- ~~D-009~~ superseded by D-034 (no roles).
- D-010 Customer and Supplier are separate models.
- D-011 Quantity is a whole number (PositiveInteger).
- D-012 Direction comes from movement_type; quantity > 0 (CHECK).
- ~~D-013~~ superseded by D-043 (money is whole Toman).
- D-014 A confirmed invoice is immutable.
- D-015 `confirm_sale` locks Product rows as a mutex.
- ~~D-016~~ superseded by D-052 (a sale can no longer drive stock negative).
- D-017 Opening stock once, before any movement; 0 = onboarded with no row. Entered only at product creation (D-044).
- D-018 The app DB role `paper_app` owns the database, schema and tables.
- D-019 DEBUG and ALLOWED_HOSTS from env, safe defaults.
- D-020 Scope = full remake request; order in the STATE.md roadmap.
- ~~D-021~~ superseded by D-052 (shortage is rejected for everyone).
- D-022 Invoice number assigned at confirmation from a locked DocumentSequence; configurable start; purchase also gets `supplier_invoice_number`.
- D-023 A confirmed invoice is cancelled (status + reversing movements), never edited. Superuser only (D-034).
- D-024 Hard delete only for unreferenced records. Movements and confirmed/cancelled invoices are never deleted, by anyone.
- D-025 Payment status is derived from PaymentAllocation, never typed. One sanctioned exception: `InventoryLayer.quantity_remaining` (D-036).
- ~~D-026~~ superseded by D-035 (`/admin/` is superuser-only; the frontend is the user surface).
- ~~D-027~~ superseded by D-034 (no roles).
- ~~D-028~~ superseded by D-034 (no memberships).
- D-029 AuditLog target reference is target_type + target_id, not GenericForeignKey.
- D-030 Chat rhythm: read-only commands may chain; state-changing steps never chain; task or ~15 msgs.
- D-031 Verification scripts: random unique identifiers, never fixed; assert on a service's returned object or after refresh_from_db(), never a stale local reference.
- D-032 Invoice discount: fixed amount (Toman since D-043, not %), invoice-level only, sales invoices only for now; validated against subtotal in confirm_sale, not clean().
- D-033 Single business: Business/BusinessMembership and every `business` FK deleted; unique constraints global; DocumentSequence singleton per doc_type.
- D-034 No roles: `is_superuser` is the only distinction; it gates cancellation only (oversell gate removed by D-052).
- D-035 `/admin/` is superuser-only (PaperPlusAdminSite); the frontend is the user surface.
- D-036 FIFO cost layers: InventoryLayer + signed InventoryConsumption; purchase cancel blocked once any of its stock was sold.
- D-037 Profit is realised profit — zero unless confirmed; oversold units are surfaced as uncosted, never priced.
- D-038 Payment gains customer/supplier (at most one, matching direction), so unallocated money is still traceable.
- D-039 Cheque gains CANCELLED, from PENDING only, with no Payment.
- D-040 Expense lives in apps.payments, backed by a real Payment(OUT). (related_person removed by D-045.)
- ~~D-041~~ superseded by D-044 (manual adjustment removed, its schema reverted).
- D-042 Split payment allocation settles a party's oldest open invoice first (invoice_date order), one allocate_payment call per invoice inside record_payment's own transaction; new SalesInvoice.outstanding/PurchaseInvoice.outstanding properties back it.
- D-043 Money is whole Toman everywhere (storage, input, display, reports); one `toman` filter; no Rial in the UI.
- D-044 Stock changes through documents only: no manual adjustment; opening stock only at product creation; ADJUSTMENT_IN/OUT = cancellation reversals only.
- D-045 Expense has no counterparty; its paying account is an explicit choice (real account, or cash chosen on purpose); Bank Accounts gets create/edit pages.
- D-046 Sales invoice defaults to full settlement into a chosen account (`plan_full_payment`); split/cheque/credit rows are the explicit alternative mode.
- D-047 htmx swaps a 422 response (a form re-rendered with its errors) via `htmx-config` in base.html; other 4xx/5xx stay non-swapping errors.
- D-048 An invoice discount is shared across its lines pro rata by line total (largest remainder, whole Toman); line profit and per-product report rows are net of it and sum to the invoice/report totals. Derived, never stored.
- ~~D-049~~ superseded by D-051 (no deployment work in this repo).
- D-050 Visual identity: IBM Carbon-inspired (flat, square, one blue accent), changed via `app.css` tokens only.
- D-051 Deployment and the SHADOW parallel-run are out of scope and removed from the repo.
- D-052 A sale may never exceed the stock on hand, not even for a superuser; buy first.
- D-053 A purchase invoice has the same full-settlement / split payment mode as a sale.
- D-054 Date years limited to 1380-1450; deactivated parties stay visible while a balance exists; inactive products can't be traded.
- D-055 Cancelling an invoice refunds its payments (opposite Payment per allocation) and cancels its pending cheques.
- D-056 Clearing a cheque requires choosing the account (or cash on purpose).
- D-057 Expense receipts: PDF/PNG/JPG/WebP only, content must match, max 5 MB.
- D-058 Sign-in throttling: 5 failures per phone / 30 per IP → 15-minute lock (HTTP 429).
- D-059 The Suppliers list has an active/inactive/all filter and search, like Customers.
- D-060 Backup page/command (any signed-in user): one zip of data + receipts; restore only into an empty database.
- D-061 Printed sales invoice = A4 company document with seller/buyer boxes, words, stamp-and-signature boxes; issuer from `.env`.
- D-062 Visual identity = hostiran.net look (supersedes D-050).
- D-064 Invoice numbers are `year/running` (e.g. 1405/0042), per type, restarting each Jalali year.
- D-065 The module menu is a hamburger-opened drawer on all screen sizes.
- D-063 Install/update on a host: `manage.py update`, WhiteNoise, `deploy/UPDATING.md` (amends D-051).
- D-066 The DB engine is chosen by `DATABASE_URL`: PostgreSQL normally, SQLite on the `deploy` branch for a host without PostgreSQL.
- D-067 Bank accounts are `pos` (card reader) or `current`; shown in two sections.
- D-068 Cheques carry an `issuer` (who signed it) besides the bank name.
- D-069 No cash: card reader (pos) / bank transfer (current) / cheque; unpaid remainder is نسیه with a due date; a card reader never pays out.
- D-070 Sales discount may be typed as a percent; only Toman is stored.
- D-071 Receivables/Payables split into cheques and credit-on-account, each with due dates and settle actions.
- D-072 Expenses are paid by transfer, cheque or credit; `Expense.payment` is nullable.
- D-073 Fixed repeating costs (`RecurringExpense`) remind and advance; they book nothing themselves.
- D-074 Dashboard shows the coming week's payments instead of recent activity.

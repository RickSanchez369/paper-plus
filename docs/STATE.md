# STATE — paper-plus

Updated 2026-09-24, after the 3.4 math-verification simulation (3.4 itself still open). Phase 1 merged to main. Database flushed of test data 2026-09-24 (backup: backups/paper_plus_2026-09-24_013908.sql); phase 3 (real data) underway.

## Next
4.1 — Inventory overview: stock, last purchase price, selling price, approximate value, status. (3.4 stays open in the background — see note below; Phase 4 runs in parallel with SHADOW by roadmap design.)

## Built (details: PROJECT_MAP.md, git log)
- Django 6.1.1, Python 3.13.2, PostgreSQL 18, database `paper_plus`, venv `.venv`.
- Models: Business, BusinessMembership, User (phone login), Product (+ is_onboarded), Customer, Supplier, InventoryMovement, PurchaseInvoice/Item, SalesInvoice/Item.
- Services: `set_opening_stock`, `confirm_purchase`, `confirm_sale`. Selectors: `get_stock`, `get_stock_map`.
- `apps/shared/permissions.py`: `get_membership`, `has_role`, `is_owner`, `require_role`, `get_business_ids`.
- `apps/shared/admin_mixins.py`: `BusinessScopedAdminMixin` on every admin (queryset, FK choices, business list filter). Verified 20/20.
- Admin: Persian labels; no deletes except draft invoices; confirm actions call the services; ledger view-only for everyone.
- `tools/`: `backup.ps1` (restore verified), `project_map.py`, `reassign_ownership.sql`.
- Security gate cleared 2026-09-21: SECRET_KEY rotated, `paper_app` role, postgres password rotated, DEBUG/ALLOWED_HOSTS from env.
- D-027 Seller permission scope; Owner/Seller Group seeded (migration 0003) + synced from BusinessMembership.role via signal (apps/shared/signals.py).
- D-028: Business add restricted to superuser; BusinessMembership.user and UserCreateForm.business scoped to viewer's own businesses; user+membership+group created atomically from UserAdmin (verified 8/8, scripts/test_owner_user_admin.py).
- D-029/1.6: `AuditLog` model (apps/shared) + `log_event()` helper (apps/shared/audit.py), called from
  set_opening_stock, confirm_purchase, confirm_sale, inside the same atomic transaction. Admin is
  view-only (no add/change/delete). Verified 3/3, scripts/test_audit_log.py.
- 2.1: `DocumentSequence` model (apps/shared) + `get_next_document_number()` service
  (apps/shared/services.py), select_for_update inside transaction.atomic. Verified 6/6,
  scripts/test_document_sequence.py.
- 2.2: `invoice_number` auto-assigned by `confirm_purchase`/`confirm_sale` at confirmation
  (blank while draft, conditional unique constraint); `PurchaseInvoice.supplier_invoice_number`
  added; both `invoice_number` fields read-only in admin. Verified 5/5,
  scripts/test_auto_invoice_number.py.
- 2.3: `Product.default_selling_price` (BigIntegerField, default=0) + non-negative
  CheckConstraint; shown in admin (اطلاعات اصلی). Verified 3/3,
  scripts/test_default_selling_price.py.
- 2.4: `SaleItem.unit_price` now `blank=True`; `clean_fields()` fills a blank
  price from `Product.default_selling_price` before validation — a
  one-time snapshot, never re-synced if the product's default changes
  later. Verified 3/3, scripts/test_default_price_snapshot.py.
- 2.5: `Product.__str__` shows live stock via `get_stock()` (unsaved instances
  skipped via `self._state.adding`), so it appears wherever Product is
  autocompleted (SaleItemInline, PurchaseItemInline) with no admin.py
  change needed. Verified 3/3, scripts/test_product_str_shows_stock.py.
- 2.6: `confirm_sale` rejects (raises ValidationError, nothing written) when
  the sale would drive any product's stock negative and the caller is not
  an Owner/superuser (D-021); Owner/superuser still get it confirmed with
  shortages returned as a warning (D-016). Verified 4/4,
  scripts/test_shortage_policy.py.
- D-031: verification-script rules (random unique ids; assert on a
  service's returned object, not a stale local reference).
- 2.7/D-032: `SalesInvoice.discount_amount` (BigIntegerField, default 0,
  non-negative CHECK); `subtotal`/`total` properties; confirm_sale rejects
  discount_amount > subtotal. Sales only, invoice-level only. Verified 3/3,
  scripts/test_invoice_discount.py.
- 2.8: `payment_method` (choices: cash/card/bank_transfer/cheque/credit,
  default cash) + free-text `payment_note` on both PurchaseInvoice and
  SalesInvoice; editable after confirmation (label only, no ledger effect).
  Real bank account / cheque lifecycle / customer debt tracking is phase
  4.3-4.5 (see Phase 4 note), not this field. Verified 5/5,
  scripts/test_payment_method.py.
- 2.9: `InventoryMovement.unit_price` (nullable, required in practice for
  every type incl. opening/adjustment per Sina's call); `purchase_item` /
  `sale_item` FKs (nullable, exactly one set per type, enforced by
  `inventory_item_reference_matches_type` CHECK). `set_opening_stock` now
  requires `unit_price`; `confirm_purchase`/`confirm_sale` populate the
  item FK + unit_price from the invoice line. Verified 4/4,
  scripts/test_movement_item_link.py.
- 2.10: `Status.CANCELLED` on both invoices; `cancel_purchase`/`cancel_sale`
  (Owner/superuser only, D-023) reject anything but a confirmed invoice,
  write one ADJUSTMENT_OUT/ADJUSTMENT_IN movement per original line to
  fully reverse stock, then freeze the invoice -- never edited, never
  reopened; a mistake means a brand new invoice. `AuditLog.EventType`
  gained cancel_purchase/cancel_sale. Admin: "cancel_selected" action on
  both invoice admins. Verified 10/10, scripts/test_cancel_invoice.py.
- 2.11: every Rial amount in admin shown via `format_rial` (list_display and
  detail: unit_price on InventoryMovement, default_selling_price on Product,
  subtotal/total on SalesInvoice, total on PurchaseInvoice); a fixed Toman
  hint (`TOMAN_HINT`, 1 Toman = 10 Rial, D-013) added as `help_text` under
  every Rial input field (SaleItem.unit_price, PurchaseItem.unit_price,
  SalesInvoice.discount_amount, Product.default_selling_price / opening
  price). No new verification script (display-only, no service change).
- 3.2: real superuser created (technical account only, no BusinessMembership);
  real Business `paper-plus` created; a separate real Owner user created via
  `UserAdmin`'s atomic add form (D-028) with an active `owner` membership on
  `paper-plus` (Owner group synced automatically). `DocumentSequence` rows
  for `sale` and `purchase` on `paper-plus` created with `next_number`
  starting at a real business number (D-022, no zero-padding — the field is
  a plain PositiveIntegerField, decided as out of scope for now).
- 3.3: 6 real paper products (A4/A5, two brands, two sheet-count variants
  each) onboarded on `paper-plus` via `set_opening_stock` (D-017, actor =
  the real Owner user); 2 real customers, 2 real suppliers created. No test
  placeholders (Phase 3 hard gate: real data only, to keep SHADOW accurate).
- 3.4 note (Sina's call, 2026-09-24): a real 3-consecutive-day SHADOW run
  needs real elapsed days and real physical counts, which Sina does not
  have time for right now. In its place, `scripts/test_shadow_simulation.py`
  ran 3 invoice-dates back to back against a hand-kept stock figure
  (16/16 passed) — this only confirms the math (acceptance scenarios 4, 6,
  8, 9, 10, 11 + D-016/D-021/D-023), it does **not** satisfy the real HARD
  GATE. 3.4 stays `[ ]` open; the real daily comparison starts whenever
  Sina has real time for it. Moving on to Phase 4 meanwhile is intentional
  (roadmap already scopes Phase 4 as parallel to SHADOW).

## Roadmap
Ids are permanent: never renumber, only mark. `[x]` done, `[~]` in progress, `[ ]` todo. `[R n]` = section n of remake.md.

### Phase 0 — Decisions and docs
- [x] 0.1 D-020..D-026 logged
- [x] 0.2 Roadmap created
- [x] 0.3 `tools/project_map.py` generates PROJECT_MAP.md

### Phase 1 — Permissions and audit (before real data)
- [x] 1.1 `apps/shared/permissions.py`, used by services [R 1, 17B]
- [x] 1.2 Admin scoping mixin on all admins; superuser unscoped (D-026) [R 1, 2]
- [x] 1.3 Owner manages Owners and Sellers of own business; cannot touch superuser or privilege fields [R 2]
- [x] 1.4 Seller self-deactivation (deactivate, never delete) [R 2]
- [x] 1.5 `django-simple-history` on Product, User, BusinessMembership, invoices [R 16]
- [x] 1.6 `AuditLog` for service events: confirm, cancel, adjustment, opening stock, price change [R 16]

### Phase 2 — Invoice core (schema changes before real data)
- [x] 2.1 `DocumentSequence` (business, doc type, next number, configurable start), `select_for_update` (D-022) [R 4, 5]
- [x] 2.2 Auto number at confirmation for sales and purchase; `supplier_invoice_number`; number read-only [R 4, 5]
- [x] 2.3 `Product.default_selling_price` (Rial, BigInteger) [R 7, 15]
- [x] 2.4 Blank sale-item price filled from the default; stored price is a snapshot, never updated [R 7, 17C]
- [x] 2.5 Product autocomplete label shows current stock [R 6]
- [x] 2.6 Shortage policy by role in `confirm_sale` (D-021) [R 6, 17E]
- [x] 2.7 Invoice-level discount; subtotal / discount / total; shaped for a later line discount [R 9]
- [x] 2.8 `payment_method` on invoices (status comes in 4.3) [R 10]
- [x] 2.9 InventoryMovement gets a reference to its invoice item and a `unit_price` [R 13]
- [x] 2.10 `cancel_sale` / `cancel_purchase`: cancelled + reversing movements; Owner and superuser only (D-023) [R 11]
- [x] 2.11 Rial and Toman side by side everywhere; Toman hint under every price input [R 8]

### Phase 3 — Real data and SHADOW start
- [x] 3.1 Backup, then `flush` test data
- [x] 3.2 Real superuser, Business, memberships, document sequence starts
- [x] 3.3 Products with opening stock; customers; suppliers
- [ ] 3.4 Daily discrepancy log started

### Phase 4 — Financial modules (in parallel with SHADOW)
- [ ] 4.1 Inventory overview: stock, last purchase price, selling price, approximate value, status (negative / low / normal) [R 12, 14]
- [ ] 4.2 Per-product transaction history with invoice link, user, price [R 13]
- [ ] 4.3 `BankAccount` model (name, account number, business FK); `Payment` +
      `PaymentAllocation` referencing it for bank-transfer payments; derived
      payment status (D-025) [R 10]
- [ ] 4.4 `Cheque` lifecycle: pending / cleared / bounced, linked to a Payment [R 3, 10]
- [ ] 4.5 Customer account: invoices, payments, cheques, running balance
      (credit/نسیه derived from PaymentAllocation, never a stored debt field), statement [R 3]
- [ ] 4.6 Sales and purchase returns as separate documents with own movement types [R 13]
- [ ] 4.7 Purchase and selling price management with history [R 14, 15]

### Phase 4 note
Full money tracking (bank accounts, cheque lifecycle, customer debt/نسیه) is
scoped here, not in 2.8 — 2.8 only adds a `payment_method` label + free-text
note on invoices. Building the real ledger before Payment/PaymentAllocation
exist would create a second, conflicting source of truth for debt (violates
D-025). Deferred deliberately, not forgotten (Sina, 2026-09-23).

### Phase 5 — Acceptance
- [ ] 5.1 One verification script per scenario in `scripts/` [R 19]
- [ ] 5.2 All 15 scenarios pass
- [ ] 5.3 Full admin review: labels, permissions, formatting [R 18]

## Acceptance scenarios [R 19]
1. Superuser: full CRUD everywhere, within D-024
2. Owner manages Sellers, cannot bypass superuser limits
3. Seller deactivates own account
4. Sales invoice created without typing a number
5. Product selection shows current stock
6. Default selling price fills the invoice
7. Owner changes an invoice price; product price unchanged
8. Discount applied; totals correct
9. Payment method and status recorded and visible
10. Wrong invoice cancelled by Owner; history kept
11. Stock correct after purchase and sale
12. Per-product transaction history visible
13. Purchase and selling price manageable
14. Every amount shown as `X,XXX,XXX ریال | XXX,XXX تومان`
15. Concurrent sales: no uncontrolled overselling (D-015, D-021)

## Tracking
- Daily: tasks closed.
- From phase 3, daily: discrepancies (exit SHADOW = 3 consecutive days at 0).
- Phase 5: scenarios passed (target 15/15).
- Exit condition: if phases 1-2 are not done by day 14 (2026-10-05), move the remaining phase 2 tasks to phase 4 and start phase 3.

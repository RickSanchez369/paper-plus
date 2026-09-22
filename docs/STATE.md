# STATE — paper-plus

Updated 2026-09-22, after ROADMAP 2.3. Phase 1 merged to main. Database holds test data only until phase 3.

## Next
2.4 — Blank sale-item price filled from the default; stored price is a snapshot, never updated [R 7, 17C].

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
- [ ] 2.3 `Product.default_selling_price` (Rial, BigInteger) [R 7, 15]
- [ ] 2.4 Blank sale-item price filled from the default; stored price is a snapshot, never updated [R 7, 17C]
- [ ] 2.5 Product autocomplete label shows current stock [R 6]
- [ ] 2.6 Shortage policy by role in `confirm_sale` (D-021) [R 6, 17E]
- [ ] 2.7 Invoice-level discount; subtotal / discount / total; shaped for a later line discount [R 9]
- [ ] 2.8 `payment_method` on invoices (status comes in 4.3) [R 10]
- [ ] 2.9 InventoryMovement gets a reference to its invoice item and a `unit_price` [R 13]
- [ ] 2.10 `cancel_sale` / `cancel_purchase`: cancelled + reversing movements; Owner and superuser only (D-023) [R 11]
- [ ] 2.11 Rial and Toman side by side everywhere; Toman hint under every price input [R 8]

### Phase 3 — Real data and SHADOW start
- [ ] 3.1 Backup, then `flush` test data
- [ ] 3.2 Real superuser, Business, memberships, document sequence starts
- [ ] 3.3 Products with opening stock; customers; suppliers
- [ ] 3.4 Daily discrepancy log started

### Phase 4 — Financial modules (in parallel with SHADOW)
- [ ] 4.1 Inventory overview: stock, last purchase price, selling price, approximate value, status (negative / low / normal) [R 12, 14]
- [ ] 4.2 Per-product transaction history with invoice link, user, price [R 13]
- [ ] 4.3 `Payment` + `PaymentAllocation`; derived payment status (D-025) [R 10]
- [ ] 4.4 `Cheque` lifecycle: pending / cleared / bounced [R 3, 10]
- [ ] 4.5 Customer account: invoices, payments, cheques, running balance, statement [R 3]
- [ ] 4.6 Sales and purchase returns as separate documents with own movement types [R 13]
- [ ] 4.7 Purchase and selling price management with history [R 14, 15]

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

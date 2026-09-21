# Roadmap

Source of truth for task order. STATE.md says where we are; this file says
what comes next. Task ids are permanent: never renumber, only mark done.
`[R n]` = section n of the remake request (remake.md).
Decisions referenced: DECISIONS.md D-020 to D-026.

Status: [ ] todo  [~] in progress  [x] done

---

## Phase 0 — Decisions and docs
- [x] 0.1 D-020..D-026 logged in DECISIONS.md
- [x] 0.2 ROADMAP.md created; STATE.md and CHAT_PROMPT.md point to it
- [x] 0.3 `tools/project_map.py` generates PROJECT_MAP.md from the code

## Phase 1 — Permissions and audit (before any real data)
- [x] 1.1 `apps/shared/permissions.py`: get membership, `is_owner`,
      `require_role`; used by services, not only by admin        [R 1, 17B]
- [ ] 1.2 Admin scoping mixin: queryset and FK choices limited to the
      user's businesses; superuser unscoped; applied to all admins (D-026) [R 1, 2]
- [ ] 1.3 Owner manages Owners and Sellers of own business; cannot touch
      superuser or privilege fields                                [R 2]
- [ ] 1.4 Seller self-deactivation (deactivate, never delete)      [R 2]
- [ ] 1.5 `django-simple-history` on Product, User, BusinessMembership,
      invoices (before/after, who, when)                           [R 16]
- [ ] 1.6 `AuditLog` for service events: confirm, cancel, adjustment,
      opening stock, price change                                  [R 16]

## Phase 2 — Invoice core (schema changes before real data)
- [ ] 2.1 `DocumentSequence` (business, doc type, next number, configurable
      start), locked with select_for_update (D-022)                [R 4, 5]
- [ ] 2.2 Auto invoice number at confirmation for sales and purchase;
      `supplier_invoice_number` on purchase; number read-only      [R 4, 5]
- [ ] 2.3 `Product.default_selling_price` (Rial, BigInteger)        [R 7, 15]
- [ ] 2.4 Blank sale-item price is filled from the default; stored price
      is a snapshot, never updated afterwards                      [R 7, 17C]
- [ ] 2.5 Product autocomplete label shows current stock           [R 6]
- [ ] 2.6 Shortage policy by role in `confirm_sale` (D-021)        [R 6, 17E]
- [ ] 2.7 Invoice-level discount; subtotal / discount / final total;
      model shaped so a line-level discount can be added later     [R 9]
- [ ] 2.8 `payment_method` field on invoices (status comes in 4.3) [R 10]
- [ ] 2.9 InventoryMovement gets a reference to its invoice item and a
      `unit_price`                                                 [R 13]
- [ ] 2.10 `cancel_sale` / `cancel_purchase`: status cancelled + reversing
      movements; Owner and superuser only (D-023)                  [R 11]
- [ ] 2.11 Rial and Toman shown side by side everywhere; Toman hint under
      every price input                                            [R 8]

## Phase 3 — Real data and SHADOW start
- [ ] 3.1 Backup, then `flush` test data
- [ ] 3.2 Real superuser, Business, memberships, document sequence starts
- [ ] 3.3 Products with opening stock; customers; suppliers
- [ ] 3.4 Daily discrepancy log started (every mismatch = a bug, never a hand fix)

## Phase 4 — Financial modules (built in parallel with SHADOW)
- [ ] 4.1 Inventory overview: stock, last purchase price, selling price,
      approximate value, status (negative / low / normal)          [R 12, 14]
- [ ] 4.2 Per-product transaction history with invoice link, user, price [R 13]
- [ ] 4.3 `Payment` + `PaymentAllocation`; payment status derived (D-025) [R 10]
- [ ] 4.4 `Cheque` with lifecycle: pending / cleared / bounced     [R 3, 10]
- [ ] 4.5 Customer account: invoices, payments, cheques, running
      balance, statement                                          [R 3]
- [ ] 4.6 Sales and purchase returns as separate documents with their
      own movement types                                           [R 13]
- [ ] 4.7 Purchase and selling price management with history      [R 14, 15]

## Phase 5 — Acceptance
- [ ] 5.1 One verification script per scenario in `scripts/`       [R 19]
- [ ] 5.2 All 15 scenarios pass
- [ ] 5.3 Full admin review (labels, permissions, formatting)     [R 18 step 20]

---

## Acceptance scenarios [R 19]
1. Superuser: full CRUD everywhere, within D-024
2. Owner manages Sellers, cannot bypass superuser limits
3. Seller deactivates own account
4. Sales invoice created without typing a number
5. Product selection shows current stock
6. Default selling price fills the invoice automatically
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
- KPI, daily: tasks closed per day
- KPI, daily from phase 3: discrepancies per day (exit SHADOW = 3 days at 0)
- KPI, phase 5: scenarios passed (target 15/15)
- Exit condition: if phases 1 and 2 are not done by day 14, move the
  remaining phase 2 tasks to phase 4 and start phase 3.
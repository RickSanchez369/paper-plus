# STATE — paper-plus

Updated 2026-09-26, after the **pre-Phase-D correction batch** (D-043..D-046: Toman everywhere, bank-account/supplier management pages, expense paying account, stock through documents only, selling-price updates, new product mid-purchase, sales discount placement + full-settlement default). Before that: Dashboard (Phase C module 10) of the rebuild (REDESIGN_VISION) -- **Phase C is complete, all 11 modules built.** Earlier: User Activity (module 9), Financial Reports (module 8), Customers (module 7), Expenses (module 6), Bank Accounts (module 5), Receivables/Payables/Cheques (module 4), Inventory (module 3), Purchasing + Suppliers (module 2), ROADMAP 4.4 + the 4.3b invoice-side payment-entry extension. Phase 1 merged to main. Current database state is described under "Rebuild in progress" below.

## Rebuild in progress — branch `explore/vision-rethink`

`docs/REDESIGN_VISION.md` + `docs/MASTER_PROMPT.md` drive this work and
override the roadmap below wherever they disagree. The ROADMAP entries that
survive are being rebuilt as pages, not as Admin screens.

**The old URGENT item (the real Owner account having no admin permissions
after the 3.1 flush) is closed, not fixed:** roles are gone entirely
(D-034), so there is no Owner/Seller Group left to seed. `/admin/` is now
superuser-only (D-035) and both real accounts are superusers.

The database was flushed again 2026-09-25 (Sina's call, backup:
`backups/paper_plus_2026-09-24_232818.sql`) because dropping the `business`
column would otherwise have merged the QA tenant's rows into the real ones.
`manage.py flush` could not do it — see `tools/flush_all.py`. Real data
(6 products + opening stock, 2 customers, 2 suppliers, 1 bank account) has
to be re-entered; the two `DocumentSequence` rows were recreated at 9956001.
Since D-044 the opening stock is entered on the Inventory new-product page
itself ("موجودی فعلی" + unit cost), at creation -- there is no later page
for it -- and bank accounts/suppliers on their own module pages (D-045).

## Next
Pre-Phase-D correction batch is done, and so are C.fix-1 (D-047) and
C.fix-2 (see Built). C.fix-3 (per-product profit vs. invoice discount)
still waits for Sina's decision (PENDING below).

**Phase D — visual identity** (MASTER_PROMPT §3's own build order: Phase
C's 11 modules, all now built, then Phase D). REDESIGN_VISION §5: pick
(or blend) from the 4 candidate systems in `docs/design/` (Stripe,
Linear, IBM, PostHog) or ask Sina to pick if it's not obvious now that
real pages exist to compare against. Use the `design-taste-frontend`
skill while building/restyling pages, and `redesign-existing-projects`
for pages already built in Phase C. Apply consistently app-wide, not a
different feel per module (MASTER_PROMPT's own warning).

Not yet built, carried forward from Phase C's own scope notes (raise
these with Sina before touching, per RULES.md, since they weren't part
of any module's confirmed spec):
- 3.4's real SHADOW run (still open, see its own note above) -- now that
  every module exists, this is worth revisiting with Sina.
- ROADMAP 4.6 (returns) stays explicitly out of scope (Sina, 2026-09-24).

Purchasing + Suppliers (Phase C module 2) is done: list, one-shot
new-purchase form, detail, print, cancel, Suppliers sub-section (list +
detail) — see Built. Sales (Phase C module 1) is done: list, one-shot
new-sale form, detail, print, cancel. Phase B is done: shell + login +
htmx (`2ba2149`) and the three shared components (`312163a` + `69bd923`).

Sales (Phase C module 1) is done: list, one-shot new-sale form, detail,
print, cancel — see Built. Phase B is done: shell + login + htmx
(`2ba2149`, 24/24 scripts + a browser pass) and the three shared
components (`312163a` + `69bd923`).

Phase A is done and verified: 22 scripts, 256 checks. Commits `9d985e5`
(drop multi-tenancy and roles), `19d25b3` (FIFO cost layers), `01ec98e`
(payment party, cheque cancellation, expenses).

### Carried forward, not yet built
- **3.4 real SHADOW** never closed; it now depends on Phase C pages existing
  to be worth running at all.
- **ROADMAP 4.6 (returns)** is explicitly out of scope for this round
  (Sina, 2026-09-24). Do not design around it.

## Built (details: PROJECT_MAP.md, git log)
- Django 6.1.1, Python 3.13.2, PostgreSQL 18, database `paper_plus`, venv `.venv`.
- Models: User (phone login), Product (+ is_onboarded), Customer, Supplier, InventoryMovement, InventoryLayer, InventoryConsumption, PurchaseInvoice/Item, SalesInvoice/Item, BankAccount, Payment, PaymentAllocation, Cheque, Expense, AuditLog, DocumentSequence. (Business/BusinessMembership deleted, D-033.)
- Services: `set_opening_stock`, `consume_fifo`, `restore_consumptions`, `cancel_layer`, `confirm_purchase`/`cancel_purchase`, `confirm_sale`/`cancel_sale`, `record_payment`, `allocate_payment`, `record_cheque`, `clear_cheque`, `bounce_cheque`, `cancel_cheque`, `record_expense`, `cancel_expense`, `get_next_document_number`. Selectors: `get_stock`, `get_stock_map`, `get_active_layers`, `get_current_cost_map`, `get_last_known_cost_map`, `get_inventory_value_map`, `get_total_inventory_value`, `get_layer_balance`, `get_bank_account_balance`.
- `apps/shared/permissions.py`: `is_privileged`, `require_privileged` (the per-business role helpers are deleted, D-034).
- `apps/shared/admin_site.py`: `PaperPlusAdminSite`, superuser-only (D-035). `admin_mixins.py` deleted with multi-tenancy.
- Admin: Persian labels; no deletes except draft invoices; confirm actions call the services; ledger view-only for everyone.
- `tools/`: `backup.ps1` (restore verified), `project_map.py`, `reassign_ownership.sql`, `flush_all.py`.
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
- 4.1: `apps/inventory/selectors.get_cost_map` (latest unit cost per product,
  from its most recent opening/purchase movement). `ProductAdmin` gained
  two columns -- "آخرین قیمت خرید" and "ارزش تقریبی موجودی" (stock × that
  cost; valuation is cost-based, not selling price, per standard inventory
  accounting -- Sina's call, 2026-09-24) -- plus a total-inventory-value
  banner above the change list (first admin template override in the repo:
  `apps/products/templates/admin/products/product/change_list.html`). No
  low-stock threshold/status field -- Sina scoped 4.1 down to stock + cost
  + value only; a separate date-range profit/loss report he described
  (sales, costs, expenses, USD tracking) is a new feature outside every
  existing roadmap id and needs its own decision (see PENDING note below),
  not built here.
- 4.2: `InventoryMovementAdmin` gained an "فاکتور مرتبط" (invoice) column --
  a link to the movement's source invoice via `purchase_item.invoice` /
  `sale_item.invoice` (opening/adjustment rows show "-", they carry
  neither FK). `ProductAdmin` gained a "تاریخچه تراکنش‌ها" link per row into
  `InventoryMovementAdmin`'s change list pre-filtered to that product
  (`?product__id__exact=<pk>`) -- the user (`created_by`) and price
  (`unit_price_display`) columns already existed there since 2.9/2.11.
  Verified 5/5, scripts/test_transaction_history.py.
- 4.3: new app `apps.payments` -- `BankAccount` (name, account number,
  business); `Payment` (D-012-style: `amount` always positive, `direction`
  in/out carries the sign; `bank_account` nullable = cash); `PaymentAllocation`
  ties part of a Payment to exactly one of `SalesInvoice`/`PurchaseInvoice`
  (explicit FK pair + CHECK, mirroring InventoryMovement.purchase_item/
  sale_item from 2.9 -- not a GenericForeignKey). Covers **both** sides of
  the ledger (money in from customers, money out to suppliers) -- Sina's
  call, 2026-09-24: "رد پول" tracking is the whole point of the project.
  Services `record_payment`/`allocate_payment` (apps/payments/services.py)
  take an unsaved instance, validate (direction matches invoice side, same
  business, invoice confirmed, amount within both the payment's and the
  invoice's remaining balance) and save it, locking the payment + invoice
  rows first (D-015-style). `SalesInvoice`/`PurchaseInvoice` gained
  `paid_amount`/`payment_status` (unpaid/partial/paid) as properties,
  never a stored field (D-025) -- shown read-only on both invoice admins.
  `BankAccountAdmin` shows each account's net balance (IN minus OUT).
  Payment/PaymentAllocation admins are add-only (no change/delete),
  same append-only philosophy as InventoryMovement; allocation happens on
  its own admin page (pick payment + invoice), not an inline on either --
  simpler to route through the service, at the cost of one extra click.
  AuditLog.EventType gained record_payment/allocate_payment.
  Bugfix caught by the verification script before this closed: both
  services checked `instance.pk is not None` to detect "already saved",
  but `BaseModel.id` defaults to `uuid4()` at construction time, so `pk`
  is never `None` even for a brand-new instance -- fixed to check
  `instance._state.adding` instead (the pattern already used elsewhere in
  admin.py, e.g. `stock_display`). Verified 15/15, scripts/test_payments.py.
- 4.3 also caught (harmless, unrelated to 4.3 itself): the 2.10 `cancelled`
  status choice on both invoices was never migrated -- it existed in
  models.py but the migration state still only had draft/confirmed. No
  functional impact (Django does not enforce `choices` in the database),
  caught and closed by the same `makemigrations` run
  (purchasing/0005, sales/0007).
- 4.4: `Cheque` (apps/payments/models.py) -- pending/cleared/bounced.
  Sina's call, 2026-09-24: a **pending** cheque is not yet money -- no
  `Payment` exists for it and it does not count toward any invoice's
  `payment_status`. `clear_cheque` creates the `Payment` and (if the
  cheque came from an invoice, see 4.3b) auto-allocates it; `bounce_cheque`
  closes it with no `Payment` at all, ever. Both are one-way. `ChequeAdmin`
  add-only (via `record_cheque`), with `mark_cleared`/`mark_bounced`
  bulk actions (never a field edit) -- same append-only philosophy as
  InventoryMovement/Payment. Direction/party consistency is a friendly
  Persian form error (`ChequeForm.clean()`), not Django's generic
  "Constraint ... is violated" (Django 4.1+ validates CheckConstraints in
  `full_clean()`, before `save_model()` ever runs -- caught live when Sina
  hit exactly that raw error while testing). Verified 15/15,
  scripts/test_cheque_lifecycle.py.
- 4.3b (Sina's request after seeing 4.3/4.4 live, 2026-09-24): split
  payment entry directly on the invoice. `SalesPaymentEntry` /
  `PurchasePaymentEntry` (one per invoice app, mirrors SaleItem/
  PurchaseItem -- not a shared payments-app model, since each belongs to
  exactly one invoice type) let Sina draft rows like "2M cheque, 1M cash"
  on a draft invoice; whatever is left under the invoice total is simply
  the نسیه/credit portion, no row needed for it.
  `confirm_sale`/`confirm_purchase` turn each row into a real `Payment`
  (auto-allocated to the same invoice immediately) or a pending `Cheque`
  pre-linked to that invoice (`Cheque.sales_invoice`/`purchase_invoice`,
  new nullable pair + CHECK, mirrors `PaymentAllocation`) -- so
  `clear_cheque` later allocates it automatically too, no manual second
  visit to the Cheques page. Rows may not sum above the invoice total
  (`ValidationError`, checked in the same all-or-nothing transaction).
  `ChequeAdmin` shows which invoice a cheque came from (blank = a general,
  unattached cheque, still supported for cash cheques not tied to any
  invoice). Bugfix caught by this work before it closed: appending
  `SalesPaymentEntry` after `SaleItem` in apps/sales/models.py (and the
  purchasing mirror) accidentally swallowed `SaleItem.__str__`/
  `line_total` into the new class, because the edit's anchor text ended
  one method short of the file's actual tail -- Python attached the
  following indented methods to the nearer, newly-opened class instead of
  `SaleItem`. Fixed by moving them back; `manage.py check` did not catch
  it (not a schema/import problem), the verification script did.
  Verified 13/13, scripts/test_invoice_payment_entries.py.
- 4.3b round 2 (Sina's live-testing feedback, 2026-09-24: "هیچ‌چیز درست
  کار نمی‌کنه"): four real UX problems, each verified by actually driving
  the admin in a browser (throwaway QA business "ZZZ-TEST-QA (delete me)"
  + a QA user with direct permissions, isolated from real data -- offer to
  delete it, not done yet) rather than trusting the backend scripts alone.
  1. Two competing payment UIs on the invoice -- removed `payment_method`/
     `payment_note` from SalesInvoiceAdmin/PurchaseInvoiceAdmin's
     `fieldsets` and `list_display` (fields stay on the model, unused).
     The payment-entry rows are now the one place to pick method + amount.
  2. Picking a product in a sale-item row now fills its price live, via a
     new JSON endpoint (`ProductAdmin.default_price_view`, business-scoped
     through `get_queryset`) and `apps/sales/static/sales/js/
     sale_item_autoprice.js`.
  3. Adding a new payment-entry row now pre-fills its amount with the
     invoice's remaining total, via `apps/shared/static/shared/js/
     payment_entry_autofill.js` (shared between sales and purchasing).
  4. A cheque entered from an invoice can be left incomplete (no cheque
     number/due date yet) and finished later on the Cheques page:
     `Cheque.cheque_number`/`due_date` are now optional at the DB level,
     `ChequeForm` no longer requires them, and `ChequeAdmin` allows editing
     (including re-pointing `sales_invoice`/`purchase_invoice`) as long as
     `status == PENDING` -- it locks only once cleared/bounced, mirroring
     invoice draft/confirmed immutability (D-014 style).
  Two real bugs surfaced only by browser testing, invisible to `manage.py
  check` or the shell scripts: (a) both new JS files ran *before*
  `admin/js/jquery.init.js` (Media ordering put them first), so
  `django.jQuery` did not exist yet at parse time -- fixed by deferring
  each script's setup to `DOMContentLoaded`. (b) Django 6.1 dispatches
  `formset:added` as a plain `CustomEvent` on the new row itself
  (`detail.formsetName`), not the older jQuery-trigger convention this was
  first written against (`function(event, $row, formsetName)`) -- fixed to
  read `event.target`/`event.detail.formsetName` directly, dropping the
  jQuery dependency for that file entirely. Full end-to-end flow confirmed
  live: incomplete cheque entered on a draft invoice -> invoice confirmed
  -> pending Cheque auto-created and linked -> completed with a cheque
  number/due date on the Cheques page -> cleared -> automatically
  allocated back to the same invoice, payment_status unpaid -> partial,
  with zero manual allocation step.
- 4.3b round 2 also surfaced (unrelated to 4.3b itself, found only because
  QA logged in as a real role account instead of superuser) the Owner
  permissions bug -- see the URGENT note at the top of this file.
- Phase B shared components (REDESIGN_VISION §8, MASTER_PROMPT 3): date-range
  picker (Jalali -- `apps/shared/forms.py` DateRangeForm + `dates.py` +
  `jalali_picker.js` + `DatePickerMonthView`), "record payment" form
  (`apps/payments/forms.py` RecordPaymentForm), inline new-customer/
  new-supplier mini-forms (`apps/partners/forms.py`). Built in `312163a`
  (WIP). The date-range picker is wired into Dashboard, Financial Reports
  and User Activity and was verified by actually clicking it, not just
  scripts -- `69bd923` fixed a real bug that only showed up there: an
  unconditional hidden `<input name="preset" value="custom">` in
  `_date_range.html` was submitted alongside whichever preset button's own
  `name="preset"` the user clicked, so Django's `QueryDict.get()` always
  resolved to "custom" and "امروز"/"این هفته"/"این ماه" silently did
  nothing. Fixed by moving `name="preset" value="custom"` onto the
  "اعمال" button itself, same pattern the other three buttons already
  used. Record-payment and quick-party forms are verified at the form
  level (`scripts/test_shared_components.py`, 37/37) but intentionally not
  wired into any page yet -- their consumers (Receivables, Payables,
  Customer/Supplier detail) are Phase C.
- Sales (REDESIGN_VISION 4.1, Phase C module 1): list (cards -- today,
  this month, open partial/credit count, month profit, all excluding
  cancelled per vision doc gap #4 -- table, free-text search, structured
  filters incl. the shared date-range picker, pagination-ready, print
  link per row), one-shot new-sale form (`apps/sales/forms.py`,
  `apps/sales/views.SalesCreateView`: invoice + item formset + payment-
  entry formset built and saved as a draft inside one
  `transaction.atomic()`, then `confirm_sale` in the same transaction --
  a rejection leaves nothing saved), detail (FIFO cost + profit per line
  and for the invoice, payment/cheque history, cancel via the existing
  `cancel_sale`, superuser-only), print (plain browser-printable page,
  no PDF per RULES.md scope). `apps/sales/static/sales/js/sale_form.js`
  is written fresh for htmx + vanilla JS (REDESIGN_VISION 2 item 8), not
  ported from admin's jQuery/select2 version: live product search with
  stock in the label, add/remove rows, live subtotal/discount/total,
  remaining/نسیه autofill on a new payment row. The shared "+ مشتری
  جدید" component (Phase B) gained its first real consumer here plus a
  `QuickCustomerCreateView` (`apps/partners/views.py`) that returns an
  out-of-band swap of `#id_customer`.
  Three real bugs found only by actually submitting the form, invisible
  to `manage.py check` or a script with hand-built clean data:
  1. `SaleInvoiceForm.discount_amount` left blank cleaned to `None`, and
     `BigIntegerField` has no ORM-level default substitution on an
     explicit `None` (`Model.save()` only applies `default=0` when a
     field is never set at all) -- a raw NOT NULL DB error on the
     single most common case (no discount). Fixed with a
     `clean_discount_amount()` returning `0` instead of `None`.
  2. The "+ مشتری جدید" disclosure is itself a `<form>`
     (`partners/_quick_party_form.html`, its own htmx POST) and was
     rendered inside `<form id="sale-form">` -- HTML forbids a nested
     `<form>`, so the browser silently truncated the outer form right
     there, and every field after it (every item row, every payment
     row, the submit button) stopped belonging to any form at all;
     submitting sent only the customer field. Same root cause as
     `69bd923`'s date-range bug, different shape. Fixed by moving the
     customer field and its disclosure outside `<form id="sale-form">`,
     with `form="sale-form"` on the customer widget's attrs reattaching
     it (HTML5's own answer to "this input belongs to a form it isn't
     nested inside").
  3. `SalesPaymentEntryForm.method` (required, no model-level `default`)
     got an English "- Select an option -" blank choice Django inserts
     automatically for any required choices-field lacking a default or
     initial (`Field.get_choices()`) -- fixed by declaring it explicitly
     with `initial=CASH`, same fix already applied to the `product`
     filter on the list page for the identical reason.
  Also found and fixed in `_form_errors.html`'s reuse: passing a
  **formset** to it silently showed nothing, because formsets expose
  `non_form_errors()` (a method), not `non_field_errors` (a Form
  attribute) -- Django templates resolve a missing attribute to empty
  rather than erroring, so a real formset-level error (e.g. this
  module's own duplicate-product-row check) would have been invisible.
  `new.html` renders `item_formset.non_form_errors`/
  `payment_formset.non_form_errors` directly instead.
  Verified end to end in an actual browser, not just scripts: created a
  4-unit cash sale against disposable QA fixtures (product with opening
  stock via `set_opening_stock`, customer, bank account, non-superuser
  then superuser QA user) -- confirmed invoice number, item FIFO cost
  and profit, payment allocation and status, list cards and table row,
  print page, and cancel (stock restored, cards correctly drop back to
  excluding the now-cancelled invoice, table still shows it with a
  cancelled status). All QA fixtures deleted afterward in dependency
  order and `DocumentSequence` (`sale`) reset to 9956001 so Sina's first
  real invoice still starts there. `scripts/test_sales_invoice.py` added
  after, 28/28 -- drives the real `/sales/` URLs with Django's test
  Client (same pattern as `test_frontend_shell.py`), not the forms/
  services directly, because all three bugs above were invisible to a
  script built from already-clean data. Covers: blank discount, an
  itemless submission, a duplicate-product row, payment rows over the
  total (all rejected with the Persian message on the page, nothing
  saved), FIFO cost/profit/payment-status on a real confirm, cancel's
  superuser gate both ways, cards excluding a cancelled invoice while
  the table still lists it, product search, and the `method` field's
  blank-choice regression. `test_frontend_shell.py` (50/50),
  `test_shared_components.py` (37/37) and `test_jalali_dates.py`
  (33/33) still pass.
- Purchasing + Suppliers (REDESIGN_VISION 4.2, Phase C module 2):
  symmetric to Sales, with the differences the vision doc calls out --
  no discount concept anywhere (the model never had one), no profit
  column on the detail page (profit is sales-only), `unit_price` always
  manually typed (a purchase price is what this purchase actually cost,
  never a default), and cancel is stricter: `cancel_purchase` blocks
  once any of the resulting `InventoryLayer` has been sold from, on top
  of the same superuser + confirmed-only gate Sales has. Suppliers
  sub-section (list: name, phone, total purchased, outstanding payable;
  detail: purchase history, cheques issued, running balance) reads
  outstanding payable from a new `apps.payments.selectors.
  get_supplier_outstanding` -- one selector so the Payables page (4.4)
  can never disagree with this one later (D-025).
  New here: `apps/products/forms.QuickProductForm` ("+ کالای جدید",
  vision doc §13) -- `default_selling_price` stays required even in a
  *purchase* flow (gap #6: silently accepting the field's 0 default
  would let the product go out the door as an accidental free sale
  later). No single target element to out-of-band swap the way the
  customer/supplier quick-adds do (item rows are a dynamic JS list, not
  one `<select>`) -- picking up the new product is just typing its name
  in any row's search box, which works immediately once it is saved.
  Reused wholesale from Sales, no changes needed: `partners/
  _quick_party_form.html` (generic enough for a product too), the
  add/remove-row and remaining-amount-autofill JS pattern (new file,
  `apps/purchasing/static/purchasing/js/purchase_form.js`, adapted only
  to set the price field's *placeholder* from the last known cost
  instead of auto-filling a value), the duplicate-product formset guard,
  and every lesson already paid for once on Sales (STATE.md 6d4521a):
  the quick-create disclosures render outside `<form id="purchase-form">`
  from the start (this module needed *two* of them, supplier and
  product, both outside), `method` is declared explicitly with
  `initial=CASH` so it never gets Django's English blank choice, and
  `amount`/`unit_price`/`quantity` are all declared with explicit
  `min_value` since none of their model fields carry one. Because of
  that, the real-submission testing this time turned up nothing new --
  `scripts/test_purchase_invoice.py` (new, mirrors `test_sales_invoice.py`,
  drives the real `/purchasing/` URLs the same way) passed 33/33 on its
  first run, and a full browser pass (new supplier and product created
  inline, purchase confirmed, print, cancel, Suppliers list/detail, all
  against disposable QA fixtures cleaned up afterward with
  `DocumentSequence(purchase)` reset to 9956001) found nothing either.
  `test_frontend_shell.py` (50/50), `test_shared_components.py` (37/37),
  `test_jalali_dates.py` (33/33) and `test_sales_invoice.py` (28/28)
  still pass.
- Inventory (REDESIGN_VISION 4.3, Phase C module 3, D-041): list (cards --
  total value from active layers at their own cost, item count,
  negative-stock warning, a USD-rate placeholder card since the source is
  explicitly undecided per the vision doc; table -- stock, current purchase
  cost with a "آخرین قیمت شناخته‌شده" fallback once a product sells out,
  selling price, this item's value, % share of total), three action
  pages instead of modals (new product, opening stock, manual adjustment --
  deliberate: these are rare actions a wrong submit can't just be edited
  away from, so each gets a full page with a clear result rather than a
  disclosure easy to submit by accident), and a per-product detail page
  (active layers, the ROADMAP-4.2 movement history extended with a
  "لایه(های) مرتبط" column and an invoice link, and a "تاریخچهٔ قیمت"
  collapsible section reusing the existing `HistoricalProduct`, gap #7 --
  no dedicated view needed).
  New service `apps.inventory.services.record_adjustment` (D-041): the
  schema work it needed -- generalizing `InventoryConsumption` beyond
  sale-only (nullable `sale_item`, new `movement` FK, CHECK exactly one),
  a new `InventoryLayer.Source.ADJUSTMENT`, and a nullable
  `InventoryMovement.layer` FK (backfilled for every pre-existing OPENING
  row via a data migration) -- is the full decision text in D-041, not
  repeated here. `set_opening_stock` was updated in the same change to set
  the new `layer` FK on future opening entries (order flipped: the layer is
  now created before the movement that links to it).
  Two things surfaced only by driving the actual pages in a browser, same
  lesson as every prior module (`feedback-verify-admin-js-in-browser`):
  1. A `{{ x|default:y }}` template filter still evaluates `y` even when
     `x` needs no fallback, and Django does **not** silently swallow a
     failed lookup inside a filter *argument* the way it does for the
     top-level variable being rendered -- `record.history_user.phone` as
     a `default` argument raised `VariableDoesNotExist` (a real 500) the
     moment `history_user` was `None`, on the price-history tab. Fixed by
     wrapping it in `{% if record.history_user %}`.
  2. `set_opening_stock` itself was never updated to set the new `layer`
     FK on the movements it creates (only the backfill migration covered
     rows that already existed) -- caught by opening stock for a fresh QA
     product and finding the transaction-history table's new layer column
     blank where it shouldn't have been.
  `scripts/test_inventory_adjustment.py` (new, 23/23) covers
  `record_adjustment` directly: both directions, the FIFO draw order, the
  weighted-average cost it fills in, rejection when the ledger can't cover
  an out-adjustment (writes nothing), a missing reason note either
  direction, and the audit-log row. `scripts/test_fifo_layers.py` had two
  assertions that assumed an empty DB (`InventoryLayer.objects.get(source=
  "opening_stock")` unfiltered by product, and an exact `get_total_
  inventory_value()` equality) -- both latent since real onboarded
  products (3.3) started existing, surfaced only now that the script was
  actually re-run; fixed to scope by product and to assert a delta against
  a captured baseline (53/53, up from 52/53 once fixed). Full browser QA:
  QA fixtures (`scripts/qa_inventory_setup.py` / `_teardown.py`, dedicated
  QA user + two products under SKUs `QA-INV-*`) walked through opening
  stock, both adjustment directions including the over-the-ledger rejection
  message, and the product detail page's layer/invoice links and price
  history, then torn down (the QA user itself is deactivated rather than
  deleted -- `AuditLog.actor` is `PROTECT`, D-029, so its own audit trail
  outlives it, same as any other hard-deleted record's, D-024).
- Receivables / Payables / Cheques (REDESIGN_VISION 4.4, Phase C module 4,
  D-042): one conceptual module, three real views replacing the
  `ModulePlaceholderView`s in `apps/payments/urls.py`. Receivables/Payables
  (`apps/payments/views.py`, new file): customers/suppliers with an open
  balance only (zero-balance parties simply absent, not shown "settled"),
  each row carrying its own `RecordPaymentForm` inline behind a `<details>`
  disclosure -- the party is already fixed by the row, matching the
  quick-party-disclosure pattern from Purchasing/Sales. Submitting records
  the `Payment` and allocates it across whichever open invoices were
  checked, oldest-invoice-first (D-042) -- `SalesInvoice.outstanding`/
  `PurchaseInvoice.outstanding` are new properties added alongside the
  existing `paid_amount`/`payment_status` (D-025) so this ordering logic,
  the two list pages, and the payment form's own over-allocation check all
  read the same number. Cheques: list with status/direction/due-date-range
  filters (`ChequeFilterForm`); detail page with the full lifecycle trace
  and, while still pending, three one-way actions (clear/bounce/cancel,
  each POST-only, guarded entirely by the existing services) plus a
  "تکمیل مشخصات" form (`ChequeCompletionForm`) for a cheque entered
  incomplete from an invoice's payment rows (4.3b) -- a plain `form.save()`
  on the descriptive fields only, mirroring `ChequeAdmin.save_model`'s own
  `change` branch (status/payment stay untouchable, no service call needed
  since nothing financial changes).
  `scripts/test_receivables_payables.py` (new, drives the real URLs with
  Django's test Client, same reasoning as Sales/Purchasing's own scripts --
  the allocation order lives in a view, not a service, so only a real POST
  exercises it) -- 31/31, covering: an over-limit split payment rejected
  writing nothing, a valid split payment settling the older invoice first
  *regardless of which order the invoices were submitted in*, a settled
  party dropping off the list, cheque completion/clear/bounce/cancel
  (including a double-clear being a no-op, not a second Payment, and a
  non-pending cheque refusing completion), and the status filter. Full
  browser QA (`scripts/qa_receivables_setup.py`/`_teardown.py`) walked
  the actual Receivables disclosure end to end -- caught nothing new in
  the server logic, but did catch that this browser tool's coordinate
  clicks on a native `<input type="checkbox">` inside a styled `<label>`
  land unreliably after the page reflows (the click "succeeds" with no
  error but leaves the box unchecked); switched to resolving the checkbox
  by its accessibility ref and setting it with `form_input` instead, which
  is reliable -- a testing-tool lesson, not a product bug (confirmed by
  first reproducing an unallocated payment, then the exact same submission
  correctly allocating once the checkbox state was verified via
  `element.checked` before submitting). The `onsubmit="return confirm(...)"`
  cancel-style buttons (cheque clear/bounce/cancel, same pattern Sales/
  Purchasing cancel already uses) also needed a ref-based click rather than
  a coordinate one to fire reliably in this tool, for the same underlying
  reason. `test_frontend_shell.py` (50/50), `test_shared_components.py`
  (37/37), `test_jalali_dates.py` (33/33), `test_sales_invoice.py` (28/28),
  `test_purchase_invoice.py` (33/33), `test_payments.py` (15/15) and
  `test_cheque_lifecycle.py` (15/15) still pass.
- Bank Accounts (REDESIGN_VISION 4.5, Phase C module 5): list -- one card
  per active account (name, owner -- already existed on `BankAccount`
  since 4.3, the vision doc's note that it was new was stale --, account
  number, live balance from `get_bank_account_balance`), plus three
  comparison deltas per card (vs. yesterday/last week/last month), each a
  plain day-offset (`timezone.localdate() - timedelta(days=N)`) rather than
  a Jalali calendar boundary -- REDESIGN_VISION doesn't pin down which, and
  a fixed offset is simplest since this is a single moment-in-time
  comparison, not a range. `get_bank_account_balance` gained an optional
  `as_of` date filter (`payment_date__lte`) for this, backward compatible
  with 4.3's existing no-argument callers. Detail: full ledger (date,
  direction, amount, source/destination, creator, timestamp) built once
  per row in `views._describe_payment` -- resolves to a cheque clearing
  (linked), an expense or its cancellation reversal (by reason, no link --
  the Expenses module isn't built yet), the invoice(s) a split payment was
  allocated to (linked), or "بدون تخصیص" for an unallocated prepayment, all
  read straight off `Payment`/`PaymentAllocation`/`Expense.payment` (no new
  model). No independent "cash" row (2.6) -- cash payments have no
  `bank_account` to belong to. No new/edit form: REDESIGN_VISION 4.5 specs
  only list + cards + detail for this module (unlike Customers, 4.7, which
  explicitly asks for header+edit) -- managing the account list itself
  stays an Admin-panel task, same as before. `scripts/test_bank_accounts.py`
  (new, drives the real `/bank-accounts/` URLs, 11/11) covers the balance
  selector's `as_of` filter and all four ledger-row shapes end to end.
  Full browser QA (`scripts/qa_bank_accounts_setup.py`/`_teardown.py`)
  walked both pages logged in as the QA user -- found nothing new, all
  four ledger rows and the three deltas rendered correctly on first try.
  `test_frontend_shell.py` (50/50), `test_shared_components.py` (37/37),
  `test_jalali_dates.py` (33/33), `test_sales_invoice.py` (28/28),
  `test_purchase_invoice.py` (33/33), `test_payments.py` (15/15),
  `test_cheque_lifecycle.py` (15/15) and `test_receivables_payables.py`
  (31/31) still pass.
- Expenses (REDESIGN_VISION 4.6, Phase C module 6): list -- newest-first,
  today's/this-month's total cards (a cancelled expense's amount excluded
  from both via `Expense.counts_toward_totals` -- the same "history, not
  hidden" table treatment Sales/Purchasing already use for a cancelled
  invoice), free-text search over person/reason, the shared date-range
  picker, and structured filters (bank account, amount range) -- same
  filter split as Sales/Purchasing (`ExpenseFilterForm` + `DateRangeForm`,
  disjoint field names, one querystring). New-expense one-shot form
  (`ExpenseForm`, a plain `ModelForm` -- no formset needed, unlike Sales/
  Purchasing, since an expense is a single row) feeds `record_expense`
  inside `transaction.atomic()`; no edit afterward, only cancel.
  `cancel_expense` (apps/payments/services.py) was missing its superuser
  gate entirely -- REDESIGN_VISION 4.6 calls for "same risk tier as
  invoice cancellation" (D-023), but the service only checked
  `is_cancelled`. Fixed in the same change, mirroring `cancel_sale`'s own
  `is_privileged` check + Persian `ValidationError` (not `PermissionDenied`,
  so the existing `except ValidationError` view pattern keeps working).
  `scripts/test_expenses.py` (new, drives the real `/expenses/` URLs,
  15/15) covers: a cash and a bank-account expense both saving correctly,
  a blank reason writing nothing, search/filter, a non-superuser's cancel
  attempt being rejected, and a double-cancel being a no-op (not a second
  reversal). Full browser QA (`scripts/qa_expenses_setup.py`/`_teardown.py`)
  walked the list, the new-expense form (including the Jalali date picker),
  and cancel -- found nothing new in the server logic, but hit this
  browser tool's own native-dialog limitation: `onsubmit="return
  confirm(...)"` (the same pattern Sales/Purchasing/Cheques cancel already
  use) always resolves `confirm()` to `false` here since native dialogs
  are disabled in this tool, so the click alone never submits. Verified
  the real POST/redirect/card-update instead via `form.submit()` in the
  console (bypasses the `submit` event entirely, so `onsubmit` never
  runs) -- confirmed correct end to end. A tool limitation, not a product
  bug; nothing to fix in the template. `test_frontend_shell.py` (50/50),
  `test_shared_components.py` (37/37), `test_jalali_dates.py` (33/33),
  `test_sales_invoice.py` (28/28), `test_purchase_invoice.py` (33/33),
  `test_payments.py` (15/15), `test_cheque_lifecycle.py` (15/15),
  `test_receivables_payables.py` (31/31) and `test_bank_accounts.py`
  (11/11) still pass.
- Customers (REDESIGN_VISION 4.7, the full ROADMAP 4.5, Phase C module 7):
  list -- name, phone, account status badge (بدهکار/تسویه‌شده, derived
  from `get_customer_outstanding`, D-025), open balance, invoice count,
  last purchase date; free-text search over name/phone; filters for
  account status and active/inactive (defaults to active-only, same as
  every other party list); "+ مشتری جدید" is the exact same inline
  mini-form used mid-invoice on Sales (its `#id_customer` out-of-band
  swap simply finds nothing to replace here, harmless). Detail: header +
  a plain (non-htmx) edit form -- `CustomerForm`, the only place
  `is_active` is editable, since deactivating a customer belongs on an
  edit page, not mid-invoice; lifetime cards (purchases, open balance,
  invoice count, last purchase); this customer's invoices/payments/
  cheques; a combined chronological statement (invoices = debit, payments
  = credit -- a cleared cheque is already a `Payment` by the time it
  reaches here, a pending or bounced one never becomes one, so reading
  `Payment` alone is enough, no separate cheque-ledger merge needed); the
  exact same "ثبت پرداخت" component and `receivables:record_payment`
  route Receivables already uses, reused as-is rather than duplicated.
  Refactor alongside this: the open-invoices query that both
  Receivables/Payables and this page need (`model.objects.filter(status=
  CONFIRMED, ...).filter(outstanding > 0)`, oldest first) moved from a
  private `apps.payments.views._open_invoices` helper into a real
  selector, `apps.payments.selectors.get_open_invoices` -- it was about
  to be imported across app boundaries by its private name otherwise.
  `scripts/test_customers.py` (new, drives the real `/customers/` URLs,
  23/23) covers: the account-status badge and filter, phone search, the
  active/inactive filter, detail-page cards/ledger for both a settled and
  an owing customer, edit (including a rejected blank name leaving the
  name untouched). Full browser QA (`scripts/qa_customers_setup.py`/
  `_teardown.py`) walked the list, detail, the "record payment" htmx
  disclosure (submitted a real payment against the QA invoice --
  confirmed the ledger and cards update correctly on reload), and the
  edit form (submitted a real address change, confirmed the success
  message and the saved value) -- found nothing new; every JS/event
  lesson already paid for on Receivables/Sales (htmx swap targets, the
  formset event shape) simply didn't apply here, since this module
  reuses those components rather than reimplementing them.
  `test_frontend_shell.py` (50/50), `test_shared_components.py` (37/37),
  `test_jalali_dates.py` (33/33), `test_sales_invoice.py` (28/28),
  `test_purchase_invoice.py` (33/33), `test_payments.py` (15/15),
  `test_cheque_lifecycle.py` (15/15), `test_receivables_payables.py`
  (31/31), `test_bank_accounts.py` (11/11) and `test_expenses.py` (15/15)
  still pass.
- Financial Reports (REDESIGN_VISION 4.8, Phase C module 8): a single
  read-only page, `apps.shared.reports` (new module, cross-app selectors --
  placed alongside `apps/shared/views.py` rather than in any one app's own
  `selectors.py`, since it reads sales/purchasing/inventory/payments/
  shared together). The shared date-range picker; five summary cards
  (sales, purchases, expenses, gross profit = Σ real per-invoice FIFO
  profit, net profit) each with % change vs. the equal-length prior period
  (`previous_period()`, computed live both times, never stored); sales-
  and purchases-by-product tables; top sellers (same rows as sales-by-
  product, capped and ranked); inventory **as of the end of the selected
  range** via a new `apps.inventory.selectors.get_inventory_as_of` --
  reconstructs remaining layers from the layer/consumption ledger's own
  `created_at` up to that date (a layer/consumption after the cutoff
  simply is not counted yet, a layer cancelled after the cutoff still
  counts as it did back then); bank account balances as of range end +
  this period's own in/out totals (`get_bank_account_balance`'s existing
  `as_of`, 4.5); open receivables/payables as of range end via two new
  selectors, `apps.payments.selectors.get_total_{receivables,payables}_
  as_of` (a payment made after the cutoff must not retroactively shrink a
  past report's outstanding figure -- existing `get_customer_outstanding`/
  `get_supplier_outstanding` stay untouched, since they answer "now", not
  "as of"); cheque counts/amounts by status, grouped by **due date** within
  the range (not when the cheque was entered -- REDESIGN_VISION 4.8 wants
  what's coming due, not paperwork history); user activity within the
  range grouped by actor from `AuditLog` (a thinner summary than the full
  per-event User Activity module, 4.9, still to come); USD rate is a
  placeholder only, same as 4.3/4.7 (source undecided).
  Also extracted while wiring the Customer-detail "record payment" reuse
  (STATE.md's own Customers entry): the open-invoices query moved from a
  private `apps.payments.views._open_invoices` helper into a real selector,
  `apps.payments.selectors.get_open_invoices` -- unrelated to this module,
  bundled here since both landed close together.
  `scripts/test_reports.py` (new, 19/19) covers every selector directly
  (a pre-range sale correctly excluded, gross profit matching hand-
  computed FIFO math, each as-of selector) plus a page-level smoke test.
  Full browser QA (`scripts/qa_reports_setup.py`/`_teardown.py`) drove the
  real `/reports/` page: verified every card/table's number by hand against
  the QA fixtures (all matched exactly, including the FIFO-costed
  inventory-value snapshot), tested three date ranges (today-only, a
  custom range entirely before today -- correctly zeroed every card and
  table with no leakage, and back to "this month" -- correctly restored
  every number with no duplication), and a hard refresh reproduced the
  same state. One real lesson from driving the Jalali date picker in this
  tool: typing into the custom-range fields opens the picker's calendar
  popup, which then intercepts a click aimed at the "اعمال" button
  underneath it -- pressing Escape to close the calendar first fixed it;
  not a product bug, the same class of tool-specific lesson already
  logged for checkboxes (Receivables) and `confirm()` dialogs (Expenses).
  Before this module's own QA, an unrelated pre-existing problem was found
  and fixed with Sina's explicit sign-off: a cash `Expense` + its cancel-
  reversal `Payment` (reason "تست مرورگر بازدید", both with `bank_account=
  None`) had survived an earlier module's QA teardown -- its cleanup
  filtered by `bank_account=<account>`, which a cash row never matches,
  the same bug class this module's own teardown script was written to
  avoid. Verified precisely against the specific rows by primary key
  (not a broad filter) before deleting; the matching `AuditLog` rows were
  identified but deliberately left in place, per this project's own
  "audit trail outlives a QA fixture" convention. `test_frontend_shell.py`
  (50/50), `test_shared_components.py` (37/37), `test_jalali_dates.py`
  (33/33), `test_sales_invoice.py` (28/28), `test_purchase_invoice.py`
  (33/33), `test_payments.py` (15/15), `test_cheque_lifecycle.py` (15/15),
  `test_receivables_payables.py` (31/31), `test_bank_accounts.py` (11/11),
  `test_expenses.py` (15/15) and `test_customers.py` (23/23) still pass.
- User Activity (REDESIGN_VISION 4.9, Phase C module 9): a new
  `apps.shared.user_activity` selector module (same placement reasoning
  as `apps.shared.reports` -- reads AuditLog across every app). Aggregate
  list (`/user-activity/`): one row per user, counts per bucket (sales/
  purchases/expenses/payments/cheques recorded + cancellations, the
  bucket an event type belongs to fixed once in `_BUCKETS`) plus each
  bucket's own amount total, filterable by user/event type alongside the
  shared date range. Drill-down (`/user-activity/<pk>/`): that one user's
  raw `AuditLog` feed, newest first, event type, timestamp, and a linked
  target resolved through a small `target_type -> URL` table
  (`resolve_target_url`) -- some targets (a bare `Payment`, `Expense`,
  `PaymentAllocation`) have no page of their own and are left unresolved
  on purpose, not a bug.
  Deliberate design call, not a literal reading of REDESIGN_VISION 4.9's
  "total amounts": the aggregate table shows an amount *per bucket*,
  never blended into one number. `record_expense`/`cancel_expense` (and
  the cheque lifecycle) book their own money through `record_payment`
  internally, which logs *its own* separate `AuditLog` row -- so the same
  Rial amount legitimately appears once under "expenses"/"cancellations"
  and once under "payments". Both are independently true facts; summing
  them would silently double-count. Not something to "fix" by suppressing
  the payment's own audit row either -- that row is its own real,
  independently useful fact (traceability, REDESIGN_VISION 2).
  `scripts/test_user_activity.py` (new, 21/21) covers the bucket/amount
  split directly (including asserting the expense-then-payment double
  representation is intentional, not accidental), the event-type filter,
  target-link resolution (a confirmed sale resolves, a bare payment does
  not), and both pages end to end.
  Full browser QA (`scripts/qa_user_activity_setup.py`/`_teardown.py`,
  two distinct QA actors performing distinct actions) found nothing new:
  every count and amount matched hand-calculation exactly, each user's
  drill-down showed only their own events (no cross-user leakage), and
  a spot-checked target link (a confirmed sale) navigated to the exact
  right invoice. Also removed in this change: `ModulePlaceholderView` and
  `shared/placeholder.html` -- this route was the mechanism's last caller
  (Financial Reports took the other one the commit before), so both were
  now fully dead code, not a separate cleanup task.
  `test_frontend_shell.py` (50/50), `test_shared_components.py` (37/37),
  `test_jalali_dates.py` (33/33), `test_sales_invoice.py` (28/28),
  `test_purchase_invoice.py` (33/33), `test_payments.py` (15/15),
  `test_cheque_lifecycle.py` (15/15), `test_receivables_payables.py`
  (31/31), `test_bank_accounts.py` (11/11), `test_expenses.py` (15/15),
  `test_customers.py` (23/23) and `test_reports.py` (19/19) still pass.
- Dashboard (REDESIGN_VISION 4.10, Phase C module 10 -- **the last of the
  11**, Phase C now complete): a new `apps.shared.dashboard` selector
  module fills in the deliberate stub `DashboardView`/`shared/
  dashboard.html` already had since Phase B. Row 1: sales/purchases/
  expenses/net-profit, each today + this month, reusing Financial
  Reports' own `sales_total`/`purchases_total`/`expenses_total`/
  `gross_profit` so this card can never disagree with that page. Row 2:
  open receivables/open payables (both "now", i.e. `get_total_
  {receivables,payables}_as_of(today)` -- reusing Reports' own as-of
  selectors rather than adding a third pair just for "now"), total bank
  balance (every active account's `get_bank_account_balance` summed, no
  `as_of`), total inventory value (`get_total_inventory_value`, already
  existed) -- each linking to its own module. Row 3 (attention-needed):
  cheques due within 7 days (new `cheques_due_soon`, 3-5 shown + a real
  "see all" count), old unpaid credit invoices (new `overdue_credit_
  invoices`, default 30-day threshold, `?overdue_days=N` query parameter
  as REDESIGN_VISION specified -- sales side only, since this widget is
  about collection risk and the payables mirror already lives on the
  Payables page), a negative-stock warning (new `apps.inventory.
  selectors.get_negative_stock_products`, defensive only -- D-016 already
  permits an oversell, this just surfaces it). Row 4: the latest global
  activity feed (new `apps.shared.user_activity.get_recent_activity`,
  no date range or actor filter, unlike User Activity's own scoped feed)
  + "see all" into User Activity.
  `scripts/test_dashboard.py` (new, 18/18) covers every selector directly
  (today vs. month KPI bounds, the 30-day vs. 50-day overdue threshold,
  cheques due soon, negative stock) plus a page-level smoke test
  including the `?overdue_days=` query parameter. Full browser QA
  (`scripts/qa_dashboard_setup.py`/`_teardown.py`, including a
  deliberately oversold product to exercise the negative-stock row) found
  nothing new: every card/table number matched hand-calculation exactly
  -- notably the net-profit figure correctly included the oversold line's
  revenue-with-no-cost-deducted per D-016/D-037, and the inventory-value
  figure correctly accounted for a sale item on the *old* invoice also
  drawing from the same product's layers, easy to under-count by hand if
  you forget it. The `overdue_days` filter and a spot-checked
  negative-stock product link (navigated to the exact right product) both
  verified live in the browser, not just via the test Client.
  `test_frontend_shell.py` (50/50), `test_shared_components.py` (37/37),
  `test_jalali_dates.py` (33/33), `test_sales_invoice.py` (28/28),
  `test_purchase_invoice.py` (33/33), `test_payments.py` (15/15),
  `test_cheque_lifecycle.py` (15/15), `test_receivables_payables.py`
  (31/31), `test_bank_accounts.py` (11/11), `test_expenses.py` (15/15),
  `test_customers.py` (23/23), `test_reports.py` (19/19) and
  `test_user_activity.py` (21/21) still pass -- 425/425 across the whole
  suite.

- Pre-Phase-D correction batch (Sina's master prompt, 2026-09-26; one
  commit; decisions D-043..D-046, options picked by Sina before building):
  **Toman** (D-043): every money column reinterpreted as whole Toman (tables
  were empty, label-only migrations); `format_toman` + a single `toman`
  filter replace the Rial helpers/filters/hints everywhere (templates,
  forms, admin, JS). **Bank Accounts**: create/edit pages
  (`BankAccountForm`, Persian unique-number error). **Expenses** (D-045):
  `related_person` dropped; `PaymentSourceField` (real accounts + explicit
  "نقدی (صندوق)", no default) is the paying-account field. **Inventory**
  (D-044): `record_adjustment` + its page/form/URL removed and its D-041
  schema reverted (`InventoryConsumption.movement`, `Source.ADJUSTMENT`);
  the separate opening-stock page removed -- opening stock only via the
  new-product page (`InventoryProductForm`) or the admin add form; the list
  shows FIFO cost, last purchase cost, current selling price and value at
  cost; per-product "تغییر قیمت فروش" (`products.services.
  update_selling_price` -- touches only `default_selling_price`, audited as
  the new `change_selling_price` event, history attributed to the user).
  **Suppliers**: create page + edit disclosure (`SupplierForm`).
  **Purchase**: "+ کالای جدید" is a `<dialog>` (outside the invoice
  `<form>`) opened from the items card or a "not found" search result; the
  new product drops straight into the row that asked for it.
  `QuickProductForm`'s selling price now starts empty (gap #6: an untouched
  `0` used to pass "required"). **Sales** (D-046): discount moved into the
  totals block; `payment_mode` full/split, full = `received_into` +
  `sales.services.plan_full_payment`, split = the old rows.
  Verification: `scripts/test_pre_phase_d.py` (new, 92/92: every item
  above incl. FIFO costs across an opening + a purchase layer, discount
  never touching stock/costs, the three payment modes, reports/dashboard
  agreement, no "ریال" on any page); `test_expenses.py`, `test_sales_
  invoice.py`, `test_expense_and_party.py`, `test_admin_form_errors.py` and
  the four scripts that imported `rial_toman` updated for the approved
  behaviour; `test_inventory_adjustment.py` deleted (its subject no longer
  exists; `test_pre_phase_d.py` asserts the removal instead) -- 685/685
  across all 36 scripts. Browser QA (`scripts/qa_pre_phase_d_setup.py`/
  `_teardown.py`, QA user 09000000012) walked bank account create +
  validation, supplier create/edit, new product with opening stock, a
  purchase with an existing product plus two products created from the
  dialog (one via "not found", one hitting a duplicate-SKU error first),
  selling-price change, a full-settlement sale into the new account with a
  discount, a split sale (cheque + cash + credit), an expense from the
  account, then the bank ledger, Dashboard and Reports -- every number
  matched hand calculation. Found and fixed during that pass: the dialog's
  labels pointed at the supplier form's inputs (both rendered `id_name`,
  fixed with `auto_id`), closing the dialog stole focus from the new row,
  and the 422 validation response was never shown inside the dialog (htmx
  2 does not swap 4xx by default; scoped `htmx:beforeSwap` handler). This
  browser tool's typing does not fire `keyup`, so the product search was
  driven by dispatching the event -- a tool limitation, not a product bug.
- C.fix-1 / C.fix-2 (Sina's go-ahead, 2026-09-26, right after the
  correction batch). C.fix-1 (D-047): `shared/base.html` carries an
  `htmx-config` meta making 422 a swapping response, so every htmx form's
  Persian validation errors actually appear (quick customer/supplier/
  product, "ثبت پرداخت"); the purchase dialog's scoped handler is gone.
  C.fix-2: `apps.products.forms.SelectedProductMixin` (on `SaleItemForm`
  and `PurchaseItemForm`) resolves the product a bound row holds -- from
  cleaned_data, or the raw id when the row itself failed validation, a
  malformed id resolving to nothing -- and both `_item_row.html` templates
  refill the search box and the "موجودی: N" label from it. Verified by
  `scripts/test_cfix_1_2.py` (new, 17/17) -- 702/702 across all 37 scripts
  -- and in the browser (`scripts/qa_cfix_setup.py`, torn down with
  `qa_pre_phase_d_teardown.py`): a duplicate quick customer, an
  over-allocated "ثبت پرداخت" and a duplicate-SKU product dialog each now
  show their error in place; a sale rejected for its missing receiving
  account comes back with the row's product name, stock and quantity.

## PENDING (raised, not decided -- do not build without Sina's go-ahead)
- ~~htmx 4xx responses are never swapped~~ -- C.fix-1, done (D-047).
- ~~Item rows lose their product name on a re-rendered invoice form~~ --
  C.fix-2, done.
- **Per-product profit vs. invoice discount** (Reports "فروش به تفکیک
  کالا", sales detail line profit): line profit is computed before the
  invoice-level discount (D-032), so the per-product column does not sum to
  the gross-profit card when a discount exists. Needs a decision on whether
  to allocate a discount across lines. Proposed: D-048, roadmap id C.fix-3.
- ~~Financial report screen~~ -- superseded by REDESIGN_VISION 4.8, now
  built as Phase C module 8 (see Built). The COGS-method question this
  note originally raised was already settled project-wide by D-036/D-037
  (FIFO, realised profit only) before the rebuild started.

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
- [x] 2.11 Rial and Toman side by side everywhere; Toman hint under every price input [R 8] (superseded by D-043: Toman only)

### Phase 3 — Real data and SHADOW start
- [x] 3.1 Backup, then `flush` test data
- [x] 3.2 Real superuser, Business, memberships, document sequence starts
- [x] 3.3 Products with opening stock; customers; suppliers
- [ ] 3.4 Daily discrepancy log started

### Phase 4 — Financial modules (in parallel with SHADOW)
- [x] 4.1 Inventory overview: stock, last purchase price, selling price, approximate value, status (negative / low / normal) [R 12, 14]
- [x] 4.2 Per-product transaction history with invoice link, user, price [R 13]
- [x] 4.3 `BankAccount` model (name, account number, business FK); `Payment` +
      `PaymentAllocation` referencing it for bank-transfer payments; derived
      payment status (D-025) [R 10]
- [x] 4.4 `Cheque` lifecycle: pending / cleared / bounced, linked to a Payment [R 3, 10]
- [x] 4.5 Customer account: invoices, payments, cheques, running balance
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
14. ~~Every amount shown as `X,XXX,XXX ریال | XXX,XXX تومان`~~ Every amount shown as `XXX,XXX تومان` (D-043)
15. Concurrent sales: no uncontrolled overselling (D-015, D-021)

## Tracking
- Daily: tasks closed.
- From phase 3, daily: discrepancies (exit SHADOW = 3 consecutive days at 0).
- Phase 5: scenarios passed (target 15/15).
- Exit condition: if phases 1-2 are not done by day 14 (2026-10-05), move the remaining phase 2 tasks to phase 4 and start phase 3.

# Decision Log

Append-only. Never rewrite a Final entry — supersede it with a new one.
If this log and SPEC.md disagree, this log wins.

---

### D-001: Project layout and settings package name
- Status: Final
- Date: 2026-09-20
- Decided by: me
- Decision: Django settings package is `core/`; apps live under `apps/`.
  The shared app from SPEC.md (`core`) is renamed to `apps/shared`.
- Options considered: settings as `config/` with app named `core`; settings as `core/` with app named `shared`.
- Rationale: avoids two different things sharing the name `core`, which would make imports ambiguous.
- Affects: all apps, `INSTALLED_APPS`.

### D-002: Configuration via environment variables
- Status: Final
- Date: 2026-09-20
- Decided by: me
- Decision: All secrets and environment-specific values are read from `.env`
  using `django-environ`. `.env` is gitignored; `.env.example` documents the keys.
- Options considered: hardcoded settings; split settings modules per environment.
- Rationale: keeps secrets out of git; the same code runs in dev and production
  by changing environment variables only.
- Affects: `core/settings.py`.

### D-003: Primary key type is UUID
- Status: Final
- Date: 2026-09-20
- Decided by: me (on recommendation)
- Decision: All main models use `UUIDField` as primary key, provided by `BaseModel`.
- Options considered: auto-incrementing Integer; UUID.
- Rationale: IDs are not guessable and do not leak record counts; multi-business
  system with financial data. Performance cost is irrelevant at the expected
  scale (<100k documents/year). Human-readable document numbers (invoice_number)
  are a separate concern, not the primary key.
- Affects: `apps/shared/models.BaseModel` and every model inheriting it.

### D-004: Time is stored in UTC
- Status: Final
- Date: 2026-09-20
- Decided by: me
- Decision: `USE_TZ = True`, `TIME_ZONE = "UTC"`. Timezone conversion and the
  Jalali calendar are presentation concerns, handled in the API/frontend layer,
  never in storage.
- Options considered: storing in `Asia/Tehran`; storing naive datetimes.
- Rationale: separating storage from presentation keeps financial calculations
  correct across DST changes and different server locations.
- Affects: `core/settings.py`, every `DateTimeField`.

### D-005: Interface language
- Status: Final
- Date: 2026-09-20
- Decided by: me
- Decision: `LANGUAGE_CODE = "fa"`. User-facing strings (`verbose_name`, labels,
  error messages) are Persian. Identifiers, class names, field names, comments,
  and commit messages stay English.
- Options considered: fully English UI; Persian identifiers.
- Rationale: field names become SQL column names; Persian columns would require
  quoting in every raw query.
- Affects: all models, admin, serializers.

### D-006: Empty text fields use `blank=True` only, never `null=True`
- Status: Final
- Date: 2026-09-20
- Decided by: me
- Decision: Optional `CharField`/`TextField` are declared `blank=True` without
  `null=True`. Empty means `""`, never `NULL`.
- Options considered: allowing both `null` and `blank`.
- Rationale: two representations of "empty" force every query to check both.
- Affects: all models.

### D-007: Users log in with their mobile phone number
- Status: Final
- Date: 2026-09-20
- Decided by: me (on recommendation)
- Decision: Custom user model `users.User` based on `AbstractBaseUser` +
  `PermissionsMixin`, with `USERNAME_FIELD = "phone"`. A `UserManager` provides
  `create_user` / `create_superuser` keyed on phone. `AUTH_USER_MODEL = "users.User"`.
  Phone format validated as `^09\d{9}$`.
- Options considered: Django default `username`; email; mobile phone.
- Rationale: the real users are business owners and salespeople, not developers;
  a phone number is what they already remember. The user model cannot be swapped
  once real data exists, so it was set up before any data entry.
- Affects: `apps/users`, `core/settings.AUTH_USER_MODEL`, every future `created_by` FK.

### D-008: User is not scoped to a Business
- Status: Superseded. Superseded by D-033 (Business removed entirely).

### D-009: Roles as a choices field
- Status: Superseded. Superseded by D-034 (no roles).

### D-010: Customer and Supplier are two separate models
- Status: Final
- Date: 2026-09-21
- Decided by: me
- Decision: `Customer` and `Supplier` are separate models in `apps/partners`,
  not one `Partner` model with a `type` field.
- Options considered: single `Partner` model with a type field; two models.
- Rationale: in this business a customer is never also a supplier. A shared
  model would allow invalid combinations (a sales invoice pointing at a
  supplier) that the database could not prevent.
- Affects: `apps/partners`, `SalesInvoice.customer`, `PurchaseInvoice.supplier`.


### D-011: Inventory quantity is a whole number
- Status: Final
- Date: 2026-09-21
- Decided by: me
- Decision: `InventoryMovement.quantity` is a `PositiveIntegerField`. Products are
  counted in whole packages (بسته); fractional quantities do not exist in v1.
- Options considered: DecimalField(12,3) for weight/length-based units.
- Rationale: the real business sells only by the package. An integer makes stock
  arithmetic exact with no rounding questions.
- Affects: `apps/inventory`, all stock aggregation.
- Note: if a weight- or length-based unit is ever introduced, this must be
  superseded by a new decision and a data migration, not edited in place.

### D-012: Movement direction comes from movement_type, not from the sign
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: `quantity` is always > 0. Whether a movement adds to or removes from
  stock is determined by `movement_type`. A `CheckConstraint` enforces quantity > 0.
- Options considered: signed quantity (negative = outflow).
- Rationale: a wrong sign is silent data corruption; a wrong type is visible.
  The database can reject an impossible quantity, but it cannot reject a wrong sign.
- Affects: `apps/inventory`, `confirm_purchase`, `confirm_sale`.


### D-013: Money stored as whole Rial
- Status: Superseded. Superseded by D-043 (whole Toman everywhere).

### D-014: A confirmed invoice is immutable
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: Once `status = confirmed`, an invoice and its items cannot be edited
  or deleted. Mistakes are corrected with an `adjustment_in` / `adjustment_out`
  InventoryMovement carrying a reason in `note`.
- Options considered: free editing with recalculation of stock movements.
- Rationale: the system runs SHADOW against a paper ledger. Editing history makes
  yesterday's stock unknowable and hides the discrepancies the shadow phase exists
  to surface.
- Affects: `apps/purchasing`, `apps/sales`, `confirm_purchase`, `confirm_sale`, admin.


### D-015: Stock concurrency is guarded by locking Product rows
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: `confirm_sale` calls `select_for_update()` on the `Product` rows of
  the invoice before reading stock. The product row is used purely as a mutex;
  its columns are not modified.
- Options considered: locking the whole InventoryMovement table; no locking.
- Rationale: stock is derived from a ledger, so there is no stock row to lock.
  Two concurrent sales of the same product must serialise, or both pass the
  same availability check.
- Affects: `apps/sales/services.confirm_sale`.

### D-016: A sale may drive stock negative
- Status: Final
- Date: 2026-09-21
- Decided by: me
- Decision: Insufficient stock does not block `confirm_sale`. The sale is
  recorded, the resulting movements are marked in their `note`, and the service
  returns the list of products that went negative so the caller can warn the user.
- Options considered: hard rejection with a ValidationError.
- Rationale: the paper ledger already works this way — goods are sold before the
  purchase invoice reaches the office. Blocking would force staff to falsify dates.
- Affects: `apps/sales/services.confirm_sale`, future reporting.
- Note: during SHADOW, every negative stock event is a discrepancy to log, not
  a normal outcome.


### D-017: Opening stock is entered once, before any other movement
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: `set_opening_stock` refuses if the product already has any
  InventoryMovement, or if `is_onboarded` is already True. A product whose
  opening stock is zero is marked onboarded with no movement row, because the
  ledger forbids quantity = 0 (D-012). Later corrections use `adjustment_in` /
  `adjustment_out`, never a second opening.
- Options considered: allowing opening stock at any time.
- Rationale: an opening movement inserted after sales rewrites the past; every
  stock figure already reported becomes wrong and the shadow-phase comparison
  against the paper ledger loses its meaning.
- Affects: `apps/inventory/services.set_opening_stock`, `Product.is_onboarded`.


### D-018: The application connects as a dedicated, non-superuser database role
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: Django connects as `paper_app`, which owns the `paper_plus` database,
  its `public` schema, and every table in it. The `postgres` superuser is used
  only for server-level administration, never by the application.
- Options considered: keeping the `postgres` superuser in `DATABASE_URL`.
- Rationale: a bug or an injected query running as superuser could reach every
  database on the server. Ownership (not GRANT) is required because `migrate`
  issues `ALTER TABLE` and `DROP`, which only the owner may run.
- Affects: `.env DATABASE_URL`, `tools/backup.ps1`, `tools/reassign_ownership.sql`.

### D-019: DEBUG and ALLOWED_HOSTS come from the environment and default to safe
- Status: Final
- Date: 2026-09-21
- Decision: `DEBUG = env.bool("DEBUG", default=False)` and
  `ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])`.
- Options considered: hardcoding DEBUG per environment.
- Rationale: a missing `.env` must fail closed, not expose tracebacks. HTTPS-related
  warnings from `check --deploy` (HSTS, SSL redirect, secure cookies) are deferred
  until an actual deployment exists.
- Affects: `core/settings.py`, `.env.example`.


### D-020: Scope expanded to the full remake request
- Status: Final
- Date: 2026-09-21
- Decided by: me
- Decision: The exclusions in STATE.md section 7 are lifted. Roles and
  permissions, audit trail, auto numbering, discount, payments, cheques,
  customer account, returns and inventory valuation are in scope.
  Order and phases live in ROADMAP.md.
- Options considered: SHADOW first with the existing features; full scope.
- Rationale: the owner wants every requested feature. Ordering keeps risk
  low: permissions and audit first, invoice schema changes before real
  data, new financial modules built in parallel with SHADOW.
- Affects: STATE.md section 7, ROADMAP.md, all apps.

### D-021: Negative stock is allowed by role
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: `confirm_sale` rejects a shortage when the confirming user is a
  Seller. Owner and superuser may confirm it; the sale is recorded and the
  shortage is reported as a warning, as in D-016.
- Options considered: always block; always allow (D-016 alone).
- Rationale: goods are sometimes sold before the purchase invoice arrives,
  so blocking everyone would force staff to falsify dates. Restricting the
  exception to owners keeps each negative-stock event a deliberate decision.
- Affects: `apps/sales/services.confirm_sale`, `apps/shared/permissions`.
- Note: complements D-016, does not supersede it.

### D-022: Invoice numbers are generated at confirmation
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: Sales and purchase invoice numbers are assigned by the system
  from a `DocumentSequence` row (one per business and document type),
  locked with `select_for_update`, at the moment of confirmation. The
  starting number of each sequence is configurable. Drafts have no number.
  The UUID pk stays the internal id (D-003). Purchase invoices also get
  `supplier_invoice_number` for the supplier's own printed number.
- Options considered: number at creation; `max() + 1`; a manually typed number.
- Rationale: numbering at confirmation leaves no gaps when a draft is
  deleted. `max() + 1` gives duplicates under concurrency. The paper
  ledger has no own numbering, so there is nothing to match manually.
- Affects: `apps/shared` (DocumentSequence), `apps/purchasing`, `apps/sales`.

### D-023: A confirmed invoice is cancelled, never edited
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: `cancel_sale` / `cancel_purchase` set status `cancelled` and write
  reversing InventoryMovement rows inside `transaction.atomic`. Only Owner
  and superuser may cancel. A cancelled invoice keeps its number. The
  correct invoice is entered as a new one.
- Options considered: editing a confirmed invoice; hard delete.
- Rationale: keeps D-014 intact. History and the audit trail survive, and
  stock is corrected by the ledger itself.
- Affects: `apps/purchasing`, `apps/sales`, `apps/inventory`, admin.

### D-024: Hard delete only for unreferenced records
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: A superuser may hard-delete a record only when nothing
  references it; PROTECT foreign keys enforce this. InventoryMovement rows
  and confirmed or cancelled invoices are never deleted, by anyone. Every
  other case uses `is_active`.
- Options considered: full delete rights for superuser.
- Rationale: deleting a ledger row or a confirmed invoice rewrites every
  stock and balance figure after it. This is an integrity rule, not a
  permission, so no role bypasses it.
- Affects: all admins.

### D-025: Payment status is derived, never stored by hand
- Status: Final
- Date: 2026-09-21
- Decided by: me (on recommendation)
- Decision: Payment method is a field on the invoice. Payment status
  (unpaid / partial / paid) is computed from `PaymentAllocation` rows.
  No field lets a user type it.
- Options considered: a manual `payment_status` field.
- Rationale: a typed status drifts from the real payments; a derived one
  cannot.
- Affects: `apps/sales`, the upcoming payments module.

### D-026: Sellers use the admin, scoped to their business
- Status: Superseded. Superseded by D-035 (`/admin/` is superuser-only).

### D-027: Seller permission scope
- Status: Superseded. Superseded by D-034 (no roles).

### D-028: User + first membership created together
- Status: Superseded. Superseded by D-033/D-034 (no memberships).

## D-029
D-029 AuditLog target reference is target_type (CharField, model label) + target_id (UUIDField),
not GenericForeignKey — no GFK used anywhere else in the project; actor FK is PROTECT, non-null,
since all three current services require a user.

## D-030
D-030 Chat rhythm: read-only/verify commands may be chained in one message; state-changing steps
(migrate, commit, DB writes) never chain. A chat still ends at task completion or ~15 messages,
whichever comes first — supersedes the earlier fixed "5 exchanges" limit.

## D-031 — Verification scripts: unique identifiers and post-call object references

Date: 2026-09-23

Context: Two verification scripts failed for reasons unrelated to the code
under test: (1) a hardcoded phone number collided with pre-existing data in
the dev database, and (2) a script asserted on a locally-held object after
calling a service that internally re-fetches and returns a fresh instance
(e.g. confirm_sale's select_for_update), so the assertion checked a stale
Python object instead of the actual result.

Decision:
- Every unique field a verification script creates (User.phone, and any
  other globally- or business-scoped unique field) gets a randomly
  generated value, never a fixed/sequential one. The dev database is never
  assumed to be empty.
- After calling any service/function that may lock, re-fetch, or otherwise
  return a different Python object than what was passed in, scripts assert
  against the *returned* object, or call `refresh_from_db()` on the
  original before asserting — never against the pre-call local reference.

Consequences: Verification scripts are slightly more verbose (random value
generation, explicit refresh) but no longer depend on the database's prior
state or on assumptions about object identity across a service call.

## D-032 — Invoice discount: fixed amount, sales-only, invoice-level
Date: 2026-09-23
Status: Final

SalesInvoice.discount_amount is a fixed Rial amount (BigIntegerField, default 0,
CHECK >= 0), not a percentage. Chosen over percentage to avoid rounding rules on
BigInteger Rial values (D-013).

Invoice-level only for now, shaped so a later line-level discount can be added
without migrating this field: SalesInvoice.subtotal/.total are properties
computed from items, not stored, so adding per-item discounts later only
changes how subtotal is computed, not the SalesInvoice schema.

Sales only — PurchaseInvoice has no discount_amount. Rationale: no product
requirement for purchase discount yet; add via a symmetrical migration if
that changes (do not reuse this field across apps).

Validation: discount_amount > subtotal is rejected in confirm_sale (not in
clean()), because subtotal depends on SaleItem rows that can still change
while the invoice is draft (ROADMAP 2.7).

## D-033 — Single business: Business/BusinessMembership removed entirely
Date: 2026-09-24
Status: Final
Supersedes: D-008, and the multi-tenant half of D-026

Context: `paper-plus` was built multi-tenant (every business-data model
carried a `business` FK, every admin was scoped by `BusinessScopedAdminMixin`).
Sina's redesign vision (REDESIGN_VISION 2.2, his words: "یک قسمت عضویت
کسب‌وکارها و خود کسب‌وکار رو حذف کنیم") establishes that this is one
business, and a second one would be a separate deployment, not a tenant in
this database.

Decision: `shared.Business` and `shared.BusinessMembership` are deleted,
along with the `business` FK on Product, Customer, Supplier, SalesInvoice,
PurchaseInvoice, InventoryMovement, DocumentSequence, AuditLog, BankAccount,
Payment and Cheque. Every `unique_*_per_business` constraint becomes global
(`unique_product_sku`, `unique_customer_name`, `unique_supplier_name`,
`unique_bank_account_number`, `unique_sales_invoice_number`,
`unique_purchase_invoice_number`), and a `DocumentSequence` row is now a
singleton per `doc_type`. `BusinessScopedAdminMixin` is deleted;
`get_business_ids` with it.

Consequences: The cross-business validation inside `confirm_sale` /
`confirm_purchase` / `record_payment` / `record_cheque` is gone — those
checks existed only to stop one tenant's data from leaking into another.
Verification scripts no longer create a Business, and must reuse the
existing `DocumentSequence` rows (`get_or_create` / `update_or_create`)
rather than inserting their own, which would now violate uniqueness.
A dev database mid-rebuild can hold tables whose model was already deleted,
which `manage.py flush` cannot truncate — hence `tools/flush_all.py`.

## D-034 — No role system: `is_superuser` is the only distinction
Date: 2026-09-24
Status: Final
Supersedes: D-009, D-027, D-028; narrows D-021 and D-023

Context: Owner/Seller lived on `BusinessMembership.role`, mirrored into auth
Groups by a signal. With Business gone the role has nowhere to live, and Sina
chose (REDESIGN_VISION 2.3, "کلاً فعلاً حذفش می‌کنیم و بعداً از پنل ادمین
اضافه می‌شه") to drop the concept rather than move it onto User.

Decision: No role field anywhere. Any authenticated user may use every page
and every action, with exactly two exceptions, both now gated on Django's
own builtin `is_superuser`:
- confirming a sale that would drive stock negative (was D-021's Owner gate),
- cancelling a sales or purchase invoice (was D-023's Owner gate).
`apps/shared/permissions.py` keeps one pair of helpers, `is_privileged(user)`
and `require_privileged(user)`; `get_membership`, `has_role`, `is_owner`,
`require_role` and `get_business_ids` are deleted. `apps/shared/signals.py`
(role -> Group sync) is deleted. Creating and deactivating logins stays an
admin-panel task, not a page in the new frontend.

Consequences: `is_privileged` keeps the old helper's rule that an inactive or
anonymous user never passes, so a deactivated superuser cannot cancel
anything. Multiple logins still exist purely for attribution —
`created_by`/`actor` stay on every model and the audit trail is unchanged.
Migration `shared/0003_seed_role_groups` stays in history but its Owner/Seller
Groups are now meaningless.

## D-035 — `/admin/` is superuser-only
Date: 2026-09-24
Status: Final
Supersedes: D-026

Context: D-026 made the admin the Seller's workplace, which was safe only
because every page was business-scoped and role-gated through the Owner/Seller
Groups. D-033 and D-034 remove both of those at once, so `is_staff` alone
would have handed any staff login raw write access to every financial model —
a real regression, not a theoretical one.

Decision: `apps/shared/admin_site.py` defines `PaperPlusAdminSite`, whose
`has_permission` requires `is_active and is_superuser`, installed by replacing
`django.contrib.admin` with `PaperPlusAdminConfig` in `INSTALLED_APPS`.
`/admin/` is a technical backend for whoever maintains the system; end users
get the real frontend (REDESIGN_VISION 2.1). Site-wide Persian admin titles
move onto that class.

Consequences: `UserAdmin` loses the business/role fields on its add page, the
Seller self-deactivation carve-out, and the `PRIVILEGE_FIELDS` lockout —
every remaining visitor is a superuser. New users are no longer given
`is_staff` on creation, because the frontend, not the admin, is their surface.

## D-036 — FIFO cost layers: InventoryLayer + InventoryConsumption
Date: 2026-09-25
Status: Final
Replaces: `get_cost_map` (latest-purchase-price valuation, ROADMAP 4.1)

Context: `get_cost_map` returned the most recent purchase price of a product
and multiplied it by total stock. That is not FIFO, cannot say what a
particular sale cost, and therefore cannot produce real per-invoice profit —
which REDESIGN_VISION 2.4 requires in full, not in a simplified form.

Decision: Two new models in `apps.inventory`.
- `InventoryLayer`: one batch of stock at one known `unit_cost`, created by
  `set_opening_stock` (source `opening_stock`) or per line by
  `confirm_purchase` (source `purchase_item`, OneToOne to the line). Holds
  the immutable original `quantity` and a maintained `quantity_remaining`.
- `InventoryConsumption`: `sale_item`, `layer`, signed `quantity`.
`confirm_sale` consumes oldest layer first, ordered by `(created_at, id)` so
ties resolve the same way every time. `cancel_sale` restores by recorded
amount per layer, not in FIFO order, because a later sale may have drawn from
the same layers in between.

`quantity_remaining` is a stored running balance, which looks like a stored
derived fact (D-025). It is allowed here on one condition: it must always
equal `quantity - sum(that layer's consumption quantities)`. That is why
reversal adds an opposite row instead of editing or deleting the original —
the same append-only shape `InventoryMovement` already uses for corrections —
and why `get_layer_balance()` exists to prove the two never drifted.

`InventoryLayer` does not duplicate `InventoryMovement`. The movement ledger
stays the immutable source of truth for *how much* stock exists and is never
mutated; a layer answers *what it cost*.

Purchase cancellation guard: `cancel_purchase` is rejected unless every
layer it created is still untouched (`quantity_remaining == quantity`), and
otherwise marks the layer `cancelled_at` rather than deleting it. Cancelled
layers leave the FIFO pool and all valuation. This is stricter than a sale's
cancel rule, deliberately: withdrawing stock that has already been sold would
leave that sale's recorded cost pointing at stock the system says never
existed. Note the rule is "currently untouched", not "never touched" — a
purchase whose only sale was itself cancelled becomes cancellable again,
because nothing depends on it any more.

Consequences: `get_cost_map` is replaced by `get_current_cost_map` (the
oldest active layer's cost — what the next sale will actually consume),
`get_last_known_cost_map` (display-only fallback once stock hits zero,
REDESIGN_VISION 8 item 5), `get_inventory_value_map` and
`get_total_inventory_value` (each layer at its own cost, since layers of one
product carry different costs). Manual stock adjustment (REDESIGN_VISION 4.3)
has no service yet; when it gets one, `adjustment_out` must consume layers
and `adjustment_in` must carry a unit cost, or layer totals and movement
totals will diverge.

## D-037 — Profit is realised profit: zero unless the invoice is confirmed
Date: 2026-09-25
Status: Final

Context: `SaleItem.profit` was first written as `line_total - cost_of_goods`.
A cancelled invoice's consumptions net to zero cost, and a draft has no
consumptions at all, so both reported their entire revenue as profit. Any
card, report or statement summing this property would have counted cancelled
invoices — exactly what REDESIGN_VISION 8 item 4 forbids across every page.
Caught by `scripts/test_fifo_layers.py`, not by review.

Decision: `SaleItem.profit` and `SalesInvoice.profit` return 0 unless the
invoice status is CONFIRMED. `line_total`, `subtotal` and `total` are
deliberately *not* changed — a cancelled invoice must still display its own
amounts on its own page; it is the aggregates that must exclude it. The rule
lives on the model so no caller can forget it.

Oversell has no cost basis: when a superuser confirms a sale that drives
stock negative (D-016), the uncovered units find no layer. No price is
invented for them. `SaleItem.uncosted_quantity` and
`SalesInvoice.has_uncosted_items` surface them, so a page showing profit can
say that it is overstated by whatever those units really cost.

## D-038 — Payment gains customer / supplier
Date: 2026-09-25
Status: Final

Context: A `Payment` reached its party only through `PaymentAllocation`, so
an unallocated payment — a prepayment taken before any invoice is picked —
had no trace to anyone at all. That breaks the founding principle that no
money moves without an origin, a destination and a person
(REDESIGN_VISION 1). Found while reviewing, not asked for.

Decision: `Payment.customer` and `Payment.supplier`, both nullable, mirroring
`Cheque`'s pair but with a looser constraint: at most one may be set, and it
must agree with `direction` (IN -> customer, OUT -> supplier). Neither is
required, because an expense's payment belongs to no party.
`confirm_sale`, `confirm_purchase` and `clear_cheque` all set it
automatically. `record_payment` raises a Persian ValidationError for each bad
combination before the CHECK constraint can surface a raw IntegrityError
(the ChequeForm lesson from ROADMAP 4.4).

Consequences: A customer's or supplier's payments are now directly
queryable (`Payment.objects.filter(customer=...)`) regardless of allocation
state, which is what the Customer-detail statement (REDESIGN_VISION 4.7)
and the Receivables page read.

## D-039 — Cheque gains CANCELLED
Date: 2026-09-25
Status: Final

Decision: `Cheque.Status.CANCELLED`, reachable only from PENDING, via a
`cancel_cheque` service shaped like `bounce_cheque`. No Payment is created or
touched: a pending cheque was never counted toward any invoice's
payment_status (the ROADMAP 4.4 rule), so withdrawing one moves no money.
This is "I entered this by mistake", not a reversal. The row is never
deleted — it stays as history, like a cancelled invoice. New AuditLog event
type `cancel_cheque`.

## D-040 — Expense lives in apps.payments, backed by a real Payment
Date: 2026-09-25
Status: Final

Context: REDESIGN_VISION 3 leaves the placement open ("either its own small
app or inside apps.payments, your call").

Decision: `Expense` goes in `apps.payments`, because it is a `Payment(OUT)`
with a reason attached — it shares the "blank bank_account means cash" rule
(REDESIGN_VISION 2.6), and a separate app for one model would only add an
import boundary. `record_expense` creates the Expense and its Payment
atomically (`Expense.payment`, OneToOne, non-null); `cancel_expense` books an
opposite `Payment(IN)` into `Expense.reversal_payment` and sets
`cancelled_at`/`cancelled_by`. Nothing is edited or deleted
(REDESIGN_VISION 2.7). A CHECK keeps the three cancellation fields all-set or
all-null.

Reusing the Payment ledger is the point: bank balances, cash flow and every
report already read `Payment`, so an expense needs no second accounting path.

`related_person` is free text, not an FK to Supplier: a landlord or a
mechanic is not a supplier, and forcing one into the partner list would put
people the business never buys goods from into payables.

`Expense.counts_toward_totals` is False once cancelled, stated on the model
rather than left to each page, because every place that totals money has to
agree (REDESIGN_VISION 8 item 4). New AuditLog event types `record_expense`
and `cancel_expense`. `document` is an optional FileField, which is why
MEDIA_ROOT/MEDIA_URL and the DEBUG-only media route now exist.

### D-041: Manual stock adjustment draws FIFO layers
- Status: Superseded. Superseded by D-044 (manual adjustment and its schema removed).

## D-042 — A split payment settles the oldest open invoice first
Date: 2026-09-25
Status: Final

Context: REDESIGN_VISION 4.4/8-item-2's "ثبت پرداخت" component lets one
Payment be allocated across several of a party's open invoices at once
(`RecordPaymentForm.invoices`, a multi-select), but the amount need not
equal the sum of what is owed on the ones picked — neither the form's own
validation (checks only that it does not *exceed* that sum) nor
`allocate_payment` (validates one allocation at a time) decides an order.

Decision: `apps.payments.views._RecordPaymentView` sorts the chosen
invoices by `invoice_date` ascending before allocating, and draws down the
payment amount against them oldest-first, exactly the same "take what one
line can absorb, carry the rest to the next" shape `consume_fifo` already
uses for stock (D-036) — one `allocate_payment` call per invoice touched,
inside the same `transaction.atomic()` as `record_payment` itself, so a
rejection from either service (e.g. the invoice was paid some other way a
moment ago) rolls back the whole payment rather than leaving it half
allocated. The sort is by the invoice's own date, not by which checkboxes
were ticked first in the browser, so the outcome cannot depend on DOM
order or a user re-ordering their clicks.

`SalesInvoice.outstanding`/`PurchaseInvoice.outstanding` (new properties,
`max(total - paid_amount, 0)`) are added alongside the existing
`paid_amount`/`payment_status` (D-025) rather than computed ad hoc in the
view or the form, so the Receivables list, the Payables list, the
"ثبت پرداخت" component's own over-allocation check, and this ordering logic
all read the exact same number.

Any amount left over once every selected invoice is fully covered stays an
unallocated `Payment` on that party's account (the form's own hint text
already says as much) — not an error, and not automatically applied to
some other, unselected invoice.

## D-043 — Money is whole Toman everywhere (supersedes D-013)
Date: 2026-09-26
Status: Final

Context: Sina's pre-Phase-D correction batch: "the entire application must
use Toman as the monetary unit" — not Rial with a Toman hint beside it. D-013
had stored whole Rial and treated Toman as display only (2.11 then showed
both side by side, acceptance scenario 14).

Decision: every money `BigIntegerField` (prices, costs, amounts, discount)
now holds **whole Toman** — the same columns, reinterpreted, no decimals.
Input, display, calculations, reports and the admin all speak Toman; the
word "ریال" appears nowhere in the UI. One presentation helper,
`apps.shared.utils.format_toman`, and one template filter, `toman`, replace
`format_rial`/`rial_to_toman`/`RIAL_PER_TOMAN` and the `rial`/`rial_toman`
filters; the "به ریال وارد شود" hint under every money input is gone.
D-032's "fixed Rial amount" discount is a fixed Toman amount.

Chosen over "keep Rial in the database, convert ×10 at every form and ÷10 at
every display" (Sina's call, 2026-09-26): one unit end to end means no
conversion point that can be forgotten, and every sum stays exact.

Migration safety: on 2026-09-26 every money-carrying table (products,
invoices, items, payment entries, payments, allocations, cheques, expenses,
layers, movements) held zero rows — the real data is still to be re-entered
after the 2026-09-25 flush — so nothing needed converting; the migrations are
label-only (`verbose_name`, no SQL). Leftover QA history rows
(`Historical*`, AuditLog payloads) keep the Rial numbers they were written
with; they describe deleted QA records and feed no calculation.

## D-044 — Stock changes through documents only (supersedes D-041; narrows D-017)
Date: 2026-09-26
Status: Final

Context: Sina: inventory should change through real business transactions —
a confirmed purchase adds, a confirmed sale removes — not through a manual
"اصلاح موجودی" or a separate "ثبت موجودی اولیه" page. Investigated before
removing: `cancel_sale`/`cancel_purchase` write `ADJUSTMENT_IN/OUT` movements
for their reversals (so those movement types must stay); `record_adjustment`
was the only writer of `InventoryConsumption.movement` and
`InventoryLayer.Source.ADJUSTMENT`; and the one legitimate non-invoice need
left is onboarding stock already on the shelf (6 real products still to be
re-entered) — without it that stock could only enter as a fake purchase,
inflating purchases and payables.

Decision (Sina's pick of the options offered, 2026-09-26):
- Manual adjustment is removed entirely: `record_adjustment`, its form, view,
  URL, template and button. The schema D-041 added only for it goes too —
  `InventoryConsumption.movement` (+ index + "exactly one source" CHECK;
  `sale_item` is NOT NULL again) and `InventoryLayer.Source.ADJUSTMENT` (the
  source CHECK is back to `opening_stock`/`purchase_item`). Tables were empty,
  so the NOT NULL could not fail; had an adjustment draw existed the ALTER
  would have failed and rolled back instead of dropping it.
- Opening stock survives only **at product creation**: optional "موجودی فعلی"
  quantity + unit purchase cost on the Inventory new-product page (and the
  admin *add* form), saved with the product in one transaction via the
  unchanged `set_opening_stock`. The separate opening-stock page is gone;
  once a product exists, only invoices move its stock. D-017's own rule
  (once, before any movement) is untouched — it just has no later entry
  point any more.
- `ADJUSTMENT_IN/OUT` are relabelled "برگشت لغو فاکتور - افزایش/کاهش": they
  are now only ever a cancellation's reversal. `AuditLog.EventType.
  RECORD_ADJUSTMENT` stays as a label for the rows logged before this.

Consequence, accepted: a physical loss, breakage or miscount has no entry
path any more; correcting one needs a new decision (e.g. a write-off
document), not a return of free-form adjustment.

## D-045 — Expense: no counterparty; the paying account is chosen explicitly
Date: 2026-09-26
Status: Final

Context: Sina: remove the Counterparty ("طرف حساب") field from the new-expense
form, and make the account selector show the real bank accounts so every
expense answers "which account paid this" — not a generic "نقدی" that an
untouched select silently falls back to. Bank accounts could until now only
be created in /admin/, so on a fresh install the selector offered nothing
but cash.

Decision: `Expense.related_person` is dropped (D-040's free-text
counterparty; zero rows existed). The expense form's `bank_account` is a new
`apps.payments.forms.PaymentSourceField`: a required choice of every active
BankAccount plus "نقدی (صندوق)" as an explicit last option, starting at
"— انتخاب حساب —" — cash stays possible (Sina's call: keep it, never as the
default) and still means `bank_account = null`, exactly as on Payment
(REDESIGN_VISION 2.6). The Bank Accounts module gains create/edit pages
(`BankAccountForm`: name, owner, account number; deactivation stays an admin
task), so accounts are managed where they are listed. Expense search runs
over reason/note.

## D-046 — A sales invoice defaults to full settlement into a chosen account
Date: 2026-09-26
Status: Final

Context: Sina: an ordinary sale is paid in full; the user should only say
which account received it, not build a payment row by hand. Cheques, credit
and split payments must stay possible. Before this, no payment rows meant
the whole invoice stayed on credit (4.3b).

Decision (Sina's pick, 2026-09-26): the new-sale form has an explicit
payment mode, `payment_mode` on `SaleInvoiceForm`:
- "تسویهٔ کامل" (default): one required `received_into`
  (`PaymentSourceField` — a real account, or cash chosen explicitly). The
  view ignores any payment rows and calls
  `apps.sales.services.plan_full_payment(invoice, account)`, which adds one
  `SalesPaymentEntry` for the server-computed `invoice.total` before
  `confirm_sale` — so the money is booked by the same path as any typed row
  (a Payment allocated to the invoice), never a second one.
- "تفکیکی / چک / نسیه": the existing rows, unchanged — whatever they leave
  unpaid stays credit, zero rows means fully on credit. Clicking
  "+ افزودن ردیف پرداخت" switches to this mode by itself.
Purchases are unchanged (not part of the request). The discount field moves
from beside the date into the totals block (subtotal → discount → final
total); it still only reduces the invoice total and profit — never stock,
FIFO consumption or layer costs.

## D-047 — htmx swaps a 422 form re-render
Date: 2026-09-26
Status: Final

Context: found in the pre-Phase-D browser pass (C.fix-1). Every htmx form
in the app — the quick customer/supplier/product forms and the shared
"ثبت پرداخت" form — answers a validation error with HTTP 422 and the same
form re-rendered with its Persian errors. htmx 2.0.4's default
`responseHandling` swaps no 4xx response, so all of those errors were
silently dropped: a duplicate name or an over-allocated payment simply did
nothing visible.

Decision: one `<meta name="htmx-config">` in `shared/base.html` makes 422 a
swapping, non-error response. The meta config merges shallowly, so the
whole `responseHandling` list is written out: htmx's own three defaults
(204 no swap, 2xx/3xx swap, other 4xx/5xx error, no swap) plus `422 → swap`,
placed before the generic 4xx/5xx rule. 422 stays reserved for exactly this
("the form you sent, back with its errors"); any other 4xx/5xx still
counts as an error and is not swapped into the page. The purchase page's
scoped `htmx:beforeSwap` handler from the correction batch is removed as
redundant.

## D-048 — An invoice discount is shared across its lines, pro rata
Date: 2026-09-26
Status: Final

Context: C.fix-3. The discount is invoice-level (D-032), but line profit —
and Reports' "فروش به تفکیک کالا", built from it — ignored it: the
per-product amount and profit columns summed to more than the sales-total
and gross-profit cards whenever an invoice had a discount, and products
usually sold at a discount looked more profitable than they are.

Decision (Sina's pick, 2026-09-26, over a separate "discounts" row in the
report or a footnote only): each line carries the share of its invoice's
discount proportional to its own line total —
`SalesInvoice.discount_allocation`, largest remainder in whole Toman so the
shares always sum to exactly `discount_amount` (floor each share, give the
leftover Toman one each to the biggest remainders, ties by item pk so an
invoice always splits the same way). `SaleItem.discount_share` /
`net_total` expose it; `SaleItem.profit` is `net_total − FIFO cost`, so an
invoice's line profits sum to its `profit` exactly. Derived on every read,
never stored (D-025) — no schema change. `reports.sales_by_product` walks
invoices (lines share their prefetched invoice) and reports net amount and
profit, so its columns equal `sales_total` and `gross_profit`. The sales
detail page shows a "سهم تخفیف" column when there is a discount; the
customer-facing print page is unchanged (still one invoice-level discount
line). Stock, FIFO consumption and layer costs are untouched, as before.

### D-049: Static files served by whitenoise
- Status: Superseded. Removed by D-051 along with the rest of the deployment setup.

### D-050: Visual identity is IBM Carbon-inspired
- Status: Final
- Date: 2026-09-30
- Decided by: Claude, on Phase D's own brief (pick or blend, ask only if not obvious)
- Decision: The app's look follows IBM's Carbon language (`docs/design/ibm/DESIGN.md`):
  flat near-square chrome (radius 2-4px), thin 1px borders instead of shadows
  (only overlays keep one), Carbon's cool-grey ramp, one blue accent
  (`--accent-600: #0f62fe`), dark `#161616` side nav with a blue marker on the
  active item, light page background `#f4f4f4`. Font stays Vazirmatn (IBM Plex
  has no Persian). Implemented by changing the token block in
  `apps/shared/static/shared/css/app.css`; component rules were not touched.
- Options considered: Stripe (financial but gradient/marketing-led), Linear
  (dark-first), PostHog (playful illustration).
- Rationale: dense, numbers-first internal tool; Carbon is built for data
  tables and forms, and its flat style matches the existing token structure.
- Affects: `app.css` only. Reversible by editing the `:root` tokens.
- Not done: dark mode (internal tool, not asked for).

### D-051: Deployment and SHADOW are out of scope
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Decision: The repo carries no deployment work and no SHADOW gate. Removed:
  `docs/deployment.md`, the production-hardening block and whitenoise
  (middleware + STORAGES) in `core/settings.py`, `gunicorn`/`whitenoise` in
  requirements.txt, the production keys in `.env.example`, roadmap task 3.4
  (the 3-day parallel run against the paper ledger), and the "Hard gates"
  section of business-rules.md. Supersedes D-049.
- Note: older entries (D-014, D-016, D-017, D-019, D-020) still mention SHADOW
  or a future deployment as historical rationale; they are not rewritten.
  The app still reads DEBUG/ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS from `.env`.

### D-052: A sale can never exceed the stock on hand
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Decision: `confirm_sale` rejects any line above the available stock, for
  every user including a superuser; the new-sale form shows the same error
  before submit and disables the submit button. The missing goods have to be
  bought first. Supersedes D-016 and D-021; D-034's list of superuser-gated
  actions shrinks to cancellation only.
- Rationale: goods sold before the purchase invoice existed made stock
  negative and left those units without a cost basis; Sina wants the ledger
  never to be in that state.
- Note: `SaleItem.uncosted_quantity`, the Dashboard's negative-stock row and
  the `shortages` element of `confirm_sale`'s return value are kept but can
  no longer be triggered by a new sale (the tuple is always `(invoice, [])`).

### D-053: A purchase invoice settles like a sale (mode + account)
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Decision: The new-purchase form gets the same payment mode as the new-sale
  form (D-046): "تسویهٔ کامل" (default) with one required paying account, or
  "تفکیکی / چک / نسیه" with typed rows (the rest stays credit).
  `purchasing.services.plan_full_payment(invoice, bank_account)` books the
  full-settlement row from the server's own `total_amount`. Payment rows show
  the cheque number, issuing bank and due date only for the cheque method
  (dropped server-side for other methods). Amends D-046's "purchases are
  unchanged".

### D-054: Rules settled by the full QA pass
- Status: Final
- Date: 2026-09-30
- Decided by: Claude, from defects found while testing every page and scenario
- Decision:
  - Every Jalali date field accepts years 1380-1450 only. A Gregorian date typed
    by mistake ("2026/09/30" reads as Jalali 2026) used to date a document
    centuries away.
  - A deactivated product cannot be sold or bought, even by a hand-made POST.
  - Deactivated customers/suppliers stay listed on Receivables/Payables while
    they owe or are owed money; deactivating never hides a balance.
  - The dashboard's cheque widget includes pending cheques already past their
    due date, and a separate widget lists pending cheques still missing a due
    date or number (they can never fall inside a "due soon" window).
  - Documents numbers (invoice, cheque) are shown without digit grouping.
  - Login accepts Persian digits and stray spaces in the phone.
  - Enter inside an invoice form's text/number box does not submit it.
  - The customers list "همه" option really means everyone.

### D-055: Cancelling an invoice gives its money back
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Context: `cancel_sale`/`cancel_purchase` reversed stock but left the invoice's
  payments booked: the money stayed in the bank balance and the customer's or
  supplier's account showed a credit nobody could see (found by the QA pass).
- Decision: Inside the same transaction, cancelling an invoice books, for every
  payment allocation still standing on it, ONE refund `Payment` in the opposite
  direction (customer refund = OUT, supplier refund = IN), for exactly the
  allocated amount, same bank account (or cash) and same party, dated the day of
  the cancellation, `is_reversal = True`, and links it on the allocation
  (`PaymentAllocation.reversal_payment`). The original payment and allocation are
  never edited or deleted (D-014/D-023). A payment shared with other invoices is
  refunded only for this invoice's part; an unallocated prepayment is untouched.
  Pending cheques of the invoice never became money and are cancelled; cleared
  cheques stay cleared (their payment is refunded like any other); bounced stay
  bounced. `paid_amount` counts only allocations that were not reversed. New
  audit event `reverse_payment`.
- Schema: `Payment.is_reversal`, `PaymentAllocation.reversal_payment` (one-to-one),
  and `payment_party_matches_direction` now lets a reversal run against the party's
  usual direction (still at most one party).
- Consequence: bank balances, the customer statement (refund = debit line), the
  bank ledger and reports show the refund; cancelling is now the only action that
  moves money without a person typing an amount, which is why it stays
  superuser-only.

### D-056: Clearing a cheque needs an explicit account
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Decision: The cheque detail page's "وصول چک" carries a required account picker
  (`ClearChequeForm`, a `PaymentSourceField`), pre-selected with the cheque's own
  account. A real account, or cash chosen on purpose, must be answered; a cheque
  with no account can no longer slip into cash silently (D-045's rule, applied to
  clearing). `clear_cheque` without an account argument uses the cheque's own account
  and refuses when it has none; `bank_account=None` means cash on purpose.

### D-057: Expense receipts are PDF or images, at most 5 MB
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Decision: `Expense.document` accepts only .pdf, .png, .jpg/.jpeg and .webp, up to
  5 MB, and the file's leading bytes must match its extension
  (`apps/payments/validators.validate_receipt`). Pages a browser could run (.html,
  .svg), executables and disguised files are refused, on the form and in /admin/.

### D-058: Sign-in is throttled
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Decision: Failed sign-ins are counted per typed phone number (5) and per client IP
  (30) in Django's cache; over the limit, further attempts get HTTP 429 with a "try
  again in 15 minutes" message even with the right password, until 15 minutes pass
  without a new failure. A success resets that phone's counter. The count is keyed on
  what was typed, so an unknown number locks exactly like a real one (no account
  enumeration). Persian digits and stray spaces count as the same phone.
- Limit: the counters live in the per-process cache (`apps/users/throttle.py`); they
  reset on restart and are not shared between server processes. Point `CACHES` at a
  shared cache if the app ever runs as several processes.

### D-059: The Suppliers list can show inactive suppliers
- Status: Final
- Date: 2026-09-30
- Decided by: Sina
- Decision: Like the Customers list, the Suppliers list has a search box (name/phone)
  and an active / inactive / all filter (default active); inactive rows carry a
  "غیرفعال" badge. Deactivating a supplier still only hides it by default.

### D-060: One-click backup of the whole business
- Status: Final
- Date: 2026-10-01
- Decided by: Sina
- Decision: A superuser-only page (sidebar "پشتیبان‌گیری", `/backup/`) has a POST button
  that builds and streams one zip: `manifest.json` (time, row counts), `database.json`
  (Django `dumpdata` of every app model, natural keys; sessions, content types,
  permissions and the admin log are left out) and `media/` (uploaded receipts).
  Nothing is stored on the server by the page. `manage.py backup_db` writes the same
  zip to `BACKUP_DIR`; `manage.py restore_db FILE` loads it into an EMPTY migrated
  database only (refuses otherwise) and replaces the numbering rows migrate seeds.
- Why JSON and not pg_dump: it needs no binary on the host and survives a PostgreSQL
  version change. Verified by restoring a real backup into a scratch schema: every
  model's row count matched.
- Consequence: the file holds every amount, customer address and password hash, hence
  POST-only (a link or prefetch can never trigger it).
- Amended 2026-10-01 (Sina): any signed-in user may back up, not only superusers (there
  are no roles in this app); the menu link shows for everyone.

### D-061: The printed sales invoice is a company document with stamp boxes
- Status: Final
- Date: 2026-10-01
- Decided by: Sina
- Decision: `sales/print.html` is an A4 "صورت‌حساب فروش کالا": logo box, title, number and
  date; seller and buyer boxes; numbered item table; totals with the amount in words
  (`apps/shared/words.py`); paid/outstanding when confirmed; two boxes "مهر و امضای
  فروشنده / خریدار"; a diagonal watermark for cancelled ("باطل شده") and draft invoices.
  The issuer's details come from `settings.COMPANY`, filled from `COMPANY_*` keys in
  `.env`, so they change without a code update; an empty key drops that line. The
  purchase print stays the plain internal copy. Still no PDF generation: the browser's
  print dialog is the mechanism.
- Open: Sina will supply the real company details (and logo) later.

### D-062: Visual identity moves from IBM Carbon to the hostiran.net look
- Status: Final
- Date: 2026-10-01
- Decided by: Sina
- Decision: Replaces D-050. Navy-tinted neutrals (`#0a1f44` ink, `#213368` action), a
  navy gradient sidebar/sign-in/dashboard banner with a cyan (`#26a9e0`) highlight and
  a dotted glow, blue `#0077ff` for links/focus/selection, pale blue-grey page with white
  rounded cards (radius 8 controls / 12 buttons / 16 cards), full-border white inputs,
  pill badges, flat surfaces (shadow only on overlays). Vazirmatn stays as the font
  (hostiran's Dana is a licensed font). Still only tokens on `:root` plus a few
  component rules in `app.css`; no new dependencies.

### D-063: The app can be installed and updated on a host (amends D-051)
- Status: Final
- Date: 2026-10-01
- Decided by: Sina
- Decision: D-051 removed the old deployment machinery; Sina now wants to host the app,
  so a minimal host-agnostic path is back (SHADOW stays out): WhiteNoise serves the
  collected static files (`STATIC_ROOT`), production-only cookie/proxy security settings
  read from `.env`, `BACKUP_DIR`, and `manage.py update` (safety backup -> migrate ->
  collectstatic -> `check --deploy`) as the single command after every code update.
  `deploy/UPDATING.md` (Persian runbook) and `deploy/passenger_wsgi.py` are the only
  hosting files. `.env`, `media/` and `backups/` are never part of an update.
- Found while testing a fresh database: `shared.0003_seed_role_groups` crashed on an empty
  DB (content types do not exist yet during `migrate`); it now skips the seed there (the
  roles were retired long ago). Without this no new host could have been installed.
- Hosting needs Python >= 3.12 and PostgreSQL; MySQL is not supported.

### D-064: Invoice numbers read like real invoice numbers: year/running number
- Status: Final
- Date: 2026-10-01
- Decided by: Sina (on recommendation)
- Context: D-022's numbers started at 9956001, which looked arbitrary on a printed invoice.
- Decision: A number is "<Jalali year>/<running number, at least 4 digits>", e.g.
  `1405/0042` (shown ۱۴۰۵/۰۰۴۲). Sales and purchases count separately, and the running
  number restarts at 1 every Farvardin (the year is the Jalali year of the day the invoice
  is confirmed). `DocumentSequence` is now one row per (`doc_type`, `year`), created on
  first use and locked with `select_for_update` (D-022's concurrency guarantee is
  unchanged); the old single counter is year 0 and no longer used. The DB still refuses
  two confirmed invoices with the same number.
- Existing invoices keep the number they already have (9956001...): their numbers are
  written into ledger notes that are append-only (D-014), so they are not renumbered.
- Schema: migration `shared.0016` (adds `year`, unique on `doc_type`+`year`; drops unused
  legacy counters).

### D-065: The menu is a drawer opened by a hamburger button
- Status: Final
- Date: 2026-10-01
- Decided by: Sina
- Decision: The permanent sidebar is gone. A hamburger button at the start of the header
  opens the module list as a drawer sliding in from the right over a dim overlay, on
  every screen size; closed, nothing of it is shown or reachable by keyboard. Overlay, X
  and Esc close it; it is closed on every page load (no remembered state). Small script:
  `shared/js/nav_drawer.js`.

### D-066: The database engine is chosen by `DATABASE_URL`; SQLite is allowed for a host without PostgreSQL
- Status: Final
- Date: 2026-10-01
- Decided by: Sina
- Context: The first host (hostiran "هاست فریم‌ورک") offers PostgreSQL only on the dearer "پلاس" plan.
- Decision: Nothing in the code is PostgreSQL-only, so `DATABASE_URL` alone picks the engine:
  `postgres://...` (development, `main`, any host with PostgreSQL) or `sqlite:////abs/path/db.sqlite3`
  (the `deploy` branch's target). On SQLite, `settings.py` turns on `transaction_mode=IMMEDIATE`
  (every write transaction takes the database's write lock first), which keeps the no-duplicate-number
  and no-oversell guarantees that `select_for_update` gives on PostgreSQL (8 threads x 10 numbers: 80
  unique). The whole QA suite, the fuzz run and a restore of a PostgreSQL backup were run on SQLite
  and pass.
- Limits: one writer at a time (fine for a few users, not for heavy parallel load); the file must live
  outside any web-served folder; MySQL/MariaDB is NOT supported (partial unique constraints are ignored there).
- The `deploy` branch is `dev` plus host-specific files only (`passenger_wsgi.py` at the root, a SQLite
  `.env.example`, the host runbook); bring in new work with `git merge dev`.

### D-067: A bank account is either a card reader or a current account
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: `BankAccount.account_type` = `pos` (کارت‌خوان) or `current` (حساب جاری), default `current`
  (every account that existed before is a current account). The Bank Accounts page shows the two kinds
  as separate sections. Card payments will only be accepted into `pos` accounts, transfers/cheques/
  expenses only through `current` ones (D-069).

### D-068: A cheque records who issued it, apart from the bank
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: `Cheque.issuer` («صادرکنندهٔ چک», free text, optional) is added next to the existing
  `bank_name`, and mirrored on `SalesPaymentEntry`/`PurchasePaymentEntry` so it is typed once on the
  invoice and copied onto the cheque. Shown on every page that lists or details a cheque.

### D-069: Cash is gone; money moves by card reader, bank transfer or cheque
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Context: The business never handles cash through the system; "نقدی" only confused the payment screens.
- Decision: No form offers cash any more. Receiving: card reader (a `pos` account), bank transfer (a `current`
  account), cheque. Paying out: bank transfer (`current`) or cheque only — a card reader cannot pay anyone.
  Full settlement ("تسویهٔ کامل") = card, transfer or both at once (amounts must sum to the server's own
  invoice total; one amount blank takes the rest). Split mode rows are card / transfer / cheque; whatever
  they leave unpaid is credit (نسیه) and needs `credit_due_date` (new nullable field on both invoices; a due
  date on a fully covered invoice is dropped). Account-vs-method is enforced in `validate_entry_account`
  (service) and mirrored in the forms; cheque clearing needs a current account.
- Legacy: payments/entries written before this (`bank_account` null, method `cash`) stay valid and readable
  ("نقدی" / "نقدی (قدیمی)"); nothing is rewritten. `PaymentSourceField` is replaced by `AccountChoiceField`.

### D-070: A sales discount can be typed as a percent
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: The new-sale form has a Toman / percent switch for the discount. The percent (0–100, two decimals)
  is turned into whole Toman by `percent_to_amount` (rounded down) once the lines exist; only the Toman
  figure is stored — D-032/D-048 are untouched (invoice-level, pro rata across lines, never stored as a percent).

### D-071: Receivables and Payables are split by how the money will arrive/leave
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: Both pages show (1) pending cheques, each with due date, issuer, bank and pass/bounce buttons
  (for customers «وصول شد», for suppliers «پاس شد»), (2) credit on account per invoice with its due date and a
  pay-all-or-part form (`PayInvoiceForm`; at most the credit part, cheques are settled by clearing them), and
  (3) the per-party totals with the general payment form. The credit part is derived
  (`get_credit_items`: invoice outstanding minus its pending cheques), never stored (D-025).

### D-072: An expense is paid by transfer, by cheque, or on credit
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: `Expense.payment_method` = transfer (as before: Payment OUT from a current account at once),
  cheque (a pending OUT `Cheque` with no customer/supplier, linked by `Cheque.expense`; clearing it links
  the payment to the expense) or credit (nothing booked; `due_date` required; later `pay_expense`).
  `Expense.payment` is therefore nullable; paid = a payment exists (derived). Cancelling an unpaid expense
  needs no reversal. Totals/reports still count an expense on its own date, paid or not.

### D-073: Fixed, repeating costs (rent, bills) with reminders
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: `RecurringExpense` (reason, usual amount, every N days/months — months are Jalali —, next due
  date, remind N days ahead, active). It books nothing: «ثبت پرداخت» opens the expense form pre-filled and, once
  recorded, the next due date advances one period; «رد کردن» skips a period (audit-logged). Deactivated, never deleted.

### D-074: The dashboard shows next week's payments instead of recent activity
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: «پرداخت‌های هفتهٔ آینده» lists, soonest first and including anything overdue: cheques we issued
  (supplier or expense), credit expenses, fixed costs whose reminder window opened, supplier credit due.
  The activity feed leaves the dashboard (its own page stays).

### D-075: Wholesale and retail prices, chosen once on the sales invoice
- Status: Final, except that D-081 drops the sale-type choice on the invoice and changes what the two prices mean
- Date: 2026-10-03
- Decided by: Sina (the idea); design chosen after comparing 12 independent proposals judged on owner fit,
  live-data safety, correctness/tests, extensibility and counter UX.
- Decision: `Product.default_selling_price` keeps its name and now means the RETAIL price;
  `Product.wholesale_selling_price` is new (0 = unset, then retail is suggested). `SalesInvoice.price_tier`
  (`retail` default / `wholesale`) is picked at the top of the form and frozen with the invoice (D-014); old
  invoices read as retail (there was only one price). `SaleItem.unit_price` stays the only stored line price
  (a snapshot). One service, `update_selling_prices(product, user, retail=None, wholesale=None)` (None = leave
  alone), logs one `change_selling_price` row per changed tier (payload has `tier`); `update_selling_price`
  remains as the retail-only wrapper. `Product.price_for(tier)` is the single reader.
- Counter behaviour: both prices ride on each search result (`data-price-retail/-wholesale`), so switching
  the sale type needs no request. Switching reprices lines still on a tier price and never overwrites a
  price the cashier typed (a line is "manual" when its price differs from the tier price — derived from the
  numbers, no stored flag); the page says how many lines were kept. A blank price is filled server-side from
  the invoice's own tier. Inventory edits both prices on the product page (with history); a product whose
  wholesale price is unset or equal to retail is flagged.
- Reports: «فروش عمده و خرد» card (invoices, net sales, discount, profit, margin per type) that adds up to
  `sales_total`/`gross_profit` exactly.
- Rejected: a price-list table or append-only price ledger (heavier than two fixed prices), a customer-level
  default tier, per-line tier, quantity breaks, renaming the retail column (rebuilds the table on SQLite).

### D-076: A product is counted in pack or carton; the two are separate products
- Status: Superseded by D-081 (2026-10-04)
- Date: 2026-10-03
- Decided by: Sina
- Decision: `Product.unit` is one of `بسته` / `کارتن` (the stored value is the Persian word, so every page that
  prints it is unchanged; existing free-text units were normalised in migration `products.0007`). The same
  goods sold in both units are two products with their own stock, FIFO layers, costs and prices — no
  pack-per-carton ratio exists or is needed. Inventory shows the pack and carton products in two sections,
  each with its own stock total (never added together).

### D-077: Scheduled backups on the host use `backup_db --keep N`
- Status: Final
- Date: 2026-10-03
- Decided by: Sina
- Decision: The host's one SQLite file is protected by a cPanel cron job running `manage.py backup_db --keep 14`
  daily (the command prunes only files named `paper-plus-backup-*.zip` in the target folder). Setup steps are in
  `deploy/HOSTIRAN.md` (deploy branch). Copying a backup off the host stays a manual weekly habit.

### D-078: Full settlement is ticked per method; a single card reader is the default
- Status: Final
- Date: 2026-10-04
- Decided by: Sina
- Decision: on the full-settlement panel of a sales/purchase invoice, «کارت‌خوان» and «حواله بانکی» are tick boxes
  (`use_pos`, `use_transfer`). Only a ticked method shows its fields and counts; an unticked method's account and
  amount are ignored by the server even if sent. Both ticked keeps the two-amount rule of D-069. When exactly one
  active card-reader account exists the account is not asked for: the page shows its name, and the form falls back
  to it if none is posted; with several the choice stays. Card rows in split mode preselect a lone card reader too.
  Purchase invoices still have no card option (D-069: a card reader only receives money).

### D-079: One dashboard card for receivables and payables
- Status: Final
- Date: 2026-10-04
- Decided by: Sina
- Decision: «پرداخت‌های هفتهٔ آینده» (D-074) and «نیازمند توجه» are replaced by one card, «مطالبات و بدهی‌ها», with two
  columns. Receivables: cheques we hold (IN) and customer credit (نسیه). Payables: cheques we issued, and credit
  (supplier credit, credit expenses, fixed costs). Each group lists what is overdue or due within 10 days, soonest first,
  with group, column and overdue totals. Money settled by card reader or transfer is not owed and never shown.
  Cheques missing a number or due date stay a one-line notice (they have no date to place them); the
  negative-stock block is gone with D-052. `get_upcoming_receivables` mirrors `get_upcoming_payments`.

### D-080: USD rate history, read from an Iranian price site, frozen on each invoice
- Status: Final
- Date: 2026-10-04
- Decided by: Sina (the need; the source and the moment were left to the implementer)
- Decision: `shared.ExchangeRate` is an append-only log of rate reads (`rate` in Toman or NULL, `rate_date`,
  `fetched_at`, `source`, `status` ok/failed, `error`); a DB check makes ok ⇒ rate > 0 and failed ⇒ no rate, so
  a broken source cannot put a made-up or zero number anywhere, and old rows are never edited. Source: the live
  price on tgju.org's dollar page (Rial ÷ 10), with tgju's JSON history table as fallback; both are tried in order
  starting from `USD_RATE_SOURCE` (`USD_RATE_URL` overrides its address). A read far from the last valid rate
  (over 2x either way) is stored as a failure, not a rate. stdlib `urllib` only, 8 s timeout.
- Reading: `manage.py fetch_usd_rate` from a cron job every few hours, and a «بروزرسانی نرخ» button on the Inventory
  and Reports cards. Invoice confirmation never makes a network call.
- Snapshot: `confirm_sale` / `confirm_purchase` store the latest valid row in `SalesInvoice.usd_rate` /
  `PurchaseInvoice.usd_rate` (null for older invoices and when no rate was ever read). Detail and print pages show
  the rate with the time it was read; a later rate never changes a confirmed invoice.
- Cards show the newest valid rate with its age, flag it «قدیمی» after `USD_RATE_STALE_HOURS` (12), and say when the
  last attempt failed. Unknown: whether the shared host allows outbound HTTPS; test from the host before relying on it.

### D-081: One product, two trade units: pack (base) and carton
- Status: Final
- Date: 2026-10-04
- Decided by: Sina
- Decision: a product is ONE product again. Its base unit is the pack; `Product.pack_per_carton` (default 5, editable
  per product, never below 1) says how many packs make a carton. Stock, FIFO layers, movements, consumptions and every
  cost are counted in packs only, so there is one stock figure and FIFO code is unchanged. The carton + pack split is how
  a quantity is typed and shown: an invoice line (`SaleItem`/`PurchaseItem`) has `cartons`, `pack_per_carton` (a snapshot,
  so changing the ratio later never rewrites an old line) and `carton_price`; `quantity` stays the stored total in packs;
  loose packs = quantity - cartons x ratio; `line_total = cartons x carton_price + loose packs x unit_price` (`unit_price`
  = price of one pack), so a carton priced as a whole is never rounded through a per-pack figure. A user types cartons
  and packs in one row; one row per product per invoice stays.
- Prices: `default_selling_price` = retail = price of one pack; `wholesale_selling_price` = wholesale = price of one whole
  carton (0 = unset, suggested as pack price x ratio). A sales line prices cartons at the carton price and packs at the
  pack price, both editable, a blank one filled from the product. The sale type on the invoice form is gone;
  `SalesInvoice.price_tier` is set when the invoice is confirmed (wholesale if any line has cartons) so the
  wholesale/retail report keeps working and old invoices read as before.
- Average vs FIFO: inventory shows «میانگین قیمت خرید» = Σ(remaining x layer cost) / Σ(remaining) over active layers only
  (`get_average_cost_map`), for reading stock. Cost of goods, profit and layer consumption stay on real FIFO
  (`consume_fifo`); no calculation reads the average. The product page shows both, plus the next FIFO layer cost.
- Display: stock and quantities print as «۶ کارتن + ۴ بسته (۳۴ بسته)» (inventory, product search, invoice rows with the
  stock left after the line, detail and printed invoices; the printed line shows what was typed). The negative-stock
  card/section is removed from Inventory and the dashboard; oversell protection in forms and `confirm_sale` is unchanged.
  The pack/carton sections and the unit column are gone. No «empty carton» item exists (cartons = 0 just means none).
- Purchase line cost: the FIFO layer cost per pack is the line's money / its packs, rounded to the nearest Toman
  (`PurchaseItem.unit_cost`); invoice totals stay exact.
- Existing data: migration `products.0009` turns a pack product's old wholesale price into a carton price (x ratio; a
  price that only equalled retail becomes unset). Carton-counted products are converted by a command, never guessed:
  `inventory_unit_report` (read-only) shows every product, uneven costs and look-alike pairs; the owner writes a map of
  merges; `convert_units [--map FILE] [--dry-run] [--allow-rounding]` rewrites stock, layers, movements, consumptions
  and invoice lines into packs in one transaction (invoice totals must stay exactly equal, stock must match, uneven
  costs are refused unless rounding is allowed and the drift is printed). `Product.unit` stays until every database has
  been converted, then a later migration drops it.

### D-082: Freight on a purchase invoice
- Status: Final
- Date: 2026-10-04
- Decided by: Sina (paid to the same supplier, split by quantity)
- Decision: `PurchaseInvoice.freight_amount` (Toman, default 0) is entered by ticking «کرایه بار» on the purchase form.
  It is part of `total_amount` (= lines + freight), so it is part of what the supplier is owed and of every payment,
  payable and report figure that already reads `total_amount`. At confirmation it is spread over the lines in
  proportion to their packs (`allocate_freight`, largest remainder, exact sum) and stored per line in
  `PurchaseItem.freight_share`; the FIFO layer cost and the purchase movement price per pack become
  (line goods + freight share) / packs, rounded to the nearest Toman (`PurchaseItem.unit_cost`; `carton_cost` = the same
  per carton). The invoice detail shows items total, freight, total and the landed cost per pack and per carton; the
  print shows the freight line. Cancelling keeps working because it reads the stored layer. Unticked = the amount is ignored.

### D-083: Data-UI audit fixes (identity unchanged)
- Status: Final
- Date: 2026-10-04
- Decided by: Sina (audit by ten read-only agents, then verified in the browser)
- Decision: palette, fonts and card style stay. Fixes: (1) `.num` is RTL, so «number + unit» reads with the unit on the
  left of the figure everywhere; a negative figure keeps its minus on the left of the digits (`_keep_sign_left`);
  numeric cells never wrap. (2) One status vocabulary: `{% status_badge kind value label %}` and `{% flag_badge tone label %}`
  in `paper.py` hold the status-to-tone map (paid green, partial amber, unpaid red, cancelled muted/struck, bounced solid red,
  pending cheque blue, overdue red); badges carry a dot besides colour; no template maps a status to a class itself.
  (3) Small text uses `--*-700` tokens (>= 4.5:1), links use `--accent-700`, one global `:focus-visible` ring.
  (4) Invoice detail pages open with a summary strip: total, paid, remaining, status. (5) The growing lists (sales, purchases,
  expenses, inventory, customers, suppliers, cheques) share one pager (25 per page, `{% pager %}`) and key columns sort
  through a whitelisted `sort`/`dir` (`{% sort_th %}`); receivables/payables boards, bank-account cards and fixed costs
  stay unpaged, being bounded action boards with inline forms. (6) Product search rows have two levels,
  separators, price, stock grade and a focus state. (7) The invoice line grid gets a mid-width two-row layout (721-1100px).
- Not done on purpose: no change to money logic; the audit claim that numeric table columns are misaligned was rejected
  (right-aligned cells already stack the units digit).

### D-084: Fifty-critic UI audit, batch 1 (global fixes)
- Status: Final
- Date: 2026-10-04
- Decided by: Sina (50 read-only critic agents, one angle each; findings verified, then applied in the browser)
- Decision: identity and drawer menu (D-065) stay. Applied: (1) stacked `.card`s get a gap, card edge/surface tokens
  darken one step and `--shadow-sm` is a hairline; form controls use `--control-border` (3:1); stat-card stripe is an inset
  shadow (no crescent corners). (2) Tabular figures on the whole body (Persian digits are proportional), no letter-spacing
  on Persian labels, h1 weight 700, nothing below 12px. (3) Buttons: real `:disabled`, `:active`, and `.btn--danger` on every
  cancel/bounce; focus ring on `--accent-700` (accent-500 only on navy); selected date/preset on `--accent-700`. (4) Fields:
  `.field--invalid` + `aria-invalid`, alerts have `role=alert`, flash messages are a live region with a side stripe. (5) New
  `shared/js/ui.js`: failed htmx calls and an expired session show a toast instead of silence or a login card in a dropdown;
  Persian/Arabic digits typed into numeric boxes become Latin. Numeric boxes are `NumericInput` (`type=text`,
  `inputmode=numeric`): `type=number` silently dropped Persian digits. (6) Error pages 404/403/CSRF/500 exist, standalone,
  Persian. (7) Invoice form: product search picks with Enter, focus moves to cartons then back to the next row's search,
  editing the name after a pick clears the stale product, results close on Esc/outside click, double submit is blocked,
  confirm bar is sticky, live totals use the same thousands separator as the server. (8) Date picker reopens on click and
  ArrowDown, flips above the input when low, bigger cells on touch. (9) `_STATUS_TONES["invoice"]` was keyed `active`
  (a dead key; real values are draft/confirmed/cancelled): fixed. Lists show the document status only when it is not
  confirmed, a cancelled row is dimmed with no payment badge, and an empty filtered list offers "clear filters" instead of
  "register your first invoice". (10) Inventory list: search (`q`), in-stock filter, out-of-stock count and badge, name and
  code on two lines. (11) Dashboard: an attention strip for overdue/incomplete first, month figure leads each tile with
  today beneath, net profit tile is primary and red on loss, tiles that are links are whole-tile links, dues card retitled.
- Batch 2, same decision: expense receipts are a real link; the expense form is narrow with method cards and tinted panels;
  user-activity range and filter forms carry each other's values; filter forms keep the chosen sort and show «clear filters»;
  reports: `fa_percent` (was truncating +12.9% to +12), cost cards no longer paint a rise green, net profit is the primary
  tile, new presets «ماه قبل» and «امسال»; oversold stock reads «منفی ...»; bank cards put the name first and the whole card
  links, balance strip on the detail page; supplier detail opens with a debt tile; tables always sit in `.table-card`
  (scroll inside the card on phones, the table keeps its roles); overdue dues rows are tinted; cheque detail words
  pass/clear by direction; customer page has «فاکتور فروش جدید» (`/sales/new/?customer=`) and the invoice links to its
  customer; sidebar marks the current page (`aria-current`, edge) and the drawer makes the page inert; login at 16px;
  static assets cache one day (`STATIC_MAX_AGE`), the font is preloaded, print waits for the font.
- Not done on purpose (needs Sina): desktop permanent sidebar (contradicts D-065); merging the customer and date cards on
  the sale form; one anatomy for all detail pages; a keyboard-navigable calendar; thousands separators inside inputs;
  required-field markers; admin theming.

### D-085: Two-hundred-critic UI audit (ease, detail, design)
- Status: Final
- Date: 2026-10-04
- Decided by: Sina (asked for 100 ease-of-use, 50 fine-detail and 50 design findings, all to be fixed; ease must never remove a capability)
- Decision: 196 critics (100 ease, 50 detail, 46 design; the design set has 28 screens + 18 themes, not 50) each wrote one finding;
  13 implementers, each owning a file group, applied 147 and merged 37 duplicates. Everything is presentation: templates, CSS, JS,
  template tags, extra read-only context in views. No model, migration, service or data-writing endpoint changed. Highlights: sticky
  invoice dock with a live "what will be posted" sentence, remembered payment choices (localStorage, applied only on a fresh form),
  due-term chips, discount segmented control, customer type-ahead, cheque shortcut row, named cancel/bounce dialogs, print in place,
  Ctrl+K quick-jump palette (pages and actions only), compact-table switch, record-cards for tables on phones, ledger tables, hero
  bands and split bars on dues/bank/supplier pages, KPI compare lines, reports profit bridge, brand mark, empty-state component,
  sort/pager/badge/select/checkbox details, error pages, toasts, print rules. CSS from the 13 groups sits in app.css under
  "UI audit 200" headers (about 160 KB; consolidation is a later task).
- Not done on purpose: 64 deferred entries in `docs/UI_AUDIT_200_DEFERRED.md` (CSV export, reissue-invoice copy, remembered last
  backup, server-side global search, all-dates search default, two-column sale workbench, invoice-summary partial rewrite, and similar).
  Each needs Sina's decision before work starts.

### D-086: Sales invoices are numbered by day and Persian letter
- Status: Final (amends D-064 for sales; purchases keep D-064)
- Date: 2026-10-04
- Decided by: Sina
- Decision: a sales invoice number is "<letter>/<Jalali yyyymmdd of the invoice date>": the first sale of 12 Mehr 1405 is
  `الف/14050712`, the second `ب/14050712`, and so on through the 32 letters of the Persian alphabet. After «ی» the
  alphabet starts again with a round number (Sina's choice): 33rd = `الف2/14050712`, 65th = `الف3/...`. The day is the
  invoice's own date, so a backdated invoice takes its own day's next letter. `DocumentSequence` gains `day` (Jalali
  MMDD; 0 = a whole-year counter) and is unique on (`doc_type`, `year`, `day`); one row per sales day, created and locked
  exactly like D-064's rows. Purchases stay `1405/0001`.
- Display: digits are stored ASCII and shown Persian (`fa_digits`). A lettered round needs an Arabic letter mark
  (U+061C) between its digit and the slash, or the bidi algorithm glues the digit to the date; it is added on display
  only (`display_document_number`), never stored. The sales list search accepts Persian digits.
- Existing invoices keep their numbers (`1405/0001`, `9956001`): they are written into append-only ledger notes (D-014).
- Schema: migration `shared.0019`.

### D-087: Party credit: money beyond the open invoices is kept on purpose, shown, and used first
- Status: Final (amends D-042)
- Date: 2026-10-04
- Decided by: Sina (the "combined" option, after the bug was reproduced)
- Context: a payment could be recorded for a customer with nothing open (or with no invoice ticked); it reached the
  bank balance and the statement table but no balance figure (customer card, lists, Receivables, dashboard) and was
  never used by the next invoice, so the customer was in effect billed twice. Same on the supplier side.
- Decision:
  - «ثبت پرداخت»: with no invoice ticked, the amount settles every open invoice oldest first (D-042 left it
    unallocated). Ticked invoices still cap the amount. What is left beyond all open invoices is accepted only with
    the new tick «مازاد به‌عنوان بستانکاری (پیش‌دریافت) / پیش‌پرداخت ثبت شود»; otherwise the form refuses it.
  - Credit = Σ unallocated amount of the party's non-reversal payments in its normal direction (`get_party_credit`,
    `get_credit_payments`, `get_credit_balances`); derived, never stored (D-025). A refund (D-055) is never credit.
  - `confirm_sale` / `confirm_purchase` call `apply_party_credit` first: oldest credit payment first, one ordinary
    `allocate_payment` each, audit event `apply_credit`. Payment rows may then cover only total - credit; a due date is
    needed only if something is still unpaid. `plan_full_payment` books total - credit (nothing when credit covers all).
  - Shown: customer/supplier page (own card), customer/supplier lists (badge), Receivables «بستانکاران» and Payables
    «پیش‌پرداخت به تأمین‌کننده» sections, and a notice on the new invoice form (`party_credit.js`) that also lowers the
    full-settlement amount.
  - Cancelling an invoice paid from credit refunds that part like any payment (D-055), not back into credit.
- Schema: migration `shared.0020` (audit event choice only).

### D-088: The printed sales invoice is a one-page brand sheet; the USD rate is not printed
- Status: Final (replaces D-061's layout; its stamp boxes, words, watermark and COMPANY_* source stay)
- Date: 2026-10-04
- Decided by: Sina (reference picture, brand «کاغذ پلاس», phones, email, colours light green + navy + white)
- Decision: `sales/print.html` + `sales/css/invoice_print.css`: brand head with a drawn paper logo (inline SVG, no file
  needed), invoice details (number, invoice date, credit due date, print date) and buyer, a navy pill header over pale
  green pill rows, a «روش پرداخت و تسویه» box (money received by method and date, earlier credit used, pending cheques
  with due dates, open نسیه with its due date: `apps/sales/printing.settlement_rows`), short terms, totals with the
  amount in words, seller/buyer stamp boxes, a thank-you line picked from 12 by the invoice id (varied across invoices,
  the same on a reprint), and a navy footer band with phones (name + number), email and social glyphs (a handle prints
  only when set). A «سیاه‌وسفید» switch (remembered per browser) turns it into an ink-saving black-and-white sheet.
- One page: the sheet is exactly A4; the server picks a row density from the line count (>10 compact, >18 dense, >30
  tiny) and a small script steps tighter until the sheet fits; checked in the browser with 1, 22 and 38 lines.
  Only if even the smallest rows overflow does it flow onto a second sheet, with a notice on screen.
- New `.env` keys (blank = the owner's defaults): `COMPANY_BRAND` (کاغذ پلاس), `COMPANY_PHONES`
  ("خندانی:09145572511,حقگو:09145589832"), `COMPANY_EMAIL` (kaghazplus1@gmail.com), `COMPANY_INSTAGRAM`,
  `COMPANY_TELEGRAM`, `COMPANY_WHATSAPP`, `COMPANY_TERMS` ("|"-separated lines).
- The USD rate (D-080) stays frozen on every invoice and visible on the sales and purchase detail pages, but is no longer
  printed on either invoice: it is for the owner, not the customer.

### D-089: Sales and purchase returns
- Status: Final (ROADMAP 4.6, out of scope since 2026-09-24, brought in by Sina)
- Date: 2026-10-04
- Decided by: Sina (returns linked to an invoice, money first off the invoice, the rest refunded or kept as credit, chosen
  on each return)
- Decision: new app `apps.returns` with `SalesReturn`/`SalesReturnItem` and `PurchaseReturn`/`PurchaseReturnItem`, written
  only by `record_sales_return` / `record_purchase_return` (one transaction each) and never edited. A return is started from
  a confirmed invoice («ثبت مرجوعی»); each line can give back at most what that line sold/bought minus earlier returns
  (cartons + packs typed, stored in packs). Numbers: own yearly series per kind (`1405/0001`, `DocumentSequence` types
  `sales_return` / `purchase_return`). Menu item «مرجوعی» lists both kinds in two tabs.
- Value: a line's share of what it really brought in (sales: net of the invoice discount, D-048; purchases: the goods price,
  freight is not refunded), taken on the running total so returning a line in pieces adds up to exactly the whole line.
- Stock (FIFO stays exact, D-036): a sales return puts the packs back as a NEW layer (source `sales_return`) at that line's
  own FIFO cost per pack; a purchase return draws that purchase line's own layer down with a consumption row (so only what
  is still on the shelf from that purchase can go back). Movements `sales_return` (in) / `purchase_return` (out). The
  original invoice, its consumptions and its profit are never touched (D-014).
- Money: the value first comes off what is still open on the invoice outside pending cheques (a pending cheque's part stays
  open so the cheque can still clear) through a credit-note `Payment` (`is_credit_note`, no bank account, allocated to the
  invoice; kept out of statements, the return itself is the statement line). The surplus is either refunded through a
  current account (a reversal payment; a card reader never pays out, D-069) or left as the party's credit (the unallocated
  rest of the credit note), which D-087 then shows everywhere and uses on the next invoice.
- Reports: returns are booked on their own date and shown beside sales/purchases, not netted into them: «مرجوعی‌ها» card,
  and net profit = gross profit - profit given back by sales returns (value - cost back on the shelf) - expenses.
- An invoice with a return can no longer be cancelled (the return already moved part of its goods and money).
- Schema: `returns.0001`, `inventory.0007/0008` (layer source + `sales_return_item`, nullable `sale_item` + `purchase_return_item`
  on consumptions, new movement types and constraints), `payments.0013` (`is_credit_note` + check), `shared.0021`.

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
- Status: Final
- Date: 2026-09-20
- Decided by: me
- Decision: `User` carries no `business` FK, deliberately departing from
  non-negotiable rule 1. The user-to-business relation lives in a separate
  `BusinessMembership` model.
- Options considered: one `business` FK on User.
- Rationale: one person may work in more than one business; a direct FK would
  force duplicate user accounts and duplicate credentials.
- Affects: `apps/users`, upcoming `BusinessMembership`.

### D-009: Roles as a choices field, not a separate model
- Status: Final
- Date: 2026-09-20
- Decided by: me (on recommendation)
- Decision: `BusinessMembership.role` is a `CharField` with fixed choices
  (owner, salesperson), not a `Role` model.
- Options considered: separate `Role` model with dynamic permissions.
- Rationale: SPEC.md describes two owners and a few salespeople; roles are not
  expected to be dynamic. Migrating from choices to a model later is a one-day
  job, cheaper than carrying the complexity now.
- Affects: upcoming `BusinessMembership`.


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


### D-013: Money is stored as whole Rial in BigIntegerField
- Status: Final
- Date: 2026-09-21
- Decided by: me
- Decision: All money fields are `BigIntegerField` holding whole Rial. No decimals.
  Toman display and thousand separators are presentation concerns: a shared helper
  in `apps/shared` formats numbers as `1,234,567` and shows a Toman hint under
  price inputs. Storage never changes.
- Options considered: Toman as integer; DecimalField with 2 places.
- Rationale: the paper ledger is in Rial; converting at storage time would create
  rounding and a permanent ambiguity about which unit a row is in. Integer Rial
  makes every sum exact.
- Affects: `PurchaseItem.unit_price`, `SaleItem.unit_price`, all future money fields,
  admin and serializers.

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
- Status: Final
- Date: 2026-09-21
- Decided by: me
- Decision: Sellers log in to the Django admin. Every admin filters its
  queryset and foreign-key choices to the businesses the user belongs to.
  Role checks are also enforced inside services, not only in the admin.
  Superuser is not scoped.
- Options considered: a separate frontend for sellers (Vue, deferred).
- Rationale: the admin is the only UI in this phase. Scoping in both the
  admin and the services means a hidden button is never the only barrier.
- Affects: all admins, `apps/shared/permissions`, all services.


## D-027 — Seller permission scope
Seller may create, view, and confirm SalesInvoice/SaleItem for their
business only, selecting Product and Customer from existing records.
No access to purchasing app. No create/edit on Product, Customer,
Supplier. InventoryMovement ledger is view-only (admin-wide rule).
Owner has full CRUD within their business, subject to D-024 limits.
Decided 2026-09-22.


## D-028
D-028 — New user + first membership created together from UserAdmin add page, in one transaction; business/role required. Owner sees 
only own businesses; superuser sees all. A user with no business is created via createsuperuser, not admin.


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

## D-041 — Manual stock adjustment draws FIFO layers like a sale
Date: 2026-09-25
Status: Final

Context: REDESIGN_VISION 4.3 asks for a manual adjustment (in/out, mandatory
reason note); STATE.md had flagged since 4.1 that `adjustment_out` must
consume FIFO layers and `adjustment_in` must carry a unit cost, "or layer
totals and movement totals diverge" (D-036) — otherwise `InventoryMovement`
(the stock ledger) and `InventoryLayer` (the cost basis) would silently
disagree the first time anyone used it.

Decision: `InventoryConsumption` is generalized from "what a sale item drew
from a layer" to "what a sale item *or* an adjustment_out movement drew from
a layer" — `sale_item` becomes nullable, a new nullable `movement` FK is
added, and a CHECK enforces exactly one of the two is set. This is the same
shape already used repeatedly in this schema for "one of two possible
owners" (`Payment.customer`/`supplier`, `Cheque.sales_invoice`/
`purchase_invoice`, `PaymentAllocation`'s invoice pair) — not a new pattern.
`InventoryLayer.Source` gains `adjustment` (alongside `opening_stock`,
`purchase_item`), for a layer an increase opens. `InventoryMovement` gains a
nullable `layer` FK, set only for `opening`/`adjustment_in` (the two types
with no invoice item to hang a layer link off of) — a backfill migration
links every pre-existing OPENING movement to its layer, since
`set_opening_stock` always created both together, one-to-one, before this
field existed to record it.

`record_adjustment(product, movement_type, quantity, user, note,
unit_price=None)` (apps/inventory/services.py): `adjustment_in` opens a new
layer at `unit_price` (required, same rule as `set_opening_stock`).
`adjustment_out` consumes active layers oldest-first exactly like
`consume_fifo`, records one `InventoryConsumption` per layer touched
(`movement=`, not `sale_item=`), and is rejected outright — nothing
written — if the ledger cannot cover the requested quantity: an adjustment
corrects a physical count, it does not manufacture an oversell the way a
sale is allowed to (D-016 is sale-specific, not extended here). Its
`unit_price` is filled in afterward as the weighted-average cost of what it
actually drew.

No privilege gate: `apps/shared/permissions.py`'s docstring states exactly
two actions are superuser-gated (oversell-confirm, cancellation); adding a
third would contradict that explicit design call (D-034), and nothing in
REDESIGN_VISION 4.3 asks for one. The mandatory reason note is the only
safeguard.

Consequences: every stock-changing row — opening, purchase, sale,
adjustment_in, adjustment_out — now resolves to the specific layer(s) it
touched, closing the last gap in REDESIGN_VISION 4.3's "which layer each row
touched" requirement for the per-product transaction history.

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

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
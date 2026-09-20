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
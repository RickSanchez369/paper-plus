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
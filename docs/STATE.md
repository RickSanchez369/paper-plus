# Project State

Last updated: 2026-09-20, after task 21.

## 1. Where we are
Infrastructure complete. First model created. No real data yet.

## 2. Done
- Django 6.1.1 project on Python 3.13.2, venv at `.venv`
- PostgreSQL 18, database `paper_plus`, connected via `DATABASE_URL`
- Settings read from `.env` (django-environ); `.env.example` in git
- `apps/` package created; app `apps/shared` registered
- `BaseModel` (abstract: UUID pk, created_at, updated_at)
- `Business` model: name, legal_name, registration_number, phone, address, is_active
- Migration `shared.0001_initial` applied and verified in PostgreSQL
- Decisions D-001 to D-006 logged
- Custom `User` model (`users.User`): phone as USERNAME_FIELD, UUID pk, UserManager
- `AUTH_USER_MODEL` set; database dropped and rebuilt from scratch (no data existed)
- Superuser created and verified
- Decisions D-007, D-008 logged
- `BusinessMembership` (business FK, user FK, role choices, is_active, unique(business,user))
- Migration `shared.0002_businessmembership` applied and verified
- Decision D-009 logged


## 3. Next step
`Product` in a new app `apps/products`:
- `business` FK, name, sku (unique per business), unit, is_active
- Inherits BaseModel. No `stock` field (derived from InventoryMovement).
- Remember: fix `name = "apps.products"` in apps.py after startapp.

## 4. Build order after that
1. `User` + `BusinessMembership` (which user belongs to which business)
2. `Product` (no multi-unit in v1 slice)
3. `Customer`, `Supplier`
4. `InventoryMovement` (ledger, source of truth for stock)
5. `PurchaseInvoice` + `PurchaseItem` + `confirm_purchase` service
6. `SalesInvoice` + `SaleItem` + `confirm_sale` service (stock check, select_for_update)
7. Opening stock (`movement_type=opening`) + `is_onboarded` flag on Product
8. `pg_dump` backup script, then real data entry

## 5. Traps and reminders
- Windows / PowerShell only. No WSL.
- Activate venv in every new terminal: `.venv\Scripts\Activate.ps1`
- `startapp` in a subfolder: must fix `name = "apps.<app>"` in that app's `apps.py`
- PowerShell console shows UTF-8 Persian as garbage via `Get-Content`. The data is
  fine. Verify through Python, not the console. `chcp 65001` fixes display per window.
- Use `psycopg[binary]` (quoted in PowerShell), never `psycopg2`.
- `pg_dump` lives at `C:\Program Files\PostgreSQL\18\bin` — not in PATH yet.
- git commits fail silently if not verified: always run `git log --oneline` after committing.
- Read every migration and run `sqlmigrate` before `migrate`.
- Never reference the user model directly; use `settings.AUTH_USER_MODEL` in FKs.
- `sqlmigrate` output is display-garbled for Persian; data is correct.
- New models: constraints appear inside CreateModel options, not as separate AddConstraint.

## 6. Security debt (must clear before real data)
- [ ] Rotate `SECRET_KEY` — the current one was exposed in chat
- [ ] Replace weak postgres password (`admin`)
- [ ] Create a dedicated DB user instead of the `postgres` superuser
- [ ] `DEBUG=False` + `ALLOWED_HOSTS` for production
- [ ] `pg_dump` before every `migrate` once real data exists

## 7. Scope rules for this slice
Excluded from v1: cheques, returns, multi-unit conversion, costing/profit,
FinancialObligation, PaymentAllocation, AuditLog, custom roles, Docker, CI,
PDF, reports, OpenAPI, Vue.
System is SHADOW until its numbers match the paper ledger three days running.
- HARD GATE: before the first real record, clear all of section 6.
- HARD GATE: system stays SHADOW (paper ledger runs in parallel) until three
  consecutive days of zero discrepancy. Every discrepancy is a bug — log it,
  never fix it by hand.

## 8. Working agreement
- One task per message; Sina runs it and reports `ok` or pastes the error.
- Claude writes models and serializers; Sina writes the service layer.
- Explanations alongside steps, in Persian. Code and comments in English.
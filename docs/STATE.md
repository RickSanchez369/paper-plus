# Project State

Last updated: 2026-09-21, after the admin layer was completed.

## 1. Where we are
Infrastructure, models, services and admin complete. Only test data in the
database. Next: wipe test data, then real data entry under SHADOW.

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
- `BusinessMembership` (business FK, user FK, role choices, is_active, unique(business,user)) — migrated & tested
- App `apps/products` created and registered
- `Product` (business FK PROTECT, name, sku, unit, description, is_active; unique(business,sku)) — migrated & tested
- Decision D-009 logged
- App `apps/partners`; `Customer` and `Supplier` (business FK PROTECT, name,
  phone, address, note, is_active; unique(business,name) each) — migrated & tested
- Decision D-010 logged
- App `apps/inventory`; `InventoryMovement` (business, product PROTECT,
  movement_type choices, quantity PositiveInteger, note, created_by PROTECT;
  CheckConstraint quantity>0; index on (product, created_at)) — migrated & tested
- Stock verified by aggregation over the ledger (opening 10 - sale 3 = 7)
- Decisions D-010, D-011, D-012 logged
- `apps/shared/utils.py`: format_number, rial_to_toman, format_rial (display only)
- App `apps/purchasing`; `PurchaseInvoice` (supplier PROTECT, invoice_number unique
  per business, invoice_date, status draft/confirmed, confirmed_at, created_by)
  and `PurchaseItem` (invoice CASCADE, product PROTECT, quantity, unit_price BigInteger;
  CHECK qty>0, price>=0; unique(invoice,product)) — migrated & tested
- Decisions D-013, D-014 logged
- `apps/purchasing/services.py`: `confirm_purchase(invoice, user)` — select_for_update
  on the invoice, rejects non-draft / empty / foreign-business product or supplier,
  bulk_creates one purchase InventoryMovement per item, sets status+confirmed_at.
  Verified: empty, happy path (stock 10/4), double-confirm, foreign product (no write).
- App `apps/sales`; `SalesInvoice` + `SaleItem` (mirror of purchasing) — migrated & tested
- `apps/inventory/selectors.py`: `get_stock(product)`, `get_stock_map(ids)` — read-only,
  signed-quantity CASE in SQL
- `apps/sales/services.py`: `confirm_sale(invoice, user) -> (invoice, shortages)`
  — select_for_update on invoice + on Product rows (sorted by pk, no deadlock),
  same validations as purchase, allows negative stock and marks it in the note.
  Verified: empty, happy path (10→7), oversell (4−6=−2 reported), double-confirm,
  foreign product.
- Decisions D-015, D-016 logged
- `Product.is_onboarded` BooleanField + migration `products.0002` — applied & verified
- `apps/inventory/services.set_opening_stock(product, quantity, user)` — atomic,
  select_for_update on Product, rejects onboarded / has-movements / negative,
  quantity 0 marks onboarded without a movement row. 15/15 checks passed.
- Decision D-017 logged
- `scripts/` untracked from git (was committed by mistake, now gitignored)
- `tools/backup.ps1`: pg_dump to a gitignored `backups/`, credentials read from
  `.env`, password passed via PGPASSWORD. Restore into a scratch database verified
  (20 tables), scratch database dropped.
- Security gate cleared: SECRET_KEY rotated; DB role `paper_app` created and made
  owner of the database, schema and all tables (`tools/reassign_ownership.sql`);
  `DATABASE_URL` switched to `paper_app`; `postgres` password rotated twice and the
  old one proven dead; DEBUG and ALLOWED_HOSTS read from `.env` with safe defaults.
- Decisions D-017, D-018, D-019 logged
- Admin layer complete (Persian labels, no deletes anywhere except draft invoices):
  - `shared`: Business (+ membership inline), BusinessMembership; site titles in Persian
  - `users`: custom UserAdmin on phone; BaseUserCreationForm; privilege fields
    read-only for non-superusers
  - `products`: stock column via one `get_stock_map` per page; one-time
    "opening stock" form field calling `set_opening_stock` (blank = not counted,
    0 = onboarded without movement)
  - `partners`: Customer, Supplier via shared PartnerAdmin base
  - `purchasing` / `sales`: invoice + item inline, `created_by` set in save_model,
    confirm action calls the service, confirmed invoice view-only, bulk delete
    removed; sales shows shortages as a warning (D-016)
  - `inventory`: ledger view-only for everyone, superuser included
- Verified in admin: purchase confirm, sale confirm incl. negative stock warning,
  double-confirm rejected, opening stock 10 / 0 / blank / -5

## 3. Next step
Wipe test data before the first real record. Order:
1. `.\tools\backup.ps1` (keep the test-data dump, just in case)
2. `python manage.py flush` (empties all tables, schema untouched, superuser gone)
3. `python manage.py createsuperuser` (real owner phone)
4. Create the real Business in admin, then memberships
5. Real data entry: products with opening stock, customers, suppliers
Then SHADOW: log every discrepancy, three clean days in a row to exit.

## 4. Build order after that
All items done (see section 2). Next build work is decided after SHADOW.

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
- Shell tests: create the Business inside the same test block. `Business.objects.first()`
  returns None after a previous test cleaned up, and the failure then looks like a
  different bug (NotNullViolation, false-positive "unique works").
- Constraints on new models appear inside CreateModel options, not as separate AddConstraint.
- `CheckConstraint` uses `condition=` in Django 5.1+, not `check=`.
- InventoryMovement is append-only. Corrections are new adjustment_in/adjustment_out
  rows, never edits or deletes.
  - Money: BigIntegerField, whole Rial. Never Decimal, never Toman in storage.
- Display formatting lives in apps/shared/utils.py, never in models.
- Never pipe a script into `manage.py shell` — it replays line by line and any
  try/except block breaks. Use:
  python manage.py shell -c "exec(open('path.py', encoding='utf-8').read())"
- VS Code / PowerShell may write UTF-8 files with a BOM; Python then fails on the
  first line. Strip it with UTF8Encoding($false).
- Locking a lazy queryset does nothing: wrap `select_for_update()` in `list()`.
- Always order locked rows by pk; unordered locks across transactions deadlock.
- `confirm_sale` returns a tuple `(invoice, shortages)`, unlike `confirm_purchase`.
- Django connects as `paper_app`, not `postgres`. New tables created outside
  `migrate` must have their owner set, or `migrate` fails with
  "permission denied for table ...".
- `psql --command` with `$$` blocks: put the SQL in a file, PowerShell eats `$$`.
- Backup: `.\tools\backup.ps1`. Restore test = createdb scratch, psql --file, drop it.
- Use `git --no-pager log/show/diff` in PowerShell; the pager blocks the terminal.
- `git commit` reporting fewer files than expected is usually fine: the rest were
  already committed. Verify with `git --no-pager show --stat HEAD`, not by guessing.
  - Admin: `has_delete_permission(obj=None)` returning False is what removes the
  bulk "delete selected" action; per-object checks alone do not.
- Admin inline permission methods receive the PARENT object, not the row.
- `autocomplete_fields` requires `search_fields` on the target's admin (admin.E039).
- An exception raised in `ProductAdmin.save_model` (service rejection) is a 500,
  but the request transaction rolls back the product save too.



## 6. Security debt (must clear before real data)
- [-] Rotate `SECRET_KEY` — the current one was exposed in chat
- [-] Replace weak postgres password (`admin`)
- [-] Create a dedicated DB user instead of the `postgres` superuser
- [-] `DEBUG=False` + `ALLOWED_HOSTS` for production
- [-] `pg_dump` before every `migrate` once real data exists
- [x] All cleared 2026-09-21. `pg_dump` before every `migrate` is now a standing rule.

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
- Replies: code + test + notes only. No conceptual explanations unless asked.
- End of every completed unit: give the commit message.
- Every file: thorough English comments (WHY, not just what), docstrings on
  every class and public function; Persian `verbose_name`, admin labels,
  action descriptions and messages. Identifiers stay English (D-005).
- Replies: concise, no filler, but complete and exact.
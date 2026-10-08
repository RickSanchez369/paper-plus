# Kaghaz Plus (کاغذ پلاس)

A single-business web application for a paper-products trading company:
sales, purchasing, inventory (real FIFO costing), payments, cheques,
receivables/payables, expenses, bank accounts, financial reports and
user-activity tracking — cross-linked so every Toman and every unit of
stock traces back to who did what, when, why, and on which document.

## Status

Rebuilt from a Django-Admin-only multi-tenant tool into a single-business
frontend (merged into `dev` and `main` 2026-09-26). All 11 modules are built
and browser-verified. Phase D (visual identity) is next; see
[docs/STATE.md](docs/STATE.md).

## Stack

Django 6.1.1, Python 3.13.2, PostgreSQL 18, HTMX + Django templates (no
SPA, no separate API). Interface language is Persian (`fa`); code and
identifiers are English. Windows/PowerShell development environment.

## Modules

Sales · Purchasing (+ Suppliers) · Inventory · Receivables/Payables/Cheques
· Bank Accounts · Expenses · Customers · Financial Reports · User Activity
· Dashboard.

See [docs/architecture.md](docs/architecture.md) for how these fit
together (apps, core principles, domain model, key flows).

## Getting started

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Copy `.env.example` to `.env` first and fill in `SECRET_KEY`/`DATABASE_URL`.
Django connects to PostgreSQL as the `paper_app` role (never `postgres`),
see `docs/RULES.md`'s "Traps" section for the environment-specific
gotchas (BOM-free files, `psycopg[binary]`, console encoding, etc.).

## Documentation

Start at [docs/README.md](docs/README.md); it maps every document to the
question it answers. Working rules: `docs/RULES.md`; current state and next
step: `docs/STATE.md`; the why behind every rule: `docs/DECISIONS.md`.

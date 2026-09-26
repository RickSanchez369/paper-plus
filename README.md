# Paper Plus

A single-business web application for a paper-products trading company:
sales, purchasing, inventory (real FIFO costing), payments, cheques,
receivables/payables, expenses, bank accounts, financial reports and
user-activity tracking — cross-linked so every Toman and every unit of
stock traces back to who did what, when, why, and on which document.

## Status

Rebuilt from a Django-Admin-only multi-tenant tool into a real,
single-business frontend (branch `explore/vision-rethink`, merged into
`dev` and `main` 2026-09-26, then retired). **Phase C is complete — all 11
modules are built and browser-verified.** Phase D (visual identity) is
next; not started. See [docs/STATE.md](docs/STATE.md) for the exact
current state and roadmap.

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

For a production server (VPS, nginx, gunicorn, systemd, backups), see
[docs/deployment.md](docs/deployment.md).

## Documentation

Start at [docs/README.md](docs/README.md) — it maps every document to
what question it answers and when to read it. In short: `docs/RULES.md`
(binding process rules), `docs/STATE.md` (current state + roadmap,
its "Next" section is where new work starts), `docs/DECISIONS.md` (the
full append-only *why* behind every non-obvious rule), and
`docs/architecture.md` (system overview, domain model, key flows).

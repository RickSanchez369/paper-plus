# RULES — paper-plus

How work on this repo is conducted. What the running system must never
violate lives in [business-rules.md](business-rules.md); full rationale for
any `D-0xx` in [DECISIONS.md](DECISIONS.md) (append-only, wins on conflict).

## Session start
- Read RULES.md, STATE.md ("Next" is the starting point), then
  PROJECT_MAP.md. Never guess a field, related name, choice value or
  signature — check PROJECT_MAP.md or ask for the file.
- New decision: append the full entry to DECISIONS.md and one index line to
  business-rules.md, in the same commit.
- Scope is the STATE.md roadmap (D-020). Anything else is out of scope;
  say so. Excluded: Docker, CI, PDF, OpenAPI, Vue. Ask before changing a
  Final decision.

## Language
- Chat: Persian. Identifiers, commands, technical terms: English.
- Code, comments, docstrings, commit messages: English.
- User-facing strings (verbose_name, labels, messages, errors): Persian (D-005).

## Workflow
- Autonomous: do the whole task (edit, migrate, script, test, commit, push),
  verify it yourself, then report and continue with the next task.
- Report per task, short: task id, what changed, what was verified, notes.
  Label flaws Critical / Major / Minor.
- Ask the user only for: a real design fork or business ambiguity, a
  defect/gap outside the current task, a destructive or hard-to-reverse
  action, or a failure you can't resolve.
- Before `migrate`: read every migration and run `sqlmigrate`. Once real data
  exists, run `.\tools\backup.ps1` first.
- Every file: English comments explaining WHY; docstrings on every class
  and public function.
- Secrets never in chat: use a placeholder or `Read-Host`. If one is pasted,
  rotating it is the next task.

## Git
- Work on `dev`. Commit per task and push:
  `git commit -m "type(scope): message (ROADMAP x.y)"` — one line, with the
  ROADMAP `[x]` in the same commit.
- End of a phase: `git switch main; git pull; git merge --no-ff dev -m "merge: phase N"; git push; git switch dev`.
- Merging any other long-lived branch into `dev`/`main`, force-push and
  history rewrites need the user's explicit OK.
- Always `git --no-pager`.

## UI work
- Follows docs/UI_EVOLUTION.md (D-094): refine, never replace; no measured proof of a real UX gain = no change.

## Testing
- Verification scripts live in `scripts/` (gitignored, throwaway);
  operational scripts in `tools/` (tracked).
  Run: `python manage.py shell -c "exec(open('scripts/NAME.py', encoding='utf-8').read())"`
- Pattern: all data inside one `transaction.atomic`, `raise _Rollback` at
  the end, print `n/N passed`.
- Before a new script that calls `confirm_sale`/`confirm_purchase`/
  `set_opening_stock`, copy the setup boilerplate verbatim from an existing
  passing script that calls the same service.
- `DocumentSequence` is one row per (`doc_type`, Jalali `year`) (D-033, D-064): it is
  created by `get_next_document_number` on first use; tests read it with
  `filter(...).first()`, never `create` a row by hand.
- Unique fields (User.phone, ...): random, never fixed, e.g.
  `f"09{random.randint(100000000, 999999999)}"`. The dev DB is never empty (D-031).
- After a service that may lock/re-fetch, assert on the object it returns
  or `.refresh_from_db()` first, never the stale local variable (D-031).
- Anything with a form, live calculation or htmx swap needs real browser QA
  with throwaway data; `manage.py check` and scripts miss JS bugs.
- Never pipe a file into `manage.py shell`; never paste try/except into the REPL.

## Environment traps (Windows / PowerShell only)
- Activate the venv: `.venv\Scripts\Activate.ps1`.
- Write files as UTF-8 without BOM (`[Text.UTF8Encoding]::new($false)`);
  PS 5.1 `Set-Content -Encoding UTF8` adds a BOM → SyntaxError on line 1.
- Console garbles Persian (`Get-Content`, `sqlmigrate`); data is fine, verify
  via Python. Printing Persian needs `$env:PYTHONIOENCODING="utf-8"`.
- Install `"psycopg[binary]"` (quoted), never psycopg2.
- `pg_dump` is in `C:\Program Files\PostgreSQL\18\bin`, not in PATH.
- `psql` with `$$`: put the SQL in a file; PowerShell eats `$$`.
- Tables created outside `migrate` must be owned by `paper_app`.
- `startapp` in a subfolder: set `name = "apps.<app>"` in `apps.py`.

## Django gotchas
- `CheckConstraint(condition=...)`, not `check=`; constraints appear inside
  CreateModel options.
- `select_for_update()` on a lazy queryset locks nothing: wrap in `list()`,
  order locked rows by pk.
- `confirm_sale` returns `(invoice, shortages)`; `confirm_purchase` returns
  the invoice.
- Admin: `has_delete_permission(obj=None)` → False removes bulk delete;
  inline permission methods receive the PARENT object; `autocomplete_fields`
  needs `search_fields` on the target admin (E039); inline `get_queryset`
  returns `.none()` without view/change permission (ModelAdmin doesn't);
  an exception in `save_model` is a 500 but the request transaction rolls
  back the save.

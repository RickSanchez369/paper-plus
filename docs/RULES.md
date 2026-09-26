# RULES — paper-plus

Continuation of an ongoing project. No "stage 0", master plan or understanding phase.

This file covers how work on this repo is conducted — chat rhythm, git
conventions, dev environment. What the running system itself must never
violate lives in [business-rules.md](business-rules.md) instead.

> **Rebuild (Phases A–C) is done, merged into `dev`/`main`, branch retired
> (2026-09-26).** `docs/REDESIGN_VISION.md` and `docs/MASTER_PROMPT.md`
> remain the source of truth for the decisions/rules they changed, and for
> Phase D (visual identity, not started) which their build order and
> autonomy authorization still cover.

## Start of chat
Sina runs `python tools/project_map.py` and uploads RULES.md, STATE.md, PROJECT_MAP.md.
Read in that order; continue from STATE.md "Next".
- Never guess a field, related name, choice value or signature. Check PROJECT_MAP.md; else ask for the file.
- Full decision text lives in `docs/DECISIONS.md` (append-only archive, not uploaded). Ask for it only when `business-rules.md`'s index is not enough.
- New decision: append the full entry to DECISIONS.md and one index line in `business-rules.md`, same commit.
- Start a new chat after each completed ROADMAP task or ~15 messages.

## Language
- Chat: Persian. Technical terms, identifiers, commands: English.
- Code, comments, docstrings, commit messages: English.
- User-facing strings (verbose_name, labels, messages, errors): Persian (D-005).

## Rhythm — one task per message
1. Task in one line, with its ROADMAP id.
2. Why + what the command does, 2-4 lines. Never a bare list of commands.
3. Exactly one thing: one command, one file, or one set of edits in one file.
4. Expected result, so a failure is recognisable.
5. Stop and wait.
6. Completed task ends with the commit message and `x.y | Phase n: a/b | Overall: a/34 (~%)`.
- "ok" = output matched exactly; move on. Anything else: Sina pastes the output.
- Read-only/verify commands may be chained in one message (e.g. `git status` + `git log`).
  State-changing steps (migrate, git commit, anything touching the DB) are never chained.
- git: output is always pasted. Verify with `git --no-pager show --stat HEAD`.
- Branch: normally `dev`. Merging any long-lived work branch into `dev` needs Sina's explicit review first.
- Push after every completed task: `git push`.
- End of a phase: `git switch main; git pull; git merge --no-ff dev -m "merge: phase N"; git push; git switch dev`.
- Commit: `git commit -m "type(scope): message (ROADMAP x.y)"`, one line, nothing before it. The ROADMAP `[x]` goes in the same commit.
- Replies: code, tests, notes. No preamble, no recap, no concept lessons unless asked.
- Flaws are labelled Critical / Major / Minor.
- Exception: after an "ok", two steps may go in one message only if the second is a
  pure read/verification command with no schema, service, or data write (e.g. `sqlmigrate`
  after `makemigrations`). Never batch: `migrate` itself, model/service edits, or anything
  touching a rule in `business-rules.md`'s core invariants.

## Division of labour
- Claude writes everything: models, serializers, admin, services — complete file contents or exact find -> replace edits.
- Sina reads each block before running it, especially anything touching `business-rules.md`'s core invariants.
- Every file: English comments explaining WHY; docstrings on every class and public function.

## Working conventions
- Windows / PowerShell only. No WSL, bash, Docker.
- Secrets never in chat: use a placeholder (PPPP) or `Read-Host`. If one is pasted, rotating it is the next task.
- Scope = the roadmap in STATE.md (D-020). Anything else: say "out of scope" and move on. Excluded: Docker, CI, PDF, OpenAPI, Vue.
- DECISIONS.md wins over SPEC.md. Ask before changing a Final decision.
- Read every migration and run `sqlmigrate` before `migrate`. Once real data exists, run `.\tools\backup.ps1` first.

## Testing
- Before writing a new verification script that calls confirm_sale/confirm_purchase/
  set_opening_stock, open one existing passing script that already calls the same
  service (see PROJECT_MAP.md's `scripts/` list) and copy its setup boilerplate
  (DocumentSequence, User, opening stock) verbatim. Never reconstruct
  that boilerplate from memory.
- Verification scripts: `scripts/` (gitignored, throwaway). Operational scripts: `tools/` (tracked).
- Run: `python manage.py shell -c "exec(open('scripts/NAME.py', encoding='utf-8').read())"`
- Script pattern: all data created inside one `transaction.atomic`, `raise _Rollback` at the end, print `n/N passed`.
- `DocumentSequence` is a singleton per `doc_type` now (D-033): reuse the real row with
  `get_or_create`, or `update_or_create` to reset its counter when the script asserts on
  concrete invoice numbers. Never `create` one — it violates the unique constraint.
- Never pipe a file into `manage.py shell`; never paste try/except into the REPL.
- `PS C:\...>` is PowerShell, `>>>` is the Django shell.
- Unique fields (User.phone, etc.): generate randomly, e.g.
  `f"09{random.randint(100000000, 999999999)}"`. Never a fixed/sequential
  number (D-031) — the dev database is never assumed empty.
- After calling a service that may lock/re-fetch (select_for_update),
  assert on the object it *returns*, or call `.refresh_from_db()` first.
  Never assert on the pre-call local variable (D-031).

## Traps
- Activate the venv in every terminal: `.venv\Scripts\Activate.ps1`.
- `startapp` in a subfolder: set `name = "apps.<app>"` in its `apps.py`.
- Write files as UTF-8 without BOM: `[Text.UTF8Encoding]::new($false)`. A BOM gives SyntaxError on line 1. `Set-Content -Encoding UTF8` (PS 5.1) adds a BOM.
- The console garbles Persian (`Get-Content`, `sqlmigrate`); the data is fine. Verify through Python. `chcp 65001` fixes one window; `$env:PYTHONIOENCODING="utf-8"` fixes a script that prints Persian (a bare `print()` of Persian raises UnicodeEncodeError under cp1256).
- Install `"psycopg[binary]"` (quoted), never psycopg2.
- `pg_dump` is in `C:\Program Files\PostgreSQL\18\bin`, not in PATH.
- Always `git --no-pager`; the pager blocks the terminal.
- `psql` with `$$`: put the SQL in a file; PowerShell eats `$$`.
- Tables created outside `migrate` need owner `paper_app`, or `migrate` fails with permission denied.
- New-model constraints appear inside CreateModel options. `CheckConstraint(condition=...)`, not `check=`.
- `select_for_update()` on a lazy queryset locks nothing: wrap in `list()`. Always order locked rows by pk.
- `confirm_sale` returns `(invoice, shortages)`; `confirm_purchase` returns the invoice.
- Admin: `has_delete_permission(obj=None)` returning False removes bulk delete. Inline permission methods receive the PARENT object. `autocomplete_fields` needs `search_fields` on the target admin (E039).
- Inline `get_queryset` returns `.none()` without a Django view/change permission; ModelAdmin does not.
- An exception in `save_model` is a 500, but the request transaction rolls back the save.

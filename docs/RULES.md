# RULES — paper-plus

Continuation of an ongoing project. No "stage 0", master plan or understanding phase.

## Start of chat
Sina runs `python tools/project_map.py` and uploads RULES.md, STATE.md, PROJECT_MAP.md.
Read in that order; continue from STATE.md "Next".
- Never guess a field, related name, choice value or signature. Check PROJECT_MAP.md; else ask for the file.
- Full decision text lives in `docs/DECISIONS.md` (append-only archive, not uploaded). Ask for it only when the index below is not enough.
- New decision: append the full entry to DECISIONS.md and one index line here, same commit.
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
- "ok" = output matched exactly; move on. Anything else: Sina pastes the output.
- git: output is always pasted. Verify with `git --no-pager show --stat HEAD`.
- Branch: all work on `dev`. Check `git branch` shows `* dev` at the start of every session.
- Push after every completed task: `git push`.
- End of a phase: `git switch main; git pull; git merge --no-ff dev -m "merge: phase N"; git push; git switch dev`.
- Commit: `git commit -m "type(scope): message (ROADMAP x.y)"`, one line, nothing before it. The ROADMAP `[x]` goes in the same commit.
- Replies: code, tests, notes. No preamble, no recap, no concept lessons unless asked.
- Flaws are labelled Critical / Major / Minor.
- Exception: after an "ok", two steps may go in one message only if the second is a
  pure read/verification command with no schema, service, or data write (e.g. `sqlmigrate`
  after `makemigrations`). Never batch: `migrate` itself, model/service edits, or anything
  touching D-014/D-017/D-023/D-024.

## Division of labour
- Claude writes everything: models, serializers, admin, services — complete file contents or exact find -> replace edits.
- Sina reads each block before running it, especially anything touching D-014/D-017/D-023/D-024.
- Every file: English comments explaining WHY; docstrings on every class and public function.

## Non-negotiable
- Windows / PowerShell only. No WSL, bash, Docker.
- Every business-data model has a `business` FK (exception: User, D-008).
- Writes that touch stock or money go through a service inside `transaction.atomic`. Admin calls the service; it never writes movements or money.
- Stock is derived from `InventoryMovement`; no stock field. The ledger is append-only; corrections are adjustment rows.
- Money: BigIntegerField, whole Rial. Formatting only in `apps/shared/utils.py`.
- User FKs use `settings.AUTH_USER_MODEL`.
- Read every migration and run `sqlmigrate` before `migrate`. Once real data exists, run `.\tools\backup.ps1` first.
- Django connects as `paper_app`, never `postgres`.
- Secrets never in chat: use a placeholder (PPPP) or `Read-Host`. If one is pasted, rotating it is the next task.
- DECISIONS.md wins over SPEC.md. Ask before changing a Final decision.
- Scope = the roadmap in STATE.md (D-020). Anything else: say "out of scope" and move on. Excluded: Docker, CI, PDF, OpenAPI, Vue.
- HARD GATE: every schema change of phases 1-2 is done before the first real record (phase 3).
- HARD GATE: SHADOW (paper ledger in parallel) until 3 consecutive days of 0 discrepancies. Every discrepancy is a bug: log it, never fix data by hand.
- Integrity rules no role bypasses: D-014, D-017, D-023, D-024.

## Testing
- Verification scripts: `scripts/` (gitignored, throwaway). Operational scripts: `tools/` (tracked).
- Run: `python manage.py shell -c "exec(open('scripts/NAME.py', encoding='utf-8').read())"`
- Script pattern: all data created inside one `transaction.atomic`, `raise _Rollback` at the end, print `n/N passed`. Create the Business inside the script.
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
- The console garbles Persian (`Get-Content`, `sqlmigrate`); the data is fine. Verify through Python. `chcp 65001` fixes one window.
- Install `"psycopg[binary]"` (quoted), never psycopg2.
- `pg_dump` is in `C:\Program Files\PostgreSQL\18\bin`, not in PATH.
- Always `git --no-pager`; the pager blocks the terminal.
- `psql` with `$$`: put the SQL in a file; PowerShell eats `$$`.
- Tables created outside `migrate` need owner `paper_app`, or `migrate` fails with permission denied.
- New-model constraints appear inside CreateModel options. `CheckConstraint(condition=...)`, not `check=`.
- `select_for_update()` on a lazy queryset locks nothing: wrap in `list()`. Always order locked rows by pk.
- `confirm_sale` returns `(invoice, shortages)`; `confirm_purchase` returns the invoice.
- Admin: `has_delete_permission(obj=None)` returning False removes bulk delete. Inline permission methods receive the PARENT object. `autocomplete_fields` needs `search_fields` on the target admin (E039).
- Admin scoping: `BusinessScopedAdminMixin` goes first in the bases. Set `business_lookup` when the FK is not direct (`pk`, `invoice__business`, `memberships__business`); `scope_distinct = True` for to-many paths.
- Inline `get_queryset` returns `.none()` without a Django view/change permission; ModelAdmin does not.
- An exception in `save_model` is a 500, but the request transaction rolls back the save.

## Decision index (full text: docs/DECISIONS.md)
- D-001 Settings package `core/`; apps in `apps/`; shared app is `apps/shared`.
- D-002 Config and secrets from `.env` (django-environ); `.env.example` in git.
- D-003 UUID pk via BaseModel. Human document numbers are separate.
- D-004 Store UTC. Timezone and Jalali are presentation.
- D-005 Persian user-facing strings; English identifiers.
- D-006 Optional text fields: `blank=True`, never `null=True`.
- D-007 Login by phone (`^09\d{9}$`); custom `users.User`.
- D-008 User has no business FK; BusinessMembership links user and business.
- D-009 Role is a choices field (owner, salesperson), not a model.
- D-010 Customer and Supplier are separate models.
- D-011 Quantity is a whole number (PositiveInteger).
- D-012 Direction comes from movement_type; quantity > 0 (CHECK).
- D-013 Money is BigInteger whole Rial; Toman is display only.
- D-014 A confirmed invoice is immutable.
- D-015 `confirm_sale` locks Product rows as a mutex.
- D-016 A sale may drive stock negative; shortages are returned as a warning.
- D-017 Opening stock once, before any movement; 0 = onboarded with no row.
- D-018 The app DB role `paper_app` owns the database, schema and tables.
- D-019 DEBUG and ALLOWED_HOSTS from env, safe defaults.
- D-020 Scope = full remake request; order in the STATE.md roadmap.
- D-021 Shortage on sale: Seller rejected; Owner and superuser allowed with a warning.
- D-022 Invoice number assigned at confirmation from a locked DocumentSequence; configurable start; purchase also gets `supplier_invoice_number`.
- D-023 A confirmed invoice is cancelled (status + reversing movements), never edited. Owner and superuser only.
- D-024 Hard delete only for unreferenced records. Movements and confirmed/cancelled invoices are never deleted, by anyone.
- D-025 Payment status is derived from PaymentAllocation, never typed.
- D-026 Sellers use the admin. Admins and services are scoped to the user's businesses; superuser is not scoped.
- D-027 Seller: sell only, from existing Product/Customer; no purchasing; no create on Product/Customer/Supplier.
- D-028 New user + first membership created atomically from UserAdmin; scoped by viewer.
- D-029 AuditLog target reference is target_type + target_id, not GenericForeignKey.
- D-030 Chat rhythm: read-only commands may chain; state-changing steps never chain; task or ~15 msgs.
- D-031 Verification scripts: random unique identifiers, never fixed; assert on a service's returned object or after refresh_from_db(), never a stale local reference.
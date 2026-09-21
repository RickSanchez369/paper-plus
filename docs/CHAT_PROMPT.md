# How we work

Continuation of an ongoing project. Do NOT start any "stage 0", master plan,
or understanding phase.

## Starting a new chat
Before the chat, Sina runs:
    python tools/project_map.py
and uploads: CHAT_PROMPT.md, STATE.md, DECISIONS.md, ROADMAP.md, PROJECT_MAP.md.
Read them in that order, then continue from STATE.md "Next step".
- ROADMAP.md: task order and ids. Refer to tasks by id (e.g. "task 2.6").
- PROJECT_MAP.md: actual files, models, fields and choice values.
- Never guess a field name, related name, choice value or function
  signature. Check PROJECT_MAP.md; if it is not there, ask for the file.

## Chat
- Persian. Technical terms, identifiers, commands: English.
- Code, comments, docstrings, commit messages: English.
- User-facing strings (verbose_name, labels, errors): Persian.

## Rhythm — one task per message
1. State the task in one line.
2. Explain WHY it is needed and WHAT the command does, in 2-4 lines,
   before giving the command. Never a bare list of commands.
3. Give exactly one thing to do: one command, one file, or one edit.
4. Give the expected result so a failure is recognisable.
5. Stop. Wait.
6. End every completed task with one short progress line: ROADMAP task id,
   phase progress, and overall progress. No explanation.

"ok" from Sina means the output matched the expected result exactly — move on.
Anything else means a problem: he pastes the output.
For git commands the user always pastes output — git fails silently.


## Division of labour
- Claude writes models, serializers, admin.
- Sina writes the service layer (business logic) with Claude reviewing.
- Never more than one file per message.

## Non-negotiable
- Windows / PowerShell. No WSL, no bash, no Docker.
- Read every migration and run `sqlmigrate` before `migrate`.
- Every model that holds business data has a `business` FK.
- All writes that touch stock or money go through a service, inside
  `transaction.atomic`.
- Stock is derived from `InventoryMovement`. No `stock` field on Product.
- FKs to the user model use `settings.AUTH_USER_MODEL`, never a direct import.
- If DECISIONS.md and SPEC.md disagree, DECISIONS.md wins.
- Ask before changing anything already marked Final in DECISIONS.md.
- Secrets never appear in chat: passwords, SECRET_KEY, DATABASE_URL, .env content.
  Commands that need one use a placeholder (PPPP) or PowerShell `Read-Host`.
  If a secret is pasted anyway, rotating it is the next task, before anything else.
- Django connects to PostgreSQL as `paper_app`, never as `postgres`.
- Run `.\tools\backup.ps1` before every `migrate` once real data exists.
- Admin never writes stock or money directly. Confirming an invoice in admin calls
  the service (`confirm_purchase` / `confirm_sale`), never `save()` on movements.
- Sina may not be able to author files; give complete, exact file contents to paste.
- After each completed ROADMAP task, mark it [x] in ROADMAP.md in the same commit.

## Scope
See ROADMAP.md (D-020). Anything not in it is out of scope — say so
and move on. Do not add features because they seem useful.

## Reply style
- Code, tests, and notes only. No conceptual explanations unless asked.
- Every completed unit ends with the commit message.
- Minimum tokens. No preamble, no recap of what was just done.

## Testing
- Verification scripts live in `scripts/` (gitignored), not in the shell.
- Run with:
  python manage.py shell -c "exec(open('scripts/NAME.py', encoding='utf-8').read())"
- Never pipe a file into `manage.py shell`, and never paste a try/except block
  into the REPL — both break on the blank-line rule.
  - Verification scripts go in `scripts/` (gitignored, throwaway).
  Operational scripts go in `tools/` (tracked in git).
- Check the prompt before pasting: `PS C:\...>` is PowerShell, `>>>` is the Django
  shell. PowerShell blocks pasted into the Django shell fail with SyntaxError.
# How we work

Continuation of an ongoing project. Do NOT start any "stage 0", master plan,
or understanding phase. Read STATE.md and continue from its "Next step".

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

The user replies "ok" (green, move on) or pastes the error.
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

## Scope
See STATE.md section 7. Anything outside it is out of scope — say so
and move on. Do not add features because they seem useful.
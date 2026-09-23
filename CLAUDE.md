# CLAUDE.md — paper-plus

Read in this exact order before doing anything:
1. docs/RULES.md — binding, not "in spirit". Every rule there applies here too.
2. docs/STATE.md — "Next" section is the only valid starting point.
3. docs/PROJECT_MAP.md — the only source for field names, related_names,
   choice values, and function signatures. Never guess these; if
   PROJECT_MAP.md doesn't answer it, ask the user for the file.

## Non-negotiable process rules
- One ROADMAP task per turn. In your reply: task id, 2-4 lines of why/what,
  exactly ONE command or ONE file edit, expected result. Then stop.
  Do not proceed to a second step in the same turn even if tool access
  would technically allow it.
- Any state-changing action (migrate, git commit, git push, git merge,
  anything writing to the DB) requires the user to paste real output
  AND say ok/confirm for that exact step before you run the next one.
  Read-only/verify commands (git status, git branch, git log) may be
  suggested together.
- If you discover something outside the current roadmap task (a bug,
  an architecture issue, a missing decision) — STOP. Do not fix it.
  Report it, propose a D-xxx entry and a roadmap id, and wait for the
  user's decision before touching any code for it.
- If a rule in RULES.md is ambiguous or a new situation isn't covered,
  ask the user directly — do not infer or assume what they'd want.
- Language: talk to the user in Persian. Code, comments, docstrings,
  identifiers, commit messages, file paths, and technical terms stay
  in English, inline in the Persian text.
- No preamble, no recap of what RULES.md already says, no unrequested
  concept explanations — match apps/*/admin.py's own comment style:
  short, WHY-focused.
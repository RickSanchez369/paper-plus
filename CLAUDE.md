# CLAUDE.md — paper-plus

Read before starting, in this order:
1. docs/RULES.md — how work is done here (binding).
2. docs/STATE.md — its "Next" section is the only valid starting point.
3. docs/PROJECT_MAP.md — the only source for field names, related_names,
   choice values and signatures. Never guess; if it doesn't answer, ask
   for the file (regenerate: `python tools/project_map.py`).

## How to work
- Work autonomously: do every step of a task yourself (edits, migrations,
  scripts, tests, commits, pushes), verify each yourself, then move to the
  next ROADMAP task. No asking for permission or pasted output between steps.
- After each task, report briefly: task id, what was done, what was
  verified (results), anything notable. Then continue.
- Stop and ask the user only when:
  - a real design fork or business-logic ambiguity exists that the docs
    don't resolve;
  - you find a defect or gap outside the current task (report it, propose a
    D-xxx entry + roadmap id, don't fix it silently);
  - the action is destructive or hard to reverse (force-push, history
    rewrite, dropping/flushing real data, deleting non-throwaway records);
  - a step fails and you can't fix it after a real attempt.
- Never guess at a fork; ask.

## Style
- Talk to the user in Persian. Code, comments, docstrings, identifiers,
  commit messages, paths and technical terms stay English.
- No preamble, no recap of the docs, no unrequested concept lessons.
- Comments: short, WHY-focused, matching apps/*/admin.py.

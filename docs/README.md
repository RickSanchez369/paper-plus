# Documentation map — paper-plus

Start here. Read only what the task in front of you needs.

## Every session starts with (in this order)
1. [RULES.md](RULES.md) — how work is done here: workflow, git, testing, environment traps.
2. [STATE.md](STATE.md) — where we are; its **"Next"** section is the starting point.
3. `PROJECT_MAP.md` — generated snapshot of the live schema (`python tools/project_map.py`, gitignored). Never guess a field name, related_name, choice value or signature.

## Reference
| Doc | Answers |
|---|---|
| [architecture.md](architecture.md) | How the system is organized: apps, principles, domain model, key flows |
| [business-rules.md](business-rules.md) | What the system must never violate, plus the one-line `D-0xx` index |
| [DECISIONS.md](DECISIONS.md) | *Why* a rule exists. Append-only; wins over any other doc on conflict |
| [REDESIGN_VISION.md](REDESIGN_VISION.md) | Condensed summary of the finished rebuild (original in git history) |
| `design/ibm/DESIGN.md` | The Carbon reference behind the visual identity (D-050) |

## Where to look
- **Sales/purchasing/inventory logic:** architecture.md §4–5, the service in `apps/*/services.py`, then D-014, D-016, D-017, D-023, D-024, D-036, D-037, D-044.
- **Payments/cheques/expenses:** architecture.md §4, D-025, D-038..D-042, D-045.
- **Schema changes:** PROJECT_MAP.md + architecture.md §2–4 + the relevant D-0xx; read every migration and run `sqlmigrate` first.
- **Pages/templates/htmx:** the module's view docstrings; browser QA is mandatory for anything with a form or an htmx swap (RULES.md).
- **Look and feel:** D-050, `design/ibm/DESIGN.md`, and the `:root` tokens in `apps/shared/static/shared/css/app.css`.

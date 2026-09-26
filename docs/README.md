# Documentation map — paper-plus

Start here. Read only what the task in front of you needs.

## Every session starts with (in this order)
1. [RULES.md](RULES.md) — binding process rules, non-negotiables, decision index. Not "in spirit" — every rule applies.
2. [STATE.md](STATE.md) — current state; its **"Next"** section is the only valid starting point for new work.
3. `PROJECT_MAP.md` — generated snapshot of the live schema and file tree (`python tools/project_map.py`). Not committed (gitignored, regenerated per session). Never guess a field name, related_name, choice value or signature — check here, or ask for the file.

## Reference (read when the task touches them)
| Doc | Answers | Status |
|---|---|---|
| [architecture.md](architecture.md) | How the system is organized: apps, core principles, domain model, key flows | Current |
| [DECISIONS.md](DECISIONS.md) | *Why* a specific rule/model/behavior exists, append-only, Final vs superseded | Current — wins over any other doc if they disagree |
| [REDESIGN_VISION.md](REDESIGN_VISION.md) | The 2026-09-24 full-rebuild design spec: architecture decisions, per-module page design, cross-page consistency review | Phases A–C: historical (built, merged into `dev`/`main` 2026-09-26). §5–6 (visual design pick, USD-rate source): still open, relevant to the upcoming Phase D |
| [MASTER_PROMPT.md](MASTER_PROMPT.md) | The build plan/order and standing autonomy authorization used to execute the rebuild | Historical for Phases A–C (executed); its Phase D instructions still apply when that phase starts |
| `design/{stripe,linear,ibm,posthog}/DESIGN.md` | Four external reference design systems, downloaded verbatim, for the Phase D visual-identity pick | Reference material, unmodified, not yet chosen from |

## Task-oriented — where to look
- **Modifying sales/purchasing/inventory logic:** [architecture.md](architecture.md) §4–5 (domain model, sale-confirmation flow), then the relevant service in `apps/sales|purchasing|inventory/services.py`, then its `D-0xx` entries in [DECISIONS.md](DECISIONS.md) (D-014, D-016, D-017, D-023, D-024, D-036, D-037, D-044).
- **Modifying payments/cheques/expenses:** [architecture.md](architecture.md) §4 (money chain), D-025, D-038 through D-042, D-045.
- **Modifying the database/schema:** `PROJECT_MAP.md` (exact current fields) + [architecture.md](architecture.md) §2–4 + the relevant `D-0xx`. Read every migration and run `sqlmigrate` before `migrate` (RULES.md).
- **Modifying a page/template/frontend behavior:** [REDESIGN_VISION.md](REDESIGN_VISION.md) §4 for that module's spec, RULES.md's testing section (browser QA is mandatory for anything with a form or an HTMX swap — two real JS bugs were only ever caught that way).
- **Starting Phase D (visual identity):** [MASTER_PROMPT.md](MASTER_PROMPT.md) §3 Phase D, [REDESIGN_VISION.md](REDESIGN_VISION.md) §5–6, `docs/design/*/DESIGN.md`.

## Current vs historical, in one line
`RULES.md` and `STATE.md` are always current. `DECISIONS.md` is a permanent
append-only archive — an entry's own `Status` (Final / superseded by D-0xx)
tells you if it still holds. `MASTER_PROMPT.md`/`REDESIGN_VISION.md`
describe the rebuild that produced the current system — read them for the
*why* behind Phase A–C, not as a to-do list (that work is done).

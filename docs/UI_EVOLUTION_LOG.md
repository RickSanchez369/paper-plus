# UI Evolution log

One entry per change or per "No change required" verdict. Rules: `UI_EVOLUTION.md`.

Entry template:
- Page / element:
- Task served:
- Baseline (metric, value, width):
- After (same metric, value):
- Level / Preservation / UX score:
- Verdict: changed | no change required

## Entries
### 2026-10-05 baseline sweep 1 (demo SQLite, 390 / 1024 px, console clean)
Metrics: page-level horizontal overflow, interactive targets under 32 px (WCAG 2.2 AA minimum is 24 px), hit area of
radios/checkboxes via their label.
- /returns/ - overflow 0 at 390 and 1024; 0 small targets. Verdict: no change required.
- /expenses/recurring/ and /new/ - overflow 0; 0 small targets. Verdict: no change required.
- /backup/ - overflow 0; 0 small targets. Verdict: no change required.
- /user-activity/ - overflow 0; 6 count links 27 px high at 390 (above the 24 px minimum); table scrolls 192 px inside its
  card at 1024 (by design, admin-only page). No proven problem for a real task. Verdict: no change required.
- /sales/new/ - overflow 0; native inputs are 18 px but their labels are 29-44 px high (tier 39, discount mode 29, pay
  ticks 44), all above 24 px; the 1 px select is the folded customer combo (intentional). Verdict: no change required.
Not yet measured: contrast ratios, click/keystroke counts for the main tasks (sale entry, payment, return), detail pages,
print. Next sweep must measure those before any change is proposed.

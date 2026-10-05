# UI Evolution Mode (D-094)

Refine the existing UI; never replace it. Default assumption: the existing design is correct.

## Golden rule
If a change cannot be PROVEN to improve the real user experience, that part may not be changed.
"No change required" is a valid, desirable audit result. Taste ("modern", "trendy", "SaaS does it") is not evidence.

## Proof (required before every change; recorded in `UI_EVOLUTION_LOG.md`)
1. Task: the concrete user task it serves (enter a sale line, find an overdue cheque ...).
2. Baseline measured in the real browser on the demo DB (`tools/qa/preview.ps1`) at 1440 / 1024 / 390 px: clicks or
   keystrokes, tap-target px, contrast ratio, overflow px, recovery steps, content visible without scroll.
3. After: measured the same way; the target metric strictly better, no other metric worse.
4. Level, Design Preservation Score (target >= 8, below needs justification), UX Improvement Score (must clearly exceed
   the visual disruption).
No baseline problem found -> record "No change required".

## Change levels
- L1 micro polish (spacing, alignment, contrast, focus, hover) - preferred.
- L2 component refinement - strongly preferred.
- L3 interaction improvement (fewer clicks, feedback, keyboard flow, error recovery) - encouraged.
- L4 structural refinement - only with clear UX justification.
- L5 redesign (drawer, identity, layout system, major interaction patterns) - prohibited without explicit approval.
Order of preference: refine > adjust > polish > optimize > simplify > replace. Always ask: can the same gain be had
while preserving more of the existing design?

## Design DNA to preserve
- Colour: navy-tinted ink ramp (`--ink-*`), `--action` #213368, links/focus `--accent-700`, cyan only on navy,
  money tones `--positive/negative/warning-*` (use `-700` for small text), surfaces `--surface`, `--surface-sunken`.
- Type: Vazirmatn, body 14px / 1.65, h1 22px, nothing under 12px, tabular numerals, `.num` RTL.
- Spacing 4px scale (`--space-1..7`); radii 8 (controls) / 12 (buttons) / 16 (cards), pill badges; flat white cards,
  shadows only on overlays.
- Navigation: right-side drawer over a scrim (D-065), header with back control, `.page-head` -> hero/summary ->
  `.card` -> `.table-card` -> pager.
- Components: `.btn`, `.card`, `.table-card`, `.field` + filled inputs with `--control-border`, `status_badge` /
  `flag_badge` (single tone map), flash/toast, Jalali date picker, `toman` filters (whole Toman only).
- Identity: hostiran look (D-062). Tokens live in `apps/shared/static/shared/css/app.css`.
No dribbblification: no gradients, glass, decorative motion, hero sections or extra whitespace without a UX purpose.

## Constraints
Presentation only (no models, services or write endpoints). New colours through tokens, logical CSS properties (RTL),
check earlier overrides in `app.css` before adding rules. Out of scope: `docs/UI_AUDIT_200_DEFERRED.md` (dropped by Sina).

## Final test (record at the end of the log)
Recognisable to a current user? Noticeably better to use? Easier without harmful simplification? Identity intact?
Friction down? Consistency up? More polished without being over-designed?

## Mobile addendum (D-095)
Goal: the phone experience at 9/10 (Sina rates the whole site 7/10). Everything above still applies, including the golden rule.
- Structure may change (tables to cards, long forms to steps, primary actions to a bottom bar) wherever models, services, data and
  business behaviour stay untouched. The drawer menu (D-065) and the visual identity (D-062) stay frozen.
- Mobile rules live in NEW files `apps/shared/static/shared/css/mobile_*.css`, loaded after `app.css` in `shared/base.html` and
  scoped by media queries, so they are reviewable and revertable and desktop output does not move. Markup changes only when
  CSS cannot do it; every id, `data-*` hook and field name used by the JS and by `tools/qa/*` must survive.
- Scorecard: `python tools/qa/mobile_audit.py` (Playwright on the installed Chrome, throwaway demo DB from
  `python tools/qa/mobile_env.py NAME PORT`). Metrics per page at 360 / 390 / 430 px plus 1024 / 1440 as a desktop regression guard:
  page overflow, primary actions under 44 px, any tap target under 24 px, inputs under 16 px (iOS Safari zooms on focus),
  viewport-fit, manifest, apple-touch-icon. 9/10 = zero overflow, primary actions >= 44 px, no input < 16 px on touch devices,
  installable, the four daily flows (new sale, receive a payment, inventory lookup, dashboard) at or below their measured
  taps/keys, desktop unchanged.
- Method: 100 read-only critics return evidence-backed findings; only proven ones are implemented, in file-owner groups.

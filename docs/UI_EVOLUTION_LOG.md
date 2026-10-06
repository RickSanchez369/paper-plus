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

### 2026-10-05 sweep 2: text contrast (computed on 17 pages, demo SQLite)
Metric: WCAG contrast of every visible text node (4.5:1 normal, 3:1 large); gradient backgrounds skipped (hero, drawer, login).
- Dashboard, sales (list/new), purchasing, inventory, returns, recurring, reports, activity, backup: 0 failures. No change required.
- Empty-value marker "—" (receivables, payables, cheques, expenses, customers): 3.06:1 at 12-13.5px. It is `aria-hidden`
  with an sr-only twin "ثبت نشده"; a deliberately quiet placeholder carrying no information. No task is harmed.
  Verdict: no change required (the sr-only twin shows up as a checker false positive).
- Bank accounts, negative balance: the unit "تومان" (12px) rendered at 3.94:1 because `.is-negative .money__unit` fades it to
  opacity .8 on top of the muted caption colour. Task: read an overdrawn account's balance. Baseline 3.94:1 -> after 6.5:1
  (opacity 1, same colour as every other card's unit); no other metric changed (0 failures on the page, 54 nodes checked).
  Level L1, Preservation 10, UX 3 (small but strictly positive, zero visual disruption). Verdict: changed (app.css).
Note: a QA server started before a migration serves OperationalError; restart it after Python/migration changes.
Still not measured: click/keystroke counts for sale entry, payment and return; detail pages; print.

### 2026-10-05 sweep 3: keyboard flow of the sale form (task: enter one sale line and confirm, 390 px pane)
Measured with real key presses on the demo DB. Customer: 2 chars + Down + Enter = 4 keys, focus jumps to the product box.
Product: 2 chars + Enter = 3 keys, focus lands in cartons. Quantity: Tab + digit = 2 keys; Enter walks to the price boxes.
Already well designed: no change required for any of those steps.
- Finish: from the last price box the first 12 Tab stops (remove, add row, discount mode, discount amount, payment mode,
  cheque button, card tick, transfer tick, three settle buttons ...) still do not reach «ثبت و تأیید»; baseline >= 13 Tab
  presses (mouse: 1 click on the sticky dock). No keyboard shortcut existed (only Ctrl+K palette and Ctrl+P on sales pages).
- Change: Ctrl/Cmd+Enter presses the same submit button via `requestSubmit` (so the disabled state, the "tick a payment
  method" guard and the double-submit lock still apply); `aria-keyshortcuts` + title on the button. Plain Enter is unchanged
  (it never posts, by design).
- After: 1 key press. Empty invoice + Ctrl+Enter: refused with the existing inline message, URL unchanged. No payment ticked +
  Ctrl+Enter: refused. Valid line + card tick + Ctrl+Enter: exactly one confirmed invoice, redirect to its detail page.
- Level L3, Preservation 10 (no visual change except a tooltip), UX 7 (>= 13 keys -> 1 for keyboard users, per invoice).
  Verdict: changed (sale_form.js, sales/new.html). Not extended to purchase/return forms: not measured yet.
Note: the first attempt (Tab then Enter right after choosing a product) once landed on the dashboard; not reproducible in
three further runs, treated as a pane artifact.
Still not measured: payment receipt and return keyboard/click counts, detail pages, print.

### 2026-10-05 sweep 4: receive a payment, record a return (390 px pane)
- Receivables «ثبت پرداخت کلی»: opening the disclosure focuses the amount box; prefilled date and last account; «کل مانده»
  chip; Enter in the amount records it and focus lands on the autofocused «بروزرسانی فهرست» button. Keyboard: open + digits
  + Enter. Verified: a 1000-Toman payment recorded that way. Verdict: no change required.
- Return form: on load focus was on BODY; baseline = 8 Tab stops (menu, back, quick jump, logout, two breadcrumb links, the
  items scroller) before the first quantity box, while the invoice forms start in their first field.
  Change: focus the first quantity box on load, but not when an error is visible (the hidden per-row over-limit note is
  ignored via offsetHeight). After: 0 Tab stops, focus on the first quantity box. Level L3, Preservation 10 (no visual
  change), UX 5. Verdict: changed (returns/return_form.js). qa_26 (49) and qa_24 pass.
Pane note: `location.reload()` run from the JS tool sends the pane to the dashboard; navigate instead. This also explains
the earlier unexplained jump in sweep 3.
Not yet measured: purchase form shortcut, detail pages (invoice, cheque), print preview.

### 2026-10-05 sweep 5: purchase form (task: record a purchase and confirm, keyboard)
- Baseline: focus on BODY at load, 5 Tab stops to the supplier select; from the last row field 12 Tab stops (remove, add row,
  new product, freight tick/amount, payment modes, cheque button, transfer tick, settle button, cancel) before the submit
  button. Same gap as the sale form (sweep 3), same shared row/Enter code.
- Change: Ctrl/Cmd+Enter presses the same submit button through `requestSubmit` (server validation and the double-submit
  lock still run); `aria-keyshortcuts` + title on the button; the supplier select takes focus on a fresh form (not when a
  supplier is preset).
- After: 0 Tab stops to the supplier, 1 key to finish. Empty form + Ctrl+Enter: refused with the existing message, focus on
  the offending control. Transfer ticked without an account + Ctrl+Enter: server refusal with its normal field error, no
  document. Valid line + account + Ctrl+Enter: one purchase confirmed (۱۴۰۵/۰۰۰۲), redirect to its detail page.
- Level L3, Preservation 10, UX 6. Verdict: changed (purchase_form.js, purchasing/new.html).
  qa_02 (129), qa_22 (28), qa_24 (25) pass.
Not yet measured: detail pages (invoice, cheque), print preview.

### 2026-10-05 sweep 6: detail pages (sale, purchase, cheque, customer, bank account), 362 px pane
Metrics: page overflow, contrast, and WCAG 2.5.8 target size with its spacing exception (a target under 24 px passes when a
24 px circle on its centre touches no other target; inline links in sentences are exempt). Controls inside a CLOSED
<details> are excluded: Chromium still reports layout rects for them (this inflated the first spacing run with 6 false hits).
- Overflow 0 on all five. Cell links 21-22 px high (party, invoice, cheque links): 0 spacing violations after the exclusion.
  Verdict: no change required for target size.
- Contrast: customer, bank account, cheque pages 0 real failures (only the aria-hidden "—", see sweep 2).
- Sale detail 3.91:1 and purchase detail 4.09:1: the 12px unit "تومان" in the summary strip («مانده»/«تسویه») inherits the
  status colour and was faded to opacity .8. Task: read what is still owed on an invoice. Baseline 3.91 / 4.09 -> after
  >= 4.5 (opacity 1, same colour as the figure; size 12px / weight 400 keep it subordinate), 0 failures on both pages.
  Level L1, Preservation 10, UX 3. Verdict: changed (app.css `.summary-strip__item--owed/--settled .money__unit`).
  qa_14 (32), qa_24 (25), qa_08 (3) pass.
Print preview: not re-measured here (the pane cannot render print media); covered by qa_14 and the D-088 browser check.
Open for a later sweep only if Sina points at a page: dashboard hero/gradient surfaces (contrast skipped for gradients).

### 2026-10-05 sweep 7: contrast on gradient surfaces (login, dashboard)
Method: text on a gradient is tested against the WORST plausible background (opaque base stops, plus each translucent glow
stop composited over them). Conservative on purpose; every flag is then checked against the real geometry.
- Login `.auth__kicker` (cyan on the navy panel): flagged 2.39:1 only because the cyan glow sits bottom-left (circle at 15%
  110%); the text is top-right on plain navy, 4.5:1 against the lightest base stop. Verdict: no change required.
- Dashboard hero date line (rgb 200,208,222, 14px): flagged 3.81:1 from the glow (circle at 12% 120%, radius 45%); the text
  is on the right, beyond the glow radius, on plain navy (~7:1). Verdict: no change required.
- Dashboard primary card («سود خالص این ماه») neutral delta line "ماه قبل مبنایی برای درصد نداشت": kept the light-theme muted
  grey (85,97,122) on the navy gradient = 1.94:1 (lightest stop) to 2.41:1 at 12px; visibly dim in the browser. Task: understand
  why the month card shows no percent. Baseline 1.94-2.41 -> after rgb(227,233,243) (`--ink-200`, same token as the unit in
  that card), well above 4.5:1; up/down delta colours unaffected (lower specificity). Level L1, Preservation 10, UX 3.
  Verdict: changed (app.css). qa_19 (11), qa_24 (25), qa_08 (3) pass.
Still unmeasured: the open drawer's text (second pass), print preview.

### 2026-10-05 sweep 8: open drawer and form error states
- Open navigation drawer (navy gradient chrome), 18 text nodes against the worst-case background: 0 failures. No change required.
- Sale form after a refused Ctrl+Enter (inline error visible): 58 text nodes, 0 failures. Purchase form in the same state:
  47 nodes, 0 failures. No change required.
- Not covered: recurring-expense form error state (the pane dropped the session mid-test), print preview. Neither has any
  earlier finding pointing at it; left unmeasured rather than changed.
Summary of this pass (all L1/L3, identity untouched): contrast fixed in 3 places (negative stat-card unit, summary-strip unit,
navy dashboard card delta line), keyboard finish shortcut on the sale and purchase forms, initial focus on the purchase
supplier and the return quantity. Everything else measured as no change required.

## Mobile pass (D-095)
### Baseline scorecard 2026-10-05 (`mobile_audit.py`, demo DB, headless Chrome, touch emulation below 600 px)
26 pages (20 lists/forms + 6 detail pages). Counts are sums over pages.
| width | pages with page overflow | primary actions < 44 px | taps < 24 px | inputs < 16 px |
|---|---|---|---|---|
| 360 | 5 (purchasing list 28, bank accounts 29, expenses 28, reports 3, activity 3 px) | 206 | 43 | 64 |
| 390 | 0 | 208 | 43 | 64 |
| 430 | 1 (bank accounts 5 px) | 211 | 41 | 64 |
| 1024 / 1440 (desktop guard) | 0 / 0 | 242 / 242 | 40 / 41 | 64 / 64 |
Shell: no `viewport-fit=cover`, no manifest, no apple-touch-icon. `.btn` controls are 40 px (`--ctl-sm`), the 44 px line is the
Apple/WCAG-AAA guideline, so the 208 is a ceiling to reduce on the daily flows first, not a bug count. The 64 inputs under 16 px
are a real defect class on iPhone (focus zoom). Next: 100 read-only critics, then grouped implementation.

### Mobile pass, critic wave 1 (2026-10-05/06) and what was done about it
Critics launched: 24. The account's usage limit killed 15 of them mid-run; 5 delivered full reports (c003 inventory lookup,
c004 dashboard glance, c005 sales-new thumb, c008 dashboard thumb, c010 inventory list thumb). The remaining 76 were NOT run:
relaunching them would hit the limit again, so the proven findings below were implemented and every other page was checked by me
with `mobile_audit.py` plus screenshots. Findings with evidence are in the git-ignored `tools/qa/.mobile/FINDINGS.md`.

Scorecard (same tool, same demo DB), baseline -> now:
| width | pages with overflow | primary actions < 44 px | inputs < 16 px | manifest / apple icon |
|---|---|---|---|---|
| 360 | 5 -> 0 | 206 -> 4 | 64 -> 1 (a file input) | none -> yes |
| 390 | 0 -> 0 | 208 -> 4 | 64 -> 1 | none -> yes |
| 430 | 1 -> 0 | 211 -> 4 | 64 -> 1 | none -> yes |
| 1024 / 1440 (desktop guard) | 0 / 0 | 242 -> 243 (the new hero button) | 64 / 64 unchanged | |
Taps under 24 px: 43 -> 36 (the rest are cell links with enough spacing, see sweep 6).

Changes (each measured; level; desktop unchanged unless noted):
- Dashboard dues card (c004-F1 Critical, c008-F1): amount and action buttons of every row were off-screen (tables 640 px in a 308 px
  scroller) because the totals row's colspan vetoed card mode. Fix: `data-card-skip` rows are ignored by `eligible()`; compact dues card
  CSS. After: every button inside the viewport at 360 and 390, 44 px actions, about 120 px per row. L2.
- All controls 44 px (c005-F4, c008-F5): `--control-h`/`--ctl-sm` 44 px and chips/presets/summary buttons on phones: 208 -> 4. L1.
- Inputs 16 px on touch/narrow screens (iOS focus zoom): 64 -> 1. L1.
- 360 px overflow (c010-F1, c021 baseline): date-range presets wrap, stacked cards use minmax(0,1fr), pager fits 278 px: 5 pages -> 0. L1.
- Sale/purchase dock (c005-F1..F5): cancel removed from the phone dock (a tap on it dropped a filled invoice), one compact row (119 -> 86 px
  idle, recap line kept and hidden while typing), real height published as --dock-h so the undo bar/toast never overlap. L3.
- Customer combo no longer auto-focuses on touch (its list covered the quick-add button) (c005-F7). L1.
- Logout asks once on touchscreens (c008-F4: taps at 70-78 px left the page). L2.
- Dashboard: month tiles open THIS month's report (they opened last month's, showing 0) (c004-F6, c008-F3); stock-out alert strip
  (c004-F2, all widths); hero compact with one-tap «ثبت دریافت از مشتری» (c008-F2, all widths); KPI tiles label+figure on one line
  (192 -> about 150 px each); 2x2 position grid. L2/L3.
- Inventory list (c003, c010): first card from y=863 to y=499 (stock + prices on the first screen), phone sort chips (the sortable header
  is hidden on cards), whole card is the link (18 % -> 100 % tappable), prices before costs, `hx-replace-url` (search no longer pushes a
  history entry per pause), search folds Persian/Arabic digits, ك/ي, ZWNJ and word order (q=۴ found 0 rows, q=4 found 2). L1/L2.
- Customer cards: balance and status badge get the full card width (the badge broke mid-word, the figure was clipped). L1.
- List pages: extra filters fold behind one button (opens by itself when the address carries a filter): first row of the list moved
  from y=1116 to 689 (sales), 1079 to 738 (purchasing), 585 to 329 (cheques), 522 to 351 (customers). 2x2 summary tiles on list pages. L2.
- Installable: manifest + icons + apple-touch-icon, no service worker (Chrome installability check: no errors besides incognito). L3.
Not done on purpose (no proof strong enough or too risky): item-row prices behind a disclosure (c005-F6), moving remove out of the row,
price-form sticky bar and select-on-focus (c003-F7), dashboard section reordering (two critics argued opposite orders), viewport-fit=cover
(no measured harm without it). Checks: manage.py check, makemigrations --check, 1545 QA checks pass (qa_02..28), desktop scorecard unchanged.


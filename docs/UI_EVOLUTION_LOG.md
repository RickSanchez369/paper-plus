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

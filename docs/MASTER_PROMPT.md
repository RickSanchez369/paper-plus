# MASTER PROMPT — paper-plus rebuild (branch `explore/vision-rethink`)

> **Status (2026-09-26): Phases A–C executed exactly as planned here,**
> merged into `dev`/`main`, branch retired. Kept as the historical build
> plan and as the still-active plan/authorization for Phase D (§3), which
> has not started. Do not re-run Phases A–C.

Written 2026-09-24, stage 5 of Sina's own 6-stage process (see
`docs/REDESIGN_VISION.md` §7). This is the text meant to be pasted as the
opening message of a **new chat**, on this same branch, to actually start
building. Everything it refers to is already committed on
`explore/vision-rethink`.

---

## 0. Read this first

Before writing a single line of code, read `docs/REDESIGN_VISION.md` in
full. It is the single source of truth for this rebuild: the architecture
decisions, the model changes, the full 11-module page design, the stage-3
cross-page consistency review, and what is explicitly out of scope
(returns, ROADMAP 4.6 — do not touch it).

**Do not trust** `docs/RULES.md`, `docs/STATE.md`, or `docs/PROJECT_MAP.md`
for this work — they describe the *old* multi-tenant, Django-Admin-only
system this rebuild is deliberately leaving behind. `docs/PROJECT_MAP.md`
is still useful for one thing only: confirming exact current field names
before you rename/remove them (never guess a field name — regenerate it
with `tools/project_map.py` as you go, same as before).

Also load this session's memory (`feedback-autonomous-execution.md` in
particular) if it is not already in context — it documents the standing
authorization this rebuild operates under (§2 below restates the essential
part so this prompt is self-contained either way).

## 1. What this is

`paper-plus` is being rebuilt from Django-Admin-as-UI into a real,
single-business web application for a paper-products trading company:
sales, purchasing, inventory (true FIFO costing), payments, cheques,
receivables/payables, expenses, bank accounts, financial reports, and
user-activity tracking — all cross-linked so every rial and every unit of
stock traces back to who did what, when, and why (`REDESIGN_VISION.md` §1
quotes Sina's own framing of this principle; do not weaken it for
convenience anywhere).

## 2. How to work (standing authorization, not a one-off)

This is **not** the normal `docs/RULES.md` one-task-per-turn, wait-for-
pasted-output rhythm. Sina explicitly suspended that for this rebuild:
work continuously through the plan below, in sensible increments, verify
each increment yourself (see §6), commit each logical increment on
`explore/vision-rethink` yourself, and move to the next increment without
stopping to ask permission. **Only stop and ask Sina directly** when you
hit:
- a genuine fork between two reasonable designs with different real
  consequences (not "which is technically fine" — an actual tradeoff), or
- a specific business-logic ambiguity that neither the original vision
  document nor `REDESIGN_VISION.md` resolves.
Never guess at those two categories. Everything else — writing the
models, the services, the views, the templates, the HTMX wiring, the
migrations, running `manage.py migrate`, committing — do directly.

**One hard exception:** never merge `explore/vision-rethink` into `dev`,
and never force-push, without Sina explicitly reviewing and approving
that specific merge. This branch can carry many commits before that
happens — that part is fine to do autonomously — but the merge itself is
a one-way door for the shared `main`/`dev` history and needs his eyes on
it first.

## 3. Build order

Follow this order — each phase should be independently verifiable before
the next starts, because later phases depend on earlier ones being
actually correct, not just "written."

### Phase A — backend foundation (no frontend yet)
1. Remove `shared.Business`, `shared.BusinessMembership`, every `business`
   FK across every app, `BusinessScopedAdminMixin`, the per-business
   functions in `apps/shared/permissions.py`, and the group-sync signal in
   `apps/shared/signals.py`. Regenerate `PROJECT_MAP.md` after.
2. Add `apps.inventory.InventoryLayer` and `InventoryConsumption`
   (`REDESIGN_VISION.md` §3). Rewire `confirm_purchase`/`set_opening_stock`
   to create a layer; rewire `confirm_sale` to consume oldest-layer-first
   and record consumptions; rewire `cancel_sale` to reverse exact
   consumptions back to their original layers; add the purchase-
   cancellation guard (block if the layer was ever touched).
3. Add `Payment.customer`/`Payment.supplier` (nullable, mirroring
   `Cheque`'s pattern, looser constraint — see §3 of the vision doc for the
   exact rule). Update `confirm_sale`/`confirm_purchase` to set them when
   creating a Payment from a payment-entry row.
4. Add `Cheque.Status.CANCELLED` + a `cancel_cheque` service (one-way from
   PENDING only, no Payment involved, mirrors `bounce_cheque`'s shape).
5. Add `Expense` (new model — either its own small app or inside
   `apps.payments`, your call, it's not a fork) + `record_expense` +
   `cancel_expense` services, exactly as specced in `REDESIGN_VISION.md`
   §3. New `AuditLog.EventType` values: `record_expense`, `cancel_expense`,
   `cancel_cheque`.
6. Add the small stuff `REDESIGN_VISION.md` §8 flagged: `BankAccount.owner`
   field (the vision doc's "صاحب حساب").
7. Write/update `scripts/` verification scripts for every behavior change
   above (existing project convention: throwaway data inside
   `transaction.atomic()` + `raise _Rollback`, `check(label, condition)`
   helper, English-only labels — Persian text in a `print()` under this
   project's shell has crashed before, see the console-encoding lesson in
   git history). Do not proceed to Phase B until these pass.

### Phase B — frontend skeleton
- Base template: persistent sidebar nav (the 11 modules from
  `REDESIGN_VISION.md` §4), header, content block. Login page (phone +
  password — the auth model doesn't change, just drop the old business-
  picker step, there is only one business now). Dashboard route exists
  but can be a stub until Phase C finishes the modules it aggregates.
  Wire up HTMX (`REDESIGN_VISION.md` §2 item 8) — vendor it via a static
  file or a CDN link consistent with how this project already serves
  static assets, whichever fits the existing `apps/shared/static/`
  convention.
- Shared components used in multiple places (do these once, reuse
  everywhere — `REDESIGN_VISION.md` §8 explicitly flagged the "record
  payment" and "new customer/supplier" forms as must-be-shared, not
  reimplemented per page):
  - date-range picker (used by Dashboard, Financial Reports, User Activity)
  - "record payment" form (used by Receivables, Payables, Customer detail,
    Supplier detail)
  - inline "new customer" / "new supplier" mini-form

### Phase C — the 11 modules, in this order
Sales → Purchasing (+ Suppliers sub-section) → Inventory → Receivables/
Payables/Cheques → Bank Accounts → Expenses → Customers → Financial
Reports → User Activity → Dashboard (last, since it only aggregates).
This is the same order the design conversation used, for the same reason:
each module's dependencies (FIFO profit, Expense ledger, Payment party
fields) are ready by the time you reach the module that needs them. Build
each module's full spec from `REDESIGN_VISION.md` §4 (list, detail,
create-flow, filters, search, empty/error states, print where specified)
— do not build a thinner version and call it done; the spec is already
concrete on purpose. Every UI-facing string is Persian (this project has
always been Persian-first for end users — `LANGUAGE_CODE = "fa"`, existing
model `verbose_name`s are all Persian — the fact this master prompt and
`REDESIGN_VISION.md` are written in English is a docs-only convention,
never the UI language).

### Phase D — visual identity
Pick (or blend) from the 4 candidate systems in `docs/design/` (Stripe,
Linear, IBM, PostHog — see `REDESIGN_VISION.md` §5) or ask Sina to pick
if it's not obvious once real pages exist to compare against. Use the
`design-taste-frontend` skill while building pages, and
`redesign-existing-projects` if restyling something already built in
Phase C. Apply consistently app-wide — not a different feel per module.

## 4. Explicitly out of scope — do not build

**Sales/purchase returns (ROADMAP 4.6).** Sina's exact words: "فعلاً از
دامنه خارجش کن، برای بعد نگهش داریم." No page, no model, no service for
this. If you notice invoice cancellation isn't a substitute for a return
(it isn't — cancellation voids the *whole* document), that's already
known and already deferred; don't re-raise it, don't design around it.

## 5. Non-negotiables carried over from the old system

- **Views never write directly** — same rule as before, just s/Admin/View/:
  all money/stock/state changes go through `apps/*/services.py` functions,
  wrapped in `transaction.atomic()`, called from views.
- **Append-only.** Nothing financial is ever hard-deleted or edited in
  place after confirmation. Corrections are new, opposite entries
  (`cancel_sale`, `cancel_purchase`, `cancel_expense`, `cancel_cheque`,
  `bounce_cheque`) — this pattern already exists, just extend it, don't
  reinvent it.
- **Never store a derived fact.** `payment_status`, every balance, every
  report number — always a computed property or a live query, never a
  field that can drift from the ledger it's derived from (D-025).
- **Full traceability.** Every money movement and every stock movement
  must resolve back to: who, when, why, and which document. If you add
  any new model that records a fact about money or stock, it needs a
  `created_by` and enough foreign keys to answer those four questions —
  don't add an exception.

## 6. Verification — mandatory, not optional

Two layers, both required for every module, neither one substitutes for
the other:
1. **`scripts/` verification scripts**, same convention as always
   (isolated throwaway data, rolled back, `check()`/`OK`/`FAIL`).
2. **Real browser QA**, via the Claude_Browser tool, using an isolated
   throwaway test user/data (never real business data) — because this
   project has already been burned twice by JS bugs that
   `manage.py check` and backend scripts cannot see at all (Media/script
   load ordering, event-handling API changes). This risk is *larger* now,
   not smaller: the old bugs were in a few admin JS files; this rebuild is
   HTMX-driven interactivity across all 11 modules. Do not mark any page
   with a form, a live calculation, or an HTMX swap as done without
   actually clicking through it in a browser first. See memory
   `feedback-verify-admin-js-in-browser` for the exact prior failure modes
   to check for for (load order, event payload shape).

## 7. First concrete action

Start Phase A, step 1 (remove Business/BusinessMembership and everything
that references them). Report back only once Phase A is fully verified
(step 7's scripts passing), or sooner if you hit one of the two stop
conditions in §2.

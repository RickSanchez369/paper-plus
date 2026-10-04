# UI audit of 2026-10-04 (200 critics): what was deferred and why

Source: 196 findings from 196 read-only critics (100 ease, 50 detail, 46 design). 13 implementers applied what could be done
safely without touching models, services or data-writing endpoints. Each entry below needs a decision from Sina (a new feature,
a changed default, or a layout rewrite judged too risky to do blind). Merged = same idea as another finding.

## sales_pages
- **E093** - Needs SalesCreateView prefill/replace logic, new.html banner/hidden field and an atomic cancel+confirm in the POST; business flow plus files outside this group.
- **E094** - Needs a ?copy_from prefill in SalesCreateView, a changed cancel redirect, new.html banner and products/forms.py SelectedProductMixin changes; outside this group and touches the write path.
- **G008** - Rewrites the shared _invoice_summary.html partial, deletes .summary-strip CSS and edits purchasing/detail.html; belongs to the shared/purchasing group.
- **E047** - Full version (pay form on invoice page, remembered bank account, safe next redirect) needs payments views/forms and session state; only the receivables-page link was done here.
- **E048** - All edits are in payments/_dues_page.html and shared ui.js, which this group does not own.
- **E085 (remaining templates)** - cheque_detail, cheques_list and _dues_page belong to the payments group; the party_link tag is ready for them to adopt.
- **E086 (remaining parts)** - cheque_detail trail, named cheque confirms and customer_detail ledger links are in files owned by other groups; _trail_chip.html is reusable.
- **E014/E013 default all-dates search** - Changes the default meaning of the date window for text searches; per policy not built, only the explicit one-click widening was.

## sales_form
- **E095** - Its remembered-method part shipped via E002 and autofocus via E001; the rest ('ثبت و فاکتور بعدی' second submit button, flash message with links, redirect change) needs edits to apps/sales/views.py (not mine) and sales/detail.html.
- **E096** - Needs views.py redirect with ?saved=1 and a new 'saved' bar in sales/detail.html (files owned by other groups). The fresh-form autofocus part shipped via E001.
- **G004** - Redesigns sales/detail.html and the shared _invoice_summary.html, which are outside this group's files.
- **G003-rail** - The sticky two-column summary rail (form display:contents plus moving the totals card into an aside) is too risky to do blind; the hero total and dock cover its purpose.
- **E010-summary** - Not built: the per-row payment sentence panel and the radio-label rewording in forms.py. The dock recap, the credit sentence and the cheque hint under 'دریافت چک مشتری' cover the same ground; forms.py is outside my files.

## purchasing
- **E025** - Credit due-date chips, sentence, remembered term and inline guard live in the shared payment card (apps/payments template + shared/invoice_payment.js), which another group has already implemented (data-due-term chips, #credit-summary, guard); not purchasing-owned, so building it here would duplicate.
- **E026 (rest)** - Radio relabel (apps/payments/forms.py), the in-card settle-summary, due chips, 'all credit' button and inline guard belong to the shared card and are covered by the other group's credit work; only the purchase submit-bar consequence line was done here.
- **E082** - Needs apps/payments forms/views/selectors (new grouped balance selector, widget attrs), a new shared pay_guard.js and base.html script; all outside apps/purchasing and touching payables/receivables for every module.
- **E081 (rest)** - Payables-page reorder and per-row 'pay all' buttons, RecordPaymentForm default changes in payments/forms.py and the success-partial back link are in apps/payments (not mine); the same defaults are applied for the supplier-detail form through view-level form.initial instead.
- **E030(e)** - Optional per-row 'پرداخت' link not added: the pre-filled #pay card on the same page already covers settling open invoices.

## inventory
- **E036** - Days-of-cover needs a new sales-velocity selector over SaleItem and a 14/30-day window meaning; merged into the simpler viewer-side threshold lens of E035.
- **E035 (dashboard shortcut part)** - Needs an edit to apps/shared/templates/shared/dashboard.html and dashboard view counts, owned by another group; the inventory-side lens (card link, chips, remembered threshold) is done.
- **E087 (inline quick price form in expanded card, tap-to-expand rows, collapsible lede)** - Needs a new hx-post flow against a redirecting view and a new ui.js tap handler; too risky blind. Live htmx search, search-above-KPIs, phone card layout and 2-col KPIs from E087/E088 are implemented.
- **E037 (global smooth scroll)** - A page-wide html scroll-behavior change would affect other groups' pages; anchors, jump nav, scroll-margin, :target cue and list link are implemented.
- **E034 (confirm-step refinements)** - Merged into E033; the below-cost / 3x typo warn-then-confirm submit was included in price_form.js.

## dues_cheques
- **E043** - Only touches the expense form (expense_new.html, expense_form.js, forms.py AccountSelect), which is not in this group's files; left to the group that owns the expense page.
- **E044** - Same as E043: expense cheque panel and purchasing/_payment_entry_row.html are other groups' files and need a new Jalali date-math JS.
- **E039 (cheques-list one-tap column)** - Dues rows and the cheque page are done; adding actions to the cheques list needs ChequeActionView._back to preserve filters (a write endpoint) and a new column in the redesigned table.
- **E077 part D / E019 on customer and supplier detail** - The «دریافت پرداخت» header shortcut and loading payment_form JS live in partners/purchasing templates, which this group does not own. Those pages get the richer invoice rows and still work without the JS.
- **E019 pre-filled amount and pre-ticked invoices** - Not done deliberately: invoice outstanding includes pending cheques, so a full-balance default would double-count a cheque that clears later. Date, last-used account, live oldest-first allocation and a «کل مانده» chip are in instead.
- **E045 alert-strip links and G044 expenses_list/recurring_list call sites** - dashboard.html, expenses_list.html and recurring_list.html belong to other groups. The due_chip/due_tier tags are ready for them.
- **E042 native dialog** - Used a named native confirm() (data-confirm) instead of a custom dialog element, which is safer without a browser. Same information, same guard.

## partners
- **E079 (part 2: sticky tfoot)** - .table-card is overflow-x:auto so position:sticky would pin to the card, not the viewport; a closing line (tfoot) and a worded verdict at the top give the same result.
- **E079 (part 4 extra: #statement links on receivables rows)** - those templates belong to another group; only the customers-list balance link was added.
- **G011 (optional row click JS)** - marked optional; the name and balance links already give one-click entry, skipped to avoid regression risk.

## expenses_bank
- **E056** - Live schedule preview needs a new preview endpoint plus a urls.py change and server-side Jalali date math. Only its static hints and the repeat-row layout fix were done, under E055.

## insight
- **E071** - Remembered 'last backup' (localStorage nudge on dashboard/backup page) is a deferral-policy item (remembered last backup); it also needs ui.js, which this group does not own.
- **E072** - Same remembered 'last backup' status plus a fetch-based download and a drawer reminder dot that touch ui.js and _sidebar.html (not owned); too risky to do blind.
- **E075** - Global header USD chip needs base.html and a new header-wide feature (not owned); the in-place htmx refresh, change vs previous rate, failure reason and impact line were delivered on the existing card via E076.
- **E097** - The 'close the day' strip is a whole new feature, and its backup memory is a remembered last backup (deferral policy).
- **E098** - Same as E097: a new end-of-day checklist feature with a remembered last backup.
- **E100-csv** - The CSV/Excel download half of E100 is a new data export (deferral policy); only its print/PDF and copy-summary halves were built, under E099.
- **E063-calendar-baseline** - Making reports.previous_period month-aligned and showing last-month's same span for the 'this month' preset changes the default meaning of the comparison window; only the labelling of the existing baseline (which dates the percentage compares with, and a 'previous period was zero' note) was added.
- **E067-sales-list-summary** - The quantity/amount/profit strip on the sales list when a product filter is set requires editing apps/sales/views.py and sales/list.html (not owned); the report-row drill-down link with the range carried over was built.
- **E091-hero-swap** - Swapping the hero's primary button to the next setup step was not done to keep both hero buttons always reachable; the guided card carries the next-step highlight instead. The sales/purchase search dead-end link from E092 point 6 touches other groups' templates and was skipped.

## shell
- **E083** - Global search across customers/products/invoices needs a new server-side search endpoint; E084 merged into it. The client-side Ctrl+K page and action jump (G046) ships instead.
- **G035** - Turning the header into the breadcrumb trail means rewriting {% block header %} and the in-content breadcrumbs in 15+ other groups' templates, and it overlaps D010 and D011. D010 is done in JS and D011 gives the header back button; a header-wide restructure needs the owning groups.
- **D005(server part)** - The forms.py placeholder change and the dates.py invisible-character strip are Python files outside the shell group. The JS side (Persian digits, pasted bidi marks, canonical format, calendar highlight) is done.
- **D050(partial)** - Only the CSS success styling, the focus-to-confirmation hook and the tick are done. The wording fix (the Customers page says the customer was selected in an invoice), the compact flag in partners/views.py and the template edits belong to the partners and purchasing groups.
- **G042(print)** - The mark is applied to the favicon, drawer, header, sign-in and error pages. The printed invoice logo is in sales/print.html and print_invoice.css, which other groups own.
- **D037(SKU)** - The term pattern and the FIFO auto-upgrade are done. The product-code (SKU) markup in the inventory h1 and the title-to-data-tip swap on the "تعیین نشده" badge are in inventory templates owned by another group.

## print
- **D021 (page X of Y running footer)** - The @page @bottom-center margin box needs a non-zero page margin, which contradicts the E016/D020 fix (margin: 0 to remove browser headers/footers); Chrome 131+ only anyway.

## css_foundation
- **D048** - Already covered by the shell group (scrim fade without hidden, motion tokens, toast fade, reduced-motion in shell.css as D012/D009/G041); redoing it would fight their tokens.
- **D047 print stamp** - Needs a print-only line in base.html (not mine); the rest of D047 is done.
- **D046 input alignment** - Right-aligning dir=ltr inputs is a form-wide change that is risky to judge without a browser.
- **D014 U+2212 minus swap** - Optional; rewriting text nodes in JS risks breaking copy-paste and markup cells.
- **D026 p.field__hint margin-bottom** - Would add 12px in flex/grid parents other groups restyled; needs a visual pass.
- **D003 base .badge line-height hardening** - Optional; changes every status badge height.
- **D031 other forms** - product_new, bank_account_form and recurring_form already restructured by other groups.
- **D040 .row-actions wrapper + outside-click close** - Templates are owned by the dues group; Esc-to-close and the panel look are done.

## design_system
- **G038** - End-aligned money columns need every <th> to carry the numeric flag across ~21 templates owned by other groups, and the ledger/inventory tables already have their own alignment; most other items (row hover, last-row rule, clipped action cell, sort glyph) already shipped in round 1.
- **G040 (.pop floating panels)** - Turning the 13 inline <details> row forms into fixed-position popovers with click-away and a JS placer would fight the existing inline-form row styles and htmx-swapped markup; too risky without a browser.
- **G033 (in-card dead ends and the sales/recurring/expenses/bank/dues empty blocks)** - About 20 field__hint empties and 5 placeholders with custom actions or presets sit in other groups' templates and were left as is. They still get the centred CTA and the medallion from CSS.
- **G037 (template conversions)** - product_new, expense_new, bank_account_form and recurring_form already use their own grids (pn-grid, exb-*, form-grid) from round 1; only the shared CSS primitives were added.
- **G036 (action-bar markup, sales detail badge move)** - The .action-bar CSS is added but not applied. The sales/purchase detail header rows belong to other groups and were not restructured.
- **G031/G036 (touch 44px, .filters height cleanup)** - A global 44px minimum on every button would misalign buttons and the 41px inputs. Row buttons use the 40px --ctl-sm token on phones and touch screens instead.

Total deferred entries: 64.

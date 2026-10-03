# Graph Report - paper-plus-dev  (2026-10-04)

## Corpus Check
- 219 files · ~108,790 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 4, .css 2, .example 1)

## Summary
- 1900 nodes · 4540 edges · 130 communities (99 shown, 31 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 573 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2fa01cb6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- htmx.min.js
- payments/views.py
- django_conf
- django_db
- payments/services.py
- paper.py
- backup.py
- qa_lib.py
- Cheque
- DESIGN.md
- sales/views.py
- BankAccount
- products/admin.py
- Payment
- SalesInvoiceAdmin
- dates.py
- PurchaseInvoiceAdmin
- Product
- shared/views.py
- reports.py
- D-048 — An invoice discount is shared across its lines, pro rata
- Decision Log
- purchasing/forms.py
- InventoryLayerAdmin
- InventoryLayer
- sale_form.js
- InventoryDetailView
- SalesInvoice
- check
- Harness
- UserAdmin
- display
- format_toman
- purchase_form.js
- ChequeAdmin
- AuditLog
- users/views.py
- ExpenseForm
- PurchaseInvoice
- cancel_sale
- confirm_sale
- sales/urls.py
- purchasing/views.py
- CustomerDetailView
- QuickCustomerForm
- QuickProductForm
- SaleItem
- dashboard.py
- scenarios
- ExpenseForm
- purchasing/urls.py
- context_processors.py
- django_apps
- jalali_picker.js
- os
- project_map.py
- User
- PaymentAllocationAdmin
- BankAccountForm
- ExpensesListView
- PaymentAllocation
- scenarios
- SalesListView
- D-037 — Profit is realised profit: zero unless the invoice is confirmed
- SaleInvoiceForm
- DateRangeForm
- users/admin.py
- get_supplier_outstanding
- PurchasingListView
- SupplierDetailView
- shared/forms.py
- throttle.py
- PartnerAdmin
- CustomerListView
- SupplierForm
- invoice_payment.js
- نصب و به‌روزرسانی روی هاست
- qa_12_cancel_refunds.py
- PaperPlusLoginView
- RULES — paper-plus
- 0005_remove_inventorylayer_inventory_layer_source_matches_item_and_more.py
- InvoicePaymentFields
- AuditLogAdmin
- 0003_seed_role_groups.py
- UserManager
- Paper Plus
- kpi_cards
- 0002_historicaluser.py
- STATE — paper-plus
- qa_02_purchase.py
- throttle_scenarios
- 0007_tiered_prices.py
- sale_item_autoprice.js
- 0014_seed_document_sequences.py
- 0016_document_sequence_per_year.py
- CLAUDE.md — paper-plus
- Documentation map — paper-plus
- REDESIGN_VISION — condensed
- manage.py
- .is_active
- payments/apps.py
- products/apps.py
- purchasing/apps.py
- shared/apps.py
- expense_form.js
- core/urls.py
- qa/README.md

## God Nodes (most connected - your core abstractions)
1. `SalesInvoice` - 85 edges
2. `Payment` - 67 edges
3. `PurchaseInvoice` - 66 edges
4. `Cheque` - 61 edges
5. `Product` - 53 edges
6. `Decision Log` - 48 edges
7. `Expense` - 43 edges
8. `BankAccount` - 42 edges
9. `InventoryLayer` - 41 edges
10. `format_toman()` - 37 edges

## Surprising Connections (you probably didn't know these)
- `D-017: Opening stock is entered once, before any other movement` --references--> `set_opening_stock()`  [INFERRED]
  docs/DECISIONS.md → apps/inventory/services.py
- `D-056: Clearing a cheque needs an explicit account` --references--> `ClearChequeForm`  [INFERRED]
  docs/DECISIONS.md → apps/payments/forms.py
- `D-025: Payment status is derived, never stored by hand` --references--> `PaymentAllocation`  [INFERRED]
  docs/DECISIONS.md → apps/payments/models.py
- `D-073: Fixed, repeating costs (rent, bills) with reminders` --references--> `RecurringExpense`  [INFERRED]
  docs/DECISIONS.md → apps/payments/models.py
- `D-003: Primary key type is UUID` --references--> `BaseModel`  [INFERRED]
  docs/DECISIONS.md → apps/shared/models.py

## Import Cycles
- None detected.

## Communities (130 total, 31 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (100): A(), ae(), an(), at(), B(), be(), bn(), bt() (+92 more)

### Community 1 - "payments/views.py"
Cohesion: 0.06
Nodes (49): ChequeFilterForm, ClearChequeForm, Cheques list filters: status, direction, and a due-date range -- deliberately…, وصول چک": which account the money lands in / leaves from. A real answer is…, Add or edit a fixed, repeating cost (D-073): what, how much, how often, when…, RecurringExpenseForm, Routes for the five modules whose models live in this app. Receivables,…, BankAccountDetailView (+41 more)

### Community 2 - "django_conf"
Cohesion: 0.05
Nodes (34): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+26 more)

### Community 3 - "django_db"
Cohesion: 0.03
Nodes (32): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+24 more)

### Community 4 - "payments/services.py"
Cohesion: 0.09
Nodes (49): Admin for BankAccount, Payment, PaymentAllocation and Cheque (ROADMAP 4.3,…, advance_recurring(), allocate_payment(), bounce_cheque(), cancel_cheque(), cancel_expense(), clear_cheque(), next_due_after() (+41 more)

### Community 5 - "paper.py"
Cohesion: 0.06
Nodes (39): format_date(), format_datetime(), Turn ASCII digits into Persian ones for display., "۱۴۰۵/۰۷/۰۳", or "۳ مهر ۱۴۰۵" when a sentence reads better than a code. Returns…, ۱۴۰۵/۰۷/۰۳ ساعت ۱۴:۳۰" — for audit rows, where the time matters., to_persian_digits(), dict_get(), fa_digits() (+31 more)

### Community 6 - "backup.py"
Cohesion: 0.07
Nodes (32): backup_filename(), build_backup(), business_model_labels(), _dump_json(), Every model that goes into a backup, for the page's "what's inside" list., Whole-business backup: one zip with the data and the uploaded receipts.…, Return an open, rewound temporary file holding the zip (caller closes it)., Load a backup into the current database. Refuses a non-empty one. The business… (+24 more)

### Community 7 - "qa_lib.py"
Cohesion: 0.10
Nodes (25): Admin for Customer and Supplier (D-010: two separate models). Both models share…, Customer, A buyer of the business's products., PriceTier, The two ways the business sells (D-075): to shops in bulk, or to walk-in buyers., The one-shot new-sale form. Three pieces submitted together: the invoice…, BaseModel, Abstract base for all main models. Provides a UUID primary key and… (+17 more)

### Community 8 - "Cheque"
Cohesion: 0.08
Nodes (33): Cheque, Meta, A physical cheque's lifecycle (ROADMAP 4.4): pending -> cleared / bounced. A…, Money movements, independent of the invoices they settle (ROADMAP 4.3). A…, A fixed cost that comes round again: shop rent, electricity, water -- every…, هر ۱ ماه" style text for lists., RecurringExpense, Status (+25 more)

### Community 9 - "DESIGN.md"
Cohesion: 0.05
Nodes (37): Border Radius Scale, Brand & Accent, Breakpoints, Buttons, Cards & Containers, Collapsing Strategy, Colors, Components (+29 more)

### Community 10 - "sales/views.py"
Cohesion: 0.10
Nodes (23): Admin for InventoryMovement: a read-only view of the stock ledger. The ledger…, The Inventory module's one stock-creating form: a new product, with its opening…, Inventory module routes. No opening-stock or adjustment page: stock changes…, Inventory module views. Nothing here writes stock directly -- set_opening_stock…, The Customers module plus the inline "new customer" component shared with…, excluded_product_ids(), "کالای جدید", inline mid-purchase. Unlike the quick customer/supplier forms,…, Ids from the item-row search's `exclude` parameter (products already on the… (+15 more)

### Community 11 - "BankAccount"
Cohesion: 0.08
Nodes (22): AccountChoiceField, AccountSelect, ChequeCompletionForm, current_account_field(), Meta, PayInvoiceForm, PaymentEntryFormMixin, pos_account_field() (+14 more)

### Community 12 - "products/admin.py"
Cohesion: 0.09
Nodes (26): get_active_layers(), get_current_cost_map(), get_inventory_value_map(), get_last_known_cost_map(), get_layer_balance(), get_stock_map(), Most recent known cost per product, including exhausted layers. Display-only…, Toman value of each product's stock: {product_id: value}. Sum of every active… (+18 more)

### Community 13 - "Payment"
Cohesion: 0.08
Nodes (23): Direction, Expense, Payment, PaymentMethod, Sum of this payment's allocations so far, in Toman., How much of this payment has not yet been tied to an invoice., Whoever this money moved with, or None for an expense/unattributed row., Money spent on running the business: rent, wages, fuel, a repair. Deliberately… (+15 more)

### Community 14 - "SalesInvoiceAdmin"
Cohesion: 0.10
Nodes (15): is_locked(), Media, action, display, register, SimpleHistoryAdmin, Sales invoices: draft entry in admin, confirmation via the service., Confirm each selected invoice through confirm_sale. One service call per… (+7 more)

### Community 15 - "dates.py"
Cohesion: 0.10
Nodes (27): clamp_month(), month_grid(), Today as a `jdatetime.date`, in the active (Tehran) timezone., First and last Gregorian dates of the Jalali week containing a date. The…, One month laid out for the date picker: leading blanks, then each day. Lives…, Normalise a year/month the client asked for, rolling over at the edges. The…, Jalali is the calendar this business works in; Gregorian/UTC is what the…, A stored date (or datetime) as a `jdatetime.date`. A datetime is converted in… (+19 more)

### Community 16 - "PurchaseInvoiceAdmin"
Cohesion: 0.10
Nodes (15): is_locked(), Media, PurchaseInvoiceAdmin, PurchaseItemInline, PurchasePaymentEntryInline, action, display, register (+7 more)

### Community 17 - "Product"
Cohesion: 0.11
Nodes (21): InventoryMovement, MovementType, Append-only ledger of stock changes. The single source of truth for stock. Rows…, Quantity with its effect on stock: positive for inflow, negative for outflow., get_negative_stock_products(), get_stock(), get_total_inventory_value(), Toman value of all stock on hand, across every product. (+13 more)

### Community 18 - "shared/views.py"
Cohesion: 0.14
Nodes (20): User Activity's own filters, alongside the shared date range: which user, which…, UserActivityFilterForm, Dashboard, plus the two cross-cutting report modules., BackupView, DashboardView, DatePickerMonthView, DateRangeMixin, LoginRequiredMixin (+12 more)

### Community 19 - "reports.py"
Cohesion: 0.11
Nodes (26): cheques_by_status(), expenses_total(), gross_profit(), inventory_snapshot(), pct_change(), previous_period(), purchases_by_product(), purchases_total() (+18 more)

### Community 20 - "D-048 — An invoice discount is shared across its lines, pro rata"
Cohesion: 0.08
Nodes (24): This line's part of the invoice discount (D-048, see…, What this line actually brought in: line total minus its share of the invoice…, D-048 — An invoice discount is shared across its lines, pro rata, D-049: Static files served by whitenoise, D-050: Visual identity is IBM Carbon-inspired, D-051: Deployment and SHADOW are out of scope, D-053: A purchase invoice settles like a sale (mode + account), D-054: Rules settled by the full QA pass (+16 more)

### Community 21 - "Decision Log"
Cohesion: 0.08
Nodes (26): D-001: Project layout and settings package name, D-002: Configuration via environment variables, D-003: Primary key type is UUID, D-004: Time is stored in UTC, D-005: Interface language, D-006: Empty text fields use `blank=True` only, never `null=True`, D-008: User is not scoped to a Business, D-009: Roles as a choices field (+18 more)

### Community 22 - "purchasing/forms.py"
Cohesion: 0.10
Nodes (19): For an invoice item form whose `product` is a hidden input filled by the row's…, Live stock of `selected_product`, the same figure a search result shows., SelectedProductMixin, Meta, PurchasePaymentEntryForm, The cheque fields are optional here on purpose, mirrors…, Meta, PurchaseItemForm (+11 more)

### Community 23 - "InventoryLayerAdmin"
Cohesion: 0.11
Nodes (8): InventoryConsumptionAdmin, InventoryLayerAdmin, InventoryMovementAdmin, display, register, Read-only view of which layer each sold line drew from. Append-only: a…, Read-only ledger browser: filter, search, inspect. Never write., Read-only view of the FIFO cost layers. Written only by services…

### Community 24 - "InventoryLayer"
Cohesion: 0.12
Nodes (18): InventoryConsumption, InventoryLayer, Meta, One batch of stock bought (or counted in) at one known unit cost. The cost…, Toman still sitting in this layer., Exactly how much of one layer one sale item took (D-036). A sale is the only…, Toman this row accounts for, at the layer's own cost., Source (+10 more)

### Community 25 - "sale_form.js"
Cohesion: 0.19
Nodes (17): applyTier(), chosenProductIds(), currentDiscount(), currentDiscountMode(), currentTier(), formatToman(), intVal(), pickProduct() (+9 more)

### Community 26 - "InventoryDetailView"
Cohesion: 0.11
Nodes (14): InventoryProductForm, QuickProductForm plus an optional one-time opening stock. Blank quantity: the…, InventoryDetailView, ProductCreateView, DetailView, LoginRequiredMixin, View, + کالای جدید", with an optional one-time opening stock (D-044) -- the only… (+6 more)

### Community 27 - "SalesInvoice"
Cohesion: 0.09
Nodes (13): PaymentMethod, PaymentStatus, Confirmed and cancelled invoices are both frozen (D-014, D-023)., Deprecated alias for `subtotal`; kept until admin.py is checked (2.7 cleanup)., A sale to a customer. Mirrors PurchaseInvoice. Draft invoices are editable;…, Subtotal minus the invoice-level discount, in Toman (R 9)., Sum of PaymentAllocation rows against this invoice, in Toman (4.3), not…, unpaid / partial / paid, derived from paid_amount vs total -- never typed… (+5 more)

### Community 28 - "check"
Cohesion: 0.15
Nodes (17): overdue_credit_invoices(), Confirmed sales invoices still owing money, older than `threshold_days`. Sales…, last(), n_inv(), scenarios(), scenarios(), Receipt upload rules (only PDF/PNG/JPG/WebP, matching content, <= 5 MB)., upload_scenarios() (+9 more)

### Community 29 - "Harness"
Cohesion: 0.13
Nodes (9): new(), exp(), Harness, Exception, items: [(product, qty, price)]; account: BankAccount | None (cash no longer…, POST the clear form. account: "cheque" (its own account, else cash), "cash", a…, rnd(), _Rollback (+1 more)

### Community 30 - "UserAdmin"
Cohesion: 0.12
Nodes (15): AdminConfig, AdminSite, PaperPlusAdminConfig, PaperPlusAdminSite, Django admin, reachable by active superusers only., Superuser-only admin site. WHY this exists now: until this rebuild, `/admin/`…, Replaces `django.contrib.admin` in INSTALLED_APPS., register (+7 more)

### Community 31 - "display"
Cohesion: 0.14
Nodes (5): ExpenseAdmin, PaymentAdmin, display, Add-only: every Expense is created through `record_expense`, which also books…, Add-only: every Payment is created through `record_payment` (see save_model).

### Community 32 - "format_toman"
Cohesion: 0.16
Nodes (8): ProductAdmin, display, register, SimpleHistoryAdmin, Add the total inventory value (4.1: "دارایی کل") across the current (filtered)…, Product catalogue with a live stock column and one-time opening stock., format_toman(), 250,000 تومان' -- every stored amount is already whole Toman (D-043).

### Community 33 - "purchase_form.js"
Cohesion: 0.20
Nodes (13): addRow(), chosenProductIds(), fillRow(), formatToman(), intVal(), pickProduct(), recomputeInvoice(), recomputeRemaining() (+5 more)

### Community 34 - "ChequeAdmin"
Cohesion: 0.13
Nodes (7): ChequeAdmin, action, A PENDING cheque is still editable (Sina, 2026-09-24: entering one incomplete…, One clear_cheque call per row; a rejected one does not affect the rest., One cancel_cheque call per row; a rejected one does not affect the rest., One bounce_cheque call per row; a rejected one does not affect the rest., One cancel_expense call per row; a rejected one does not affect the rest.

### Community 35 - "AuditLog"
Cohesion: 0.12
Nodes (15): Admin registration for the shared app. Business and BusinessMembership are…, AuditLog, EventType, Meta, Append-only record of service-level events (D-029). Never updated or deleted…, _amount_for(), get_activity_feed(), get_activity_summary() (+7 more)

### Community 36 - "users/views.py"
Cohesion: 0.13
Nodes (13): parse_jalali(), Normalise Persian/Arabic-Indic digits to ASCII for parsing., Parse a typed Jalali date into a Gregorian `datetime.date`. Returns None when…, to_ascii_digits(), Sign-in and sign-out. User management itself stays in /admin/ (D-034)., PaperPlusLogoutView, PhoneLoginForm, Django's login form, relabelled for a phone number. `AuthenticationForm` hard-… (+5 more)

### Community 37 - "ExpenseForm"
Cohesion: 0.14
Nodes (9): ChequeForm, ExpenseForm, Meta, PaymentAllocationForm, PaymentForm, Persian errors for the amount and exactly-one-invoice CHECKs (see PaymentForm)., Shows a friendly Persian error for the direction/party (or direction/invoice)…, `payment` and the cancellation fields belong to the services, not a form.… (+1 more)

### Community 38 - "PurchaseInvoice"
Cohesion: 0.12
Nodes (10): PaymentMethod, PaymentStatus, PurchaseInvoice, Confirmed and cancelled invoices are both frozen (D-014, D-023)., Sum of line totals, in Toman., Sum of PaymentAllocation rows against this invoice, in Toman (4.3), not…, A purchase from a supplier. Draft invoices are editable. Once confirmed by…, unpaid / partial / paid, derived from paid_amount vs total_amount -- never… (+2 more)

### Community 39 - "cancel_sale"
Cohesion: 0.15
Nodes (15): cancel_purchase(), atomic, Cancel a confirmed purchase invoice: reverse its stock, freeze it (D-023). The…, cancel_sale(), atomic, Cancel a confirmed sales invoice: reverse its stock, freeze it (D-023). The…, 1. What it is, 4. Domain model (+7 more)

### Community 40 - "confirm_sale"
Cohesion: 0.13
Nodes (15): Meta, The cheque fields (number/bank/due date) are optional here on purpose (Sina,…, SalesPaymentEntryForm, Meta, Method, One planned payment line on a draft sales invoice (added at Sina's request,…, SalesPaymentEntry, confirm_sale() (+7 more)

### Community 41 - "sales/urls.py"
Cohesion: 0.17
Nodes (11): ProductSearchView, DetailView, LoginRequiredMixin, View, Live product search for an item row. Returns a results partial, not JSON -- the…, Detail: items with FIFO cost + profit per line, totals with invoice profit…, POST-only: cancel_sale itself is the only real guard (superuser + confirmed-…, A print-friendly render of the same invoice (RULES.md excludes PDF generation… (+3 more)

### Community 42 - "purchasing/views.py"
Cohesion: 0.19
Nodes (11): QuickSupplierForm, "مشتری جدید" / "تأمین‌کننده جدید" — the inline mini-forms. A party can be…, New supplier, inline. Reused by the Suppliers sub-section and the purchase form., Meta, A vendor the business buys products from., Supplier, QuickSupplierCreateView, Purchasing module views. Mirrors apps/sales/views.py; nothing here writes stock… (+3 more)

### Community 43 - "CustomerDetailView"
Cohesion: 0.17
Nodes (12): CustomerForm, Full edit form for the Customers detail page -- the quick-create form only asks…, Customers module routes. Suppliers live under Purchasing., CustomerDetailView, CustomerUpdateView, DetailView, LoginRequiredMixin, View (+4 more)

### Community 44 - "QuickCustomerForm"
Cohesion: 0.16
Nodes (12): QuickCustomerForm, New customer, inline. Reused by the Customers page and the sale form., QuickCustomerCreateView, Creates a Customer from the inline mini-form (htmx POST). On success, returns…, percent_to_amount(), Whole-Toman discount for ``percent`` % of ``subtotal`` (D-070). Rounded down,…, _empty_forms(), _posted_tier() (+4 more)

### Community 45 - "QuickProductForm"
Cohesion: 0.17
Nodes (10): Meta, QuickProductForm, New product, inline. Reused wherever a purchase or (later) the Inventory module…, PurchaseInvoiceForm, Header fields: who, when, the supplier's own invoice number. No discount field…, plan_full_payment(), The default settlement (mirrors sales, D-046/D-053/D-069): the whole invoice…, _empty_forms() (+2 more)

### Community 46 - "SaleItem"
Cohesion: 0.13
Nodes (8): One invoice line. `product` is a hidden input: the visible picker is the JS-…, (retail, wholesale) of the product this row already holds, so a re-rendered row…, SaleItemForm, One line of a sales invoice., Fill a blank unit_price from the product's current default before the…, What these units actually cost, in Toman, from the FIFO layers this line drew…, How many of these units FIFO could actually find a layer for., SaleItem

### Community 47 - "dashboard.py"
Cohesion: 0.15
Nodes (12): cheques_due_soon(), cheques_needing_completion(), negative_stock(), Products whose stock has gone negative (defensive only, D-016 -- an oversell is…, What has to be paid in the next ``days`` days (plus anything already late),…, The latest N events, all users., Read-only aggregates for the Dashboard. Everything here is computed live, same…, Pending cheques due within `days`, INCLUDING ones already past their due date… (+4 more)

### Community 48 - "scenarios"
Cohesion: 0.16
Nodes (13): InventoryListView, TemplateView, List: cards (total value, item count, negative-stock warning, a USD…, atomic, Set a product's current selling prices (D-075): ``retail`` is…, Write services for the product catalogue., Set the RETAIL price only (the one price there was before D-075); kept for…, update_selling_price() (+5 more)

### Community 49 - "ExpenseForm"
Cohesion: 0.16
Nodes (7): ExpenseForm, New-expense one-shot form (D-045, D-072): date, reason, amount and HOW it is…, An unsaved Cheque with the typed cheque details, for a cheque expense (else…, ExpenseCreateView, New-expense one-shot form: atomic create of the Expense (and, for a transfer,…, A UUID from a query string, or None when it is missing or malformed., _uuid_or_none()

### Community 50 - "purchasing/urls.py"
Cohesion: 0.21
Nodes (11): Purchasing module routes, including the Suppliers sub-section., ProductSearchView, PurchaseCancelView, LoginRequiredMixin, View, QuickProductCreateView, Live product search for an item row -- mirrors sales.views's version, with the…, Creates a Product from the inline "+ کالای جدید" mini-form. Reuses partners/… (+3 more)

### Community 51 - "context_processors.py"
Cohesion: 0.14
Nodes (11): company(), navigation(), Who issues printed documents (settings.COMPANY, filled from .env)., The sidebar, plus which section the current page belongs to. The active section…, Context every page of the frontend needs, so no view has to remember it., NavGroup, NavItem, One clickable destination in the sidebar. (+3 more)

### Community 52 - "django_apps"
Cohesion: 0.15
Nodes (9): InventoryConfig, AppConfig, PartnersConfig, AppConfig, AppConfig, SalesConfig, AppConfig, UsersConfig (+1 more)

### Community 53 - "jalali_picker.js"
Cohesion: 0.31
Nodes (11): buildPopup(), close(), commit(), currentGrid(), load(), markSelected(), onPopupClick(), open() (+3 more)

### Community 54 - "os"
Cohesion: 0.18
Nodes (8): ASGI config for core project. It exposes the ASGI callable as a module-level…, WSGI config for core project. It exposes the WSGI callable as a module-level…, Entry point for hosts that run Python apps through Passenger…, django_core_asgi, django_core_wsgi, os, sys, Empty every table in the database, keeping the schema and the applied-…

### Community 55 - "project_map.py"
Cohesion: 0.21
Nodes (12): importlib, inspect, build_tree(), describe_field(), describe_functions(), describe_model(), main(), Generate PROJECT_MAP.md: file tree, settings, models and public functions. Run… (+4 more)

### Community 56 - "User"
Cohesion: 0.18
Nodes (9): AbstractBaseUser, Meta, First + last name, or "" when neither is set. AbstractBaseUser does not provide…, First name if known, otherwise the phone number., Custom user, identified by mobile phone number. Carries no role: any…, User, Business & technical rules — paper-plus, Decision index (full text: [DECISIONS.md](DECISIONS.md)) (+1 more)

### Community 57 - "PaymentAllocationAdmin"
Cohesion: 0.17
Nodes (6): BankAccountAdmin, PaymentAllocationAdmin, register, Add-only: every allocation is created through `allocate_payment` (see…, Fixed costs are managed on the Expenses > هزینه‌های ثابت page; this is the…, RecurringExpenseAdmin

### Community 58 - "BankAccountForm"
Cohesion: 0.23
Nodes (7): BankAccountForm, Add or edit an account from the Bank Accounts page itself -- before this, an…, BankAccountCreateView, BankAccountUpdateView, + حساب بانکی جدید" -- a full page, like Inventory's new product: not mid-…, Fix a name/owner/number typo. Same form as create; the ledger is untouched --…, D-045 — Expense: no counterparty; the paying account is chosen explicitly

### Community 59 - "ExpensesListView"
Cohesion: 0.23
Nodes (8): ExpenseFilterForm, PayExpenseForm, Expenses list filters: free-text search over reason/note, bank account, and an…, پرداخت" for an expense that is still owed (a نسیه one when its date comes, or…, ExpensePayView, ExpensesListView, Expenses: newest-first, cards for today's and this month's totals (cancelled…, POST-only door to pay_expense (a نسیه expense, or one whose cheque bounced).

### Community 60 - "PaymentAllocation"
Cohesion: 0.23
Nodes (8): Money received from a customer, or paid to a supplier. The party is fixed by…, Money from a customer comes in; money to a supplier goes out., RecordPaymentForm, PaymentAllocation, Ties part (or all) of a Payment to exactly one invoice (D-025). Exactly one of…, Shared POST handler behind the one "ثبت پرداخت" component: books the Payment,…, _RecordPaymentView, D-038 — Payment gains customer / supplier

### Community 61 - "scenarios"
Cohesion: 0.18
Nodes (9): get_total_payables_as_of(), get_total_receivables_as_of(), Business-wide accounts receivable as of a past date: confirmed sales invoices…, Exact mirror of `get_total_receivables_as_of`, Supplier/PurchaseInvoice side., Open receivables, open payables, total bank balance (all active accounts…, totals_now(), Open receivables/payables as of range end -- the business-wide totals; the per-…, receivables_payables_as_of() (+1 more)

### Community 62 - "SalesListView"
Cohesion: 0.20
Nodes (7): BaseSaleItemFormSet, Catches the same product picked twice before the DB's unique constraint…, The list page's structured filters, deliberately separate from the free-text…, SalesFilterForm, TemplateView, List: summary cards always show today/this-month/ open/profit regardless of the…, SalesListView

### Community 63 - "D-037 — Profit is realised profit: zero unless the invoice is confirmed"
Cohesion: 0.17
Nodes (7): Sum of line totals, before discount, in Toman (R 9)., Realised profit: invoice total minus real cost of goods, in Toman. The discount…, True when any line was sold without a cost basis (see SaleItem)., Units sold with no layer behind them, so no cost basis at all. Non-zero only…, Realised profit: net total (after this line's share of the invoice discount,…, D-037 — Profit is realised profit: zero unless the invoice is confirmed, D-052: A sale can never exceed the stock on hand

### Community 64 - "SaleInvoiceForm"
Cohesion: 0.18
Nodes (5): Meta, One planned payment row (card reader / bank transfer / cheque, D-069), same…, Invoice-level fields: who, when, how much discount, and how it was settled. The…, SaleInvoiceForm, SalesPaymentEntryForm

### Community 65 - "DateRangeForm"
Cohesion: 0.22
Nodes (6): DateRangeForm, Preset, The Gregorian dates a named preset covers, inclusive of both ends., (start, end) for this submission, falling back to the default when the form was…, Which button should look pressed., The date range every report-shaped page filters by. Built once here because…

### Community 66 - "users/admin.py"
Cohesion: 0.20
Nodes (10): Meta, Admin for the custom User model (D-007: phone is the USERNAME_FIELD). Django's…, Form for the "add user" page: phone + name + password twice. Based on…, Form for the "change user" page. Only Meta is replaced; the parent keeps the…, UserCreateForm, UserEditForm, BaseUserCreationForm, django_contrib_auth_admin (+2 more)

### Community 67 - "get_supplier_outstanding"
Cohesion: 0.24
Nodes (7): get_supplier_outstanding(), Accounts payable: this supplier's unpaid balance across its confirmed purchase…, Suppliers list filters: free-text search over name/phone and active/inactive…, SupplierFilterForm, TemplateView, Suppliers sub-section list: name, phone, total purchased, outstanding payable…, SupplierListView

### Community 68 - "PurchasingListView"
Cohesion: 0.24
Nodes (6): BasePurchaseItemFormSet, PurchasingFilterForm, Catches the same product picked twice before the DB's unique constraint…, Mirrors sales.forms.SalesFilterForm; see there for why the date range and the…, PurchasingListView, List: symmetric to Sales' list, no profit card -- profit is sales-only.

### Community 69 - "SupplierDetailView"
Cohesion: 0.20
Nodes (7): PurchaseDetailView, PurchasePrintView, DetailView, Detail: no profit column -- profit is sales-only. Payment/cheque history and…, A print-friendly render of the same invoice (RULES.md excludes PDF generation…, Purchase history, payments made, cheques issued, running balance -- the same…, SupplierDetailView

### Community 70 - "shared/forms.py"
Cohesion: 0.20
Nodes (6): JalaliDateInput, A text box the Jalali date-picker attaches to. Deliberately not `<input…, Form pieces every module reuses. `JalaliDateField` is the only way a date…, Show a stored Gregorian date back to the user as Jalali., django_contrib_auth, django_utils

### Community 71 - "throttle.py"
Cohesion: 0.36
Nodes (7): _ip_key(), is_locked(), _phone_key(), Brute-force protection for the sign-in page. Failed sign-ins are counted per…, record_failure(), reset(), django_core_cache

### Community 72 - "PartnerAdmin"
Cohesion: 0.29
Nodes (7): CustomerAdmin, PartnerAdmin, register, Shared configuration for Customer and Supplier. Not registered itself; a plain…, Customers: the counterparty of sales invoices., Suppliers: the counterparty of purchase invoices., SupplierAdmin

### Community 73 - "CustomerListView"
Cohesion: 0.29
Nodes (7): CustomerFilterForm, Customers list filters: free-text search over name/phone, account status…, _customer_row(), CustomerListView, TemplateView, One list-page row: badge, open balance, invoice count, last purchase date --…, List: name, phone, account status badge, open balance, invoice count, last…

### Community 74 - "SupplierForm"
Cohesion: 0.32
Nodes (5): Meta, Full create/edit form for the Suppliers sub-section -- the supplier counterpart…, SupplierForm, + تأمین‌کنندهٔ جدید" on the Suppliers list itself -- the same Supplier model…, SupplierCreateView

### Community 75 - "invoice_payment.js"
Cohesion: 0.43
Nodes (6): digitsToAscii(), field(), num(), syncCreditDue(), syncFullAmounts(), total()

### Community 76 - "نصب و به‌روزرسانی روی هاست"
Cohesion: 0.25
Nodes (7): بازیابی, تنظیم مشخصات شرکت روی فاکتور, نصب اول, نصب و به‌روزرسانی روی هاست, هر بار که تغییری داده شد (به‌روزرسانی), پشتیبان‌گیری, پیش‌نیازهای هاست (قبل از خرید بپرسید)

### Community 78 - "qa_12_cancel_refunds.py"
Cohesion: 0.43
Nodes (6): get_customer_outstanding(), Accounts receivable: this customer's unpaid balance across its confirmed sales…, last_purchase(), last_sale(), D-055: cancelling an invoice gives its money back., scenarios()

### Community 79 - "PaperPlusLoginView"
Cohesion: 0.43
Nodes (3): PaperPlusLoginView, Sign-in page. Already-signed-in visitors are sent on to the dashboard., LoginView

### Community 80 - "RULES — paper-plus"
Cohesion: 0.29
Nodes (7): Django gotchas, Environment traps (Windows / PowerShell only), Git, Language, RULES — paper-plus, Session start, Workflow

### Community 81 - "0005_remove_inventorylayer_inventory_layer_source_matches_item_and_more.py"
Cohesion: 0.33
Nodes (5): link_opening_movements_to_their_layer(), Migration, noop_reverse(), Nothing to undo: unlinking would only throw away a fact, not restore prior…, Backfill `InventoryMovement.layer` for every existing OPENING row.…

### Community 82 - "InvoicePaymentFields"
Cohesion: 0.33
Nodes (3): InvoicePaymentFields, ``[(method, account, amount_or_None)]`` for the methods picked, for…, The payment half of the sales/purchase invoice forms (D-069), written once so…

### Community 83 - "AuditLogAdmin"
Cohesion: 0.33
Nodes (3): AuditLogAdmin, register, Read-only view of AuditLog rows (D-029). No add/change/delete: rows are written…

### Community 84 - "0003_seed_role_groups.py"
Cohesion: 0.40
Nodes (4): get_perms(), Migration, Return Permission objects for app_label.ModelName matching codenames., seed_groups()

### Community 85 - "UserManager"
Cohesion: 0.53
Nodes (4): Manager for the custom User model. Django calls these two methods; they must…, UserManager, BaseUserManager, D-007: Users log in with their mobile phone number

### Community 86 - "Paper Plus"
Cohesion: 0.33
Nodes (6): Documentation, Getting started, Modules, Paper Plus, Stack, Status

### Community 87 - "kpi_cards"
Cohesion: 0.40
Nodes (4): kpi_cards(), Sales/purchases/expenses/net-profit, each today + this month -- reuses…, month_bounds(), First and last Gregorian dates of a Jalali month. Used by the date-range…

### Community 88 - "0002_historicaluser.py"
Cohesion: 0.40
Nodes (3): Migration, Migration, django_core_validators

### Community 89 - "STATE — paper-plus"
Cohesion: 0.40
Nodes (5): Acceptance scenarios (ROADMAP Phase 5, not yet formally closed), Next, Open items (raise with Sina before touching), STATE — paper-plus, Where we are

### Community 90 - "qa_02_purchase.py"
Cohesion: 0.60
Nodes (4): n_inv(), scenarios(), seq(), digits_fa()

### Community 91 - "throttle_scenarios"
Cohesion: 0.50
Nodes (4): Sign-in brute-force protection (D-058)., throttle_scenarios(), fresh(), login()

### Community 92 - "0007_tiered_prices.py"
Cohesion: 0.50
Nodes (3): Migration, Nothing changes on day one: wholesale starts equal to retail (the owner edits…, seed_wholesale_and_units()

### Community 93 - "sale_item_autoprice.js"
Cohesion: 0.83
Nodes (3): bind(), fillPrice(), ready()

### Community 94 - "0014_seed_document_sequences.py"
Cohesion: 0.50
Nodes (3): Migration, Make sure one counter row exists per document type. `get_next_document_number`…, seed_sequences()

### Community 95 - "0016_document_sequence_per_year.py"
Cohesion: 0.50
Nodes (3): drop_unused_legacy_counters(), Migration, The pre-D-064 counters (year 0, seeded at 9956001) that never issued a number…

### Community 96 - "CLAUDE.md — paper-plus"
Cohesion: 0.50
Nodes (3): CLAUDE.md — paper-plus, How to work, Style

### Community 97 - "Documentation map — paper-plus"
Cohesion: 0.50
Nodes (4): Documentation map — paper-plus, Every session starts with (in this order), Reference, Where to look

### Community 98 - "REDESIGN_VISION — condensed"
Cohesion: 0.50
Nodes (4): Cross-page rules (§8), Modules (§4), REDESIGN_VISION — condensed, Still open

### Community 99 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Django's command-line utility for administrative tasks., Run administrative tasks.

## Knowledge Gaps
- **194 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `Migration` (+189 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 812 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SalesInvoice` connect `SalesInvoice` to `payments/views.py`, `payments/services.py`, `paper.py`, `qa_lib.py`, `Cheque`, `sales/views.py`, `Payment`, `dates.py`, `Product`, `reports.py`, `check`, `AuditLog`, `cancel_sale`, `confirm_sale`, `sales/urls.py`, `CustomerDetailView`, `dashboard.py`, `scenarios`, `scenarios`, `SalesListView`, `D-037 — Profit is realised profit: zero unless the invoice is confirmed`, `SaleInvoiceForm`, `CustomerListView`, `qa_12_cancel_refunds.py`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `format_toman()` connect `format_toman` to `payments/views.py`, `ChequeAdmin`, `payments/services.py`, `paper.py`, `cancel_sale`, `sales/urls.py`, `sales/views.py`, `BankAccount`, `products/admin.py`, `purchasing/views.py`, `SalesInvoiceAdmin`, `Payment`, `PurchaseInvoiceAdmin`, `InventoryLayerAdmin`, `PaymentAllocationAdmin`, `display`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `Decision Log` connect `Decision Log` to `.is_active`, `payments/services.py`, `paper.py`, `cancel_sale`, `confirm_sale`, `products/admin.py`, `architecture.md`, `Payment`, `dates.py`, `D-048 — An invoice discount is shared across its lines, pro rata`, `UserManager`, `BankAccountForm`, `PaymentAllocation`, `UserAdmin`, `D-037 — Profit is realised profit: zero unless the invoice is confirmed`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 43 inferred relationships involving `SalesInvoice` (e.g. with `_customer_row()` and `CustomerDetailView`) actually correct?**
  _`SalesInvoice` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `Payment` (e.g. with `CustomerDetailView` and `PaymentForm`) actually correct?**
  _`Payment` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `PurchaseInvoice` (e.g. with `get_supplier_outstanding()` and `get_total_payables_as_of()`) actually correct?**
  _`PurchaseInvoice` has 34 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Cheque` (e.g. with `ChequeAdmin` and `ChequeForm`) actually correct?**
  _`Cheque` has 37 INFERRED edges - model-reasoned connections that need verification._
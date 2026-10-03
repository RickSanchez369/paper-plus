# Graph Report - paper-plus-dev  (2026-10-04)

## Corpus Check
- 240 files · ~119,051 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 4, .css 2, .example 1)

## Summary
- 2057 nodes · 4963 edges · 141 communities (105 shown, 36 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 634 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2d0991c7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- htmx.min.js
- payments/views.py
- django_db_models_deletion
- django_db
- payments/services.py
- paper.py
- backup.py
- sales/services.py
- Cheque
- DESIGN.md
- purchasing/views.py
- payments/forms.py
- products/admin.py
- Payment
- is_locked
- dates.py
- PurchaseInvoiceAdmin
- Product
- DateRangeForm
- audit
- D-048 — An invoice discount is shared across its lines, pro rata
- Decision Log
- sales/forms.py
- InventoryLayerAdmin
- InventoryLayer
- sale_form.js
- InventoryDetailView
- SalesInvoice
- check
- Harness
- User
- ChequeAdmin
- format_toman
- purchase_form.js
- .mark_bounced
- shared/models.py
- users/views.py
- ExpenseForm
- PurchaseInvoice
- cancel_purchase
- SalesPaymentEntry
- SalesListView
- Customer
- QuickCustomerForm
- percent_to_amount
- PurchaseInvoiceForm
- .clean_fields
- django_conf
- qa_17_pricing_units.py
- ExpenseForm
- LoginRequiredMixin
- context_processors.py
- django_apps
- jalali_picker.js
- os
- project_map.py
- ExchangeRate
- PaymentAllocationAdmin
- BankAccountForm
- ExpensesListView
- RecordPaymentForm
- RecurringExpenseForm
- .clean
- D-037 — Profit is realised profit: zero unless the invoice is confirmed
- SaleInvoiceForm
- LoginRequiredMixin
- exchange.py
- SupplierListView
- PurchasingListView
- purchasing/urls.py
- Expense
- RecurringExpense
- PartnerAdmin
- SalesInvoiceAdmin
- SupplierForm
- invoice_payment.js
- نصب و به‌روزرسانی روی هاست
- architecture.md
- BankAccount
- qa_lib.py
- confirm_sale
- 0005_remove_inventorylayer_inventory_layer_source_matches_item_and_more.py
- InvoicePaymentFields
- shared/admin.py
- 0003_seed_role_groups.py
- convert_units.py
- ClearChequeForm
- kpi_cards
- users/models.py
- QuickProductForm
- django_core_management_base
- django_test
- 0007_tiered_prices.py
- sale_item_autoprice.js
- 0014_seed_document_sequences.py
- 0016_document_sequence_per_year.py
- CLAUDE.md — paper-plus
- PaymentAdmin
- number_to_words
- qa_20_usd_rate.py
- .is_active
- usd_rate_card
- 0012_carton_pack.py
- parent_url
- qa_03_sales.py
- expense_form.js
- validators.py
- qa/README.md
- qa_21_units.py
- ProductAdminForm
- 0009_wholesale_per_carton.py
- sales_by_product
- pathlib
- RecurringExpenseAdmin
- PurchasePaymentEntryForm
- .discount_allocation
- .discount_share
- .net_total

## God Nodes (most connected - your core abstractions)
1. `SalesInvoice` - 99 edges
2. `PurchaseInvoice` - 74 edges
3. `Payment` - 70 edges
4. `Cheque` - 61 edges
5. `Product` - 61 edges
6. `InventoryLayer` - 50 edges
7. `Decision Log` - 48 edges
8. `BankAccount` - 45 edges
9. `Expense` - 43 edges
10. `confirm_sale()` - 41 edges

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

## Communities (141 total, 36 thin omitted)

### Community 0 - "htmx.min.js"
Cohesion: 0.08
Nodes (100): A(), ae(), an(), at(), B(), be(), bn(), bt() (+92 more)

### Community 1 - "payments/views.py"
Cohesion: 0.13
Nodes (18): Routes for the five modules whose models live in this app. Receivables,…, ExpenseCancelView, PayablesListView, PayCustomerInvoiceView, _PayInvoiceView, PaySupplierInvoiceView, Money owed to the business, by cheque and by credit on account., Exact mirror of Receivables, Supplier/PurchaseInvoice side -- reads the same… (+10 more)

### Community 2 - "django_db_models_deletion"
Cohesion: 0.06
Nodes (21): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+13 more)

### Community 3 - "django_db"
Cohesion: 0.03
Nodes (33): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+25 more)

### Community 4 - "payments/services.py"
Cohesion: 0.15
Nodes (25): Admin for BankAccount, Payment, PaymentAllocation and Cheque (ROADMAP 4.3,…, advance_recurring(), bounce_cheque(), cancel_cheque(), cancel_expense(), next_due_after(), pay_expense(), atomic (+17 more)

### Community 5 - "paper.py"
Cohesion: 0.11
Nodes (28): format_date(), format_datetime(), Turn ASCII digits into Persian ones for display., "۱۴۰۵/۰۷/۰۳", or "۳ مهر ۱۴۰۵" when a sentence reads better than a code. Returns…, ۱۴۰۵/۰۷/۰۳ ساعت ۱۴:۳۰" — for audit rows, where the time matters., to_persian_digits(), dict_get(), fa_digits() (+20 more)

### Community 6 - "backup.py"
Cohesion: 0.13
Nodes (16): backup_filename(), build_backup(), business_model_labels(), _dump_json(), Every model that goes into a backup, for the page's "what's inside" list., Whole-business backup: one zip with the data and the uploaded receipts.…, Return an open, rewound temporary file holding the zip (caller closes it)., _row_counts() (+8 more)

### Community 7 - "sales/services.py"
Cohesion: 0.07
Nodes (28): Give back to each layer exactly what ``sale_item`` took from it. Reversal is by…, restore_consumptions(), CartonLine, Meta, PriceTier, The two ways the business sells (D-075): to shops in bulk, or to walk-in buyers., The carton + pack part shared by a sales and a purchase invoice line (D-081).…, Packs beyond the whole cartons, as entered on the line. (+20 more)

### Community 8 - "Cheque"
Cohesion: 0.07
Nodes (48): Cheque, A physical cheque's lifecycle (ROADMAP 4.4): pending -> cleared / bounced. A…, Money movements, independent of the invoices they settle (ROADMAP 4.3). A…, Status, get_bank_account_balance(), get_credit_items(), get_expense_reminders(), get_total_payables_as_of() (+40 more)

### Community 9 - "DESIGN.md"
Cohesion: 0.05
Nodes (37): Border Radius Scale, Brand & Accent, Breakpoints, Buttons, Cards & Containers, Collapsing Strategy, Colors, Components (+29 more)

### Community 10 - "purchasing/views.py"
Cohesion: 0.12
Nodes (23): Admin for Customer and Supplier (D-010: two separate models). Both models share…, "مشتری جدید" / "تأمین‌کننده جدید" — the inline mini-forms. A party can be…, The Customers module plus the inline "new customer" component shared with…, excluded_product_ids(), Ids from the item-row search's `exclude` parameter (products already on the…, Purchasing module views. Mirrors apps/sales/views.py; nothing here writes stock…, Sales module views. Nothing here writes stock or money directly --…, Form pieces every module reuses. `JalaliDateField` is the only way a date… (+15 more)

### Community 11 - "payments/forms.py"
Cohesion: 0.09
Nodes (19): AccountChoiceField, AccountSelect, ChequeFilterForm, current_account_field(), PaymentEntryFormMixin, pos_account_field(), Shared behaviour of the sales/purchase payment-row forms (D-069): the method…, A <select> whose options carry `data-type` (pos/current), so the invoice form's… (+11 more)

### Community 12 - "products/admin.py"
Cohesion: 0.11
Nodes (16): Admin for InventoryMovement: a read-only view of the stock ledger. The ledger…, get_stock(), Current stock of one product, computed from the ledger., atomic, Record the one-time opening stock of a product (D-017). Called only while the…, set_opening_stock(), Admin for Product. Stock is never stored on Product; it is derived from the…, Save the product, then hand opening stock to the service. The product must be… (+8 more)

### Community 13 - "Payment"
Cohesion: 0.09
Nodes (28): Direction, Meta, Payment, PaymentAllocation, Sum of this payment's allocations so far, in Toman., How much of this payment has not yet been tied to an invoice., Whoever this money moved with, or None for an expense/unattributed row., Ties part (or all) of a Payment to exactly one invoice (D-025). Exactly one of… (+20 more)

### Community 14 - "is_locked"
Cohesion: 0.21
Nodes (7): is_locked(), Media, True when an invoice exists and is no longer a draft (D-014)., Invoice lines, edited inside the invoice page. In the permission methods below,…, Planned payment lines, edited inside the invoice page while it is a draft;…, SaleItemInline, SalesPaymentEntryInline

### Community 15 - "dates.py"
Cohesion: 0.10
Nodes (25): clamp_month(), month_grid(), Today as a `jdatetime.date`, in the active (Tehran) timezone., First and last Gregorian dates of the Jalali week containing a date. The…, One month laid out for the date picker: leading blanks, then each day. Lives…, Normalise a year/month the client asked for, rolling over at the edges. The…, Jalali is the calendar this business works in; Gregorian/UTC is what the…, A stored date (or datetime) as a `jdatetime.date`. A datetime is converted in… (+17 more)

### Community 16 - "PurchaseInvoiceAdmin"
Cohesion: 0.10
Nodes (15): is_locked(), Media, PurchaseInvoiceAdmin, PurchaseItemInline, PurchasePaymentEntryInline, action, display, register (+7 more)

### Community 17 - "Product"
Cohesion: 0.10
Nodes (25): Command, BaseCommand, Read-only report for the pack/carton conversion (D-081): `python manage.py…, ConversionError, convert(), atomic, Exception, One-time conversion from "pack products and carton products" to one product… (+17 more)

### Community 18 - "DateRangeForm"
Cohesion: 0.06
Nodes (33): DateRangeForm, JalaliDateInput, Preset, The Gregorian dates a named preset covers, inclusive of both ends., (start, end) for this submission, falling back to the default when the form was…, Which button should look pressed., User Activity's own filters, alongside the shared date range: which user, which…, A text box the Jalali date-picker attaches to. Deliberately not `<input… (+25 more)

### Community 19 - "audit"
Cohesion: 0.23
Nodes (12): gross_profit(), pct_change(), previous_period(), purchases_total(), The equal-length period immediately before (start, end), inclusive of both ends…, % change vs. the prior period. None when there is nothing to compare against (a…, The five headline cards, each with its % change vs. the equal-length prior…, sales_total() (+4 more)

### Community 20 - "D-048 — An invoice discount is shared across its lines, pro rata"
Cohesion: 0.09
Nodes (22): D-048 — An invoice discount is shared across its lines, pro rata, D-049: Static files served by whitenoise, D-050: Visual identity is IBM Carbon-inspired, D-051: Deployment and SHADOW are out of scope, D-053: A purchase invoice settles like a sale (mode + account), D-054: Rules settled by the full QA pass, D-056: Clearing a cheque needs an explicit account, D-057: Expense receipts are PDF or images, at most 5 MB (+14 more)

### Community 21 - "Decision Log"
Cohesion: 0.08
Nodes (26): D-001: Project layout and settings package name, D-002: Configuration via environment variables, D-003: Primary key type is UUID, D-004: Time is stored in UTC, D-005: Interface language, D-006: Empty text fields use `blank=True` only, never `null=True`, D-008: User is not scoped to a Business, D-009: Roles as a choices field (+18 more)

### Community 22 - "sales/forms.py"
Cohesion: 0.15
Nodes (16): CartonPackItemFormMixin, The carton + pack part of an invoice line form (D-081), shared by the sales and…, "کالای جدید", inline mid-purchase. Unlike the quick customer/supplier forms,…, For an invoice item form whose `product` is a hidden input filled by the row's…, SelectedProductMixin, PurchaseItemForm, The one-shot new-purchase form. Symmetric to apps/sales/forms.py, with these…, One invoice line, typed as cartons + loose packs in a single row (D-081).… (+8 more)

### Community 23 - "InventoryLayerAdmin"
Cohesion: 0.11
Nodes (8): InventoryConsumptionAdmin, InventoryLayerAdmin, InventoryMovementAdmin, display, register, Read-only view of which layer each sold line drew from. Append-only: a…, Read-only ledger browser: filter, search, inspect. Never write., Read-only view of the FIFO cost layers. Written only by services…

### Community 24 - "InventoryLayer"
Cohesion: 0.07
Nodes (42): InventoryConsumption, InventoryLayer, InventoryMovement, Meta, MovementType, Append-only ledger of stock changes. The single source of truth for stock. Rows…, Quantity with its effect on stock: positive for inflow, negative for outflow., One batch of stock bought (or counted in) at one known unit cost. The cost… (+34 more)

### Community 25 - "sale_form.js"
Cohesion: 0.19
Nodes (15): chosenProductIds(), currentDiscount(), currentDiscountMode(), formatToman(), intVal(), lineQuantity(), lineTotal(), pickProduct() (+7 more)

### Community 26 - "InventoryDetailView"
Cohesion: 0.09
Nodes (18): InventoryProductForm, QuickProductForm plus an optional one-time opening stock. Blank quantity: the…, Inventory module routes. No opening-stock or adjustment page: stock changes…, InventoryDetailView, InventoryListView, ProductCreateView, DetailView, LoginRequiredMixin (+10 more)

### Community 27 - "SalesInvoice"
Cohesion: 0.10
Nodes (13): _customer_row(), One list-page row: badge, open balance, invoice count, last purchase date --…, PaymentMethod, PaymentStatus, Confirmed and cancelled invoices are both frozen (D-014, D-023)., A sale to a customer. Mirrors PurchaseInvoice. Draft invoices are editable;…, Deprecated alias for `subtotal`; kept until admin.py is checked (2.7 cleanup)., Subtotal minus the invoice-level discount, in Toman (R 9). (+5 more)

### Community 28 - "check"
Cohesion: 0.16
Nodes (18): overdue_credit_invoices(), Confirmed sales invoices still owing money, older than `threshold_days`. Sales…, scenarios(), scenarios(), Receipt upload rules (only PDF/PNG/JPG/WebP, matching content, <= 5 MB)., upload_scenarios(), send(), Sign-in brute-force protection (D-058). (+10 more)

### Community 29 - "Harness"
Cohesion: 0.13
Nodes (10): new(), exp(), Harness, (product, packs, pack price) as the posted line fields (D-081): everything…, A line typed as cartons + loose packs, prices optional (a sale fills them from…, items: [(product, qty, price)]; account: BankAccount | None (cash no longer…, POST the clear form. account: "cheque" (its own account, else cash), "cash", a…, D-078: a method is only in play when its tick is posted; tests that name an… (+2 more)

### Community 30 - "User"
Cohesion: 0.05
Nodes (36): AbstractBaseUser, AdminConfig, AdminSite, PaperPlusAdminConfig, PaperPlusAdminSite, Django admin, reachable by active superusers only., Superuser-only admin site. WHY this exists now: until this rebuild, `/admin/`…, Replaces `django.contrib.admin` in INSTALLED_APPS. (+28 more)

### Community 31 - "ChequeAdmin"
Cohesion: 0.13
Nodes (7): BankAccountAdmin, ChequeAdmin, ExpenseAdmin, display, register, A PENDING cheque is still editable (Sina, 2026-09-24: entering one incomplete…, Add-only: every Expense is created through `record_expense`, which also books…

### Community 32 - "format_toman"
Cohesion: 0.15
Nodes (9): ProductAdmin, display, register, SimpleHistoryAdmin, Add the total inventory value (4.1: "دارایی کل") across the current (filtered)…, Product catalogue with a live stock column and one-time opening stock., format_toman(), 250,000 تومان' -- every stored amount is already whole Toman (D-043). (+1 more)

### Community 33 - "purchase_form.js"
Cohesion: 0.19
Nodes (14): addRow(), chosenProductIds(), fillRow(), formatToman(), intVal(), lineQuantity(), pickProduct(), recomputeInvoice() (+6 more)

### Community 34 - ".mark_bounced"
Cohesion: 0.22
Nodes (5): action, One clear_cheque call per row; a rejected one does not affect the rest., One cancel_cheque call per row; a rejected one does not affect the rest., One bounce_cheque call per row; a rejected one does not affect the rest., One cancel_expense call per row; a rejected one does not affect the rest.

### Community 35 - "shared/models.py"
Cohesion: 0.11
Nodes (20): Helper for writing AuditLog rows from inside services (D-029)., The latest N events, all users., recent_activity(), AuditLog, EventType, Meta, Append-only record of service-level events (D-029). Never updated or deleted…, Event counts grouped by actor, within the range -- the full per-event breakdown… (+12 more)

### Community 36 - "users/views.py"
Cohesion: 0.08
Nodes (23): parse_jalali(), Normalise Persian/Arabic-Indic digits to ASCII for parsing., Parse a typed Jalali date into a Gregorian `datetime.date`. Returns None when…, to_ascii_digits(), _ip_key(), is_locked(), _phone_key(), Brute-force protection for the sign-in page. Failed sign-ins are counted per… (+15 more)

### Community 37 - "ExpenseForm"
Cohesion: 0.14
Nodes (9): ChequeForm, ExpenseForm, Meta, PaymentAllocationForm, PaymentForm, Persian errors for the amount and exactly-one-invoice CHECKs (see PaymentForm)., Shows a friendly Persian error for the direction/party (or direction/invoice)…, `payment` and the cancellation fields belong to the services, not a form.… (+1 more)

### Community 38 - "PurchaseInvoice"
Cohesion: 0.08
Nodes (22): get_supplier_outstanding(), Accounts payable: this supplier's unpaid balance across its confirmed purchase…, Meta, Method, PaymentMethod, PaymentStatus, PurchaseInvoice, PurchasePaymentEntry (+14 more)

### Community 39 - "cancel_purchase"
Cohesion: 0.18
Nodes (11): cancel_layer(), Take a layer out of the FIFO pool, for a cancelled purchase. Only an untouched…, cancel_purchase(), atomic, Cancel a confirmed purchase invoice: reverse its stock, freeze it (D-023). The…, is_privileged(), The one permission concept left after the single-business rebuild.…, True for an authenticated, active superuser. None and AnonymousUser fail, same… (+3 more)

### Community 40 - "SalesPaymentEntry"
Cohesion: 0.18
Nodes (10): Meta, The cheque fields (number/bank/due date) are optional here on purpose (Sina,…, SalesPaymentEntryForm, Meta, One planned payment row (card reader / bank transfer / cheque, D-069), same…, SalesPaymentEntryForm, Method, One planned payment line on a draft sales invoice (added at Sina's request,… (+2 more)

### Community 41 - "SalesListView"
Cohesion: 0.13
Nodes (14): ProductSearchView, DetailView, LoginRequiredMixin, TemplateView, View, Live product search for an item row. Returns a results partial, not JSON -- the…, Detail: items with FIFO cost + profit per line, totals with invoice profit…, POST-only: cancel_sale itself is the only real guard (superuser + confirmed-… (+6 more)

### Community 42 - "Customer"
Cohesion: 0.11
Nodes (15): Customer, Meta, A vendor the business buys products from., A buyer of the business's products., Supplier, The price suggested for one whole carton (D-081): the wholesale price, or,…, PurchaseItem, One line of a purchase invoice. (+7 more)

### Community 43 - "QuickCustomerForm"
Cohesion: 0.11
Nodes (22): CustomerFilterForm, CustomerForm, Meta, QuickCustomerForm, Customers list filters: free-text search over name/phone, account status…, New customer, inline. Reused by the Customers page and the sale form., Full edit form for the Customers detail page -- the quick-create form only asks…, Customers module routes. Suppliers live under Purchasing. (+14 more)

### Community 44 - "percent_to_amount"
Cohesion: 0.67
Nodes (3): percent_to_amount(), Whole-Toman discount for ``percent`` % of ``subtotal`` (D-070). Rounded down,…, D-070: A sales discount can be typed as a percent

### Community 45 - "PurchaseInvoiceForm"
Cohesion: 0.24
Nodes (7): QuickSupplierForm, New supplier, inline. Reused by the Suppliers sub-section and the purchase form., PurchaseInvoiceForm, Header fields: who, when, the supplier's own invoice number. No discount field…, _empty_forms(), PurchaseCreateView, The one-shot new-purchase page -- mirrors sales.views.SalesCreateView. No…

### Community 47 - "django_conf"
Cohesion: 0.09
Nodes (12): Migration, Migration, Migration, Migration, Migration, Migration, Migration, Migration (+4 more)

### Community 48 - "qa_17_pricing_units.py"
Cohesion: 0.23
Nodes (11): atomic, Set a product's current selling prices (D-075): ``retail`` is…, Write services for the product catalogue., Set the RETAIL price only (the one price there was before D-075); kept for…, update_selling_price(), update_selling_prices(), Wholesale vs retail (D-075): invoices, net sales, discount given and profit per…, sales_by_tier() (+3 more)

### Community 49 - "ExpenseForm"
Cohesion: 0.22
Nodes (7): ExpenseForm, New-expense one-shot form (D-045, D-072): date, reason, amount and HOW it is…, An unsaved Cheque with the typed cheque details, for a cheque expense (else…, ExpenseCreateView, New-expense one-shot form: atomic create of the Expense (and, for a transfer,…, A UUID from a query string, or None when it is missing or malformed., _uuid_or_none()

### Community 50 - "LoginRequiredMixin"
Cohesion: 0.28
Nodes (8): ProductSearchView, PurchaseCancelView, LoginRequiredMixin, View, QuickSupplierCreateView, Live product search for an item row -- mirrors sales.views's version, with the…, POST-only door to cancel_purchase, which is the only real guard (superuser +…, Creates a Supplier from the inline mini-form -- mirrors…

### Community 51 - "context_processors.py"
Cohesion: 0.14
Nodes (11): company(), navigation(), Who issues printed documents (settings.COMPANY, filled from .env)., The sidebar, plus which section the current page belongs to. The active section…, Context every page of the frontend needs, so no view has to remember it., NavGroup, NavItem, One clickable destination in the sidebar. (+3 more)

### Community 52 - "django_apps"
Cohesion: 0.08
Nodes (17): InventoryConfig, AppConfig, PartnersConfig, AppConfig, PaymentsConfig, AppConfig, ProductsConfig, AppConfig (+9 more)

### Community 53 - "jalali_picker.js"
Cohesion: 0.31
Nodes (11): buildPopup(), close(), commit(), currentGrid(), load(), markSelected(), onPopupClick(), open() (+3 more)

### Community 54 - "os"
Cohesion: 0.12
Nodes (13): ASGI config for core project. It exposes the ASGI callable as a module-level…, WSGI config for core project. It exposes the WSGI callable as a module-level…, Entry point for hosts that run Python apps through Passenger…, django_core_asgi, django_core_management, django_core_wsgi, main(), Django's command-line utility for administrative tasks. (+5 more)

### Community 55 - "project_map.py"
Cohesion: 0.21
Nodes (12): importlib, inspect, build_tree(), describe_field(), describe_functions(), describe_model(), main(), Generate PROJECT_MAP.md: file tree, settings, models and public functions. Run… (+4 more)

### Community 56 - "ExchangeRate"
Cohesion: 0.16
Nodes (12): fetch_usd_rate(), atomic, Read the rate once and store one row: ``ok`` with the number, or ``failed``…, Command, BaseCommand, Read today's USD rate and store it: `python manage.py fetch_usd_rate` (run from…, ExchangeRate, One attempt to read the USD rate (D-080). Append-only, like AuditLog: an old… (+4 more)

### Community 58 - "BankAccountForm"
Cohesion: 0.23
Nodes (7): BankAccountForm, Add or edit an account from the Bank Accounts page itself -- before this, an…, BankAccountCreateView, BankAccountUpdateView, + حساب بانکی جدید" -- a full page, like Inventory's new product: not mid-…, Fix a name/owner/number typo. Same form as create; the ledger is untouched --…, D-045 — Expense: no counterparty; the paying account is chosen explicitly

### Community 59 - "ExpensesListView"
Cohesion: 0.23
Nodes (8): ExpenseFilterForm, PayExpenseForm, Expenses list filters: free-text search over reason/note, bank account, and an…, پرداخت" for an expense that is still owed (a نسیه one when its date comes, or…, ExpensePayView, ExpensesListView, Expenses: newest-first, cards for today's and this month's totals (cancelled…, POST-only door to pay_expense (a نسیه expense, or one whose cheque bounced).

### Community 60 - "RecordPaymentForm"
Cohesion: 0.15
Nodes (9): PayInvoiceForm, Money received from a customer, or paid to a supplier. The party is fixed by…, Money from a customer comes in; money to a supplier goes out., Settle (all or part of) one invoice's credit part from the Receivables /…, RecordPaymentForm, get_pending_cheques(), Pending cheques of one direction (in = from customers, out = to suppliers),…, _DuesListView (+1 more)

### Community 61 - "RecurringExpenseForm"
Cohesion: 0.14
Nodes (13): ChequeCompletionForm, Meta, تکمیل مشخصات" for a cheque entered incomplete from an invoice's payment rows…, Add or edit a fixed, repeating cost (D-073): what, how much, how often, when…, RecurringExpenseForm, ChequeCompleteView, View, تکمیل مشخصات" for a cheque entered incomplete from an invoice (4.3b) -- a plain… (+5 more)

### Community 63 - "D-037 — Profit is realised profit: zero unless the invoice is confirmed"
Cohesion: 0.17
Nodes (7): Sum of line totals, before discount, in Toman (R 9)., Realised profit: invoice total minus real cost of goods, in Toman. The discount…, True when any line was sold without a cost basis (see SaleItem)., Units sold with no layer behind them, so no cost basis at all. Non-zero only…, Realised profit: net total (after this line's share of the invoice discount,…, D-037 — Profit is realised profit: zero unless the invoice is confirmed, D-052: A sale can never exceed the stock on hand

### Community 64 - "SaleInvoiceForm"
Cohesion: 0.18
Nodes (7): Invoice-level fields: who, when, how much discount, and how it was settled. The…, SaleInvoiceForm, plan_full_payment(), The default settlement (D-046, D-069): the customer paid the whole invoice by…, _empty_forms(), The one-shot new-sale page: invoice + items + payment, submitted together,…, SalesCreateView

### Community 65 - "LoginRequiredMixin"
Cohesion: 0.15
Nodes (13): BankAccountDetailView, BankAccountListView, ChequesListView, _describe_payment(), DetailView, LoginRequiredMixin, TemplateView, Status/direction/due-date-range filters, one table covering both received and… (+5 more)

### Community 66 - "exchange.py"
Cohesion: 0.18
Nodes (15): _digits(), _http_get(), latest_valid_rate(), parse_tgju_api(), parse_tgju_profile(), Exception, RateError, USD rate in Toman, read from an Iranian price site (D-080). `fetch_usd_rate` is… (+7 more)

### Community 67 - "SupplierListView"
Cohesion: 0.33
Nodes (4): Suppliers list filters: free-text search over name/phone and active/inactive…, SupplierFilterForm, Suppliers sub-section list: name, phone, total purchased, outstanding payable…, SupplierListView

### Community 68 - "PurchasingListView"
Cohesion: 0.22
Nodes (7): BasePurchaseItemFormSet, PurchasingFilterForm, Catches the same product picked twice before the DB's unique constraint…, Mirrors sales.forms.SalesFilterForm; see there for why the date range and the…, PurchasingListView, TemplateView, List: symmetric to Sales' list, no profit card -- profit is sales-only.

### Community 69 - "purchasing/urls.py"
Cohesion: 0.20
Nodes (8): Purchasing module routes, including the Suppliers sub-section., PurchaseDetailView, PurchasePrintView, DetailView, Detail: no profit column -- profit is sales-only. Payment/cheque history and…, A print-friendly render of the same invoice (RULES.md excludes PDF generation…, Purchase history, payments made, cheques issued, running balance -- the same…, SupplierDetailView

### Community 70 - "Expense"
Cohesion: 0.16
Nodes (10): Expense, PaymentMethod, Money spent on running the business: rent, wages, fuel, a repair. Deliberately…, True once money has left for it: a bank payment exists (derived, never typed,…, False once cancelled, so no card, report or statement counts it. Stated on the…, D-040 — Expense lives in apps.payments, backed by a real Payment, D-041: Manual stock adjustment draws FIFO layers, Builds a rich dataset (every status, every payment kind), then follows EVERY… (+2 more)

### Community 71 - "RecurringExpense"
Cohesion: 0.18
Nodes (12): A fixed cost that comes round again: shop rent, electricity, water -- every…, هر ۱ ماه" style text for lists., RecurringExpense, Unit, add_months_jalali(), ``day`` moved ``months`` Jalali months ahead, keeping the day number where the…, BankAccount_exists(), j() (+4 more)

### Community 72 - "PartnerAdmin"
Cohesion: 0.29
Nodes (7): CustomerAdmin, PartnerAdmin, register, Shared configuration for Customer and Supplier. Not registered itself; a plain…, Customers: the counterparty of sales invoices., Suppliers: the counterparty of purchase invoices., SupplierAdmin

### Community 73 - "SalesInvoiceAdmin"
Cohesion: 0.16
Nodes (8): action, display, register, SimpleHistoryAdmin, Sales invoices: draft entry in admin, confirmation via the service., Confirm each selected invoice through confirm_sale. One service call per…, Cancel each selected invoice through cancel_sale (D-023). One service call per…, SalesInvoiceAdmin

### Community 74 - "SupplierForm"
Cohesion: 0.27
Nodes (6): Full create/edit form for the Suppliers sub-section -- the supplier counterpart…, SupplierForm, + تأمین‌کنندهٔ جدید" on the Suppliers list itself -- the same Supplier model…, POST-only save for the detail page's edit disclosure -- mirrors…, SupplierCreateView, SupplierUpdateView

### Community 75 - "invoice_payment.js"
Cohesion: 0.36
Nodes (6): digitsToAscii(), field(), num(), syncCreditDue(), syncFullAmounts(), total()

### Community 76 - "نصب و به‌روزرسانی روی هاست"
Cohesion: 0.20
Nodes (9): بازیابی, تنظیم مشخصات شرکت روی فاکتور, نرخ دلار (D-080), نصب اول, نصب و به‌روزرسانی روی هاست, هر بار که تغییری داده شد (به‌روزرسانی), پشتیبان‌گیری, پیش‌نیازهای هاست (قبل از خرید بپرسید) (+1 more)

### Community 77 - "architecture.md"
Cohesion: 0.08
Nodes (27): fa(), phrase(), split(), 1. What it is, 4. Domain model, 6. Frontend, Architecture — paper-plus, Related documentation (+19 more)

### Community 78 - "BankAccount"
Cohesion: 0.17
Nodes (13): AccountType, BankAccount, A bank account of the business, used to record where money moved., get_customer_outstanding(), Accounts receivable: this customer's unpaid balance across its confirmed sales…, clear_cheque(), Mark a pending cheque cleared and create the Payment it represents. The…, expenses_total() (+5 more)

### Community 79 - "qa_lib.py"
Cohesion: 0.18
Nodes (10): string, Smoke test of the superuser-only /admin/ backend: every model's list, add and…, scenarios(), j(), D-079: one dashboard card, receivables and payables, each split into cheques…, scenarios(), Exception, Shared harness for the QA scenario scripts (throwaway, gitignored). Every… (+2 more)

### Community 80 - "confirm_sale"
Cohesion: 0.13
Nodes (16): confirm_sale(), atomic, Confirm a draft sales invoice and remove its items from stock. A sale never…, D-012: Movement direction comes from movement_type, not from the sign, D-014: A confirmed invoice is immutable, D-015: Stock concurrency is guarded by locking Product rows, D-016: A sale may drive stock negative, D-021: Negative stock is allowed by role (+8 more)

### Community 81 - "0005_remove_inventorylayer_inventory_layer_source_matches_item_and_more.py"
Cohesion: 0.33
Nodes (5): link_opening_movements_to_their_layer(), Migration, noop_reverse(), Nothing to undo: unlinking would only throw away a fact, not restore prior…, Backfill `InventoryMovement.layer` for every existing OPENING row.…

### Community 82 - "InvoicePaymentFields"
Cohesion: 0.20
Nodes (6): InvoicePaymentFields, The only active card reader, or None when there are none or several (D-078)., ``[(method, account, amount_or_None)]`` for the methods picked, for…, The payment half of the sales/purchase invoice forms (D-069), written once so…, last_sale(), D-078: card reader / bank transfer are ticked on the full-settlement panel, and…

### Community 83 - "shared/admin.py"
Cohesion: 0.17
Nodes (6): AuditLogAdmin, ExchangeRateAdmin, register, Admin registration for the shared app. Business and BusinessMembership are…, Read-only view of AuditLog rows (D-029). No add/change/delete: rows are written…, Read-only history of USD rate reads (D-080); rows come from `fetch_usd_rate`…

### Community 84 - "0003_seed_role_groups.py"
Cohesion: 0.40
Nodes (4): get_perms(), Migration, Return Permission objects for app_label.ModelName matching codenames., seed_groups()

### Community 85 - "convert_units.py"
Cohesion: 0.20
Nodes (7): Command, BaseCommand, Convert carton-counted products to packs (D-081): `python manage.py…, io, json, Backup page: access rules, download, and what is inside the zip (D-060). The…, zipfile

### Community 86 - "ClearChequeForm"
Cohesion: 0.27
Nodes (6): ClearChequeForm, وصول چک": which account the money lands in / leaves from. A real answer is…, ChequeActionView, ChequeDetailView, Full lifecycle trace: party, linked invoice (or "general/unattached"), and,…, POST-only door to clear_cheque/bounce_cheque/cancel_cheque -- the services are…

### Community 87 - "kpi_cards"
Cohesion: 0.40
Nodes (4): kpi_cards(), Sales/purchases/expenses/net-profit, each today + this month -- reuses…, month_bounds(), First and last Gregorian dates of a Jalali month. Used by the date-range…

### Community 88 - "users/models.py"
Cohesion: 0.14
Nodes (9): Migration, Migration, Migration, Migration, Migration, Migration, django_contrib_auth_models, django_core_validators (+1 more)

### Community 89 - "QuickProductForm"
Cohesion: 0.25
Nodes (5): Meta, QuickProductForm, New product, inline. Reused wherever a purchase or (later) the Inventory module…, QuickProductCreateView, Creates a Product from the inline "+ کالای جدید" mini-form. Reuses partners/…

### Community 90 - "django_core_management_base"
Cohesion: 0.25
Nodes (6): Load a backup into the current database. Refuses a non-empty one. The business…, restore_backup(), Command, BaseCommand, Load a backup zip into an EMPTY, migrated database: `python manage.py…, django_core_management_base

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

### Community 98 - "number_to_words"
Cohesion: 0.36
Nodes (6): _below_thousand(), number_to_words(), 0 -> "صفر", 1250 -> "یک هزار و دویست و پنجاه". Negative gets "منفی"., A whole number spelled out in Persian, for the printed invoice's "amount in…, Printed sales invoice (D-061): words, company header, stamp boxes, statuses., scenarios()

### Community 99 - "qa_20_usd_rate.py"
Cohesion: 0.36
Nodes (6): api(), page(), D-080: USD rate history, failed reads store no number, invoices freeze the rate…, The amount as a page prints it: grouped, in either separator, in either digit…, scenarios(), shown()

### Community 101 - "usd_rate_card"
Cohesion: 0.29
Nodes (7): is_stale(), latest_attempt(), The newest row of any status, to show whether the last try failed., True when there is no valid rate or it is older than ``hours`` (default: the…, The «نرخ دلار» stat card: newest valid rate, its age, and a failed-last-try…, usd_rate_card(), inclusion_tag

### Community 102 - "0012_carton_pack.py"
Cohesion: 0.40
Nodes (3): Migration, Migration, django_db_models_expressions

### Community 103 - "parent_url"
Cohesion: 0.40
Nodes (5): parent_url(), The page one level up from `path`: drop the last URL segment, and keep dropping…, `{% static %}` plus the file's modification time, so a browser never keeps…, static_v(), simple_tag

### Community 104 - "qa_03_sales.py"
Cohesion: 0.70
Nodes (4): last(), n_inv(), scenarios(), seq()

### Community 106 - "validators.py"
Cohesion: 0.50
Nodes (3): Accept only a small PDF/PNG/JPEG/WebP whose content matches its extension., Validation for uploaded expense receipts. A receipt is a picture or a PDF and…, validate_receipt()

### Community 126 - "qa_21_units.py"
Cohesion: 0.18
Nodes (14): The Inventory module's one stock-creating form: a new product, with its opening…, ``(cartons, packs)`` for a quantity in packs, e.g. 34 with 5 -> (6, 4)., The base quantity of a line typed as cartons + loose packs: 6, 4, 5 -> 34., "۶ کارتن + ۴ بسته" with the parts that are zero left out ("۶ کارتن", "۴ بسته");…, Carton + pack arithmetic and wording (D-081). Stock, layers and FIFO are all…, split_units(), to_packs(), units_phrase() (+6 more)

### Community 130 - "ProductAdminForm"
Cohesion: 0.50
Nodes (3): Meta, ProductAdminForm, Product form plus a one-time opening stock field. Blank -> not counted yet; the…

### Community 132 - "sales_by_product"
Cohesion: 0.50
Nodes (4): qty, amount, profit per product, across every confirmed sale in the range --…, Ranked by quantity, linked -- the same rows `sales_by_product` already…, sales_by_product(), top_sellers()

### Community 133 - "pathlib"
Cohesion: 0.50
Nodes (3): Django settings for core project. Generated by 'django-admin startproject'…, environ, pathlib

### Community 135 - "PurchasePaymentEntryForm"
Cohesion: 0.67
Nodes (3): Meta, PurchasePaymentEntryForm, The cheque fields are optional here on purpose, mirrors…

## Knowledge Gaps
- **202 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `Migration` (+197 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 885 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SalesInvoice` connect `SalesInvoice` to `payments/views.py`, `payments/services.py`, `sales_by_product`, `sales/services.py`, `Cheque`, `.discount_allocation`, `purchasing/views.py`, `Payment`, `dates.py`, `Product`, `audit`, `sales/forms.py`, `InventoryLayer`, `check`, `shared/models.py`, `SalesListView`, `Customer`, `QuickCustomerForm`, `qa_17_pricing_units.py`, `D-037 — Profit is realised profit: zero unless the invoice is confirmed`, `SaleInvoiceForm`, `Expense`, `RecurringExpense`, `BankAccount`, `confirm_sale`, `InvoicePaymentFields`, `number_to_words`, `qa_20_usd_rate.py`, `qa_03_sales.py`, `qa_21_units.py`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `PurchaseInvoice` connect `PurchaseInvoice` to `payments/views.py`, `payments/services.py`, `sales/services.py`, `Cheque`, `purchasing/views.py`, `products/admin.py`, `Payment`, `dates.py`, `Product`, `audit`, `sales/forms.py`, `InventoryLayer`, `check`, `shared/models.py`, `cancel_purchase`, `Customer`, `PurchaseInvoiceForm`, `LoginRequiredMixin`, `SupplierListView`, `PurchasingListView`, `purchasing/urls.py`, `Expense`, `RecurringExpense`, `BankAccount`, `number_to_words`, `qa_20_usd_rate.py`, `qa_21_units.py`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `Product` connect `Product` to `ProductAdminForm`, `sales/services.py`, `purchasing/views.py`, `products/admin.py`, `sales/forms.py`, `InventoryLayer`, `InventoryDetailView`, `check`, `Harness`, `PurchaseInvoice`, `SalesListView`, `Customer`, `qa_17_pricing_units.py`, `LoginRequiredMixin`, `PurchasingListView`, `qa_lib.py`, `confirm_sale`, `QuickProductForm`, `qa_03_sales.py`, `qa_21_units.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 52 inferred relationships involving `SalesInvoice` (e.g. with `convert()` and `report()`) actually correct?**
  _`SalesInvoice` has 52 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `PurchaseInvoice` (e.g. with `convert()` and `report()`) actually correct?**
  _`PurchaseInvoice` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `Payment` (e.g. with `CustomerDetailView` and `PaymentForm`) actually correct?**
  _`Payment` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Cheque` (e.g. with `ChequeAdmin` and `ChequeForm`) actually correct?**
  _`Cheque` has 37 INFERRED edges - model-reasoned connections that need verification._
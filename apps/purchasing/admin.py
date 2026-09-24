#path: apps/purchasing/admin.py
"""
Admin for PurchaseInvoice and its items.

Rules enforced here:
- Stock is written only by confirm_purchase; the admin never creates
  InventoryMovement rows and never sets status itself.
- A confirmed invoice is immutable (D-014): its page becomes view-only,
  its items can no longer be added, changed or deleted, and it cannot be
  deleted. Only drafts may be deleted.
"""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import F, Sum
from simple_history.admin import SimpleHistoryAdmin

from apps.shared.admin_mixins import BusinessScopedAdminMixin
from apps.shared.utils import format_rial

from .models import PurchaseInvoice, PurchaseItem, PurchasePaymentEntry
from .services import cancel_purchase, confirm_purchase

# Only a draft invoice may be edited or deleted.
DRAFT_STATUS = "draft"

# Inherited from BaseModel; visible for debugging, never editable.
SYSTEM_FIELDS = ("id", "created_at", "updated_at")

# Shown under every Rial input; conversion is fixed (D-013), not live.
TOMAN_HINT = "به ریال وارد شود. (۱ تومان = ۱۰ ریال)"


def is_locked(invoice):
    """True when an invoice exists and is no longer a draft (D-014)."""
    return invoice is not None and invoice.status != DRAFT_STATUS


class PurchaseItemForm(forms.ModelForm):
    """Adds the Toman hint under the Rial price field (R 8)."""

    class Meta:
        model = PurchaseItem
        fields = "__all__"
        help_texts = {"unit_price": TOMAN_HINT}


class PurchaseItemInline(BusinessScopedAdminMixin, admin.TabularInline):
    """
    Invoice lines, edited inside the invoice page.

    In the permission methods below, `obj` is the parent invoice,
    not the item.
    """

    model = PurchaseItem
    form = PurchaseItemForm
    # Items have no business FK; they reach it through their invoice.
    business_lookup = "invoice__business"
    extra = 1
    fields = ("product", "quantity", "unit_price", "line_total")
    readonly_fields = ("line_total",)
    # Search box instead of a dropdown of every product.
    autocomplete_fields = ("product",)

    @admin.display(description="جمع ردیف (ریال)")
    def line_total(self, obj):
        # Unsaved row: quantity and price may still be empty.
        if obj is None or obj._state.adding:
            return "-"
        return format_rial(obj.quantity * obj.unit_price)

    def has_add_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_delete_permission(request, obj)


class PurchasePaymentEntryForm(forms.ModelForm):
    """
    The cheque fields are optional here on purpose, mirrors
    sales.SalesPaymentEntryForm (Sina, 2026-09-24): finish an incomplete
    cheque later on the Cheques page, while it is still PENDING.
    """

    class Meta:
        model = PurchasePaymentEntry
        fields = "__all__"
        help_texts = {"amount": TOMAN_HINT}


class PurchasePaymentEntryInline(BusinessScopedAdminMixin, admin.TabularInline):
    """
    Planned payment lines, edited inside the invoice page while it is a
    draft; confirm_purchase turns each row into a real Payment or Cheque
    (4.3b, mirrors sales.SalesPaymentEntryInline).
    """

    model = PurchasePaymentEntry
    form = PurchasePaymentEntryForm
    business_lookup = "invoice__business"
    extra = 0
    fields = ("method", "amount", "bank_account", "cheque_number", "bank_name", "due_date")
    autocomplete_fields = ("bank_account",)

    class Media:
        # Pre-fills a new row's amount with the invoice's remaining total (4.3b UX).
        js = ("shared/js/payment_entry_autofill.js",)

    def has_add_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not is_locked(obj) and super().has_delete_permission(request, obj)


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(BusinessScopedAdminMixin, SimpleHistoryAdmin, admin.ModelAdmin):
    """Purchase invoices: draft entry in admin, confirmation via the service."""

    list_display = (
        "invoice_number", "supplier", "business", "invoice_date",
        "status", "total_display", "payment_status_display",
        "confirmed_at", "created_by",
    )
    list_filter = ("business", "status", "invoice_date")
    search_fields = ("invoice_number", "supplier__name")
    # One JOIN per related column instead of one query per row.
    list_select_related = ("supplier", "business", "created_by")
    autocomplete_fields = ("business", "supplier")
    date_hierarchy = "invoice_date"
    # status/confirmed_at belong to the service; created_by to save_model.
    # invoice_number is assigned by confirm_purchase at confirmation (D-022);
    # never editable in the admin.
    readonly_fields = (
        "invoice_number", "status", "confirmed_at", "created_by", "payment_status_display",
    ) + SYSTEM_FIELDS
    fieldsets = (
        ("اطلاعات فاکتور", {"fields": ("business", "supplier", "supplier_invoice_number", "invoice_date")}),
        # payment_method/payment_note (2.8) are superseded by the payment-entry
        # rows below (4.3b): one place to pick method + amount, not two (Sina,
        # 2026-09-24). The fields stay on the model, just unused from here on.
        ("پرداخت", {"fields": ("payment_status_display",)}),
        ("وضعیت", {"fields": ("invoice_number", "status", "confirmed_at", "created_by")}),
        ("اطلاعات سیستمی", {"fields": SYSTEM_FIELDS, "classes": ("collapse",)}),
    )
    inlines = (PurchaseItemInline, PurchasePaymentEntryInline)
    actions = ("confirm_selected", "cancel_selected")

    def get_queryset(self, request):
        # PurchaseInvoice has no `total` property (unlike SalesInvoice, 2.7);
        # annotate here instead of a query per row in total_display.
        queryset = super().get_queryset(request)
        return queryset.annotate(_total=Sum(F("items__quantity") * F("items__unit_price")))

    @admin.display(description="جمع کل (ریال)")
    def total_display(self, obj):
        if obj is None:
            return "-"
        return format_rial(obj._total or 0)

    @admin.display(description="وضعیت پرداخت")
    def payment_status_display(self, obj):
        # Derived from PaymentAllocation, never typed (D-025, 4.3).
        # payment_status is a @property (not a model field), so there is
        # no auto-generated get_payment_status_display() -- .label works
        # because it returns the TextChoices member itself.
        if obj is None or obj._state.adding:
            return "-"
        return obj.payment_status.label

    def save_model(self, request, obj, form, change):
        # Record who entered the invoice; set once, on creation only.
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        # Confirmed invoice: Django renders the page view-only.
        return not is_locked(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # obj is None on the list page: returning False removes the bulk
        # "delete selected" action, which cannot check each invoice's status.
        if obj is None or is_locked(obj):
            return False
        return super().has_delete_permission(request, obj)

    @admin.action(description="تأیید فاکتورهای انتخاب‌شده", permissions=["change"])
    def confirm_selected(self, request, queryset):
        """
        Confirm each selected invoice through confirm_purchase.

        One service call per invoice: each runs in its own transaction,
        so a rejected invoice does not roll back the others.
        """
        for invoice in queryset:
            try:
                confirm_purchase(invoice, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} تأیید نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} تأیید شد.",
                    messages.SUCCESS,
                )

    @admin.action(description="لغو فاکتورهای انتخاب‌شده", permissions=["change"])
    def cancel_selected(self, request, queryset):
        """
        Cancel each selected invoice through cancel_purchase (D-023).

        One service call per invoice: each runs in its own transaction, so
        a rejected cancellation (wrong status, or user is not Owner) does
        not roll back the others.
        """
        for invoice in queryset:
            try:
                cancel_purchase(invoice, request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} لغو نشد: {'؛ '.join(error.messages)}",
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"فاکتور {invoice.invoice_number} لغو شد.",
                    messages.SUCCESS,
                )
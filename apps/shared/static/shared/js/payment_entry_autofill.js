// When a new payment-entry row is added, pre-fill its amount with whatever
// is left of the invoice total after the rows already filled in (4.3b UX
// request, 2026-09-24: "بقیه‌اش نقدی باشه دیگه لازم نباشه دستی وارد کنم").
// Sina can still overwrite it for a smaller split.
//
// Django 6.1's admin/js/inlines.js dispatches "formset:added" as a plain
// CustomEvent on the new row itself (bubbles: true, detail.formsetName) --
// not the older jQuery-trigger convention of extra positional arguments --
// so this only needs a native listener, no jQuery.
(function () {
    "use strict";

    function sumOtherRows(formsetName) {
        var total = 0;
        var selector = 'input[name^="' + formsetName + '-"][name$="-amount"]';
        document.querySelectorAll(selector).forEach(function (input) {
            var row = input.closest("tr, .form-row");
            var deleteBox = row ? row.querySelector('input[name$="-DELETE"]') : null;
            if (deleteBox && deleteBox.checked) {
                return;
            }
            var value = parseInt(input.value, 10);
            if (!isNaN(value)) {
                total += value;
            }
        });
        return total;
    }

    document.addEventListener("formset:added", function (event) {
        var formsetName = event.detail && event.detail.formsetName;
        var row = event.target;
        var invoiceTotal = window.__invoicePaymentEntryTotalRial;
        if (!formsetName || !row || typeof invoiceTotal !== "number") {
            return;
        }
        var amountInput = row.querySelector('input[name$="-amount"]');
        if (!amountInput || amountInput.value) {
            return;
        }
        var remaining = invoiceTotal - sumOtherRows(formsetName);
        if (remaining > 0) {
            amountInput.value = remaining;
        }
    });
})();

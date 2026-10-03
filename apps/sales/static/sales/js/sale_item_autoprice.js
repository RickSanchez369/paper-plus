// Autofill a sale-item row's unit_price with the picked product's default
// selling price (4.3b UX request, 2026-09-24). The backend already fills a
// blank price from the same default at save time (R 7, 17C) -- this only
// makes that visible immediately, before saving; typing over it afterward
// still wins, exactly like the backend snapshot behaviour.
(function () {
    "use strict";

    function fillPrice(productSelect) {
        var productId = productSelect.value;
        if (!productId) {
            return;
        }
        var row = productSelect.closest("tr, .form-row");
        if (!row) {
            return;
        }
        var priceInput = row.querySelector('input[name$="-unit_price"]');
        if (!priceInput) {
            return;
        }
        fetch("/admin/products/product/" + productId + "/default-price/", {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (response) {
                return response.ok ? response.json() : null;
            })
            .then(function (data) {
                if (data && typeof data.default_selling_price !== "undefined") {
                    // The admin row is one line of packs, so it takes the pack price (D-081).
                    priceInput.value = data.default_selling_price;
                }
            })
            .catch(function () {
                /* silent: manual entry still works if the request fails */
            });
    }

    function bind($) {
        // select2 (used by autocomplete_fields) dispatches its "change" at
        // the jQuery level; a plain document.addEventListener("change", ...)
        // never sees it. Delegate through django.jQuery instead, and cover
        // rows added later via "Add another" too.
        $(document).on("change", 'select[name$="-product"]', function () {
            fillPrice(this);
        });
    }

    function ready() {
        // Media ordering puts this file before admin/js/jquery.init.js
        // (the one that defines django.jQuery), so it is not there yet at
        // parse time. DOMContentLoaded always fires after every blocking
        // <script src> on the page has already run, regardless of order.
        if (typeof django !== "undefined" && django.jQuery) {
            bind(django.jQuery);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", ready);
    } else {
        ready();
    }
})();

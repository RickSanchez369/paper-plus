/*
 * The new-sale form's client side: product search
 * results, add/remove item and payment rows, live subtotal/discount/total,
 * the payment-mode switch (full settlement vs. split/credit, D-046), and
 * the remaining/نسیه amount. Written fresh for this page rather than
 * ported from apps/sales/admin.py's inline JS -- that version leans on
 * Django admin's select2 and django.jQuery, neither of which exists here.
 *
 * All server-side validation still happens on submit, same as always
 * (SaleItemForm/SalesPaymentEntryForm/confirm_sale) -- everything below is
 * presentation, not a second source of truth for what a valid invoice is.
 */
(function () {
  "use strict";

  function formatToman(value) {
    var n = Math.max(0, Math.round(value || 0));
    var withCommas = n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, "\u066c");
    return withCommas.replace(/[0-9]/g, function (digit) {
      return String.fromCharCode(0x06f0 + Number(digit));
    });
  }

  function intVal(input) {
    var n = parseInt(input && input.value, 10);
    return isNaN(n) ? 0 : n;
  }

  function addRow(containerId, templateId, prefix) {
    var container = document.getElementById(containerId);
    var template = document.getElementById(templateId);
    var totalInput = document.querySelector('input[name="' + prefix + '-TOTAL_FORMS"]');
    if (!container || !template || !totalInput) return;

    var index = parseInt(totalInput.value, 10) || 0;
    var html = template.innerHTML.split("__prefix__").join(String(index));
    var wrapper = document.createElement("div");
    wrapper.innerHTML = html.trim();
    var row = wrapper.firstElementChild;
    container.appendChild(row);
    totalInput.value = index + 1;

    // htmx only wires up attributes it has seen; a row inserted by plain
    // JS (not swapped in by htmx itself) needs one explicit pass.
    if (window.htmx) {
      window.htmx.process(row);
    }
    return row;
  }

  // A line is cartons x carton price + loose packs x pack price (D-081).
  function lineQuantity(row) {
    var ratio = parseInt(row.dataset.ratio, 10) || 1;
    return intVal(row.querySelector('input[name$="-cartons"]')) * ratio + intVal(row.querySelector('input[name$="-packs"]'));
  }

  function lineTotal(row) {
    return (
      intVal(row.querySelector('input[name$="-cartons"]')) * intVal(row.querySelector('input[name$="-carton_price"]')) +
      intVal(row.querySelector('input[name$="-packs"]')) * intVal(row.querySelector('input[name$="-unit_price"]'))
    );
  }

  function recomputeInvoice() {
    var subtotal = 0;
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      var total = lineTotal(row);
      var totalCell = row.querySelector("[data-item-row-total]");
      if (totalCell) totalCell.textContent = formatToman(total);
      subtotal += total;
    });

    var discount = currentDiscount(subtotal);
    var total = Math.max(subtotal - discount, 0);

    validateStock();

    setText("sale-subtotal", formatToman(subtotal));
    setText("sale-total", formatToman(total));
    setText("sale-full-amount", formatToman(total));

    recomputeRemaining(total);
    document.dispatchEvent(new CustomEvent("invoice:recomputed"));
  }

  // Discount typed as Toman or as a percent of the subtotal (D-070); the
  // server recomputes the percent itself, this is only the live preview.
  function currentDiscountMode() {
    var checked = document.querySelector('input[name="discount_mode"]:checked');
    return checked ? checked.value : "amount";
  }

  function currentDiscount(subtotal) {
    var discount;
    if (currentDiscountMode() === "percent") {
      var pct = parseFloat((document.getElementById("id_discount_percent") || {}).value);
      discount = isNaN(pct) ? 0 : Math.floor((subtotal * Math.min(Math.max(pct, 0), 100)) / 100);
      setText("sale-discount-preview", formatToman(discount));
    } else {
      discount = intVal(document.getElementById("id_discount_amount"));
    }
    return discount;
  }

  function showDiscountPanel(mode) {
    document.querySelectorAll("[data-discount-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.discountPanel !== mode;
    });
  }

  function recomputeRemaining(total) {
    var paid = 0;
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(function (row) {
      paid += intVal(row.querySelector('input[name$="-amount"]'));
    });
    setText("sale-remaining", formatToman(Math.max(total - paid, 0)));
  }

  function currentTotal() {
    var el = document.getElementById("sale-total");
    if (!el) return 0;
    var ascii = el.textContent.replace(/[۰-۹]/g, function (d) {
      return String(d.charCodeAt(0) - 0x06f0);
    });
    return parseInt(ascii.replace(/,/g, ""), 10) || 0;
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  // One product, one line: ids already chosen in the other rows.
  function chosenProductIds(exceptRow) {
    var ids = [];
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      if (row === exceptRow) return;
      var id = row.querySelector('input[name$="-product"]').value;
      if (id) ids.push(id);
    });
    return ids;
  }

  // A line above the stock on hand is refused by the server too (D-052);
  // this only says so before the submit, and shows what would be left.
  function validateStock() {
    var blocked = false;
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      var warn = row.querySelector("[data-item-row-warn]");
      var after = row.querySelector("[data-item-row-after]");
      var stock = row.dataset.stock;
      var over = false;
      if (stock !== undefined && stock !== "") {
        var qty = lineQuantity(row);
        var left = parseInt(stock, 10) - qty;
        over = left < 0;
        if (after) after.textContent = qty > 0 && !over ? "پس از این فروش: " + window.PaperUnits.phrase(left, row.dataset.ratio) : "";
      }
      if (warn) {
        warn.textContent = over
          ? "بیشتر از موجودی (" + window.PaperUnits.phrase(stock, row.dataset.ratio) + ") است؛ ابتدا خرید ثبت کنید."
          : "";
      }
      if (over) blocked = true;
    });
    var submit = document.querySelector("#sale-form [type=submit]");
    if (submit) {
      submit.disabled = blocked;
      submit.title = blocked ? "موجودی یک یا چند ردیف کافی نیست؛ ردیف‌های قرمز را اصلاح کنید." : "";
    }
  }

  function pickProduct(button) {
    var row = button.closest("[data-item-row]");
    if (!row) return;
    if (chosenProductIds(row).indexOf(button.dataset.id) !== -1) return;

    row.querySelector('input[name$="-product"]').value = button.dataset.id;
    row.dataset.stock = button.dataset.stock;
    row.dataset.ratio = button.dataset.ratio || "1";
    row.dataset.packPrice = button.dataset.packPrice || "0";
    row.dataset.cartonPrice = button.dataset.cartonPrice || "0";
    var search = row.querySelector("[data-item-row-search]");
    if (search) search.value = button.dataset.name;

    // Both prices are suggested from the product (D-081); the cashier can type over either.
    row.querySelector('input[name$="-unit_price"]').value = row.dataset.packPrice;
    row.querySelector('input[name$="-carton_price"]').value = row.dataset.cartonPrice;

    var stockLabel = row.querySelector("[data-item-row-stock]");
    if (stockLabel) stockLabel.textContent = "موجودی: " + window.PaperUnits.phrase(button.dataset.stock, row.dataset.ratio);

    row.dataset.pickedName = button.dataset.name;
    var results = row.querySelector(".item-row__results");
    if (results) results.innerHTML = "";

    // Next thing a clerk types is the quantity; do not make them reach for the mouse.
    var cartons = row.querySelector('input[name$="-cartons"]');
    if (cartons) {
      cartons.focus();
      cartons.select();
    }

    recomputeInvoice();
  }

  // Editing the name after a pick must not leave the OLD product id, stock and prices behind:
  // the box would read "A4" while the line bills A3.
  document.addEventListener("input", function (event) {
    var search = event.target.closest && event.target.closest("[data-item-row-search]");
    if (!search) return;
    var row = search.closest("[data-item-row]");
    if (!row || search.value === (row.dataset.pickedName || "")) return;
    var id = row.querySelector('input[name$="-product"]');
    if (id && id.value) {
      id.value = "";
      delete row.dataset.stock;
      var label = row.querySelector("[data-item-row-stock]");
      if (label) label.textContent = "";
      recomputeInvoice();
    }
  });

  // The result list closes on Esc and on a click anywhere else.
  function closeResults(except) {
    document.querySelectorAll(".item-row__results").forEach(function (box) {
      if (box !== except && !(except && box.parentNode.contains(except))) box.innerHTML = "";
    });
  }
  document.addEventListener("click", function (event) {
    closeResults(event.target.closest(".item-row__search"));
  });

  // Products already on the invoice never come back in the results: the
  // search request carries their ids and the server leaves them out.
  document.body.addEventListener("htmx:configRequest", function (event) {
    if (!event.target.matches || !event.target.matches("[data-item-row-search]")) return;
    var row = event.target.closest("[data-item-row]");
    event.detail.parameters["exclude"] = chosenProductIds(row).join(",");
  });

  // Cheque number, issuing bank and due date only exist for a cheque.
  function syncPaymentRow(row) {
    var method = row.querySelector('select[name$="-method"]');
    var cheque = row.querySelector("[data-cheque-only]");
    if (method && cheque) cheque.hidden = method.value !== "cheque";
  }

  document.addEventListener("click", function (event) {
    var pick = event.target.closest("[data-item-row-pick]");
    if (pick) {
      pickProduct(pick);
      return;
    }

    if (event.target.closest("[data-item-row-remove]")) {
      var itemRow = event.target.closest("[data-item-row]");
      if (itemRow) {
        itemRow.remove();
        recomputeInvoice();
      }
      return;
    }

    if (event.target.closest("[data-payment-row-remove]")) {
      var paymentRow = event.target.closest("[data-payment-row]");
      if (paymentRow) {
        paymentRow.remove();
        recomputeInvoice();
      }
      return;
    }

    if (event.target.id === "add-item-row") {
      var added = addRow("item-rows", "item-row-template", "items");
      var addedSearch = added && added.querySelector("[data-item-row-search]");
      if (addedSearch) addedSearch.focus();
      return;
    }

    if (event.target.id === "add-payment-row") {
      // A payment row means the customer did not simply pay in full.
      if (currentPaymentMode() !== "split") setPaymentMode("split");
      var newRow = addRow("payment-rows", "payment-row-template", "payments");
      if (newRow) {
        syncPaymentRow(newRow);
        var amountInput = newRow.querySelector('input[name$="-amount"]');
        var remaining = Math.max(currentTotal() - sumPaymentRows(), 0);
        if (amountInput && remaining > 0) {
          amountInput.value = remaining;
        }
      }
      recomputeInvoice();
    }
  });

  // "تسویهٔ کامل" shows only the receiving-account select; the split
  // panel (rows + remaining credit) only in split mode. The server reads
  // the radio, not what is visible, so this is presentation only.
  function currentPaymentMode() {
    var checked = document.querySelector('input[name="payment_mode"]:checked');
    return checked ? checked.value : "full";
  }

  function showPaymentPanel(mode) {
    document.querySelectorAll("[data-payment-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.paymentPanel !== mode;
    });
  }

  function setPaymentMode(mode) {
    var radio = document.querySelector('input[name="payment_mode"][value="' + mode + '"]');
    if (radio) radio.checked = true;
    showPaymentPanel(mode);
  }

  document.addEventListener("change", function (event) {
    if (event.target.matches('input[name="payment_mode"]')) {
      showPaymentPanel(currentPaymentMode());
    }
    if (event.target.matches('input[name="discount_mode"]')) {
      showDiscountPanel(currentDiscountMode());
      recomputeInvoice();
    }
    if (event.target.matches('select[name$="-method"]')) {
      syncPaymentRow(event.target.closest("[data-payment-row]"));
    }
  });

  function sumPaymentRows() {
    var paid = 0;
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(function (row) {
      paid += intVal(row.querySelector('input[name$="-amount"]'));
    });
    return paid;
  }

  document.addEventListener("input", function (event) {
    if (
      event.target.matches('input[name$="-cartons"]') ||
      event.target.matches('input[name$="-packs"]') ||
      event.target.matches('input[name$="-carton_price"]') ||
      event.target.matches('input[name$="-unit_price"]') ||
      event.target.matches('input[name$="-amount"]') ||
      event.target.id === "id_discount_amount" ||
      event.target.id === "id_discount_percent"
    ) {
      recomputeInvoice();
    }
  });

  // Enter inside a text/number box must not post the invoice: this form
  // creates and confirms a financial document in one go, and Enter is how
  // people finish typing a number, not how they mean to submit.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeResults();
    if (event.key !== "Enter") return;
    var t = event.target;
    // Enter in the product box picks the first result instead of doing nothing.
    if (t.matches && t.matches("[data-item-row-search]")) {
      var first = t.closest("[data-item-row]").querySelector("[data-item-row-pick]:not(:disabled)");
      if (first) pickProduct(first);
      event.preventDefault();
      return;
    }
    if (t.matches && t.matches("#sale-form input:not([type=submit]):not([type=button]):not([type=radio]):not([type=checkbox])")) {
      event.preventDefault();
    }
  });

  // This form creates and confirms a financial document: a second click must not post it twice.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.id !== "sale-form") return;
    if (form.dataset.busy) {
      event.preventDefault();
      return;
    }
    form.dataset.busy = "1";
  });
  // Back/forward restores the page with the flag still set.
  window.addEventListener("pageshow", function (event) {
    var form = document.getElementById("sale-form");
    if (form) delete form.dataset.busy;
    if (event.persisted) recomputeInvoice();
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-item-row]").forEach(function (row) {
      var s = row.querySelector("[data-item-row-search]");
      if (s && s.value) row.dataset.pickedName = s.value;
    });
    showDiscountPanel(currentDiscountMode());
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(syncPaymentRow);
    recomputeInvoice();
  });
})();

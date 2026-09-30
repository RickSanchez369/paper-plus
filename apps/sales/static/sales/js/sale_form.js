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
    var withCommas = n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
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

  function recomputeInvoice() {
    var subtotal = 0;
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      var qty = intVal(row.querySelector('input[name$="-quantity"]'));
      var price = intVal(row.querySelector('input[name$="-unit_price"]'));
      var lineTotal = qty * price;
      var totalCell = row.querySelector("[data-item-row-total]");
      if (totalCell) totalCell.textContent = formatToman(lineTotal);
      subtotal += lineTotal;
    });

    var discountInput = document.getElementById("id_discount_amount");
    var discount = intVal(discountInput);
    var total = Math.max(subtotal - discount, 0);

    validateStock();

    setText("sale-subtotal", formatToman(subtotal));
    setText("sale-total", formatToman(total));
    setText("sale-full-amount", formatToman(total));

    recomputeRemaining(total);
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
  // this only says so before the submit.
  function validateStock() {
    var blocked = false;
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      var warn = row.querySelector("[data-item-row-warn]");
      var stock = row.dataset.stock;
      var over = false;
      if (stock !== undefined && stock !== "") {
        over = intVal(row.querySelector('input[name$="-quantity"]')) > parseInt(stock, 10);
      }
      if (warn) {
        warn.textContent = over ? "بیشتر از موجودی (" + formatToman(stock).replace(/,/g, "") + ") است؛ ابتدا خرید ثبت کنید." : "";
      }
      if (over) blocked = true;
    });
    var submit = document.querySelector("#sale-form [type=submit]");
    if (submit) submit.disabled = blocked;
  }

  function pickProduct(button) {
    var row = button.closest("[data-item-row]");
    if (!row) return;
    if (chosenProductIds(row).indexOf(button.dataset.id) !== -1) return;

    row.querySelector('input[name$="-product"]').value = button.dataset.id;
    row.dataset.stock = button.dataset.stock;
    var search = row.querySelector("[data-item-row-search]");
    if (search) search.value = button.dataset.name;

    var priceInput = row.querySelector('input[name$="-unit_price"]');
    if (priceInput && !priceInput.value) {
      priceInput.value = button.dataset.price;
    }

    var stockLabel = row.querySelector("[data-item-row-stock]");
    if (stockLabel) stockLabel.textContent = "موجودی: " + button.dataset.stock;

    var results = row.querySelector(".item-row__results");
    if (results) results.innerHTML = "";

    recomputeInvoice();
  }

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
      addRow("item-rows", "item-row-template", "items");
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
      event.target.matches('input[name$="-quantity"]') ||
      event.target.matches('input[name$="-unit_price"]') ||
      event.target.matches('input[name$="-amount"]') ||
      event.target.id === "id_discount_amount"
    ) {
      recomputeInvoice();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(syncPaymentRow);
    recomputeInvoice();
  });
})();

/*
 * The new-purchase form's client side (REDESIGN_VISION 4.2). Mirrors
 * apps/sales/static/sales/js/sale_form.js almost exactly; the one real
 * difference is `pickProduct`: it sets the price field's *placeholder*
 * from the last known cost, never its value -- a purchase price is what
 * this purchase actually cost, not a default to accept silently.
 */
(function () {
  "use strict";

  function formatRial(value) {
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

    if (window.htmx) {
      window.htmx.process(row);
    }
    return row;
  }

  function recomputeInvoice() {
    var total = 0;
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      var qty = intVal(row.querySelector('input[name$="-quantity"]'));
      var price = intVal(row.querySelector('input[name$="-unit_price"]'));
      var lineTotal = qty * price;
      var totalCell = row.querySelector("[data-item-row-total]");
      if (totalCell) totalCell.textContent = formatRial(lineTotal);
      total += lineTotal;
    });

    setText("sale-total", formatRial(total));
    recomputeRemaining(total);
  }

  function recomputeRemaining(total) {
    var paid = 0;
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(function (row) {
      paid += intVal(row.querySelector('input[name$="-amount"]'));
    });
    setText("sale-remaining", formatRial(Math.max(total - paid, 0)));
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

  function pickProduct(button) {
    var row = button.closest("[data-item-row]");
    if (!row) return;

    row.querySelector('input[name$="-product"]').value = button.dataset.id;
    var search = row.querySelector("[data-item-row-search]");
    if (search) search.value = button.dataset.name;

    var priceInput = row.querySelector('input[name$="-unit_price"]');
    if (priceInput && button.dataset.lastCost) {
      priceInput.placeholder = button.dataset.lastCost;
    }

    var stockLabel = row.querySelector("[data-item-row-stock]");
    if (stockLabel) stockLabel.textContent = "موجودی: " + button.dataset.stock;

    var results = row.querySelector(".item-row__results");
    if (results) results.innerHTML = "";

    recomputeInvoice();
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
      var newRow = addRow("payment-rows", "payment-row-template", "payments");
      if (newRow) {
        var amountInput = newRow.querySelector('input[name$="-amount"]');
        var remaining = Math.max(currentTotal() - sumPaymentRows(), 0);
        if (amountInput && remaining > 0) {
          amountInput.value = remaining;
        }
      }
      recomputeInvoice();
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
      event.target.matches('input[name$="-amount"]')
    ) {
      recomputeInvoice();
    }
  });

  document.addEventListener("DOMContentLoaded", recomputeInvoice);
})();

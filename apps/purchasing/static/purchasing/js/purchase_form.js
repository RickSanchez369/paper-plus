/*
 * The new-purchase form's client side. Mirrors
 * apps/sales/static/sales/js/sale_form.js almost exactly; the real
 * differences are `pickProduct`, which sets the price field's
 * *placeholder* from the last known cost, never its value -- a purchase
 * price is what this purchase actually cost, not a default to accept
 * silently -- and the "+ کالای جدید" dialog, whose success response puts
 * the new product into the row that asked for it.
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
      if (totalCell) totalCell.textContent = formatToman(lineTotal);
      total += lineTotal;
    });

    setText("sale-total", formatToman(total));
    setText("sale-full-amount", formatToman(total));
    recomputeRemaining(total);
    document.dispatchEvent(new CustomEvent("invoice:recomputed"));
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

  // `source` is a search-result button or the quick-product success
  // element -- both carry the same data-id/name/stock(/last-cost) shape.
  function fillRow(row, source) {
    row.querySelector('input[name$="-product"]').value = source.dataset.id;
    var search = row.querySelector("[data-item-row-search]");
    if (search) search.value = source.dataset.name;

    var priceInput = row.querySelector('input[name$="-unit_price"]');
    if (priceInput) priceInput.placeholder = source.dataset.lastCost || "";

    var stockLabel = row.querySelector("[data-item-row-stock]");
    if (stockLabel) stockLabel.textContent = "موجودی: " + source.dataset.stock;

    var results = row.querySelector(".item-row__results");
    if (results) results.innerHTML = "";

    recomputeInvoice();
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

  function pickProduct(button) {
    var row = button.closest("[data-item-row]");
    if (!row || chosenProductIds(row).indexOf(button.dataset.id) !== -1) return;
    fillRow(row, button);
  }

  // Products already on the invoice never come back in the results: the
  // search request carries their ids and the server leaves them out.
  document.body.addEventListener("htmx:configRequest", function (event) {
    if (!event.target.matches || !event.target.matches("[data-item-row-search]")) return;
    var row = event.target.closest("[data-item-row]");
    event.detail.parameters["exclude"] = chosenProductIds(row).join(",");
  });

  // ---- payment: full settlement vs. split/credit, and per-method fields --
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

  // Cheque number, issuing bank and due date only exist for a cheque.
  function syncPaymentRow(row) {
    var method = row.querySelector('select[name$="-method"]');
    var cheque = row.querySelector("[data-cheque-only]");
    if (method && cheque) cheque.hidden = method.value !== "cheque";
  }

  document.addEventListener("change", function (event) {
    if (event.target.matches('input[name="payment_mode"]')) {
      showPaymentPanel(currentPaymentMode());
    }
    if (event.target.matches('select[name$="-method"]')) {
      syncPaymentRow(event.target.closest("[data-payment-row]"));
    }
  });

  // ---- "+ کالای جدید" dialog -------------------------------------------
  // The row that opened the dialog (from its "not found" result), if any;
  // otherwise the new product goes into the first empty row, or a new one.
  var quickProductRow = null;

  function openQuickProduct(trigger) {
    var dialog = document.getElementById("quick-product-dialog");
    var template = document.getElementById("quick-product-form-template");
    if (!dialog || !template) return;
    quickProductRow = trigger.closest("[data-item-row]");
    var body = dialog.querySelector("[data-quick-product-body]");
    // A fresh form every time, so a previous success/error never lingers.
    body.innerHTML = template.innerHTML;
    if (window.htmx) window.htmx.process(body);
    dialog.showModal();
    var first = body.querySelector("input:not([type=hidden])");
    if (first) first.focus();
  }

  function targetRowForNewProduct() {
    if (quickProductRow && document.body.contains(quickProductRow)) return quickProductRow;
    var empty = null;
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      if (!empty && !row.querySelector('input[name$="-product"]').value) empty = row;
    });
    return empty || addRow("item-rows", "item-row-template", "items");
  }

  // htmx fires htmx:load on each element it swaps in; the success partial
  // is the one carrying data-quick-product-created. (A rejected form comes
  // back as 422 and is swapped in place by base.html's htmx-config, D-047.)
  document.addEventListener("htmx:load", function (event) {
    var created = event.target.closest && event.target.closest("[data-quick-product-created]");
    if (!created) return;
    var row = targetRowForNewProduct();
    quickProductRow = null;
    // Close first: closing a modal dialog hands focus back to whatever
    // opened it, which would steal it from the quantity box below.
    var dialog = document.getElementById("quick-product-dialog");
    if (dialog && dialog.open) dialog.close();
    if (row) {
      fillRow(row, created);
      var qty = row.querySelector('input[name$="-quantity"]');
      if (qty) qty.focus();
    }
  });

  document.addEventListener("click", function (event) {
    var pick = event.target.closest("[data-item-row-pick]");
    if (pick) {
      pickProduct(pick);
      return;
    }

    var openQuick = event.target.closest("[data-open-quick-product]");
    if (openQuick) {
      openQuickProduct(openQuick);
      return;
    }

    if (event.target.closest("[data-close-quick-product]")) {
      var dialog = document.getElementById("quick-product-dialog");
      if (dialog) dialog.close();
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

  // Enter inside a text/number box must not post the invoice: this form
  // creates and confirms a financial document in one go, and Enter is how
  // people finish typing a number, not how they mean to submit.
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter") return;
    var t = event.target;
    if (t.matches && t.matches("#purchase-form input:not([type=submit]):not([type=button]):not([type=radio]):not([type=checkbox])")) {
      event.preventDefault();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(syncPaymentRow);
    recomputeInvoice();
  });
})();

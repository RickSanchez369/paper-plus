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

  // Read-only preview of allocate_freight (D-082): floor by packs, the leftover Toman go to the
  // biggest remainders. Display only; the server redoes the split at confirm.
  function freightShares(freight, lines) {
    var packs = lines.reduce(function (s, l) { return s + l.qty; }, 0);
    var shares = lines.map(function (l) { return packs > 0 ? Math.floor(freight * l.qty / packs) : 0; });
    var leftover = freight - shares.reduce(function (s, v) { return s + v; }, 0);
    var order = lines.map(function (l, i) { return { i: i, r: packs > 0 ? (freight * l.qty) % packs : 0 }; });
    order.sort(function (a, b) { return b.r - a.r || a.i - b.i; });
    for (var k = 0; k < order.length && leftover > 0; k++, leftover--) shares[order[k].i] += 1;
    return shares;
  }

  function recomputeInvoice() {
    var total = 0;
    var lines = [];
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      var lineTotal =
        intVal(row.querySelector('input[name$="-cartons"]')) * intVal(row.querySelector('input[name$="-carton_price"]')) +
        intVal(row.querySelector('input[name$="-packs"]')) * intVal(row.querySelector('input[name$="-unit_price"]'));
      var totalCell = row.querySelector("[data-item-row-total]");
      if (totalCell) totalCell.textContent = formatToman(lineTotal);
      var after = row.querySelector("[data-item-row-after]");
      var qty = lineQuantity(row);
      if (after && row.dataset.stock !== undefined) {
        after.textContent = qty > 0 ? "پس از این خرید: " + window.PaperUnits.phrase(parseInt(row.dataset.stock, 10) + qty, row.dataset.ratio) : "";
      }
      lines.push({ row: row, lineTotal: lineTotal, qty: qty });
      total += lineTotal;
    });

    // Freight counts only while its box is ticked (D-082); it is part of what the supplier is owed.
    // The amount box stays visible: typing a number ticks the box itself (see the freight listeners below).
    var freight = 0;
    var tick = document.getElementById("id_has_freight");
    if (tick && tick.checked) freight = intVal(document.getElementById("id_freight_amount"));
    setText("sale-subtotal", formatToman(total));
    renderFreightPreview(lines, freight, total, tick);
    total += freight;

    setText("sale-total", formatToman(total));
    // Earlier credit of the party pays first (D-087, party_credit.js).
    var payable = window.payableAfterCredit ? window.payableAfterCredit(total) : total;
    setText("sale-full-amount", formatToman(payable));
    recomputeRemaining(payable);
    document.dispatchEvent(new CustomEvent("invoice:recomputed"));
  }

  // What freight does to each pack's landed cost, shown under every row and as one sentence under
  // the freight box: freight changes cost, not just the total, so a typo in it should be visible.
  function renderFreightPreview(lines, freight, itemsTotal, tick) {
    var packs = lines.reduce(function (s, l) { return s + l.qty; }, 0);
    var shares = freight && packs ? freightShares(freight, lines) : null;
    lines.forEach(function (l, i) {
      var el = l.row.querySelector("[data-item-row-landed]");
      if (!el) return;
      if (!shares || !l.qty) {
        el.textContent = "";
        el.classList.remove("is-high");
        return;
      }
      var perPack = Math.floor((2 * (l.lineTotal + shares[i]) + l.qty) / (2 * l.qty));
      var base = Math.floor((2 * l.lineTotal + l.qty) / (2 * l.qty));
      var extra = perPack - base;
      el.textContent = "با سهم کرایه (" + formatToman(shares[i]) + "): بهای تمام‌شدهٔ هر بسته " + formatToman(perPack) +
        (extra > 0 ? " (+" + formatToman(extra) + " از کرایه)" : "");
      // Freight alone adding over a quarter to the pack cost is almost always a typo in the amount.
      el.classList.toggle("is-high", base > 0 && extra / base > 0.25);
    });
    var sum = document.querySelector("[data-freight-summary]");
    if (!sum) return;
    if (freight && packs) {
      sum.textContent = "کرایه حدود " + formatToman(Math.round(freight / packs)) + " تومان به ازای هر بسته (" +
        window.PaperUnits.fa(packs) + " بسته)" +
        (itemsTotal > 0 ? " و " + window.PaperUnits.fa(Math.round(freight * 100 / itemsTotal)) + "٪ جمع اقلام" : "") + ".";
    } else if (tick && tick.checked) {
      sum.textContent = "مبلغ کرایه را وارد کنید؛ سهم هر کالا همین‌جا و زیر هر ردیف نمایش داده می‌شود.";
    } else {
      sum.textContent = "";
    }
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
    // formatToman prints the Arabic thousands mark (٬), not a comma: strip every non-digit.
    return parseInt(ascii.replace(/[^0-9]/g, ""), 10) || 0;
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
    row.dataset.pickedName = source.dataset.name;

    row.dataset.stock = source.dataset.stock || "0";
    row.dataset.ratio = source.dataset.ratio || "1";
    // The last known cost per pack is only a hint; a carton hint is that times the ratio.
    var lastCost = parseInt(source.dataset.lastCost, 10);
    var priceInput = row.querySelector('input[name$="-unit_price"]');
    if (priceInput) priceInput.placeholder = isNaN(lastCost) ? "" : formatToman(lastCost);
    var cartonInput = row.querySelector('input[name$="-carton_price"]');
    if (cartonInput) cartonInput.placeholder = isNaN(lastCost) ? "" : formatToman(lastCost * parseInt(row.dataset.ratio, 10));

    var stockLabel = row.querySelector("[data-item-row-stock]");
    if (stockLabel) stockLabel.textContent = "موجودی: " + window.PaperUnits.phrase(row.dataset.stock, row.dataset.ratio);

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
    var cartons = row.querySelector('input[name$="-cartons"]');
    if (cartons) {
      cartons.focus();
      cartons.select();
    }
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
    // What he already typed in the row's search box (and no product picked there) becomes the name.
    var rowSearch = quickProductRow && quickProductRow.querySelector("[data-item-row-search]");
    var rowPicked = quickProductRow && quickProductRow.querySelector('input[name$="-product"]');
    var typed = rowSearch && !(rowPicked && rowPicked.value) ? rowSearch.value.trim() : "";
    var nameInput = body.querySelector('input[name="name"]');
    if (nameInput && typed) nameInput.value = typed;
    // The shared partial only says "ثبت"; here it also puts the product on the invoice.
    var submit = body.querySelector('button[type="submit"]');
    if (submit) submit.textContent = "ثبت کالا و افزودن به فاکتور";
    dialog.showModal();
    // First empty box, so with the name already in, typing continues at the SKU.
    var inputs = Array.prototype.slice.call(body.querySelectorAll("input:not([type=hidden])"));
    var target = inputs.filter(function (i) { return !i.value; })[0] || inputs[0];
    if (target) {
      target.focus();
      target.select();
    }
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
      var qty = row.querySelector('input[name$="-cartons"]');
      if (qty) qty.focus();
    }
  });

  // Editing the name after a pick must not leave the OLD product id and stock behind.
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
      var added = addRow("item-rows", "item-row-template", "items");
      var addedSearch = added && added.querySelector("[data-item-row-search]");
      if (addedSearch) addedSearch.focus();
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
    // A typed freight amount ticks its own box first, so it can never be silently dropped.
    if (event.target.id === "id_freight_amount") syncFreightTick();
    if (
      event.target.matches('input[name$="-cartons"]') ||
      event.target.matches('input[name$="-packs"]') ||
      event.target.matches('input[name$="-unit_price"]') ||
      event.target.matches('input[name$="-carton_price"]') ||
      event.target.matches('input[name$="-amount"]') ||
      event.target.id === "id_freight_amount"
    ) {
      recomputeInvoice();
    }
  });

  document.addEventListener("change", function (event) {
    if (event.target.id === "id_has_freight") {
      recomputeInvoice();
      // Ticked: the next thing to do is type the amount.
      var amount = document.getElementById("id_freight_amount");
      if (event.target.checked && amount) {
        amount.focus();
        amount.select();
      }
    }
    if (event.target.id === "id_supplier") refreshFreightChip();
  });

  // ---- freight shortcuts: the supplier's last freight is one tap away -----
  // Per-browser memory only (localStorage); it is never posted, and the box stays editable.
  function freightKey() {
    var sup = document.getElementById("id_supplier");
    return sup && sup.value ? "pp.freight." + sup.value : null;
  }

  function lastFreight() {
    var key = freightKey();
    if (!key) return 0;
    try {
      return parseInt(window.localStorage.getItem(key), 10) || 0;
    } catch (e) {
      return 0;
    }
  }

  function syncFreightTick() {
    var tick = document.getElementById("id_has_freight");
    var amount = document.getElementById("id_freight_amount");
    if (!tick || !amount) return;
    var has = intVal(amount) > 0;
    if (tick.checked !== has) tick.checked = has;
    refreshFreightChip();
  }

  function refreshFreightChip() {
    var chip = document.querySelector("[data-freight-suggest]");
    if (!chip) return;
    var last = lastFreight();
    chip.hidden = !last || intVal(document.getElementById("id_freight_amount")) === last;
    chip.dataset.value = String(last);
    chip.textContent = "کرایهٔ دفعهٔ قبل: " + formatToman(last) + " تومان";
  }

  document.addEventListener("click", function (event) {
    var chip = event.target.closest && event.target.closest("[data-freight-suggest]");
    var amount = document.getElementById("id_freight_amount");
    if (!chip || !amount) return;
    amount.value = chip.dataset.value;
    amount.dispatchEvent(new Event("input", { bubbles: true }));
  });

  document.addEventListener("submit", function (event) {
    if (event.target.id !== "purchase-form") return;
    var key = freightKey();
    var tick = document.getElementById("id_has_freight");
    var used = intVal(document.getElementById("id_freight_amount"));
    try {
      if (key && tick && tick.checked && used > 0) window.localStorage.setItem(key, String(used));
    } catch (e) { /* storage blocked: the shortcut simply stays off */ }
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
      else if (t.value.trim() && t.closest(".item-row__search").querySelector(".item-row__result--empty [data-open-quick-product]")) {
        // "Not found" is on screen: Enter is the same as its "+ ساخت کالای جدید" button.
        openQuickProduct(t);
      }
      event.preventDefault();
      return;
    }
    if (t.matches && t.matches("#purchase-form input:not([type=submit]):not([type=button]):not([type=radio]):not([type=checkbox])")) {
      event.preventDefault();
    }
  });

  // This form creates and confirms a financial document: a second click must not post it twice.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.id !== "purchase-form") return;
    if (form.dataset.busy) {
      event.preventDefault();
      return;
    }
    form.dataset.busy = "1";
  });
  window.addEventListener("pageshow", function (event) {
    var form = document.getElementById("purchase-form");
    if (form) delete form.dataset.busy;
    if (event.persisted) recomputeInvoice();
  });

  document.addEventListener("invoice:party-changed", function () { recomputeInvoice(); });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-item-row]").forEach(function (row) {
      var s = row.querySelector("[data-item-row-search]");
      if (s && s.value) row.dataset.pickedName = s.value;
    });
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(syncPaymentRow);
    recomputeInvoice();
    refreshFreightChip();
  });
})();

/*
 * Product search list: one visible "active" row shared by keyboard and mouse, with
 * ArrowUp/ArrowDown and proper listbox roles. Enter picks the active row; with no
 * movement that is the first in-stock result, exactly what Enter always did.
 * Self-contained (event delegation, no dependency on the form script's internals) so the
 * purchase form carries the very same block.
 */
(function () {
  "use strict";

  var uid = 0;

  function options(box) {
    return Array.prototype.slice.call(box.querySelectorAll("[data-item-row-pick]:not(:disabled)"));
  }

  function inputOf(box) {
    return box.parentNode.querySelector("[data-item-row-search]");
  }

  function setActive(box, option, scroll) {
    var input = inputOf(box);
    Array.prototype.forEach.call(box.querySelectorAll("[aria-selected]"), function (o) {
      o.removeAttribute("aria-selected");
    });
    if (!option) {
      if (input) input.removeAttribute("aria-activedescendant");
      return;
    }
    option.setAttribute("aria-selected", "true");
    if (input) input.setAttribute("aria-activedescendant", option.id);
    if (scroll && option.scrollIntoView) option.scrollIntoView({ block: "nearest" });
  }

  function activeOption(box) {
    return box.querySelector('[data-item-row-pick][aria-selected="true"]:not(:disabled)');
  }

  function boxOf(input) {
    return input.parentNode.querySelector(".item-row__results");
  }

  // After every swap of results: roles, ids, and the first in-stock row becomes the active one.
  document.body.addEventListener("htmx:afterSwap", function (event) {
    var box = (event.detail && event.detail.target) || event.target;
    if (!box || !box.classList || !box.classList.contains("item-row__results")) return;
    var input = inputOf(box);
    if (!input) return;
    box.id = box.id || "search-results-" + (++uid);
    box.setAttribute("role", "listbox");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-controls", box.id);
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "true");
    Array.prototype.forEach.call(box.querySelectorAll(".item-row__result"), function (option, i) {
      option.id = box.id + "-" + i;
      option.setAttribute("role", "option");
    });
    setActive(box, options(box)[0], false);
    if (!box._watched && window.MutationObserver) {
      // The form script empties the box on pick / Esc / outside click: collapse the combobox state.
      box._watched = true;
      new MutationObserver(function () {
        if (box.children.length) return;
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
      }).observe(box, { childList: true });
    }
  });

  // Capture phase: runs before the form script's own Enter branch.
  document.addEventListener("keydown", function (event) {
    var input = event.target;
    if (!input.matches || !input.matches("[data-item-row-search]")) return;
    var box = boxOf(input);
    if (!box || !box.children.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      var list = options(box);
      if (!list.length) return;
      var current = list.indexOf(activeOption(box));
      var next = event.key === "ArrowDown" ? current + 1 : current - 1;
      setActive(box, list[(next + list.length) % list.length], true);
      event.preventDefault();
    } else if (event.key === "Enter") {
      var active = activeOption(box);
      if (!active) return;
      event.preventDefault();
      event.stopPropagation();
      active.click();
    }
  }, true);

  // Mouse and keyboard share one highlight.
  document.addEventListener("mouseover", function (event) {
    var option = event.target.closest && event.target.closest("[data-item-row-pick]:not(:disabled)");
    if (!option) return;
    var box = option.closest(".item-row__results");
    if (box && option.getAttribute("aria-selected") !== "true") setActive(box, option, false);
  });
})();

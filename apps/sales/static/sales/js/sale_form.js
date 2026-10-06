/*
 * The new-sale form's client side: product search
 * results, add/remove item and payment rows, live subtotal/discount/total,
 * the payment-mode switch (full settlement vs. split/credit, D-046), and
 * the remaining/نسیه amount. Written fresh for this page rather than
 * ported from apps/sales/admin.py's inline JS -- that version leans on
 * Django admin's select2 and django.jQuery, neither of which exists here.
 *
 * Also here: the sticky "dock" recap (who / how paid / total) and the stock-blocked
 * reason, discount receipt line + presets, one-tap cheque row, Enter-as-next-field,
 * undoable row removal, and (second block at the end) the product-list active row.
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

  // Money on this page is printed with Persian digits and the Arabic thousands mark (٬),
  // so reading it back must drop every non-digit, not just a comma.
  function toInt(text) {
    var ascii = String(text || "").replace(/[۰-۹]/g, function (d) {
      return String(d.charCodeAt(0) - 0x06f0);
    });
    return parseInt(ascii.replace(/[^0-9]/g, ""), 10) || 0;
  }

  // Remembered choices are a convenience: a blocked store must never break the form.
  function storeGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function storeSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* no memory in a private window */ }
  }

  function faDigits(value) {
    return String(value).replace(/[0-9]/g, function (d) {
      return String.fromCharCode(0x06f0 + Number(d));
    }).replace(".", "٫");
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
    renderDiscount(subtotal, discount);

    setText("sale-subtotal", formatToman(subtotal));
    setText("sale-total", formatToman(total));
    // Earlier credit of the party pays first (D-087, party_credit.js).
    var payable = window.payableAfterCredit ? window.payableAfterCredit(total) : total;
    setText("sale-full-amount", formatToman(payable));
    document.querySelectorAll("[data-dock-total]").forEach(function (el) {
      el.textContent = formatToman(total);
    });

    recomputeRemaining(payable);
    document.dispatchEvent(new CustomEvent("invoice:recomputed"));
    scheduleRecap();
  }

  // The resolved discount as its own line plus the two mistakes that used to surface only after
  // a rejected submit (percent above 100, discount above the subtotal).
  function renderDiscount(subtotal, discount) {
    var line = document.getElementById("sale-discount-line");
    if (!line) return;
    var mode = currentDiscountMode();
    var pct = document.getElementById("id_discount_percent");
    var rawPct = parseFloat(pct && pct.value);
    line.hidden = discount <= 0;
    setText("sale-discount-applied", "−" + formatToman(discount));
    var equiv = "";
    if (discount > 0 && subtotal > 0) {
      equiv = mode === "percent" && !isNaN(rawPct)
        ? "(" + faDigits(Math.min(rawPct, 100)) + "٪ از جمع اقلام)"
        : "(≈ " + faDigits(Math.round((discount / subtotal) * 1000) / 10) + "٪ از جمع اقلام)";
    }
    setText("sale-discount-equiv", equiv);
    var msg = "";
    if (mode === "percent" && rawPct > 100) {
      msg = "درصد تخفیف نمی‌تواند از ۱۰۰ بیشتر باشد؛ تا ۱۰۰٪ حساب شد.";
    } else if (mode === "amount" && discount > subtotal) {
      msg = "تخفیف (" + formatToman(discount) + " تومان) از جمع اقلام (" + formatToman(subtotal) + " تومان) بیشتر است؛ ثبت فاکتور با این مبلغ ممکن نیست.";
    }
    var warn = document.getElementById("sale-discount-warn");
    if (warn && warn.textContent !== msg) {
      warn.textContent = msg;
      warn.hidden = !msg;
    }
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
    return el ? toInt(el.textContent) : 0;
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
    var overRows = [];
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
      row.classList.toggle("item-row--over", over);
      if (over) {
        blocked = true;
        overRows.push(row);
      }
    });
    var submit = document.querySelector("#sale-form [type=submit]");
    if (submit) {
      submit.disabled = blocked;
      submit.title = blocked ? "موجودی یک یا چند ردیف کافی نیست؛ ردیف‌های علامت‌خورده را اصلاح کنید." : "";
    }
    // A disabled button explains itself only by hover; say it next to the button, and offer the jump.
    var reason = document.getElementById("sale-blocked-reason");
    if (reason) {
      var text = reason.querySelector("[data-blocked-text]");
      reason.hidden = !blocked;
      if (text) {
        text.textContent = blocked ? "ثبت ممکن نیست: موجودی " + faDigits(overRows.length) + " ردیف کافی نیست." : "";
      }
      reason._rows = overRows;
    }
    var recap = document.getElementById("sale-recap");
    if (recap) recap.hidden = blocked;
  }

  // ---- wholesale / retail (D-090): four prices per product, the invoice's sale type picks two
  function currentTier() {
    var checked = document.querySelector('input[name="price_tier"]:checked');
    return checked ? checked.value : "retail";
  }

  function tierPrice(row, unit, tier) {
    var raw = row.dataset[(tier || currentTier()) + (unit === "carton" ? "Carton" : "Pack")];
    var n = parseInt(raw, 10);
    return isNaN(n) ? "" : n;
  }

  function priceInputs(row) {
    return { pack: row.querySelector('input[name$="-unit_price"]'), carton: row.querySelector('input[name$="-carton_price"]') };
  }

  // A price box is "manual" when it no longer holds the given tier's price: derived from the
  // numbers themselves (D-075's rule), so a re-rendered page keeps it without a stored flag.
  function isManual(row, tier) {
    var boxes = priceInputs(row);
    return ["pack", "carton"].some(function (unit) {
      var box = boxes[unit];
      return box && box.value !== "" && String(intVal(box)) !== String(tierPrice(row, unit, tier));
    });
  }

  // Switching the sale type reprices the lines still on the old type's prices and keeps the
  // ones the cashier typed, saying how many (never silent).
  var lastTier = null;
  function applyTier(tier) {
    var kept = 0;
    document.querySelectorAll("#item-rows [data-item-row]").forEach(function (row) {
      if (row.dataset.retailPack === undefined || !row.querySelector('input[name$="-product"]').value) return;
      if (isManual(row, lastTier || tier)) {
        kept += 1;
        return;
      }
      var boxes = priceInputs(row);
      boxes.pack.value = tierPrice(row, "pack", tier);
      boxes.carton.value = tierPrice(row, "carton", tier);
    });
    lastTier = tier;
    var note = document.getElementById("tier-note");
    if (note) {
      note.hidden = kept === 0;
      note.textContent = kept ? String(kept).replace(/[0-9]/g, function (d) { return String.fromCharCode(0x06f0 + Number(d)); }) + " ردیف با قیمت دستی تغییر نکرد." : "";
    }
    recomputeInvoice();
  }

  // The customer's type preselects the sale type, until the cashier picks one by hand.
  var tierTouched = false;
  function customerTier(id) {
    var el = document.getElementById("customer-tiers");
    try { return (JSON.parse(el ? el.textContent : "{}"))[id] || ""; } catch (e) { return ""; }
  }

  function setTier(tier) {
    var radio = document.querySelector('input[name="price_tier"][value="' + tier + '"]');
    if (radio && !radio.checked) {
      radio.checked = true;
      applyTier(tier);
    }
  }

  // Below the average purchase cost per pack: a hint on the line, never a block (D-090).
  function checkCost(row) {
    var hint = row.querySelector("[data-cost-warn]");
    var cost = parseInt(row.dataset.cost, 10);
    if (!hint) return;
    var boxes = priceInputs(row);
    var ratio = parseInt(row.dataset.ratio, 10) || 1;
    var low = !isNaN(cost) && cost > 0 && (
      (boxes.pack && boxes.pack.value !== "" && intVal(boxes.pack) < cost) ||
      (boxes.carton && boxes.carton.value !== "" && intVal(boxes.carton) < cost * ratio)
    );
    hint.hidden = !low;
  }

  function pickProduct(button) {
    var row = button.closest("[data-item-row]");
    if (!row) return;
    if (chosenProductIds(row).indexOf(button.dataset.id) !== -1) return;

    row.querySelector('input[name$="-product"]').value = button.dataset.id;
    row.dataset.stock = button.dataset.stock;
    row.dataset.ratio = button.dataset.ratio || "1";
    ["retailPack", "retailCarton", "wholesalePack", "wholesaleCarton"].forEach(function (key) {
      row.dataset[key] = button.dataset[key] || "0";
    });
    row.dataset.cost = button.dataset.cost || "";
    var search = row.querySelector("[data-item-row-search]");
    if (search) search.value = button.dataset.name;

    // Both prices come from the invoice's sale type (D-090); the cashier can type over either.
    row.querySelector('input[name$="-unit_price"]').value = tierPrice(row, "pack");
    row.querySelector('input[name$="-carton_price"]').value = tierPrice(row, "carton");
    checkCost(row);

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

  // Customer picked on this page, as the text the select shows.
  function customerName() {
    var select = document.getElementById("id_customer");
    if (!select || !select.value || select.selectedIndex < 0) return "";
    return select.options[select.selectedIndex].text.trim();
  }

  // Invoice date as a day number (today while empty or not a date): cheque terms count from it.
  function invoiceBaseJdn() {
    var el = document.getElementById("id_invoice_date");
    var jdn = el ? window.PaperJalali.parseJdn(el.value) : null;
    return jdn === null ? window.PaperJalali.todayJdn() : jdn;
  }

  // One payment row; `method` ("cheque") preselects it. The amount defaults to what is still unpaid.
  function addPaymentRow(method) {
    // A payment row means the customer did not simply pay in full.
    if (currentPaymentMode() !== "split") setPaymentMode("split");
    var row = addRow("payment-rows", "payment-row-template", "payments");
    if (!row) return null;
    var select = row.querySelector('select[name$="-method"]');
    if (method && select) {
      select.value = method;
      // Runs syncPaymentRow here and the account filter in invoice_payment.js.
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    syncPaymentRow(row);
    var amountInput = row.querySelector('input[name$="-amount"]');
    var remaining = Math.max(currentTotal() - sumPaymentRows(), 0);
    if (amountInput && remaining > 0) {
      amountInput.value = remaining;
    }
    recomputeInvoice();
    return row;
  }

  // Removal stays one click, but it is reversible: the same node goes back where it was, so the
  // formset indexes and everything typed in the line survive. Focus never falls to <body>.
  var undoBar = null;
  var undoTimer = null;
  function showUndo(text, run) {
    if (!undoBar) {
      undoBar = document.createElement("div");
      undoBar.className = "undo-bar";
      undoBar.setAttribute("role", "status");
      document.body.appendChild(undoBar);
    }
    undoBar.textContent = "";
    var label = document.createElement("span");
    label.textContent = text;
    undoBar.appendChild(label);
    if (run) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "undo-bar__action";
      button.textContent = "بازگردانی";
      button.addEventListener("click", function () {
        undoBar.hidden = true;
        run();
      });
      undoBar.appendChild(button);
    }
    undoBar.hidden = false;
    clearTimeout(undoTimer);
    undoTimer = setTimeout(function () { undoBar.hidden = true; }, 10000);
  }

  function removeWithUndo(row, noun) {
    var parent = row.parentNode;
    var next = row.nextElementSibling;
    var neighbour = next || row.previousElementSibling;
    var fallback = (neighbour && neighbour.querySelector("input, select, button")) ||
      document.getElementById(parent.id === "payment-rows" ? "add-payment-row" : "add-item-row");
    row.remove();
    recomputeInvoice();
    if (fallback) fallback.focus();
    showUndo(noun + " حذف شد.", function () {
      var product = row.querySelector('input[name$="-product"]');
      if (product && product.value && chosenProductIds(null).indexOf(product.value) !== -1) {
        showUndo("این کالا دوباره در فاکتور هست؛ بازگردانی ممکن نیست.", null);
        return;
      }
      parent.insertBefore(row, next && next.parentNode === parent ? next : null);
      recomputeInvoice();
      var first = row.querySelector("input:not([type=hidden]), select");
      if (first) first.focus();
    });
  }

  document.addEventListener("click", function (event) {
    var pick = event.target.closest("[data-item-row-pick]");
    if (pick) {
      pickProduct(pick);
      return;
    }

    if (event.target.closest("[data-item-row-remove]")) {
      var itemRow = event.target.closest("[data-item-row]");
      if (itemRow) removeWithUndo(itemRow, "ردیف کالا");
      return;
    }

    if (event.target.closest("[data-payment-row-remove]")) {
      var paymentRow = event.target.closest("[data-payment-row]");
      if (paymentRow) removeWithUndo(paymentRow, "ردیف پرداخت");
      return;
    }

    if (event.target.id === "add-item-row") {
      var added = addRow("item-rows", "item-row-template", "items");
      var addedSearch = added && added.querySelector("[data-item-row-search]");
      if (addedSearch) addedSearch.focus();
      return;
    }

    if (event.target.id === "add-payment-row") {
      addPaymentRow();
      return;
    }

    // One tap for the common sale paid by a customer cheque: a ready row, issuer = the customer.
    if (event.target.closest("[data-add-cheque]")) {
      var chequeRow = addPaymentRow("cheque");
      if (!chequeRow) return;
      var issuer = chequeRow.querySelector('input[name$="-issuer"]');
      if (issuer && !issuer.value && customerName()) {
        issuer.value = customerName();
        issuer.dataset.auto = "1";
      }
      var bank = chequeRow.querySelector('input[name$="-bank_name"]');
      var lastBank = storeGet("pp.sale.lastChequeBank");
      if (bank && lastBank && !bank.value) bank.value = lastBank;
      var number = chequeRow.querySelector('input[name$="-cheque_number"]');
      if (number) number.focus({ preventScroll: true });
      chequeRow.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }

    var dueChip = event.target.closest("[data-cheque-due-days]");
    if (dueChip) {
      var dueRow = dueChip.closest("[data-payment-row]");
      var dueInput = dueRow && dueRow.querySelector('input[name$="-due_date"]');
      if (dueInput) {
        dueInput.value = window.PaperJalali.format(invoiceBaseJdn() + parseInt(dueChip.dataset.chequeDueDays, 10));
        dueInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return;
    }

    // Discount percent presets (5/10/15/20): they only type into the real field.
    var preset = event.target.closest("[data-discount-preset]");
    if (preset) {
      var percentBox = document.getElementById("id_discount_percent");
      if (percentBox) {
        percentBox.value = preset.dataset.discountPreset;
        recomputeInvoice();
        percentBox.focus();
      }
      return;
    }

    // The sticky bar says why it is blocked; this takes the clerk to the first short line.
    if (event.target.closest("[data-blocked-jump]")) {
      var reason = document.getElementById("sale-blocked-reason");
      var shortRow = reason && reason._rows && reason._rows[0];
      if (!shortRow) return;
      shortRow.scrollIntoView({ block: "center", behavior: "smooth" });
      var qty = shortRow.querySelector('input[name$="-cartons"]');
      if (qty) qty.focus({ preventScroll: true });
      return;
    }

    // Recap shortcut: "choose a payment method" buttons tick the box exactly like a click on it.
    var quick = event.target.closest("[data-quick-method]");
    if (quick && quick.dataset.quickMethod === "credit") {
      var allCredit = document.querySelector("[data-credit-all]");
      if (allCredit) allCredit.click();
      return;
    }
    if (quick) {
      var box = document.getElementById("id_" + quick.dataset.quickMethod);
      if (box && !box.checked) {
        box.checked = true;
        box.dispatchEvent(new Event("change", { bubbles: true }));
      }
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
      // A shop that gives percent discounts finds the form already in percent mode next time.
      storeSet("pp.sale.discountMode", currentDiscountMode());
      recomputeInvoice();
      var percentField = document.getElementById("id_discount_percent");
      if (currentDiscountMode() === "percent" && percentField) percentField.focus();
    }
    if (event.target.matches('select[name$="-method"]')) {
      syncPaymentRow(event.target.closest("[data-payment-row]"));
    }
    // A cheque row's issuer follows the customer until the clerk types his own.
    if (event.target.id === "id_customer") {
      document.querySelectorAll('#payment-rows input[name$="-issuer"][data-auto]').forEach(function (issuer) {
        issuer.value = customerName();
      });
      // The quick-created customer is not in the page's tier map yet; its option carries the tier.
      var chosen = event.target.selectedOptions && event.target.selectedOptions[0];
      var preset = customerTier(event.target.value) || (chosen && chosen.dataset.tier) || "";
      if (preset && !tierTouched) setTier(preset);
    }
    if (event.target.matches('input[name="price_tier"]')) {
      tierTouched = true;
      applyTier(currentTier());
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
    if (event.target.matches('input[name$="-carton_price"]') || event.target.matches('input[name$="-unit_price"]')) {
      var priceRow = event.target.closest("[data-item-row]");
      if (priceRow) checkCost(priceRow);
    }
    if (event.target.matches('input[name$="-issuer"]')) delete event.target.dataset.auto;
  });

  // ---- the sticky bar's recap: who, how paid, how much (the amount itself is the dock total).
  var recapTimer = null;
  // Other scripts (invoice_payment.js) update the amounts after our own listeners, so read late.
  function scheduleRecap() {
    if (recapTimer) return;
    recapTimer = setTimeout(function () {
      recapTimer = null;
      renderRecap();
    }, 0);
  }

  function checked(id) {
    var el = document.getElementById(id);
    return !!(el && el.checked);
  }

  function renderRecap() {
    var el = document.getElementById("sale-recap");
    if (!el) return;
    var name = customerName();
    var total = currentTotal();
    var message = "";
    var warn = false;
    var quick = false;
    if (!total) {
      message = "هنوز قلمی با مبلغ در فاکتور نیست.";
    } else if (!name) {
      message = "مشتری انتخاب نشده است.";
      warn = true;
    } else if (currentPaymentMode() === "split") {
      var parts = [];
      document.querySelectorAll("#payment-rows [data-payment-row]").forEach(function (row) {
        var amount = intVal(row.querySelector('input[name$="-amount"]'));
        var method = row.querySelector('select[name$="-method"]');
        if (amount > 0 && method && method.selectedIndex >= 0) {
          parts.push(method.options[method.selectedIndex].text.trim() + " " + formatToman(amount));
        }
      });
      var left = toInt((document.getElementById("sale-remaining") || {}).textContent);
      if (left > 0) {
        parts.push(formatToman(left) + " نسیه");
        var due = document.getElementById("id_credit_due_date");
        if (due && !due.value.trim()) {
          parts.push("سررسید را مشخص کنید");
          warn = true;
        }
      }
      message = "برای " + name + " · تفکیکی" + (parts.length ? ": " + parts.join(" + ") : "");
    } else if (!checked("id_use_pos") && !checked("id_use_transfer")) {
      message = "روش دریافت پول را انتخاب کنید: ";
      warn = true;
      quick = true;
    } else {
      var how = [];
      var both = checked("id_use_pos") && checked("id_use_transfer");
      if (checked("id_use_pos")) {
        how.push("کارت‌خوان" + (both ? " " + formatToman(intVal(document.getElementById("id_pos_amount"))) : ""));
      }
      if (checked("id_use_transfer")) {
        how.push("حواله بانکی" + (both ? " " + formatToman(intVal(document.getElementById("id_transfer_amount"))) : ""));
      }
      message = "برای " + name + " · تسویهٔ کامل با " + how.join(" + ");
    }
    // Rewriting identical text would make a screen reader repeat it on every keystroke.
    var signature = message + "|" + warn + "|" + quick;
    if (el.dataset.signature === signature) return;
    el.dataset.signature = signature;
    el.textContent = "";
    var msg = document.createElement("span");
    msg.className = "sale-dock__msg";
    msg.textContent = message;
    el.appendChild(msg);
    el.className = "sale-dock__recap" + (warn ? " is-warn" : "");
    if (quick) {
      // «نسیه» is the third real way a shop sells (and the one that is never remembered): it jumps to the terms.
      [["use_pos", "کارت‌خوان"], ["use_transfer", "حواله بانکی"], ["credit", "نسیه"]].forEach(function (pair) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "sale-dock__link";
        button.dataset.quickMethod = pair[0];
        button.textContent = pair[1];
        el.appendChild(button);
      });
    }
  }

  document.addEventListener("change", scheduleRecap);
  document.addEventListener("input", scheduleRecap);

  // ---- keyboard flow
  // Enter walks an invoice row like Tab and, on the last price box, finishes the line and opens
  // the next one at its product search. It still never posts the invoice.
  var ROW_FIELDS = ["-cartons", "-packs", "-carton_price", "-unit_price"];

  function rowField(row, suffix) {
    return row.querySelector('input[name$="' + suffix + '"]');
  }

  function focusAndSelect(target) {
    if (!target) return;
    target.focus();
    if (target.select) target.select();
  }

  function enterInRow(input, backwards) {
    var row = input.closest("[data-item-row]");
    if (!row) return;
    var index = -1;
    ROW_FIELDS.forEach(function (suffix, i) {
      if (input.name && input.name.slice(-suffix.length) === suffix) index = i;
    });
    if (index === -1) return;
    var step = index + (backwards ? -1 : 1);
    if (step < 0) {
      focusAndSelect(row.querySelector("[data-item-row-search]"));
    } else if (step < ROW_FIELDS.length) {
      focusAndSelect(rowField(row, ROW_FIELDS[step]));
    } else if (!row.querySelector('input[name$="-product"]').value) {
      // Last box of a line that has no product yet: go back to the product search.
      focusAndSelect(row.querySelector("[data-item-row-search]"));
    } else if (lineQuantity(row) <= 0) {
      focusAndSelect(rowField(row, "-cartons"));
    } else {
      var next = row.nextElementSibling;
      if (next) {
        focusAndSelect(next.querySelector("[data-item-row-search]"));
      } else {
        // Reuses the add-row click handler, which also focuses the new search box.
        var addButton = document.getElementById("add-item-row");
        if (addButton) addButton.click();
      }
    }
  }

  function jumpToProduct() {
    var search = document.querySelector("#item-rows [data-item-row-search]");
    if (search && !search.value) search.focus();
  }

  // Enter inside a text/number box must not post the invoice: this form
  // creates and confirms a financial document in one go, and Enter is how
  // people finish typing a number, not how they mean to submit.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeResults();
    if (event.key !== "Enter") return;
    // Ctrl/Cmd+Enter is the deliberate "finish" chord: the same button, so a blocked or busy form still refuses.
    if (event.ctrlKey || event.metaKey) {
      var finish = document.querySelector('#sale-form button[type="submit"], button[type="submit"][form="sale-form"]');
      if (finish && !finish.disabled) {
        event.preventDefault();
        document.getElementById("sale-form").requestSubmit(finish);
      }
      return;
    }
    var t = event.target;
    // Enter in the product box picks the first result instead of doing nothing.
    if (t.matches && t.matches("[data-item-row-search]")) {
      var first = t.closest("[data-item-row]").querySelector("[data-item-row-pick]:not(:disabled)");
      if (first) pickProduct(first);
      event.preventDefault();
      return;
    }
    // Enter on the customer box means "this customer, next the goods".
    if (t.id === "id_customer" && t.value) {
      event.preventDefault();
      jumpToProduct();
      return;
    }
    if (t.matches && t.matches("#sale-form input:not([type=submit]):not([type=button]):not([type=radio]):not([type=checkbox])")) {
      event.preventDefault();
      enterInRow(t, event.shiftKey);
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
    // The bank of the last cheque is almost always the next one's too.
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(function (row) {
      var method = row.querySelector('select[name$="-method"]');
      var bank = row.querySelector('input[name$="-bank_name"]');
      if (currentPaymentMode() === "split" && method && method.value === "cheque" && bank && bank.value.trim()) {
        storeSet("pp.sale.lastChequeBank", bank.value.trim());
      }
    });
  });
  // Back/forward restores the page with the flag still set.
  window.addEventListener("pageshow", function (event) {
    var form = document.getElementById("sale-form");
    if (form) delete form.dataset.busy;
    if (event.persisted) recomputeInvoice();
  });

  // A new sale starts at the first empty decision: the customer, else the first empty product box.
  // A page re-rendered with errors is left alone so the messages can be read first.
  function focusStart() {
    if (document.querySelector(".form-error, .field--invalid")) return;
    if (document.getElementById("cust-combo-input")) return; // the type-ahead takes the focus itself
    var customer = document.getElementById("id_customer");
    var search = document.querySelector("#item-rows [data-item-row-search]");
    if (customer && !customer.value) customer.focus();
    else if (search && !search.value) search.focus();
  }

  document.addEventListener("invoice:party-changed", function () { recomputeInvoice(); });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-item-row]").forEach(function (row) {
      var s = row.querySelector("[data-item-row-search]");
      if (s && s.value) row.dataset.pickedName = s.value;
    });
    // Fresh form + a remembered percent habit: open in percent mode. Typed values and errors win.
    var amountBox = document.getElementById("id_discount_amount");
    var percentBox = document.getElementById("id_discount_percent");
    var percentRadio = document.querySelector('input[name="discount_mode"][value="percent"]');
    if (storeGet("pp.sale.discountMode") === "percent" && percentRadio && !(amountBox && amountBox.value) &&
        !(percentBox && percentBox.value) && !document.querySelector(".form-error, .field--invalid")) {
      percentRadio.checked = true;
    }
    showDiscountPanel(currentDiscountMode());
    lastTier = currentTier();
    // A customer already chosen (?customer=) presets the sale type on a fresh form only.
    var customerSelect = document.getElementById("id_customer");
    var isFresh = !document.querySelector(".form-error, .field--invalid") &&
      !document.querySelector('#item-rows input[name$="-product"][value]:not([value=""])');
    if (customerSelect && customerSelect.value && isFresh) {
      var preset = customerTier(customerSelect.value);
      if (preset) setTier(preset);
    }
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(syncPaymentRow);
    recomputeInvoice();
    focusStart();
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

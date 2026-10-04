/*
 * Payment behaviour shared by the new-sale and new-purchase forms (D-069):
 *  - full settlement: when both card and transfer are chosen, typing one
 *    amount fills the other with the rest of the total; when only one is
 *    chosen it takes the whole total;
 *  - payment rows: the account list follows the method (card reader for
 *    "کارت‌خوان", current account for "حواله بانکی" and "چک");
 *  - the credit due date only appears while part of the invoice is unpaid.
 * Presentation only: the server re-validates everything against the real total.
 * sale_form.js / purchase_form.js fire "invoice:recomputed" after each recompute.
 */
(function () {
  "use strict";

  var ACCOUNT_TYPE = { card: "pos", bank_transfer: "current", cheque: "current" };

  function digitsToAscii(text) {
    return text.replace(/[۰-۹]/g, function (d) {
      return String(d.charCodeAt(0) - 0x06f0);
    });
  }

  function total() {
    var el = document.getElementById("sale-total");
    return el ? parseInt(digitsToAscii(el.textContent).replace(/,/g, ""), 10) || 0 : 0;
  }

  function field(name) {
    return document.getElementById("id_" + name);
  }

  function num(input) {
    var n = parseInt(input && input.value, 10);
    return isNaN(n) ? 0 : n;
  }

  // ---- full settlement
  function syncFullAmounts(changed) {
    var posAmt = field("pos_amount");
    var trAmt = field("transfer_amount");
    var hasPos = !!(field("use_pos") && field("use_pos").checked);
    var hasTr = !!(field("use_transfer") && field("use_transfer").checked);
    var t = total();
    if (hasPos && hasTr) {
      // Two methods: the amount just typed decides, the other takes the rest.
      if (changed === "pos_amount" && posAmt && trAmt) trAmt.value = Math.max(t - num(posAmt), 0) || "";
      else if (changed === "transfer_amount" && posAmt && trAmt) posAmt.value = Math.max(t - num(trAmt), 0) || "";
      else if (posAmt && trAmt && !posAmt.value && !trAmt.value) { posAmt.value = ""; trAmt.value = ""; }
    } else if (hasPos && posAmt) {
      posAmt.value = t || "";
      if (trAmt) trAmt.value = "";
    } else if (hasTr && trAmt) {
      trAmt.value = t || "";
      if (posAmt) posAmt.value = "";
    }
  }

  // A method's fields show only while its box is ticked; hidden ones are
  // disabled so they are not posted and the server never sees stale values.
  function applyTicks() {
    document.querySelectorAll("[data-method-block]").forEach(function (block) {
      var tick = block.querySelector('input[type="checkbox"]');
      var panel = block.querySelector("[data-method-fields]");
      if (!tick || !panel) return;
      panel.hidden = !tick.checked;
      panel.querySelectorAll("input, select").forEach(function (el) {
        el.disabled = !tick.checked;
        if (!tick.checked && el.type !== "hidden" && el.tagName !== "SELECT") el.value = "";
      });
    });
  }

  // ---- payment rows
  function filterRowAccounts(row) {
    var method = row.querySelector('select[name$="-method"]');
    var account = row.querySelector('select[name$="-bank_account"]');
    if (!method || !account) return;
    var want = ACCOUNT_TYPE[method.value];
    Array.prototype.forEach.call(account.options, function (opt) {
      if (!opt.value) return;
      var ok = !want || opt.dataset.type === want;
      opt.hidden = !ok;
      opt.disabled = !ok;
    });
    var chosen = account.options[account.selectedIndex];
    if (chosen && chosen.value && chosen.disabled) account.value = "";
    // A single card reader is the obvious account for a card row (D-078).
    if (method.value === "card" && !account.value) {
      var pos = Array.prototype.filter.call(account.options, function (o) { return o.value && !o.disabled; });
      if (pos.length === 1) account.value = pos[0].value;
    }
  }

  function syncCreditDue() {
    var wrap = document.querySelector("[data-credit-due]");
    var remaining = document.getElementById("sale-remaining");
    if (!wrap || !remaining) return;
    wrap.hidden = (parseInt(digitsToAscii(remaining.textContent).replace(/,/g, ""), 10) || 0) <= 0;
  }

  document.addEventListener("invoice:recomputed", function () {
    var mode = document.querySelector('input[name="payment_mode"]:checked');
    if (!mode || mode.value === "full") syncFullAmounts();
    syncCreditDue();
  });

  document.addEventListener("input", function (event) {
    var id = event.target.id;
    if (id === "id_pos_amount" || id === "id_transfer_amount") syncFullAmounts(id.replace("id_", ""));
  });

  document.addEventListener("change", function (event) {
    var t = event.target;
    if (t.id === "id_use_pos" || t.id === "id_use_transfer") {
      applyTicks();
      syncFullAmounts();
    }
    if (t.matches && t.matches('select[name$="-method"]')) filterRowAccounts(t.closest("[data-payment-row]"));
  });

  // A row added by the form script: filter its accounts once it exists.
  document.addEventListener("click", function (event) {
    if (event.target.id === "add-payment-row") {
      setTimeout(function () {
        document.querySelectorAll("#payment-rows [data-payment-row]").forEach(filterRowAccounts);
      }, 0);
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(filterRowAccounts);
    applyTicks();
    syncCreditDue();
  });
})();

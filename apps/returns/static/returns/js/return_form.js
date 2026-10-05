/*
 * New return form (D-089): flags a line typed above what is left to return, and shows
 * the refund account only when "refund" is chosen. Presentation only: the service
 * re-checks every quantity and the account.
 */
(function () {
  "use strict";

  function toInt(value) {
    var ascii = String(value || "").replace(/[۰-۹]/g, function (d) { return d.charCodeAt(0) - 0x06f0; })
      .replace(/[٠-٩]/g, function (d) { return d.charCodeAt(0) - 0x0660; });
    return parseInt(ascii.replace(/[^0-9]/g, ""), 10) || 0;
  }

  function checkRow(row) {
    var inputs = row.querySelectorAll(".ret-qty");
    var ratio = parseInt(row.getAttribute("data-ratio"), 10) || 1;
    var left = parseInt(row.getAttribute("data-left"), 10) || 0;
    var total = toInt(inputs[0].value) * ratio + toInt(inputs[1].value);
    var over = total > left;
    var note = row.querySelector("[data-over]");
    if (note) note.hidden = !over;
    row.classList.toggle("is-over", over);
    return over;
  }

  function syncAccount(form) {
    var refund = form.querySelector('input[name="settle_mode"][value="refund"]');
    var box = form.querySelector("[data-refund-account]");
    if (box) box.hidden = !(refund && refund.checked);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-return-form]");
    if (!form) return;
    form.addEventListener("input", function (e) {
      var row = e.target.closest && e.target.closest("[data-return-row]");
      if (row) checkRow(row);
    });
    form.addEventListener("change", function (e) {
      if (e.target.name === "settle_mode") syncAccount(form);
    });
    form.addEventListener("submit", function (e) {
      var bad = false;
      form.querySelectorAll("[data-return-row]").forEach(function (row) { if (checkRow(row)) bad = true; });
      if (bad) e.preventDefault();
    });
    syncAccount(form);
    form.querySelectorAll("[data-return-row]").forEach(checkRow);
    // Typing the quantity is the whole job: start there (like the invoice forms) instead of eight Tab stops
    // away, unless the page came back with errors the user has to read first.
    var firstQty = form.querySelector(".ret-qty");
    var shownError = Array.prototype.some.call(document.querySelectorAll(".field__error, [role=alert]"), function (el) {
      return el.offsetHeight > 0; // the per-row over-limit note exists in the DOM but starts hidden
    });
    if (firstQty && !shownError) firstQty.focus();
  });
})();

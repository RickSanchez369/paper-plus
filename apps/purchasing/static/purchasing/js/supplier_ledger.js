/*
 * Supplier detail page, presentation only:
 *  - the purchase-history filter (all / open / paid / cancelled) only shows and
 *    hides rows that are already in the page, and sums what is shown;
 *  - in the "ثبت پرداخت" form the amount follows the ticked invoices, until the
 *    amount has been typed by hand.
 * Without JS every row shows and the form works as it always did.
 */
(function () {
  "use strict";

  function toman(n) {
    var s = String(Math.max(0, Math.round(n || 0))).replace(/\B(?=(\d{3})+(?!\d))/g, "٬");
    return s.replace(/[0-9]/g, function (d) { return String.fromCharCode(0x06f0 + Number(d)); }) + " تومان";
  }

  // ---- purchase history filter + shown totals ------------------------------
  function applyFilter(group, mode) {
    var table = document.querySelector(group.dataset.ledgerFilter);
    if (!table) return;
    var total = 0;
    var paid = 0;
    table.querySelectorAll("tbody tr[data-state]").forEach(function (row) {
      var show = mode === "all" || row.dataset.state === mode;
      row.hidden = !show;
      // A cancelled invoice is no debt and no purchase: it never enters the sums.
      if (show && row.dataset.state !== "cancelled") {
        total += parseInt(row.dataset.total, 10) || 0;
        paid += parseInt(row.dataset.paid, 10) || 0;
      }
    });
    group.querySelectorAll("[data-f]").forEach(function (chip) {
      chip.setAttribute("aria-pressed", String(chip.dataset.f === mode));
    });
    var foot = table.querySelector("[data-ledger-total]");
    if (foot) {
      var t = foot.querySelector('[data-sum="total"]');
      var p = foot.querySelector('[data-sum="paid"]');
      if (t) t.textContent = toman(total);
      if (p) p.textContent = toman(paid);
      foot.hidden = false;
    }
  }

  document.addEventListener("click", function (event) {
    var chip = event.target.closest && event.target.closest("[data-ledger-filter] [data-f]");
    if (!chip) return;
    applyFilter(chip.closest("[data-ledger-filter]"), chip.dataset.f);
  });

  // ---- payment form: amount follows the ticked invoices --------------------
  var amounts = null;

  function openAmounts() {
    if (amounts !== null) return amounts;
    var el = document.getElementById("open-invoice-amounts");
    try {
      amounts = el ? JSON.parse(el.textContent) : {};
    } catch (e) {
      amounts = {};
    }
    return amounts;
  }

  document.addEventListener("input", function (event) {
    var t = event.target;
    if (event.isTrusted && t.matches && t.matches('#pay input[name="amount"]')) t.dataset.touched = "1";
  });

  document.addEventListener("change", function (event) {
    var t = event.target;
    if (!t.matches || !t.matches('#pay input[name="invoices"]')) return;
    var form = t.closest("form");
    var box = form && form.querySelector('input[name="amount"]');
    if (!box || box.dataset.touched) return;
    var map = openAmounts();
    var sum = 0;
    form.querySelectorAll('input[name="invoices"]:checked').forEach(function (c) {
      sum += Number(map[c.value]) || 0;
    });
    if (sum > 0) box.value = sum;
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-ledger-filter]").forEach(function (group) {
      group.hidden = false; // the buttons only work with this script, so only it shows them
      applyFilter(group, "all");
    });
  });
})();

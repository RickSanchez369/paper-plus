/*
 * Party credit on a new sales/purchase invoice (D-087): money the customer paid
 * (or we paid the supplier) beyond earlier invoices is used on this invoice first,
 * so the amount still to settle is the total minus that credit.
 *
 * Reads the {party pk: credit} map printed by the page (#party-credits) and the
 * party <select> (#id_customer or #id_supplier); shows the notice in the payment
 * card and tells the form scripts to recompute when the party changes.
 * Presentation only: confirm_sale / confirm_purchase apply the real credit.
 */
(function () {
  "use strict";

  var credits = null;

  function map() {
    if (credits === null) {
      var el = document.getElementById("party-credits");
      try { credits = el ? JSON.parse(el.textContent) : {}; } catch (e) { credits = {}; }
    }
    return credits;
  }

  function partySelect() {
    return document.getElementById("id_customer") || document.getElementById("id_supplier");
  }

  function fmt(n) {
    return String(Math.max(0, Math.round(n || 0))).replace(/\B(?=(\d{3})+(?!\d))/g, "٬").replace(/[0-9]/g, function (d) {
      return String.fromCharCode(0x06f0 + Number(d));
    });
  }

  // The credit of the party picked right now, in Toman (0 = none or no party yet).
  window.partyCredit = function () {
    var select = partySelect();
    return (select && map()[select.value]) || 0;
  };

  // What is left to settle once the credit is used: never below zero.
  window.payableAfterCredit = function (total) {
    return Math.max((total || 0) - window.partyCredit(), 0);
  };

  function render(total) {
    var note = document.getElementById("party-credit-note");
    if (!note) return;
    var credit = window.partyCredit();
    note.hidden = !credit;
    if (!credit) return;
    var used = Math.min(credit, total || 0);
    var put = function (id, value) {
      var el = document.getElementById(id);
      if (el) el.textContent = fmt(value);
    };
    put("party-credit-amount", credit);
    put("party-credit-used", used);
    put("party-credit-due", Math.max((total || 0) - credit, 0));
  }

  document.addEventListener("invoice:recomputed", function () {
    var el = document.getElementById("sale-total");
    var total = el ? parseInt(el.textContent.replace(/[۰-۹]/g, function (d) { return d.charCodeAt(0) - 0x06f0; }).replace(/[^0-9]/g, ""), 10) || 0 : 0;
    render(total);
  });

  // Delegated: the quick-create form swaps in a fresh <select> after adding a party.
  document.addEventListener("change", function (event) {
    var id = event.target && event.target.id;
    if (id === "id_customer" || id === "id_supplier") {
      document.dispatchEvent(new CustomEvent("invoice:party-changed"));
    }
  });
})();

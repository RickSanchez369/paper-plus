/*
 * New-expense form (D-072): show only the fields of the chosen payment method
 * (bank transfer / cheque / credit). Presentation only -- the server form
 * validates what each method needs.
 */
(function () {
  "use strict";

  function currentMethod() {
    var checked = document.querySelector('#expense-form input[name="payment_method"]:checked');
    return checked ? checked.value : "transfer";
  }

  function sync() {
    var method = currentMethod();
    document.querySelectorAll("[data-expense-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.expensePanel.split(" ").indexOf(method) === -1;
    });
  }

  document.addEventListener("change", function (event) {
    if (event.target.matches('#expense-form input[name="payment_method"]')) sync();
  });
  document.addEventListener("DOMContentLoaded", sync);
})();

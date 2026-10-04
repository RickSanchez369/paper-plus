/*
 * Fixed-cost form: quick-start chips (title, period, reminder and the last known
 * amount), due-date shortcut chips, and the amount of a past expense when a
 * known title is picked. Presentation only -- every value stays editable and the
 * server validates as before. Delegated from `document`, so it survives swaps.
 */
(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }

  // Same notification the date picker sends, so anything listening to the box sees the change.
  function setValue(id, value) {
    var el = $(id);
    if (!el || value === "" || value === null || value === undefined) return;
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function pastAmounts() {
    var node = $("recurring-past-amounts");
    if (!node) return {};
    try { return JSON.parse(node.textContent); } catch (e) { return {}; }
  }

  document.addEventListener("click", function (event) {
    var chip = event.target.closest ? event.target.closest(".exb-chip") : null;
    if (!chip || !chip.closest("#recurring-form, .exb-chips--start")) return;

    if (chip.hasAttribute("data-reason")) {
      setValue("id_reason", chip.getAttribute("data-reason"));
      setValue("id_repeat_every", chip.getAttribute("data-every"));
      setValue("id_repeat_unit", chip.getAttribute("data-unit"));
      setValue("id_remind_days_before", chip.getAttribute("data-remind"));
      setValue("id_amount", chip.getAttribute("data-amount"));
      // Jump to what is still missing.
      var amount = $("id_amount");
      if (amount && !amount.value) amount.focus();
    } else if (chip.hasAttribute("data-value")) {
      setValue(chip.parentNode.getAttribute("data-chip-target"), chip.getAttribute("data-value"));
    }
  });

  // Picking a past expense title from the list also suggests its amount, when none is typed yet.
  document.addEventListener("change", function (event) {
    if (event.target.id !== "id_reason") return;
    var amount = $("id_amount");
    var known = pastAmounts()[event.target.value.trim()];
    if (amount && !amount.value && known) amount.value = known;
  });

  // Arrived from a starter chip (reason filled, amount missing): the amount is the next thing to type.
  document.addEventListener("DOMContentLoaded", function () {
    var reason = $("id_reason");
    var amount = $("id_amount");
    if (reason && amount && reason.value && !amount.value && !document.querySelector(".field--invalid")) amount.focus();
  });
})();

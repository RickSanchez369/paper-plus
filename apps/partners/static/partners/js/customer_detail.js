/* Customer detail: header panels (pay / edit) and statement printing. */
(function () {
  "use strict";

  // Delegated, so it keeps working after any htmx swap inside the page.
  document.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-open-panel]");
    if (opener) {
      var panel = document.getElementById(opener.getAttribute("data-open-panel"));
      if (!panel) { return; }
      var willOpen = !panel.open;
      // One panel at a time keeps the header from growing.
      document.querySelectorAll(".head-panel").forEach(function (other) { other.open = false; });
      document.querySelectorAll("[data-open-panel]").forEach(function (btn) {
        btn.setAttribute("aria-expanded", "false");
      });
      if (willOpen) {
        panel.open = true;
        opener.setAttribute("aria-expanded", "true");
        var field = panel.querySelector("input:not([type=hidden]):not([disabled]), select, textarea");
        if (field) { field.focus(); }
      }
      return;
    }
    if (event.target.closest("[data-print-statement]")) {
      window.print();
    }
  });

  // Print only the statement: the class also covers Ctrl+P, not just the button.
  window.addEventListener("beforeprint", function () {
    document.body.classList.add("printing-statement");
  });
  window.addEventListener("afterprint", function () {
    document.body.classList.remove("printing-statement");
  });
})();

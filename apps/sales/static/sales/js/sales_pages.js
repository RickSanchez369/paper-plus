/* Sales list/detail behaviour: the print shortcut, and open/close the cancel-confirmation dialog. Delegated listeners only, so an
   htmx swap never loses them. */
(function () {
  "use strict";

  // --- Print ------------------------------------------------------------
  // The "چاپ" links open the print page itself (colour or black-and-white is chosen
  // there, D-102); Ctrl/Cmd+P on the detail page goes to the same place.
  document.addEventListener("keydown", function (e) {
    if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || String(e.key).toLowerCase() !== "p") return;
    if (document.querySelector("dialog[open]")) return;
    var link = document.querySelector(".sale-detail__actions a[data-sp-print]");
    if (!link) return;
    e.preventDefault();
    window.location.href = link.href;
  });

  // --- Cancel dialog ----------------------------------------------------
  document.addEventListener("click", function (e) {
    var opener = e.target.closest ? e.target.closest("[data-sp-dialog-open]") : null;
    if (opener) {
      var dlg = document.getElementById(opener.getAttribute("data-sp-dialog-open"));
      if (dlg && !dlg.open) {
        if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
      }
      return;
    }
    if (e.target.closest && e.target.closest("[data-sp-dialog-close]")) {
      var parent = e.target.closest("dialog");
      if (parent) { if (parent.close) parent.close(); else parent.removeAttribute("open"); }
      return;
    }
    // A click on the backdrop (outside the box) is a safe way out.
    if (e.target.tagName === "DIALOG" && e.target.hasAttribute("data-sp-dialog-backdrop")) {
      var r = e.target.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) e.target.close();
    }
  });
})();

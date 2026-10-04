/* Sales list/detail behaviour: print an invoice without leaving the page, and
   open/close the cancel-confirmation dialog. Delegated listeners only, so an
   htmx swap never loses them. */
(function () {
  "use strict";

  // --- Print in place ---------------------------------------------------
  // The print page stays the preview (same URL, still opens with Ctrl+click or
  // without JS); the plain click prints it through a hidden same-origin iframe.
  var frame;

  function printInline(url) {
    if (frame && frame.parentNode) frame.parentNode.removeChild(frame);
    frame = document.createElement("iframe");
    frame.setAttribute("aria-hidden", "true");
    frame.tabIndex = -1;
    frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
    frame.onload = function () {
      var win = frame.contentWindow;
      try {
        // Vazirmatn must be ready, or the first print uses a fallback font.
        var ready = win.document.fonts ? win.document.fonts.ready : Promise.resolve();
        ready.then(function () { win.focus(); win.print(); });
      } catch (err) {
        window.location.href = url; // frame blocked: fall back to the preview page
      }
    };
    frame.src = url;
    document.body.appendChild(frame);
  }

  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a[data-sp-print]") : null;
    if (!link || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button) return; // keep "open in new tab"
    e.preventDefault();
    printInline(link.href);
  });

  // Ctrl/Cmd+P on the invoice page prints the invoice, not the app shell.
  document.addEventListener("keydown", function (e) {
    if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || String(e.key).toLowerCase() !== "p") return;
    if (document.querySelector("dialog[open]")) return;
    var link = document.querySelector(".sale-detail__actions a[data-sp-print]");
    if (!link) return;
    e.preventDefault();
    printInline(link.href);
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

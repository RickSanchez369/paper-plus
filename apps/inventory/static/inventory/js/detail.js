/*
 * Product detail: a link or bookmark that targets a section inside a collapsed
 * <details> (e.g. #price-history) opens it, so the target is never hidden.
 */
(function () {
  "use strict";

  function openTarget() {
    if (!location.hash) return;
    var id = location.hash.slice(1);
    try { id = decodeURIComponent(id); } catch (e) { /* malformed escape: use it as typed */ }
    var el = document.getElementById(id);
    var d = el && el.querySelector("details");
    if (d) d.open = true;
  }

  window.addEventListener("hashchange", openTarget);
  openTarget();
})();

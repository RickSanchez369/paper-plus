/*
 * Inventory list: remember the viewer's own "running low" threshold (cartons).
 * A per-browser convenience only -- the server never stores it and the page
 * works the same without it. The filter itself is plain ?stock=low&low=N.
 */
(function () {
  "use strict";

  var KEY = "pp.lowCartons";

  function readSaved() {
    try {
      var v = window.localStorage.getItem(KEY);
      return /^[0-9]{1,3}$/.test(v || "") && parseInt(v, 10) > 0 ? String(parseInt(v, 10)) : null;
    } catch (e) {
      return null;
    }
  }

  function save(value) {
    try { window.localStorage.setItem(KEY, value); } catch (e) { /* private window: just not remembered */ }
  }

  var saved = readSaved();
  if (saved) {
    // Opened the lens without a threshold in the URL: reuse the remembered one.
    if (/[?&]stock=low(&|$)/.test(location.search) && !/[?&]low=/.test(location.search)) {
      location.replace(location.search + "&low=" + saved);
      return;
    }
    var link = document.querySelector("[data-low-link]");
    if (link) link.setAttribute("href", "?stock=low&low=" + saved);
  }

  // Delegated: the filter form can be re-rendered, the document listener stays.
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (!t || t.name !== "low" || !t.closest || !t.closest("#inv-filter")) return;
    var v = String(t.value).replace(/[^0-9]/g, "");
    if (v && parseInt(v, 10) > 0) save(String(parseInt(v, 10)));
  });
})();

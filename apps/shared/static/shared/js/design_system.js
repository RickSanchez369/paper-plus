/*
 * Design-system helpers loaded in <head> (not deferred): the remembered table
 * density, and phone "record cards" for plain tables.
 * Everything is delegated from `document`, so htmx swaps need no re-binding.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var KEY = "pp-density";

  // ---- G031: Comfortable / Compact table density, remembered per browser ----
  function stored() {
    try { return localStorage.getItem(KEY) === "compact"; } catch (e) { return false; }
  }

  function remember(compact) {
    try { localStorage.setItem(KEY, compact ? "compact" : "comfortable"); } catch (e) { /* private mode: still works for this page */ }
  }

  function apply(compact) {
    if (compact) {
      root.setAttribute("data-density", "compact");
    } else {
      root.removeAttribute("data-density");
    }
    Array.prototype.forEach.call(document.querySelectorAll("[data-density-toggle]"), function (btn) {
      btn.setAttribute("aria-pressed", compact ? "true" : "false");
    });
  }

  // Set before first paint so a compact table never flashes comfortable.
  if (stored()) { root.setAttribute("data-density", "compact"); }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest("[data-density-toggle]") : null;
    if (!btn) { return; }
    var compact = root.getAttribute("data-density") !== "compact";
    remember(compact);
    apply(compact);
  });

  // ---- G043: phone record cards, labels copied from the column headers ----
  // Only well-formed tables opt in (one header row, no totals row, no colspan),
  // so a table that must stay tabular keeps scrolling sideways as before.
  var ACTION_SEL = "a.btn, button, summary, form";

  function headerText(th) {
    var clone = th.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll(".sr-only, .ledger__sr"), function (n) { n.parentNode.removeChild(n); });
    return clone.textContent.replace(/[⇅↑↓]/g, "").replace(/\s+/g, " ").trim();
  }

  function eligible(table) {
    if (table.classList.contains("data-table--stack") || table.classList.contains("data-table--scroll")) { return false; }
    if (table.hasAttribute("data-no-cards") || !table.tHead || table.tHead.rows.length !== 1) { return false; }
    // A footer is fine when every row of it is a marked totals row (reports, ledgers): it is shown as a summary line.
    if (table.tFoot && !Array.prototype.every.call(table.tFoot.rows, function (r) { return r.hasAttribute("data-card-skip"); })) { return false; }
    var cols = table.tHead.rows[0].cells.length;
    var rows = 0;
    for (var b = 0; b < table.tBodies.length; b++) {
      for (var r = 0; r < table.tBodies[b].rows.length; r++) {
        var row = table.tBodies[b].rows[r];
        if (row.hasAttribute("data-card-skip")) { continue; } // a totals row spans columns: it must not veto the cards
        rows++;
        if (row.cells.length !== cols) { return false; }
        for (var c = 0; c < row.cells.length; c++) {
          if (row.cells[c].colSpan > 1 || row.cells[c].rowSpan > 1) { return false; }
        }
      }
    }
    return rows > 0;
  }

  function labelTable(table) {
    var heads = Array.prototype.map.call(table.tHead.rows[0].cells, headerText);
    Array.prototype.forEach.call(table.tBodies, function (body) {
      Array.prototype.forEach.call(body.rows, function (row) {
        if (row.hasAttribute("data-card-skip")) { return; }
        // The one document link of a card (invoice no., cheque no., customer) gets a stretched hit area on phones.
        var first = row.cells[0];
        if (first && first.querySelectorAll("a[href]").length === 1) { first.querySelector("a[href]").classList.add("card-link"); }
        Array.prototype.forEach.call(row.querySelectorAll(".cell-sub"), function (sub) {
          var shown = sub.cloneNode(true);
          Array.prototype.forEach.call(shown.querySelectorAll(".sr-only"), function (x) { x.remove(); });
          if (/^[\s—-]*$/.test(shown.textContent)) { sub.setAttribute("data-empty", ""); }
        });
        Array.prototype.forEach.call(row.cells, function (td, i) {
          if (td.tagName !== "TD" || td.hasAttribute("data-label") || td.classList.contains("cell-actions")) { return; }
          // An empty cell ("—") would print its label over nothing in a card; CSS hides it on phones.
          var plain = td.textContent.replace(/\s/g, "");
          if ((plain === "" || plain === "—" || plain === "-") && !td.querySelector("a, button, input, select, details")) { td.setAttribute("data-empty", ""); }
          // A header-less (or screen-reader-only) column that holds buttons is the card's action row.
          if (!heads[i] && td.querySelector(ACTION_SEL)) {
            td.classList.add("cell-actions");
          } else if (heads[i] && i > 0) {
            td.setAttribute("data-label", heads[i]);
          }
        });
      });
    });
  }

  function cards() {
    Array.prototype.forEach.call(document.querySelectorAll("table.data-table"), function (table) {
      if (table.hasAttribute("data-cards")) {
        labelTable(table);
      } else if (eligible(table)) {
        table.setAttribute("data-cards", "");
        labelTable(table);
      }
    });
  }

  function ready() {
    apply(root.getAttribute("data-density") === "compact");
    cards();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
  document.addEventListener("htmx:afterSettle", cards);
})();

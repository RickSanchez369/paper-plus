/*
 * Keyboard layer: the Ctrl+K quick-jump palette, "/" to reach the page's
 * search, "?" for the cheat sheet, Ctrl+Enter to finish an invoice and Alt+N
 * to add an invoice row.
 *
 * Everything here is a second, faster route to something that already has a
 * button or a link; nothing replaces the drawer (D-065). Shortcuts use
 * event.code (the physical key), because on a Persian layout event.key for
 * "K", "N" or "/" is a Persian glyph and a key-based shortcut would never fire.
 * Plain keys never fire while the user is typing in a field, so digits and
 * Persian text are never hijacked.
 */
(function () {
  "use strict";

  var dlg = document.getElementById("cmdk");
  var help = document.getElementById("kbd-help");
  var canModal = !!(dlg && dlg.showModal);

  // ---------------------------------------------------------------- palette
  var input, items, groups, empty, cur = 0;

  // ي/ك typed on an Arabic keyboard, ZWNJ and Persian digits must not cause a miss.
  function norm(s) {
    return String(s || "")
      .replace(/[يى]/g, "ی").replace(/ك/g, "ک")
      .replace(/\u200c/g, " ")
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06f0); })
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); })
      .replace(/[أإآ]/g, "ا")
      .toLowerCase().trim();
  }

  function visible() {
    return items.filter(function (li) { return !li.hidden; });
  }

  function mark(i) {
    var v = visible();
    items.forEach(function (li) { li.removeAttribute("aria-selected"); });
    if (!v.length) { input.removeAttribute("aria-activedescendant"); return; }
    cur = (i + v.length) % v.length;
    v[cur].setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", v[cur].id);
    if (v[cur].scrollIntoView) v[cur].scrollIntoView({ block: "nearest" });
  }

  function filter() {
    var terms = norm(input.value).split(/\s+/).filter(Boolean);
    items.forEach(function (li) {
      var hay = norm(li.textContent + " " + (li.firstElementChild.getAttribute("data-k") || ""));
      li.hidden = !terms.every(function (t) { return hay.indexOf(t) > -1; });
    });
    // A group heading with nothing under it is just noise.
    groups.forEach(function (g) {
      var n = g.nextElementSibling, any = false;
      while (n && !n.classList.contains("cmdk__group")) {
        if (!n.hidden) any = true;
        n = n.nextElementSibling;
      }
      g.hidden = !any;
    });
    empty.hidden = visible().length > 0;
    mark(0);
  }

  function initPalette() {
    input = dlg.querySelector(".cmdk__input");
    items = [].slice.call(dlg.querySelectorAll("[role=option]"));
    groups = [].slice.call(dlg.querySelectorAll(".cmdk__group"));
    empty = dlg.querySelector(".cmdk__empty");
    items.forEach(function (li, i) { li.id = "cmdk-o" + i; });

    input.addEventListener("input", filter);
    input.addEventListener("keydown", function (e) {
      if (e.isComposing) return;
      if (e.key === "ArrowDown") { e.preventDefault(); mark(cur + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); mark(cur - 1); }
      else if (e.key === "Enter") {
        var v = visible()[cur];
        if (v) { e.preventDefault(); window.location.href = v.firstElementChild.href; }
      }
    });
    // Click on the dialog itself (not its box) = the backdrop.
    dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });
  }

  function anotherModalOpen(except) {
    var open = document.querySelectorAll("dialog[open]");
    for (var i = 0; i < open.length; i++) if (open[i] !== except) return true;
    return false;
  }

  function openPalette() {
    if (!canModal || dlg.open || anotherModalOpen()) return;
    // Never stack two overlays: the drawer closes first.
    if (document.body.classList.contains("nav-open")) {
      var closer = document.querySelector(".nav-close");
      if (closer) closer.click();
    }
    if (!items) initPalette();
    input.value = "";
    filter();
    dlg.showModal();
    input.focus();
  }

  function openHelp() {
    if (!help || !help.showModal || help.open) return;
    if (dlg && dlg.open) dlg.close();
    else if (anotherModalOpen()) return;
    help.showModal();
  }

  if (help) {
    help.addEventListener("click", function (e) {
      if (e.target === help || (e.target.closest && e.target.closest("[data-kbd-help-close]"))) help.close();
    });
  }

  // ------------------------------------------------------------ page helpers
  function typing(t) {
    return !!(t && (t.isContentEditable || (t.closest && t.closest("input, textarea, select"))));
  }

  function usable(el) {
    return el && !el.disabled && el.offsetParent !== null;
  }

  // "/" lands in the page's own search box; no such box means the palette.
  function pageSearch() {
    var found = document.querySelectorAll('[data-key-search], main input[type="search"], main input[name="q"]');
    for (var i = 0; i < found.length; i++) if (usable(found[i])) return found[i];
    return null;
  }

  // The invoice forms are the only pages with a Ctrl+Enter target (or any form that opts in).
  function saveForm(target) {
    var own = target && target.closest && target.closest("form");
    if (own) return own.matches("[data-keysave], #sale-form, #purchase-form") ? own : null;
    return document.querySelector("form[data-keysave], #sale-form, #purchase-form");
  }

  // ----------------------------------------------------------------- keys
  // Capture phase and first in line: the invoice forms swallow Enter in every
  // box (it must never post a financial document by accident), so the explicit
  // Ctrl+Enter chord has to be seen before those handlers.
  document.addEventListener("keydown", function (e) {
    if (e.isComposing || e.defaultPrevented) return;
    var mod = e.ctrlKey || e.metaKey;

    if (mod && !e.altKey && e.code === "KeyK") {
      if (!canModal) return;
      e.preventDefault();
      if (dlg.open) dlg.close(); else openPalette();
      return;
    }

    if (mod && !e.altKey && (e.code === "Enter" || e.code === "NumpadEnter")) {
      var form = saveForm(e.target);
      if (!form) return;
      var btn = form.querySelector('[type="submit"]');
      e.preventDefault();
      e.stopImmediatePropagation();
      // Same gate as a click: a disabled button (stock guard, double-submit lock) stays disabled.
      if (btn && !btn.disabled) form.requestSubmit(btn);
      return;
    }

    if (e.altKey && !mod && e.code === "KeyN") {
      var add = document.getElementById("add-item-row");
      if (add && usable(add)) { e.preventDefault(); add.click(); }
      return;
    }

    if (mod || e.altKey || typing(e.target) || anotherModalOpen()) return;

    if (e.code === "Slash" && e.shiftKey) { e.preventDefault(); openHelp(); return; }
    if (e.code === "Slash") {
      var box = pageSearch();
      e.preventDefault();
      if (box) { box.focus(); if (box.select) box.select(); }
      else openPalette();
    }
  }, true);

  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-cmdk-open], [data-kbd-help-open]");
    if (!t) return;
    if (t.hasAttribute("data-kbd-help-open")) openHelp(); else openPalette();
  });
})();

/*
 * Customer picker for the new-sale page: a type-ahead box layered over the real
 * <select id="id_customer">, which stays in the DOM and stays the submitted field.
 *
 *  - typing filters the customers; ArrowUp/Down moves, Enter picks and jumps to the
 *    first product box;
 *  - when the typed name is not an existing customer, the last row is
 *    "+ register «name» as a new customer": it opens the existing quick-create
 *    form (partners/_quick_party_form.html) pre-filled and focused, so nothing is
 *    typed twice and the create endpoint is the very same one;
 *  - the quick form also lists similar existing customers while a name is typed,
 *    so a near-duplicate is noticed before it is created.
 *
 * Without JavaScript (or if anything here fails before the box is built) the plain
 * select and the "+ مشتری جدید" disclosure work exactly as before.
 */
(function () {
  "use strict";

  // Persian-safe matching: Arabic ي/ك, ZWNJ and any digit script are the same to the user.
  function norm(text) {
    return String(text || "")
      .replace(/ي/g, "ی")
      .replace(/ك/g, "ک")
      .replace(/[‌‎‏ـ]/g, "")
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06f0); })
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); })
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  var input = null;
  var list = null;
  var rows = [];
  var active = -1;
  var pristineForm = null; // the untouched quick-create form, to bring back after one was used

  function select() {
    return document.getElementById("id_customer");
  }

  function disclosure() {
    return document.querySelector(".sale-form__customer .quick-party-disclosure");
  }

  function firstProduct() {
    return document.querySelector("#item-rows [data-item-row-search]");
  }

  function fold(sel) {
    sel.classList.add("cust-combo__native");
    sel.tabIndex = -1;
    sel.setAttribute("aria-hidden", "true");
  }

  function selectedText(sel) {
    return sel.value && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].text.trim() : "";
  }

  function toProducts() {
    var search = firstProduct();
    if (search && !search.value) search.focus();
  }

  function close() {
    if (!list) return;
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function mark() {
    Array.prototype.forEach.call(list.children, function (li, i) {
      li.setAttribute("aria-selected", String(i === active));
      if (i === active) {
        input.setAttribute("aria-activedescendant", li.id);
        if (li.scrollIntoView) li.scrollIntoView({ block: "nearest" });
      }
    });
  }

  function render() {
    var sel = select();
    var typed = input.value.trim();
    var query = norm(typed);
    var exact = false;
    rows = Array.prototype.filter.call(sel.options, function (o) { return o.value; })
      .filter(function (o) {
        var name = norm(o.text);
        if (name === query) exact = true;
        return !query || name.indexOf(query) !== -1;
      })
      .slice(0, 8)
      .map(function (o) { return { value: o.value, label: o.text.trim() }; });
    if (typed && !exact) rows.push({ create: true, label: "+ ثبت «" + typed + "» به‌عنوان مشتری جدید" });
    list.textContent = "";
    rows.forEach(function (row, i) {
      var li = document.createElement("li");
      li.id = "cust-combo-opt-" + i;
      li.setAttribute("role", "option");
      li.dataset.i = String(i);
      li.textContent = row.label;
      if (row.create) li.className = "cust-combo__new";
      list.appendChild(li);
    });
    active = rows.length ? 0 : -1; // Enter always does the obvious thing
    list.hidden = !rows.length;
    input.setAttribute("aria-expanded", String(!!rows.length));
    mark();
  }

  // The quick form is replaced by a "saved" note after one customer; bring the form back when
  // another one is needed on the same invoice.
  function ensureQuickForm(details) {
    if (details.querySelector('input[name="name"]') || !pristineForm) return;
    var current = details.querySelector(".quick-party");
    if (!current) return;
    var fresh = pristineForm.cloneNode(true);
    current.replaceWith(fresh);
    if (window.htmx) window.htmx.process(fresh);
  }

  function choose(i) {
    var row = rows[i];
    if (!row) return;
    close();
    if (row.create) {
      var details = disclosure();
      if (!details) return;
      details.open = true;
      ensureQuickForm(details);
      var name = details.querySelector('input[name="name"]');
      var phone = details.querySelector('input[name="phone"]');
      if (!name) return;
      var typed = input.value.trim();
      // Only digits typed: that was a phone number, not a name.
      if (phone && /^[\d۰-۹٠-٩\s+\-]{6,}$/.test(typed)) {
        phone.value = typed;
        name.value = "";
        name.focus();
      } else {
        name.value = typed;
        (phone || name).focus(); // Enter in the phone box submits through htmx
      }
      return;
    }
    var sel = select();
    sel.value = row.value;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    input.value = row.label;
    toProducts();
  }

  function onKey(event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (list.hidden) render();
      if (!rows.length) return;
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length;
      mark();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (!list.hidden && active > -1) choose(active);
      else toProducts();
    } else if (event.key === "Escape") {
      close();
    }
  }

  function build() {
    var sel = select();
    if (!sel || input) return;
    var field = sel.closest(".field");
    if (!field) return;

    var details = disclosure();
    var form = details && details.querySelector("form.quick-party");
    if (form) pristineForm = form.cloneNode(true);

    var wrap = document.createElement("div");
    wrap.className = "cust-combo";
    input = document.createElement("input");
    input.type = "text";
    input.className = "field__control";
    input.id = "cust-combo-input";
    input.autocomplete = "off";
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", "cust-combo-list");
    input.setAttribute("aria-autocomplete", "list");
    input.placeholder = "نام مشتری را بنویسید؛ اگر نبود، Enter = ثبت مشتری جدید";
    list = document.createElement("ul");
    list.className = "cust-combo__list";
    list.id = "cust-combo-list";
    list.setAttribute("role", "listbox");
    list.hidden = true;
    wrap.appendChild(input);
    wrap.appendChild(list);
    sel.insertAdjacentElement("afterend", wrap);

    var label = field.querySelector("label");
    if (label) label.htmlFor = "cust-combo-input";
    fold(sel);
    input.value = selectedText(sel);

    input.addEventListener("input", render);
    input.addEventListener("focus", function () { if (!input.value) render(); else if (!selectedText(select())) render(); });
    input.addEventListener("keydown", onKey);
    input.addEventListener("blur", function () { setTimeout(close, 150); });
    // mousedown, not click: the blur above would close the list before a click lands.
    list.addEventListener("mousedown", function (event) {
      var li = event.target.closest("li");
      if (!li) return;
      event.preventDefault();
      choose(parseInt(li.dataset.i, 10));
    });

    // The quick-create success swaps a NEW <select id="id_customer"> in (out-of-band) with the
    // new customer selected: fold it again, show the name, close the panel, carry on.
    new MutationObserver(function () {
      var fresh = select();
      if (!fresh || fresh.classList.contains("cust-combo__native")) return;
      fold(fresh);
      input.value = selectedText(fresh);
      var open = disclosure();
      if (open) open.removeAttribute("open");
      fresh.dispatchEvent(new Event("change", { bubbles: true }));
      toProducts();
    }).observe(field, { childList: true });

    // A fresh invoice starts at the customer; with one chosen already (?customer=) the product box leads.
    if (!sel.value) input.focus();
  }

  // Opening the manual "+ مشتری جدید" panel puts the cursor in the name box (toggle does not bubble).
  document.addEventListener("toggle", function (event) {
    var details = event.target;
    if (details.matches && details.matches(".quick-party-disclosure") && details.open) {
      var name = details.querySelector('input[name="name"]');
      // A name carried over from the type-ahead is already there: the cursor belongs in the phone box.
      if (name && !name.value) name.focus();
    }
  }, true);

  // Look before you create: similar existing customers while a name is typed in the quick form.
  document.addEventListener("input", function (event) {
    var t = event.target;
    if (!t.matches || !t.matches('.quick-party--compact input[name="name"]')) return;
    var form = t.closest(".quick-party");
    var sel = select();
    if (!form || !sel) return;
    var box = form.querySelector("[data-quick-match]");
    if (!box) {
      box = document.createElement("div");
      box.className = "quick-party__match";
      box.setAttribute("data-quick-match", "");
      box.setAttribute("aria-live", "polite");
      var submit = form.querySelector('button[type="submit"]');
      form.insertBefore(box, submit);
    }
    var query = norm(t.value);
    box.textContent = "";
    box.classList.remove("quick-party__match--exact");
    box.hidden = true;
    if (query.length < 2) return;
    var hits = Array.prototype.filter.call(sel.options, function (o) {
      var name = norm(o.text);
      return o.value && name && (name.indexOf(query) !== -1 || query.indexOf(name) !== -1);
    }).slice(0, 4);
    if (!hits.length) return;
    var exact = hits.some(function (o) { return norm(o.text) === query; });
    box.classList.toggle("quick-party__match--exact", exact);
    box.appendChild(document.createTextNode(exact
      ? "این مشتری از قبل هست؛ انتخابش کنید:"
      : "مشتری مشابه از قبل هست؛ برای انتخاب بزنید:"));
    hits.forEach(function (o) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn--quiet";
      button.textContent = o.text.trim();
      button.addEventListener("click", function () {
        sel.value = o.value;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        if (input) input.value = o.text.trim();
        var details = form.closest("details");
        if (details) details.removeAttribute("open");
        toProducts();
      });
      box.appendChild(button);
    });
    box.hidden = false;
  });

  document.addEventListener("DOMContentLoaded", build);
})();

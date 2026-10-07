/*
 * D-095 phone layer, behaviour that CSS cannot do.
 * Publishes the sticky confirm bar's real height as --dock-h so the undo bar and the toast stack above it
 * instead of overlapping a bar that grows when a warning shows (35 px overlap measured on the sale form).
 */
(function () {
  "use strict";

  var dock = document.querySelector(".sale-form__submit");
  if (dock && "ResizeObserver" in window) {
    var publish = function () {
      document.documentElement.style.setProperty("--dock-h", Math.round(dock.getBoundingClientRect().height) + "px");
    };
    new ResizeObserver(publish).observe(dock);
    publish();
  }

  // On a touchscreen the logout button sits 8 px from the search button, and a half-filled invoice has no draft:
  // real taps at x=70/78 left the page. One question before signing out (touch only; desktop is unchanged).
  var logout = document.querySelector('form[action$="/logout/"]');
  if (logout && window.matchMedia && window.matchMedia("(pointer: coarse)").matches) {
    logout.addEventListener("submit", function (event) {
      if (!window.confirm("از حساب خارج می‌شوید؟")) event.preventDefault();
    });
  }

  // List pages carry 4-6 filter fields (a 654-745 px toolbar on sales/purchasing), so the first row of the list
  // started 1.3 screens down. On a phone the first field (usually the search) stays and the rest fold behind one
  // button; the fold opens by itself when any of them is set, so an active filter is never hidden.
  var phone = window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  if (phone) {
    document.querySelectorAll("form.toolbar .filters").forEach(function (filters) {
      var fields = Array.prototype.filter.call(filters.children, function (el) { return el.classList.contains("field") || el.classList.contains("filters__search") || el.classList.contains("filters__status"); });
      if (fields.length < 2) return;
      var extra = fields.slice(1);
      var apply = filters.querySelector(":scope > .btn:not(.btn--quiet)");
      // "Active" = the address carries a value for one of the folded fields. (A select's rendered value cannot say
      // whether it is the page default or the user's choice, e.g. «فعال» on the customers list.)
      var query = new URLSearchParams(window.location.search);
      var active = extra.filter(function (el) {
        return Array.prototype.some.call(el.querySelectorAll("input, select"), function (c) {
          var sent = c.name && query.getAll(c.name).some(function (v) {
            return v !== "" && v !== "all" && v !== c.dataset.foldDefault; // the page default is not a user filter
          });
          return c.type !== "hidden" && sent;
        });
      }).length;
      extra.forEach(function (el) { el.setAttribute("data-fold", ""); });
      if (apply) apply.setAttribute("data-fold", "");
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "btn btn--quiet filters__toggle";
      toggle.setAttribute("aria-expanded", "false");
      toggle.textContent = "فیلترهای بیشتر" + (active ? " (" + active.toLocaleString("fa-IR") + " فعال)" : "");
      fields[0].insertAdjacentElement("afterend", toggle);
      // Closed even when a filter is applied (an open fold made a filtered list start 1,200 px down); the label
      // counts the active ones and the page's own "clear filters" link stays visible.
      filters.classList.add("is-folded");
      toggle.addEventListener("click", function () {
        var folded = filters.classList.toggle("is-folded");
        toggle.setAttribute("aria-expanded", folded ? "false" : "true");
      });
    });
  }

  // The phone keyboard's Enter key says "search" on a list's search box (it said "return").
  document.querySelectorAll('form.toolbar input[name="q"]').forEach(function (i) { i.setAttribute("enterkeyhint", "search"); });

  // A page title that only repeats the header's title is dropped on phones (the page-head keeps its action buttons).
  if (phone) {
    var headerTitle = document.querySelector(".header__title");
    var h1 = document.querySelector(".content > .page-head h1, .content > .page-head .page-head__row > h1");
    if (headerTitle && h1 && h1.textContent.trim() === headerTitle.textContent.trim()) h1.classList.add("is-dup-title");
  }

  // The expense reason is a free-text box with a history list; empty, it showed only the list's arrow.
  var reason = document.querySelector("#expense-form input[list=expense-reasons]");
  if (phone && reason && !reason.placeholder) reason.placeholder = "مثلاً اجاره، حقوق، قبض…";


  // ---- Round 3: live amount echo under money fields, and a find-a-party box on long dues pages -----------------------
  // A 7-digit amount typed on a phone keyboard cannot be proofread ("1250000"); the field shows the grouped figure under it.
  // Only fields that hold Toman are echoed (counts, percentages and dates are not), and desktop never gets the element.
  var MONEY = /(^|[-_])(amount|amount_min|amount_max|default_selling_price|wholesale_selling_price|retail_carton_price|wholesale_pack_price|unit_price|carton_price|freight|opening_balance|credit_limit)$/;
  var groupFa = new Intl.NumberFormat("fa-IR");
  function echoFor(input) {
    var next = input.nextElementSibling;
    if (next && next.classList.contains("amount-echo")) return next;
    if (input.closest(".field") && input.closest(".field").querySelector(":scope > .amount-echo")) return input.closest(".field").querySelector(":scope > .amount-echo");
    return null;
  }
  function isMoney(input) {
    return input.matches('input[inputmode="numeric"]:not(.js-jalali-date)') && MONEY.test(input.name || "")
      && !input.closest(".item-row") && !document.getElementById("expense-amount-words");
  }
  function renderEcho(input) {
    if (!isMoney(input)) return;
    var digits = (input.value || "").replace(/[^0-9]/g, "");
    var echo = echoFor(input);
    if (!digits) { if (echo) echo.hidden = true; return; }
    if (!echo) {
      echo = document.createElement("div");
      echo.className = "amount-echo num";
      echo.setAttribute("aria-hidden", "true");   // the field's own value is read aloud; the echo only helps the eye
      input.insertAdjacentElement("afterend", echo);
    }
    echo.textContent = groupFa.format(Number(digits)) + " تومان";
    echo.hidden = false;
  }
  if (phone) {
    document.addEventListener("input", function (e) { if (e.target.matches && e.target.matches("input")) renderEcho(e.target); });
    var primeEchoes = function (root) { (root || document).querySelectorAll('input[inputmode="numeric"]').forEach(function (i) { if (i.value) renderEcho(i); }); };
    primeEchoes(document);
    document.body.addEventListener("htmx:afterSettle", function (e) { primeEchoes(e.target); });
  }

  // Receivables / payables: with 20+ customers the party list is a long scroll. A box filters the cards on screen (names,
  // phones, invoice numbers); the totals stay the whole truth, and the box says so.
  var dues = document.getElementById("dues-parties");
  if (phone && dues) {
    var rowsAll = function () { return Array.prototype.slice.call(document.querySelectorAll(".content .data-table tbody tr:not([data-card-skip])")); };
    if (rowsAll().length >= 6) {
      var fold = function (t) {
        return t.replace(/[۰-۹]/g, function (c) { return String(c.charCodeAt(0) - 1776); })
          .replace(/[٠-٩]/g, function (c) { return String(c.charCodeAt(0) - 1632); })
          .replace(/ك/g, "ک").replace(/ي/g, "ی").replace(/\s+/g, " ").trim().toLowerCase();
      };
      var box = document.createElement("div");
      box.className = "dues-find";
      box.innerHTML = '<input type="search" class="field__control" inputmode="search" enterkeyhint="search" autocomplete="off" aria-label="یافتن در این صفحه" placeholder="یافتن نام، تلفن یا شمارهٔ فاکتور"><p class="field__hint" role="status"></p>';
      var field = box.querySelector("input"), status = box.querySelector("p");
      var card = dues.closest(".card");
      card.parentNode.insertBefore(box, card);
      field.addEventListener("input", function () {
        var q = fold(field.value), shown = 0, all = rowsAll();
        all.forEach(function (tr) {
          var hit = !q || fold(tr.textContent).indexOf(q) !== -1;
          tr.hidden = !hit;
          if (hit) shown++;
        });
        status.textContent = q ? shown.toLocaleString("fa-IR") + " مورد از " + all.length.toLocaleString("fa-IR") + " · فقط نمایش فیلتر شده؛ جمع‌ها کل صفحه‌اند." : "";
      });
    }
  }

  // A save redirects to an anchor (e.g. #selling-price) and the browser scrolls past the success message at the top,
  // so a successful save looked like nothing happened. If the message ended up above the screen, bring it back.
  if (phone) {
    window.addEventListener("load", function () {
      window.requestAnimationFrame(function () {
        var message = document.querySelector(".messages .message, .messages [role=status], .messages [role=alert]");
        if (message && message.getBoundingClientRect().bottom < 0) message.scrollIntoView({ block: "center" });
      });
    });
  }

  // After a search or a period button the page reloads at the top of a 300-700 px toolbar; the answer is the list, so
  // bring its card to the top (unless the address already points at an anchor).
  if (phone && !window.location.hash) {
    var applied = false;
    new URLSearchParams(window.location.search).forEach(function (value, key) {
      if (value !== "" && key !== "page" && key !== "sort" && key !== "dir") applied = true;
    });
    var results = document.querySelector("form.toolbar ~ .table-card, form.toolbar ~ .placeholder, form.toolbar ~ .empty-state, form.toolbar ~ p.field__hint");
    if (applied && results) window.requestAnimationFrame(function () { results.scrollIntoView({ block: "start" }); });
  }

  // A half-entered invoice has no draft: the header's back control (an edge-swipe's neighbour) asked nothing.
  var back = document.querySelector(".header__back");
  if (phone && back && document.querySelector("#sale-form, #purchase-form")) {
    back.addEventListener("click", function (event) {
      var picked = Array.prototype.some.call(document.querySelectorAll('input[name$="-product"]'), function (i) { return i.value; });
      if (picked && !window.confirm("فاکتور هنوز ثبت نشده است. از این صفحه خارج می‌شوید؟")) event.preventDefault();
    });
  }
})();

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
      var fields = Array.prototype.filter.call(filters.children, function (el) { return el.classList.contains("field"); });
      if (fields.length < 3) return;
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
    var results = document.querySelector("form.toolbar ~ .table-card");
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

/* Receivables, Payables and the cheque page: the live parts of "ثبت پرداخت", the
   named confirmations for cheque actions, and deep links that open a row's form.
   Everything is delegated from `document`, so it keeps working after htmx swaps a
   form back in; without this file every form still works as a plain form. */
(function () {
  "use strict";

  // Hooks that only make sense once this script runs (chips, ...) stay hidden until now.
  document.documentElement.classList.add("pay-js");

  var FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

  function toInt(text) {
    var ascii = String(text || "").replace(/[۰-۹]/g, function (d) { return FA_DIGITS.indexOf(d); })
      .replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); })
      .replace(/[^\d]/g, "");
    return parseInt(ascii, 10) || 0;
  }

  // "۸۱۰٬۰۰۰", the same look as the server's `toman` filter.
  function fmt(n) {
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, "٬")
      .replace(/\d/g, function (d) { return FA_DIGITS[d]; });
  }

  /* ------------------------------------------------------------------ pay form */

  function payRows(form) { return [].slice.call(form.querySelectorAll(".invoice-picker__row")); }
  function rowBox(row) { return row.querySelector("input[type=checkbox]"); }
  function rowDue(row) { return toInt(row.getAttribute("data-outstanding")); }
  function amountInput(form) { return form.querySelector('[name="amount"]'); }

  function sumOf(rows) {
    return rows.reduce(function (sum, row) { return sum + rowDue(row); }, 0);
  }

  // Tick the oldest invoices (DOM order = the order the server allocates in) the amount covers.
  // More than all of them owe is a prepayment: nothing ticked, the server books it unallocated.
  function allocate(form) {
    var rows = payRows(form);
    var left = toInt(amountInput(form).value);
    var over = left > sumOf(rows);
    rows.forEach(function (row) {
      rowBox(row).checked = !over && left > 0;
      left -= rowDue(row);
    });
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function renderPay(form) {
    var input = amountInput(form);
    var summary = form.querySelector("[data-pay-summary]");
    var submit = form.querySelector("[data-pay-submit]");
    if (!input || !summary || !submit) return;

    var rows = payRows(form);
    var ticked = rows.filter(function (row) { return rowBox(row).checked; });
    var amount = toInt(input.value);
    var tickedDue = sumOf(ticked);
    var verb = form.getAttribute("data-verb") || "پرداخت";
    var prep = verb === "دریافت" ? "از" : "به";
    var party = form.getAttribute("data-party");

    summary.textContent = "";
    summary.className = "pay-summary";
    var blocked = false;

    var creditBox = form.querySelector('input[name="as_credit"]');
    var asCredit = !!(creditBox && creditBox.checked);
    var creditWord = verb === "دریافت" ? "بستانکاری (پیش‌دریافت)" : "پیش‌پرداخت";

    if (amount > 0 && (!rows.length || !ticked.length)) {
      // Nothing ticked: the server settles the open invoices oldest first (D-087);
      // only what is left beyond all of them may stay as credit, and only on purpose.
      var leftAll = amount;
      var listAll = el("ul", "pay-summary__list");
      rows.forEach(function (row) {
        var due = rowDue(row);
        var take = Math.min(due, leftAll);
        leftAll -= take;
        if (take > 0) listAll.appendChild(el("li", "", "فاکتور " + row.getAttribute("data-name") + ": " + fmt(take) + " تومان" +
          (take === due ? " (تسویهٔ کامل)" : " (بخشی؛ " + fmt(due - take) + " می‌ماند)")));
      });
      if (rows.length) {
        summary.appendChild(el("p", "pay-summary__head", "تخصیص خودکار از قدیمی‌ترین فاکتور:"));
        summary.appendChild(listAll);
      }
      if (leftAll > 0 && !asCredit) {
        blocked = true;
        summary.classList.add("is-bad");
        summary.appendChild(el("p", "pay-summary__head", fmt(leftAll) + " تومان بیشتر از کل بدهی باز است. اگر " + creditWord +
          " است، گزینهٔ «مازاد به‌عنوان " + creditWord + " ثبت شود» را تیک بزنید."));
      } else if (leftAll > 0) {
        summary.classList.add("is-note");
        summary.appendChild(el("p", "pay-summary__head", fmt(leftAll) + " تومان به‌عنوان " + creditWord +
          " به نام «" + party + "» می‌ماند و از فاکتور بعدی او خودکار کسر می‌شود."));
      } else {
        summary.classList.add("is-ok");
      }
    } else if (rows.length && amount > 0) {
      if (amount > tickedDue) {
        blocked = true;
        summary.classList.add("is-bad");
        summary.appendChild(el("p", "pay-summary__head",
          "مبلغ " + fmt(amount - tickedDue) + " تومان از باقیماندهٔ فاکتورهای انتخاب‌شده (" + fmt(tickedDue) + ") بیشتر است."));
      } else {
        var left = amount;
        var list = el("ul", "pay-summary__list");
        var allClosed = true;
        ticked.forEach(function (row) {
          var due = rowDue(row);
          var take = Math.min(due, left);
          left -= take;
          if (take <= 0) return;
          var full = take === due;
          if (!full) allClosed = false;
          list.appendChild(el("li", "", "فاکتور " + row.getAttribute("data-name") + ": " + fmt(take) + " تومان " +
            (full ? "(تسویهٔ کامل)" : "(بخشی؛ " + fmt(due - take) + " می‌ماند)")));
        });
        summary.classList.add(allClosed ? "is-ok" : "is-note");
        summary.appendChild(el("p", "pay-summary__head", "تخصیص از قدیمی‌ترین فاکتور:"));
        summary.appendChild(list);
      }
    }

    submit.textContent = amount > 0
      ? "ثبت " + verb + " " + fmt(amount) + " تومان" + (party ? " " + prep + " «" + party + "»" : "")
      : "ثبت پرداخت";
    submit.disabled = blocked;
  }

  // A form we have not seen yet: a re-rendered one (after an error) keeps what was typed.
  function initPay(form) {
    if (form.getAttribute("data-pay-ready")) return;
    form.setAttribute("data-pay-ready", "1");
    var input = amountInput(form);
    var anyTicked = payRows(form).some(function (row) { return rowBox(row).checked; });
    form.setAttribute("data-touched", input && input.value ? "1" : "");
    form.setAttribute("data-manual", anyTicked ? "1" : "");
  }

  function payForms(root) {
    return [].slice.call((root || document).querySelectorAll("form[data-pay-form]"));
  }

  document.addEventListener("input", function (e) {
    var form = e.target.closest && e.target.closest("form[data-pay-form]");
    if (!form || e.target.name !== "amount") return;
    initPay(form);
    // Typing is the owner's own figure: from here ticks no longer rewrite it.
    form.setAttribute("data-touched", e.target.value ? "1" : "");
    if (!form.getAttribute("data-manual")) allocate(form);
    renderPay(form);
  });

  document.addEventListener("change", function (e) {
    var form = e.target.closest && e.target.closest("form[data-pay-form]");
    if (form && e.target.name === "as_credit") { renderPay(form); return; }
    if (!form || !e.target.matches || !e.target.matches(".invoice-picker input[type=checkbox]")) return;
    initPay(form);
    // A manual tick means "I know better": stop re-allocating automatically.
    form.setAttribute("data-manual", "1");
    if (!form.getAttribute("data-touched")) {
      var due = sumOf(payRows(form).filter(function (row) { return rowBox(row).checked; }));
      amountInput(form).value = due ? String(due) : "";
    }
    renderPay(form);
  });

  document.addEventListener("click", function (e) {
    var button = e.target.closest && e.target.closest("[data-pay-total], [data-pay-oldest]");
    if (!button) return;
    var form = button.closest("form[data-pay-form]");
    if (!form) return;
    initPay(form);
    form.setAttribute("data-manual", "");
    var input = amountInput(form);
    if (button.hasAttribute("data-pay-total")) {
      input.value = String(sumOf(payRows(form)));
      form.setAttribute("data-touched", input.value === "0" ? "" : "1");
    } else if (!toInt(input.value)) {
      input.focus();
      return;
    }
    allocate(form);
    renderPay(form);
  });

  // Opening a disclosure lands the cursor in the amount box (the form is usually a single number).
  document.addEventListener("toggle", function (e) {
    var box = e.target;
    if (!box.matches || !box.matches("details.quick-party-disclosure") || !box.open) return;
    var form = box.querySelector("form[data-pay-form]");
    if (!form) return;
    initPay(form);
    renderPay(form);
    var input = amountInput(form);
    if (input) { input.focus(); input.select(); }
  }, true);

  /* --------------------------------------------------------------- cheque clear */

  // One plain sentence naming the consequence; "{bank}" is filled with the chosen account.
  function clearSelect(form) { return form.querySelector("select"); }

  function clearSentence(form) {
    var select = clearSelect(form);
    var option = select && select.selectedOptions && select.selectedOptions[0];
    if (!option || !option.value) return "";
    return (form.getAttribute("data-sentence") || "").replace("{bank}", option.textContent.trim());
  }

  function renderClear(form) {
    var sentence = clearSentence(form);
    var submit = form.querySelector("[data-clear-submit]");
    var note = form.querySelector("[data-clear-sentence]");
    var label = form.querySelector("[data-clear-account-label]");
    var select = clearSelect(form);
    var option = select && select.selectedOptions && select.selectedOptions[0];
    if (label) label.textContent = option && option.value ? "حساب: " + option.textContent.trim() : "انتخاب حساب";
    if (note) {
      note.textContent = sentence || "برای ادامه، حساب جاری را انتخاب کنید.";
      note.classList.toggle("is-pending", !sentence);
    }
    if (submit) {
      submit.disabled = !sentence;
      if (sentence) submit.setAttribute("title", sentence); else submit.removeAttribute("title");
    }
  }

  document.addEventListener("change", function (e) {
    var form = e.target.closest && e.target.closest("form[data-clear-form]");
    if (form) renderClear(form);
  });

  /* ------------------------------------------------------------- confirmations */

  // The text lives in an (escaped) data attribute, so a party name with a quote cannot break it.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || !form.getAttribute) return;
    var message;
    if (form.hasAttribute("data-clear-form")) {
      message = clearSentence(form);
      if (!message) { e.preventDefault(); return; }
      message += "\nتأیید می‌کنید؟";
    } else {
      message = form.getAttribute("data-confirm");
    }
    if (message && !window.confirm(message)) e.preventDefault();
  }, true);

  /* ----------------------------------------------------------------- deep links */

  // /receivables/#inv-<id>, #chq-<id>, #party-<id>: open that row's form and focus what to do next.
  function openFromHash() {
    var id = location.hash.slice(1);
    if (!id) return;
    try { id = decodeURIComponent(id); } catch (err) { /* keep the raw hash */ }
    var row = document.getElementById(id);
    if (!row || row.tagName !== "TR") return;
    var disclosure = row.querySelector("details.quick-party-disclosure");
    if (disclosure) disclosure.open = true;
    row.scrollIntoView({ block: "center" });

    var scope = disclosure || row;
    var target;
    if (id.indexOf("party-") === 0) {
      target = scope.querySelector('input[name="amount"]');
    } else {
      var empty = [].slice.call(scope.querySelectorAll("select")).filter(function (s) { return !s.value; })[0];
      target = empty || scope.querySelector("[data-clear-submit]:not(:disabled), button[type=submit]:not(:disabled)");
    }
    if (target) target.focus({ preventScroll: true });
  }

  /* ------------------------------------------------------------------ start up */

  function start() {
    payForms().forEach(function (form) { initPay(form); renderPay(form); });
    [].slice.call(document.querySelectorAll("form[data-clear-form]")).forEach(renderClear);
    openFromHash();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
  window.addEventListener("hashchange", openFromHash);
  // The browser's own jump to the #fragment runs after load and drops focus; ask again once it is done.
  if (document.readyState !== "complete") {
    window.addEventListener("load", function () {
      setTimeout(openFromHash, 0);
      setTimeout(openFromHash, 200);
    });
  }

  // A form htmx swapped back in (validation errors): the new nodes need their summary.
  function refreshSwapped(e) {
    var root = e.target;
    if (!root || !root.querySelectorAll) return;
    var forms = payForms(root);
    if (root.matches && root.matches("form[data-pay-form]")) forms.push(root);
    forms.forEach(function (form) { initPay(form); renderPay(form); });
  }
  document.addEventListener("htmx:afterSwap", refreshSwapped);
  document.addEventListener("htmx:load", refreshSwapped);
})();

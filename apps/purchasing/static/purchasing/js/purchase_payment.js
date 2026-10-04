/*
 * Purchase-only helpers on top of the shared "پرداخت" card (D-069). The card
 * and invoice_payment.js stay as they are (they own the credit due-date terms);
 * this file adds, for purchases only:
 *  - one sentence on the submit bar saying what the click does to the
 *    supplier's balance, so the owner confirms with the consequence in view;
 *  - a "+ پرداخت با چک" shortcut: a cheque row with method, account, issuer
 *    and next cheque number pre-filled, due-date chips and a one-line summary.
 * Presentation only: every value stays visible and editable, nothing is posted
 * beyond the form's own fields, and the server re-validates everything.
 * localStorage is a convenience and may be blocked.
 */
(function () {
  "use strict";

  // ---- small helpers ------------------------------------------------------
  function toAscii(text) {
    return String(text || "")
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06f0); })
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); });
  }

  function fa(value) {
    return String(value).replace(/[0-9]/g, function (d) { return String.fromCharCode(0x06f0 + Number(d)); });
  }

  function toman(value) {
    var n = Math.max(0, Math.round(value || 0));
    return fa(n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, "٬"));
  }

  function readInt(text) {
    return parseInt(toAscii(text).replace(/[^0-9]/g, ""), 10) || 0;
  }

  function field(name) {
    return document.getElementById("id_" + name);
  }

  function shownTotal(id) {
    var el = document.getElementById(id);
    return el ? readInt(el.textContent) : 0;
  }

  function store(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, value);
    } catch (e) { /* storage blocked: the shortcuts just stay empty */ }
    return null;
  }

  // Jalali day numbers come from invoice_payment.js (window.PaperJalali); without it the chips just stay inert.
  function jalali() {
    return window.PaperJalali || null;
  }

  // The invoice date as a day number, today when the box is empty or not a date yet.
  function baseJdn() {
    var j = jalali();
    var box = field("invoice_date");
    var parsed = j && box ? j.parseJdn(box.value) : null;
    return parsed !== null && parsed !== undefined ? parsed : (j ? j.todayJdn() : null);
  }

  function supplierName() {
    var sel = field("supplier");
    if (!sel || !sel.value || sel.selectedIndex < 0) return "";
    return sel.options[sel.selectedIndex].text.trim();
  }

  function paymentMode() {
    var checked = document.querySelector('input[name="payment_mode"]:checked');
    return checked ? checked.value : "full";
  }

  // ---- the consequence line on the submit bar -----------------------------
  function consequence() {
    var total = shownTotal("sale-total");
    var remaining = shownTotal("sale-remaining");
    var name = supplierName();
    var who = name ? "«" + name + "»" : "تأمین‌کننده";
    if (!total) return "";
    if (paymentMode() !== "split") {
      return "با ثبت، کل " + toman(total) + " تومان پرداخت‌شده ثبت می‌شود و بدهی‌ای برای " + who + " نمی‌ماند.";
    }
    if (remaining > 0) {
      var due = field("credit_due_date");
      var dueText = due && due.value.trim() ? " سررسید: " + due.value.trim() + "." : " (تاریخ سررسید نسیه هنوز وارد نشده)";
      return "با ثبت، " + toman(remaining) + " تومان نسیه می‌شود و به بدهی شما به " + who + " اضافه می‌شود." + dueText;
    }
    return "با ثبت، همهٔ مبلغ با ردیف‌های پرداخت تسویه می‌شود و نسیه‌ای نمی‌ماند.";
  }

  function renderConsequence() {
    var bar = document.getElementById("submit-consequence");
    if (bar) bar.textContent = consequence();
  }

  // ---- cheque rows --------------------------------------------------------
  function paymentRows() {
    return Array.prototype.slice.call(document.querySelectorAll("#payment-rows [data-payment-row]"));
  }

  function rowEl(row, suffix) {
    return row.querySelector('[name$="-' + suffix + '"]');
  }

  function isCheque(row) {
    var method = rowEl(row, "method");
    return !!method && method.value === "cheque";
  }

  function usableAccounts(select) {
    return Array.prototype.filter.call(select.options, function (o) { return o.value && !o.disabled; });
  }

  // "چک ۵٬۰۰۰٬۰۰۰ تومانی با سررسید ... از «حساب» به «تأمین‌کننده» ثبت می‌شود."
  function renderCheque(row) {
    var note = row.querySelector("[data-cheque-summary]");
    if (!note) return;
    var j = jalali();
    var due = rowEl(row, "due_date");
    var dueJdn = j && due ? j.parseJdn(due.value) : null;
    var base = baseJdn();
    var days = dueJdn !== null && dueJdn !== undefined && base !== null ? dueJdn - base : null;
    row.querySelectorAll("[data-cheque-due-days]").forEach(function (chip) {
      chip.setAttribute("aria-pressed", String(days !== null && Number(chip.dataset.chequeDueDays) === days));
    });
    if (!isCheque(row)) {
      note.textContent = "";
      return;
    }
    var amountBox = rowEl(row, "amount");
    var amount = amountBox ? readInt(amountBox.value) : 0;
    var account = rowEl(row, "bank_account");
    var accountName = account && account.value ? account.options[account.selectedIndex].text.trim() : "";
    var number = rowEl(row, "cheque_number");
    var name = supplierName();

    var text = "چک " + (amount ? toman(amount) + " تومانی" : "") +
      (days !== null ? " با سررسید " + j.format(dueJdn) +
        " (" + (days >= 0 ? fa(days) + " روز بعد از تاریخ فاکتور" : "قبل از تاریخ فاکتور!") + ")" : "") +
      (accountName ? " از «" + accountName + "»" : "") + " به " + (name ? "«" + name + "»" : "تأمین‌کننده") + " ثبت می‌شود.";
    if (!accountName) text += " حساب بانکی را انتخاب کنید.";
    var later = [];
    if (!(number && number.value.trim())) later.push("شمارهٔ چک");
    if (days === null) later.push("تاریخ سررسید");
    if (later.length) text += " هنوز مانده: " + later.join("، ") + " (می‌توانید بعداً در «تکمیل مشخصات» چک هم وارد کنید).";
    note.textContent = text;
  }

  // Issuer = the account's owner; bank = what was typed last time for this account. Never overwrites typing.
  function setAuto(row, suffix, value) {
    var input = rowEl(row, suffix);
    if (!input || !value) return;
    if (!input.value || input.value === input.dataset.auto) {
      input.value = value;
      input.dataset.auto = value;
    }
  }

  function autofillCheque(row) {
    if (!isCheque(row)) return;
    var account = rowEl(row, "bank_account");
    if (!account) return;
    var opt = account.options[account.selectedIndex];
    setAuto(row, "issuer", opt && opt.dataset.owner);
    if (account.value) setAuto(row, "bank_name", store("pp.cheque.bank." + account.value));
  }

  function lastChequeNumber(exceptRow) {
    var found = "";
    paymentRows().forEach(function (row) {
      if (row === exceptRow || !isCheque(row)) return;
      var n = rowEl(row, "cheque_number");
      if (n && /^\d+$/.test(toAscii(n.value).trim())) found = toAscii(n.value).trim();
    });
    return found;
  }

  function startCheque() {
    var add = document.getElementById("add-payment-row");
    if (!add) return;
    var before = paymentRows().length;
    add.click(); // switches to split mode and adds a row whose amount is the unpaid remainder
    // After invoice_payment.js filtered the new row's accounts (same 0 ms queue, FIFO).
    setTimeout(function () {
      var rows = paymentRows();
      if (rows.length <= before) return;
      var row = rows[rows.length - 1];
      var method = rowEl(row, "method");
      if (!method) return;
      method.value = "cheque";
      method.dispatchEvent(new Event("change", { bubbles: true })); // shows the cheque block, filters accounts
      var account = rowEl(row, "bank_account");
      if (account && !account.value) {
        var usable = usableAccounts(account);
        var last = store("pp.cheque.account");
        var pick = usable.length === 1 ? usable[0] : usable.filter(function (o) { return o.value === last; })[0];
        if (pick) account.value = pick.value;
      }
      autofillCheque(row);
      var prev = lastChequeNumber(row);
      var numberBox = rowEl(row, "cheque_number");
      if (prev && numberBox && !numberBox.value) {
        var next = String(parseInt(prev, 10) + 1);
        numberBox.value = new Array(Math.max(prev.length - next.length, 0) + 1).join("0") + next;
      }
      renderCheque(row);
      // Not the date box: focusing it would open the picker over everything.
      if (numberBox) numberBox.focus({ preventScroll: true });
      row.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 0);
  }

  // The shared card is not ours to edit: the shortcut buttons are added next to its own controls.
  function ensureChequeButtons() {
    var fullHint = document.querySelector('[data-payment-panel="full"] > .field__hint');
    if (fullHint && !document.querySelector('[data-payment-panel="full"] [data-start-cheque]')) {
      var quick = document.createElement("div");
      quick.className = "pur-cheque-quick";
      quick.innerHTML = '<button type="button" class="btn btn--quiet" data-start-cheque>+ پرداخت با چک</button>' +
        '<span class="field__hint">ردیف چک با حساب، صادرکننده و شمارهٔ بعدی پر می‌شود؛ فقط سررسید را بزنید.</span>';
      fullHint.insertAdjacentElement("afterend", quick);
    }
    var add = document.getElementById("add-payment-row");
    if (add && !add.parentNode.querySelector("[data-start-cheque]")) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn--quiet";
      button.setAttribute("data-start-cheque", "");
      button.textContent = "+ ردیف چک (پیش‌پر)";
      add.insertAdjacentElement("afterend", button);
    }
  }

  function renderAll() {
    renderConsequence();
    paymentRows().forEach(renderCheque);
  }

  // ---- events -------------------------------------------------------------
  document.addEventListener("click", function (event) {
    var t = event.target;
    if (!t.closest) return;
    var chip = t.closest("[data-cheque-due-days]");
    if (chip) {
      var row = chip.closest("[data-payment-row]");
      var due = row && rowEl(row, "due_date");
      var j = jalali();
      var base = baseJdn();
      if (due && j && base !== null) {
        due.value = j.format(base + Number(chip.dataset.chequeDueDays));
        // The picker commits with "change"; do the same so every listener sees a date change.
        due.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return;
    }
    if (t.closest("[data-start-cheque]")) {
      startCheque();
      return;
    }
    // The shared card's term chips write the date without an event; the bar sentence follows.
    if (t.closest("[data-due-term]") || t.closest("[data-credit-all]")) renderAll();
  });

  document.addEventListener("invoice:recomputed", renderAll);

  document.addEventListener("input", function (event) {
    var t = event.target;
    if (t.id === "id_credit_due_date" || t.id === "id_invoice_date") renderAll();
    var row = t.closest && t.closest("[data-payment-row]");
    if (row) renderCheque(row);
  });

  document.addEventListener("change", function (event) {
    var t = event.target;
    var row = t.closest && t.closest("[data-payment-row]");
    if (row) {
      if (t.matches('select[name$="-method"]')) autofillCheque(row); // after the shared script filtered the accounts
      if (t.matches('select[name$="-bank_account"]')) {
        if (t.value && isCheque(row)) store("pp.cheque.account", t.value);
        autofillCheque(row);
      }
      if (t.matches('input[name$="-bank_name"]') && t.value.trim()) {
        var acc = rowEl(row, "bank_account");
        if (acc && acc.value) store("pp.cheque.bank." + acc.value, t.value.trim());
      }
    }
    renderAll();
  });

  window.addEventListener("pageshow", renderAll);

  document.addEventListener("DOMContentLoaded", function () {
    ensureChequeButtons();
    renderAll();
  });
})();

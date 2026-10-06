/*
 * New-expense form (D-072): show only the fields of the chosen payment method
 * (bank transfer / cheque / credit). Presentation only -- the server form
 * validates what each method needs.
 */
(function () {
  "use strict";

  function currentMethod() {
    var checked = document.querySelector('#expense-form input[name="payment_method"]:checked');
    return checked ? checked.value : "transfer";
  }

  var FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

  function $(id) { return document.getElementById(id); }
  function field(name) {
    var form = $("expense-form");
    return form ? form.elements[name] || null : null;
  }
  function val(name) {
    var el = field(name);
    return el && el.value ? String(el.value).trim() : "";
  }

  function toInt(text) {
    var ascii = String(text || "").replace(/[۰-۹]/g, function (d) { return FA_DIGITS.indexOf(d); })
      .replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); })
      .replace(/[^\d]/g, "");
    return parseInt(ascii, 10) || 0;
  }

  // "۴٬۵۰۰٬۰۰۰", the same look as the server's `toman` filter; a minus stays on the left of its digits.
  function fmt(n) {
    var text = String(Math.abs(Math.round(n))).replace(/\B(?=(\d{3})+(?!\d))/g, "٬")
      .replace(/\d/g, function (d) { return FA_DIGITS[d]; });
    return n < 0 ? "⁦-" + text + "⁩" : text;
  }

  // Server-provided hints (json_script): per-account name/balance/cheque hints and past-expense presets.
  function data() {
    var node = $("expense-data");
    if (!node) return { accounts: {}, presets: [] };
    try { return JSON.parse(node.textContent); } catch (e) { return { accounts: {}, presets: [] }; }
  }

  /* ---- cheque: the account already tells who signs it, which bank, and the next leaf (E051) */
  var AUTOFILL = [["issuer", "owner"], ["bank_name", "bank"], ["cheque_number", "next"]];

  function fillFromAccount() {
    var select = field("bank_account");
    var info = select && select.value ? data().accounts[select.value] : null;
    if (!info) return;
    var filled = false;
    AUTOFILL.forEach(function (pair) {
      var input = field(pair[0]);
      var value = info[pair[1]] || "";
      if (!input) return;
      // Only touch what we wrote ourselves, never what the owner typed.
      if (!input.value || input.dataset.autofilled === input.value) {
        input.value = value;
        input.dataset.autofilled = value;
        if (value) filled = true;
      }
    });
    var note = $("expense-autofill-note");
    if (note) note.hidden = !filled;
  }

  /* ---- live "what will happen" sentence (E050): read-only, the server still validates */
  function render() {
    var box = $("expense-preview");
    if (!box) return;
    var line = $("expense-preview-line");
    var sub = $("expense-preview-sub");
    var words = $("expense-amount-words");
    var amount = toInt(val("amount"));
    if (words) words.textContent = amount ? fmt(amount) + " تومان" : "";
    box.classList.remove("exb-preview--warn");
    if (!amount) { box.hidden = true; return; }

    var method = currentMethod();
    var money = fmt(amount) + " تومان";
    var why = val("reason");
    var select = field("bank_account");
    var info = select && select.value ? data().accounts[select.value] : null;
    var text = "";
    var detail = "";

    if (method === "transfer") {
      if (!info) {
        text = money + " از حساب جاری پرداخت می‌شود؛ حساب را انتخاب کنید.";
      } else {
        text = money + " از «" + info.name + "» کم می‌شود" + (why ? " بابت «" + why + "»" : "") + ".";
        detail = "موجودی حساب: " + fmt(info.balance) + " ← " + fmt(info.balance - amount) + " تومان";
        if (info.balance - amount < 0) {
          box.classList.add("exb-preview--warn");
          detail += " (موجودی منفی می‌شود؛ مبلغ و حساب را بررسی کنید)";
        }
      }
    } else if (method === "cheque") {
      text = "چکی به مبلغ " + money + " «در انتظار وصول» ثبت می‌شود؛ تا پاس‌شدن چیزی از حساب کم نمی‌شود.";
      detail = val("cheque_due_date") ? "سررسید چک: " + val("cheque_due_date") : "سررسید چک را وارد کنید.";
    } else {
      text = money + " به‌عنوان بدهی نسیه ثبت می‌شود؛ پولی خارج نمی‌شود.";
      detail = val("due_date") ? "تا " + val("due_date") + " یادآوری می‌گیرید." : "سررسید پرداخت را وارد کنید.";
    }

    // Settling a fixed cost: say how far from the usual amount and where the reminder moves.
    var banner = document.querySelector(".exb-settle");
    if (banner) {
      var usual = parseInt(banner.getAttribute("data-usual"), 10) || 0;
      if (usual && amount !== usual) {
        detail += (detail ? " · " : "") + fmt(Math.abs(amount - usual)) + " تومان " + (amount > usual ? "بیشتر" : "کمتر") + " از مبلغ معمول";
      }
      var next = banner.getAttribute("data-next-due");
      if (next) detail += (detail ? " · " : "") + "سررسید بعدی به " + next + " می‌رود.";
    }

    line.textContent = text;
    sub.textContent = detail;
    box.hidden = false;
  }

  function sync() {
    var method = currentMethod();
    document.querySelectorAll("[data-expense-panel]").forEach(function (panel) {
      panel.hidden = panel.dataset.expensePanel.split(" ").indexOf(method) === -1;
    });
    if (method === "cheque") fillFromAccount();
    render();
  }

  /* ---- reason -> last amount / method / account (E049) */
  function applyPreset(reason) {
    var preset = null;
    data().presets.forEach(function (p) { if (p.reason === reason.trim()) preset = p; });
    var amount = field("amount");
    // Never overwrite what the owner already typed.
    if (!preset || !amount || amount.value) return;
    amount.value = preset.amount;
    var radio = document.querySelector('#expense-form input[name="payment_method"][value="' + preset.method + '"]');
    if (radio) radio.checked = true;
    var select = field("bank_account");
    if (preset.account && select && !select.dataset.touched) {
      var before = select.value;
      select.value = preset.account;
      if (select.value !== preset.account) select.value = before;  // account no longer offered
    }
    var note = $("expense-preset-note");
    if (note) {
      note.textContent = "مبلغ، روش و حساب از آخرین «" + preset.reason + "» پر شد؛ هرکدام را می‌توانید تغییر دهید.";
      note.hidden = false;
    }
    sync();
    // From a datalist pick or Enter the caret is still on the reason: continue at the amount.
    if (document.activeElement === field("reason")) { amount.focus(); amount.select(); }
  }

  document.addEventListener("change", function (event) {
    var target = event.target;
    if (!target.closest || !target.closest("#expense-form")) return;
    if (target.matches('input[name="payment_method"]')) sync();
    if (target.name === "bank_account") {
      target.dataset.touched = "1";
      if (currentMethod() === "cheque") fillFromAccount();
    }
    if (target.name === "reason") applyPreset(target.value);
    render();
  });

  document.addEventListener("input", function (event) {
    var target = event.target;
    if (!target.closest || !target.closest("#expense-form")) return;
    // A datalist pick fires input (not always change): inputType is replacement text, or absent in Firefox.
    if (target.name === "reason" && (event.inputType === undefined || event.inputType === "insertReplacementText")) {
      applyPreset(target.value);
    }
    render();
  });

  // Due-date shortcut chips fill the Jalali box the same way the picker does (a bubbling change).
  document.addEventListener("click", function (event) {
    var chip = event.target.closest ? event.target.closest(".exb-chip") : null;
    if (!chip) return;
    var box = $(chip.parentNode.getAttribute("data-chip-target"));
    if (!box) return;
    box.value = chip.getAttribute("data-value");
    box.dispatchEvent(new Event("change", { bubbles: true }));
  });

  document.addEventListener("DOMContentLoaded", function () {
    sync();
    var form = $("expense-form");
    if (!form || form.querySelector(".field--invalid")) return;
    // Settling a fixed cost: only the amount may change. Otherwise start at the reason.
    var recurring = form.elements.recurring;
    var target = recurring && recurring.value ? field("amount") : field("reason");
    // A touch screen would open the keyboard (and cover the form) before anything was read.
    var touch = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
    if (touch && !(recurring && recurring.value)) return;
    if (target) { target.focus(); if (recurring && recurring.value) target.select(); }
  });
})();

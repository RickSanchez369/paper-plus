/*
 * Payment behaviour shared by the new-sale and new-purchase forms (D-069):
 *  - full settlement: when both card and transfer are chosen, typing one
 *    amount fills the other with the rest of the total; when only one is
 *    chosen it takes the whole total;
 *  - payment rows: the account list follows the method (card reader for
 *    "کارت‌خوان", current account for "حواله بانکی" and "چک");
 *  - the credit due date only appears while part of the invoice is unpaid, with
 *    one-tap terms (7/15/30... days), a plain-language sentence and a remembered term;
 *  - card + transfer together: a live "A + B = total" strip and an anchor amount;
 *  - a pre-flight check that stops the two predictable server rejections early.
 * Presentation only: the server re-validates everything against the real total.
 * sale_form.js / purchase_form.js fire "invoice:recomputed" after each recompute.
 */
(function () {
  "use strict";

  var ACCOUNT_TYPE = { card: "pos", bank_transfer: "current", cheque: "current" };

  function digitsToAscii(text) {
    return text.replace(/[۰-۹]/g, function (d) {
      return String(d.charCodeAt(0) - 0x06f0);
    });
  }

  // The forms print money with the Arabic thousands mark (٬), not a comma:
  // strip every non-digit, or "۱٬۵۰۰٬۰۰۰" would parse as 1.
  function toInt(text) {
    return parseInt(digitsToAscii(String(text || "")).replace(/[^0-9]/g, ""), 10) || 0;
  }

  // What is still to settle: the invoice total minus the party's earlier credit (D-087).
  function total() {
    var el = document.getElementById("sale-total");
    var t = el ? toInt(el.textContent) : 0;
    return window.payableAfterCredit ? window.payableAfterCredit(t) : t;
  }

  function fmt(n) {
    return String(Math.max(0, Math.round(n || 0))).replace(/\B(?=(\d{3})+(?!\d))/g, "٬").replace(/[0-9]/g, function (d) {
      return String.fromCharCode(0x06f0 + Number(d));
    });
  }

  // A convenience only (remembered choices); never let a blocked store break the page.
  function safeGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function safeSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* private window: just no memory */ }
  }

  // ---- Jalali date arithmetic (jalaali-js, public domain), only for the due-date shortcuts.
  // The server stays the judge of what a valid date is (JalaliDateField); this just
  // saves the owner from adding days to a Jalali date in his head.
  var PaperJalali = (function () {
    var BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
    function div(a, b) { return ~~(a / b); }
    function mod(a, b) { return a - ~~(a / b) * b; }

    function jalCal(jy, withoutLeap) {
      var bl = BREAKS.length, gy = jy + 621, leapJ = -14, jp = BREAKS[0], jm, jump = 0, leap, leapG, march, n, i;
      for (i = 1; i < bl; i += 1) {
        jm = BREAKS[i];
        jump = jm - jp;
        if (jy < jm) break;
        leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
        jp = jm;
      }
      n = jy - jp;
      leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
      if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
      leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
      march = 20 + leapJ - leapG;
      if (withoutLeap) return { gy: gy, march: march };
      if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
      leap = mod(mod(n + 1, 33) - 1, 4);
      if (leap === -1) leap = 4;
      return { leap: leap, gy: gy, march: march };
    }

    function g2d(gy, gm, gd) {
      var d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4) + div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408;
      return d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
    }

    function d2g(jdn) {
      var j = 4 * jdn + 139361631;
      j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
      var i = div(mod(j, 1461), 4) * 5 + 308;
      var gm = mod(div(i, 153), 12) + 1;
      return { gy: div(j, 1461) - 100100 + div(8 - gm, 6), gm: gm, gd: div(mod(i, 153), 5) + 1 };
    }

    function j2d(jy, jm, jd) {
      var r = jalCal(jy, true);
      return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
    }

    function d2j(jdn) {
      var gy = d2g(jdn).gy, jy = gy - 621, r = jalCal(jy, false), jdn1f = g2d(gy, 3, r.march), k = jdn - jdn1f, jm, jd;
      if (k >= 0) {
        if (k <= 185) return { y: jy, m: 1 + div(k, 31), d: mod(k, 31) + 1 };
        k -= 186;
      } else {
        jy -= 1;
        k += 179;
        if (r.leap === 1) k += 1;
      }
      jm = 7 + div(k, 30);
      jd = mod(k, 30) + 1;
      return { y: jy, m: jm, d: jd };
    }

    var FA = "۰۱۲۳۴۵۶۷۸۹";
    function toFa(value) {
      return String(value).replace(/[0-9]/g, function (d) { return FA.charAt(+d); });
    }
    function toAscii(text) {
      return String(text).replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06f0); })
        .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); });
    }
    function pad(n) { return (n < 10 ? "0" : "") + n; }

    // "۱۴۰۵/۰۷/۰۳" (any digits, / - . separators) -> day number, or null when not a date shape.
    function parseJdn(text) {
      var m = toAscii(text || "").match(/^\s*(\d{4})\s*[\/\-.]\s*(\d{1,2})\s*[\/\-.]\s*(\d{1,2})\s*$/);
      if (!m) return null;
      var y = +m[1], mo = +m[2], d = +m[3];
      if (y < 1300 || y > 1600 || mo < 1 || mo > 12 || d < 1 || d > 31) return null;
      var jdn = j2d(y, mo, d), back = d2j(jdn);
      // 30 Esfand of a non-leap year rolls into the next year: that is not a date.
      return back.y === y && back.m === mo && back.d === d ? jdn : null;
    }
    function todayJdn() {
      var t = new Date();
      return g2d(t.getFullYear(), t.getMonth() + 1, t.getDate());
    }
    function format(jdn) {
      var j = d2j(jdn);
      return toFa(j.y + "/" + pad(j.m) + "/" + pad(j.d));
    }
    // 0 = شنبه ... 6 = جمعه
    function weekday(jdn) { return mod(jdn + 2, 7); }
    // Last day of the month after the one `jdn` falls in.
    function endOfNextMonth(jdn) {
      var j = d2j(jdn), y = j.y, m = j.m + 2;
      if (m > 12) { m -= 12; y += 1; }
      return j2d(y, m, 1) - 1;
    }

    return { parseJdn: parseJdn, todayJdn: todayJdn, format: format, weekday: weekday, endOfNextMonth: endOfNextMonth, toFa: toFa, toAscii: toAscii };
  })();
  window.PaperJalali = PaperJalali; // sale_form.js reuses it for the cheque due-date shortcuts

  function field(name) {
    return document.getElementById("id_" + name);
  }

  function num(input) {
    var n = parseInt(input && input.value, 10);
    return isNaN(n) ? 0 : n;
  }

  function ticked(name) {
    var el = field(name);
    return !!(el && el.checked);
  }

  function isSplitMode() {
    var mode = document.querySelector('input[name="payment_mode"]:checked');
    return !!mode && mode.value === "split";
  }

  // ---- full settlement
  // The amount the owner typed last; with two methods the other one always follows it,
  // also when the invoice total moves afterwards (items, discount).
  var anchor = null;

  function syncFullAmounts(changed) {
    var posAmt = field("pos_amount");
    var trAmt = field("transfer_amount");
    var hasPos = ticked("use_pos");
    var hasTr = ticked("use_transfer");
    var t = total();
    if (hasPos && hasTr && posAmt && trAmt) {
      // Two methods: the amount just typed decides, the other takes the rest.
      if (changed) anchor = changed;
      if (changed === "pos_amount") trAmt.value = Math.max(t - num(posAmt), 0) || "";
      else if (changed === "transfer_amount") posAmt.value = Math.max(t - num(trAmt), 0) || "";
      else if (anchor) {
        var typed = anchor === "pos_amount" ? posAmt : trAmt;
        var other = typed === posAmt ? trAmt : posAmt;
        if (typed.value) other.value = Math.max(t - num(typed), 0) || "";
      } else if (!posAmt.value !== !trAmt.value) {
        // Only one box holds a number and nobody typed it: it is the auto-filled whole total.
        (posAmt.value ? posAmt : trAmt).value = t || "";
      }
    } else {
      anchor = null;
      if (hasPos && posAmt) {
        posAmt.value = t || "";
        if (trAmt) trAmt.value = "";
      } else if (hasTr && trAmt) {
        trAmt.value = t || "";
        if (posAmt) posAmt.value = "";
      }
    }
    renderSplit();
  }

  // "card A + transfer B = C of T": the equation the owner would otherwise do in his head.
  function renderSplit() {
    var both = ticked("use_pos") && ticked("use_transfer");
    ["pos", "transfer"].forEach(function (key) {
      var note = document.querySelector('[data-method-block="' + key + '"] [data-auto-note]');
      if (note) note.hidden = !(both && anchor && anchor !== key + "_amount");
    });
    var box = document.getElementById("payment-split");
    if (!box) return;
    box.hidden = !both;
    if (!both) return;
    var p = num(field("pos_amount"));
    var r = num(field("transfer_amount"));
    var t = total();
    var sum = p + r;
    function put(id, value) {
      var el = document.getElementById(id);
      if (el) el.textContent = fmt(value);
    }
    put("split-pos", p);
    put("split-tr", r);
    put("split-sum", sum);
    put("split-total", t);
    var ok = sum === t && p > 0 && r > 0;
    box.dataset.state = ok ? "ok" : "bad";
    var state = document.getElementById("split-state");
    if (state) {
      state.textContent = ok
        ? "جمع دو روش با مبلغ فاکتور برابر است."
        : sum > t
          ? "مجموع " + fmt(sum - t) + " تومان بیشتر از مبلغ فاکتور است."
          : "مبلغ یکی از روش‌ها را بنویسید؛ دیگری خودکار پر می‌شود.";
    }
  }

  // Ticking the second method: the cursor goes where the owner types next.
  function focusSecondMethod(tick) {
    if (!tick.checked || !ticked("use_pos") || !ticked("use_transfer")) return;
    var block = tick.closest("[data-method-block]");
    if (!block) return;
    var account = block.querySelector("select");
    var amount = block.querySelector('input[name$="_amount"]');
    var target = account && !account.value ? account : amount;
    if (target) {
      target.focus();
      if (target.select) target.select();
    }
  }

  // Which account the shop used last, per method, per browser.
  function accountMemoryKey(id) {
    return "pp." + (document.getElementById("sale-form") ? "sale" : "purchase") + "." + id;
  }
  function restoreAccounts() {
    ["id_pos_account", "id_transfer_account"].forEach(function (id) {
      var select = document.getElementById(id);
      if (!select || select.tagName !== "SELECT" || select.value) return;
      var saved = safeGet(accountMemoryKey(id));
      if (saved && select.querySelector('option[value="' + saved.replace(/[^0-9a-zA-Z-]/g, "") + '"]')) select.value = saved;
    });
  }

  // A fresh sale opens with the method the shop used last time; a page re-rendered after a
  // server error keeps exactly what was posted. The recap in the sticky bar always names it.
  var METHOD_KEY = "pp.sale.method";
  function restoreMethod() {
    if (!document.getElementById("sale-form") || isSplitMode()) return;
    if (ticked("use_pos") || ticked("use_transfer")) return;
    if (document.querySelector(".form-error, .field--invalid")) return;
    var last = safeGet(METHOD_KEY);
    if (!last) return;
    var wantPos = last.indexOf("pos") !== -1;
    var wantTransfer = last.indexOf("transfer") !== -1;
    if (field("use_pos") && wantPos) field("use_pos").checked = true;
    if (field("use_transfer") && wantTransfer) field("use_transfer").checked = true;
  }
  function rememberMethod() {
    if (isSplitMode() || (!ticked("use_pos") && !ticked("use_transfer"))) return;
    safeSet(METHOD_KEY, (ticked("use_pos") ? "pos" : "") + (ticked("use_transfer") ? "transfer" : ""));
  }

  // A method's fields show only while its box is ticked; hidden ones are
  // disabled so they are not posted and the server never sees stale values.
  function applyTicks() {
    document.querySelectorAll("[data-method-block]").forEach(function (block) {
      var tick = block.querySelector('input[type="checkbox"]');
      var panel = block.querySelector("[data-method-fields]");
      if (!tick || !panel) return;
      panel.hidden = !tick.checked;
      panel.querySelectorAll("input, select").forEach(function (el) {
        el.disabled = !tick.checked;
        if (!tick.checked && el.type !== "hidden" && el.tagName !== "SELECT") el.value = "";
      });
    });
  }

  // ---- payment rows
  function filterRowAccounts(row) {
    var method = row.querySelector('select[name$="-method"]');
    var account = row.querySelector('select[name$="-bank_account"]');
    if (!method || !account) return;
    var want = ACCOUNT_TYPE[method.value];
    Array.prototype.forEach.call(account.options, function (opt) {
      if (!opt.value) return;
      var ok = !want || opt.dataset.type === want;
      opt.hidden = !ok;
      opt.disabled = !ok;
    });
    var chosen = account.options[account.selectedIndex];
    if (chosen && chosen.value && chosen.disabled) account.value = "";
    // A single card reader is the obvious account for a card row (D-078); the same
    // goes for a lone current account on a transfer or cheque row.
    if (!account.value && method.value) {
      var usable = Array.prototype.filter.call(account.options, function (o) { return o.value && !o.disabled; });
      if (usable.length === 1 && (method.value === "card" || method.value === "bank_transfer" || method.value === "cheque")) {
        account.value = usable[0].value;
      }
    }
  }

  // ---- credit (نسیه) due date: one-tap terms, a plain sentence, a remembered term.
  // The field, the Jalali picker and the server rule stay as they are; chips only write into it.
  var WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];
  var dueTouched = false; // the owner typed/picked a date himself: never overwrite it
  var dueAuto = false;    // we pre-filled it once from the remembered term
  var activeTerm = null;  // "30" / "eom" while a chip decides the date

  function partyId() {
    var select = field("customer") || field("supplier");
    return select ? select.value : "";
  }
  function termKey(party) {
    return "pp.creditTerm." + (party ? "party." + party : "any");
  }

  // Terms count from the invoice date, today when it is empty or not a date yet.
  function baseJdn() {
    var el = field("invoice_date");
    var jdn = el ? PaperJalali.parseJdn(el.value) : null;
    return jdn === null ? PaperJalali.todayJdn() : jdn;
  }

  function markTerm() {
    document.querySelectorAll("[data-due-term]").forEach(function (chip) {
      chip.setAttribute("aria-pressed", String(chip.dataset.dueTerm === activeTerm));
    });
  }

  function setDueTerm(term, remember) {
    var due = field("credit_due_date");
    if (!due) return;
    var base = baseJdn();
    due.value = PaperJalali.format(term === "eom" ? PaperJalali.endOfNextMonth(base) : base + parseInt(term, 10));
    due.setAttribute("aria-invalid", "false");
    if (due.closest(".field")) due.closest(".field").classList.remove("field--invalid");
    activeTerm = String(term);
    markTerm();
    if (remember) {
      safeSet(termKey(partyId()), activeTerm);
      safeSet(termKey(""), activeTerm);
    }
    renderCreditSummary();
  }

  function renderCreditSummary() {
    var box = document.getElementById("credit-summary");
    var remaining = document.getElementById("sale-remaining");
    var due = field("credit_due_date");
    if (!box || !remaining || !due) return;
    box.classList.remove("credit-summary--warn");
    var left = toInt(remaining.textContent);
    if (!isSplitMode()) {
      box.textContent = "";
      return;
    }
    if (left <= 0) {
      box.textContent = document.querySelector("#payment-rows [data-payment-row]")
        ? "همهٔ مبلغ فاکتور با ردیف‌های پرداخت پوشش داده شده؛ چیزی نسیه نمی‌ماند." : "";
      return;
    }
    var amount = remaining.textContent.trim();
    var jdn = PaperJalali.parseJdn(due.value);
    if (jdn === null) {
      box.classList.add("credit-summary--warn");
      box.textContent = due.value.trim()
        ? "تاریخ سررسید را به شکل ۱۴۰۵/۰۷/۰۳ وارد کنید."
        : amount + " تومان نسیه می‌ماند؛ تاریخ سررسید را انتخاب کنید.";
      return;
    }
    var days = jdn - baseJdn();
    box.textContent = amount + " تومان نسیه تا " + WEEKDAYS[PaperJalali.weekday(jdn)] + " " + PaperJalali.format(jdn) +
      (days > 0 ? " (" + PaperJalali.toFa(days) + " روز پس از تاریخ فاکتور)" : days === 0 ? " (همان روز فاکتور)" : " (قبل از تاریخ فاکتور!)");
    if (days < 0) box.classList.add("credit-summary--warn");
  }

  // The first time the credit block appears with an empty date, offer the term this party
  // (else the shop) used last. It is shown, never hidden: the owner can change it at once.
  function maybeAutoDue() {
    var wrap = document.querySelector("[data-credit-due]");
    var due = field("credit_due_date");
    if (!wrap || !due || wrap.hidden || !isSplitMode() || dueTouched || dueAuto || due.value.trim()) return;
    var term = safeGet(termKey(partyId())) || safeGet(termKey(""));
    if (term === "eom" || /^[0-9]{1,3}$/.test(term || "")) {
      setDueTerm(term, false);
      dueAuto = true;
    }
  }

  function syncCreditDue() {
    var wrap = document.querySelector("[data-credit-due]");
    var remaining = document.getElementById("sale-remaining");
    if (!wrap || !remaining) return;
    wrap.hidden = toInt(remaining.textContent) <= 0;
    maybeAutoDue();
    renderCreditSummary();
  }

  function setMode(mode) {
    var radio = document.querySelector('input[name="payment_mode"][value="' + mode + '"]');
    if (!radio || radio.checked) return;
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // The two failures the server would only report after a full round trip, caught first.
  // Capture phase: the form script's double-submit flag must not be set for a refused submit.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || (form.id !== "sale-form" && form.id !== "purchase-form") || form.dataset.busy) return;
    var split = isSplitMode();
    var problem = null;
    if (!split && !ticked("use_pos") && !ticked("use_transfer")) problem = "method";
    else if (split) {
      var wrap = document.querySelector("[data-credit-due]");
      var due = field("credit_due_date");
      if (wrap && !wrap.hidden && due && !due.value.trim()) problem = "due";
    }
    if (!problem) {
      if (form.id === "sale-form") rememberMethod();
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    if (problem === "method") {
      var warn = document.getElementById("payment-method-warn");
      if (warn) warn.hidden = false;
      var panel = document.querySelector(".payment-full");
      if (panel) {
        panel.classList.add("is-attention");
        panel.scrollIntoView({ block: "center", behavior: "smooth" });
        setTimeout(function () { panel.classList.remove("is-attention"); }, 2500);
      }
      var first = field("use_pos") || field("use_transfer");
      if (first) first.focus({ preventScroll: true });
    } else {
      var dueField = field("credit_due_date");
      var box = document.getElementById("credit-summary");
      if (dueField.closest(".field")) dueField.closest(".field").classList.add("field--invalid");
      dueField.setAttribute("aria-invalid", "true");
      if (box) {
        box.textContent = "برای مبلغ نسیه، تاریخ سررسید لازم است؛ یک مهلت را بزنید یا تاریخ را وارد کنید.";
        box.classList.add("credit-summary--warn");
      }
      dueField.scrollIntoView({ block: "center", behavior: "smooth" });
      dueField.focus({ preventScroll: true });
    }
  }, true);

  document.addEventListener("invoice:recomputed", function () {
    if (!isSplitMode()) syncFullAmounts();
    syncCreditDue();
  });

  document.addEventListener("input", function (event) {
    var id = event.target.id;
    if (id === "id_pos_amount" || id === "id_transfer_amount") syncFullAmounts(id.replace("id_", ""));
    if (id === "id_credit_due_date") {
      dueTouched = true;
      activeTerm = null;
      markTerm();
      renderCreditSummary();
    }
    if (id === "id_invoice_date") {
      if (activeTerm) setDueTerm(activeTerm, false);
      else renderCreditSummary();
    }
  });

  document.addEventListener("change", function (event) {
    var t = event.target;
    if (t.id === "id_use_pos" || t.id === "id_use_transfer") {
      applyTicks();
      syncFullAmounts();
      focusSecondMethod(t);
      var warn = document.getElementById("payment-method-warn");
      if (warn) warn.hidden = true;
    }
    if (t.id === "id_pos_account" || t.id === "id_transfer_account") {
      if (t.value) safeSet(accountMemoryKey(t.id), t.value);
    }
    if (t.matches && t.matches('select[name$="-method"]')) filterRowAccounts(t.closest("[data-payment-row]"));
    if (t.name === "payment_mode") syncCreditDue();
    // The date picker writes the value and fires "change", not "input".
    if (t.id === "id_credit_due_date") {
      dueTouched = true;
      activeTerm = null;
      markTerm();
      renderCreditSummary();
    }
    if (t.id === "id_invoice_date") {
      if (activeTerm) setDueTerm(activeTerm, false);
      else renderCreditSummary();
    }
    if (t.id === "id_customer" || t.id === "id_supplier") {
      // A term picked for the previous party was only a suggestion: swap it for this party's.
      var due = field("credit_due_date");
      if (dueAuto && !dueTouched && due) {
        due.value = "";
        dueAuto = false;
        activeTerm = null;
        markTerm();
      }
      maybeAutoDue();
      renderCreditSummary();
    }
  });

  document.addEventListener("click", function (event) {
    var target = event.target;
    // A row added by the form script: filter its accounts once it exists.
    if (target.id === "add-payment-row") {
      setTimeout(function () {
        document.querySelectorAll("#payment-rows [data-payment-row]").forEach(filterRowAccounts);
      }, 0);
    }
    var term = target.closest && target.closest("[data-due-term]");
    if (term) {
      dueTouched = true;
      setDueTerm(term.dataset.dueTerm, true);
      return;
    }
    if (target.closest && target.closest("[data-split-half]")) {
      var t = total();
      var half = Math.floor(t / 2);
      var posAmt = field("pos_amount");
      if (posAmt && field("transfer_amount") && t) {
        posAmt.value = half;
        syncFullAmounts("pos_amount");
      }
      return;
    }
    // "The whole invoice is on credit": switch to split mode and land on the terms.
    if (target.closest && target.closest("[data-credit-all]")) {
      setMode("split");
      syncCreditDue();
      var chip = document.querySelector("[data-due-term]");
      if (chip) chip.focus();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    // A re-rendered page already carries a date the owner typed: it counts as his.
    var dueInput = field("credit_due_date");
    if (dueInput && dueInput.value.trim()) dueTouched = true;
    document.querySelectorAll("#payment-rows [data-payment-row]").forEach(filterRowAccounts);
    restoreAccounts();
    restoreMethod();
    applyTicks();
    syncFullAmounts();
    syncCreditDue();
  });
})();

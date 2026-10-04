/* Behaviour of the "insight" pages: dashboard, financial reports, user activity, backup.
   Everything is progressive: each page still works with this file missing (plain links,
   plain GET forms, the full table). Delegated listeners, so htmx swaps cannot unbind them. */
(function () {
  "use strict";

  function fontsReady() {
    return document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
  }

  // Clipboard with a fallback for browsers (or plain-http hosts) that have no async clipboard API.
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var box = document.createElement("textarea");
      box.value = text;
      box.setAttribute("readonly", "");
      box.style.position = "fixed";
      box.style.opacity = "0";
      document.body.appendChild(box);
      box.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      document.body.removeChild(box);
      return ok ? resolve() : reject(new Error("copy failed"));
    });
  }

  function flash(button, text) {
    var old = button.textContent;
    button.textContent = text;
    setTimeout(function () { button.textContent = old; }, 1800);
  }

  // ------------------------------------------------------------ reports: print and copy

  function reportSummary() {
    var lede = document.querySelector(".page-head__lede");
    var lines = [];
    if (lede) {
      var clone = lede.cloneNode(true);
      clone.querySelectorAll(".no-print").forEach(function (el) { el.remove(); });
      lines.push("گزارش مالی");
      lines.push(clone.textContent.replace(/\s+/g, " ").trim());
    }
    document.querySelectorAll("main .stats .stat-card").forEach(function (card) {
      var label = card.querySelector(".stat-card__label");
      var value = card.querySelector(".stat-card__value");
      if (!label || !value) return;
      var delta = card.querySelector(".stat-card__delta");
      var line = label.textContent.trim() + ": " + value.textContent.replace(/\s+/g, " ").trim();
      if (delta) line += " (" + delta.textContent.replace(/\s+/g, " ").trim() + ")";
      lines.push(line);
    });
    return lines.join("\n");
  }

  document.addEventListener("click", function (e) {
    var target = e.target;
    if (!target.closest) return;

    var printBtn = target.closest("[data-report-print]");
    if (printBtn) {
      // Wait for the font, like the invoice print buttons: printing before it loads falls back to a wrong face.
      fontsReady().then(function () { window.print(); });
      return;
    }

    var copyBtn = target.closest("[data-report-copy]");
    if (copyBtn) {
      var status = document.querySelector("[data-report-status]");
      copyText(reportSummary()).then(function () {
        flash(copyBtn, "کپی شد");
        if (status) status.textContent = "خلاصهٔ گزارش کپی شد؛ در پیام‌رسان پیست کنید.";
      }, function () {
        if (status) status.textContent = "کپی انجام نشد؛ مرورگر اجازه نداد.";
      });
      return;
    }

    var dataCopy = target.closest("[data-copy]");
    if (dataCopy) {
      var source = document.querySelector(dataCopy.getAttribute("data-copy"));
      if (!source) return;
      copyText(source.textContent.trim()).then(function () {
        flash(dataCopy, dataCopy.getAttribute("data-copied") || "کپی شد");
      }, function () {});
      return;
    }

    var dismiss = target.closest("[data-setup-dismiss]");
    if (dismiss) {
      var card = dismiss.closest("[data-setup]");
      if (card) card.hidden = true;
      try { localStorage.setItem("pp.setupDismissed", "1"); } catch (err) { /* storage blocked: hidden for this visit only */ }
    }
  });

  // ------------------------------------------------------------ dashboard: first-steps card

  (function () {
    var card = document.querySelector("[data-setup]");
    if (!card) return;
    try { if (localStorage.getItem("pp.setupDismissed") === "1") card.hidden = true; } catch (err) { /* keep it visible */ }
  })();

  // ------------------------------------------------------------ reports: live product filter

  // One spelling for Persian/Arabic digits and letters, so «ک» typed on any keyboard finds «ک».
  function normalise(text) {
    return String(text)
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 1776); })
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 1632); })
      .replace(/ي/g, "ی").replace(/ك/g, "ک")
      .replace(/‌/g, " ")
      .toLowerCase().trim();
  }

  function formatToman(number) {
    var text;
    try { text = new Intl.NumberFormat("fa-IR").format(number); } catch (err) { text = String(number); }
    return text + " تومان";
  }

  document.addEventListener("input", function (e) {
    var box = e.target;
    if (!box || box.id !== "product-filter") return;
    var table = document.getElementById("sales-by-product-table");
    if (!table) return;

    var rows = [].slice.call(table.querySelectorAll("tbody tr"));
    var summary = document.getElementById("product-filter-summary");
    var label = document.getElementById("product-totals-label");
    var totalAmount = document.getElementById("tot-amount");
    var totalProfit = document.getElementById("tot-profit");

    // The unfiltered figures are the server's own; remember them once so clearing the box restores them exactly.
    if (!table.hasAttribute("data-kept")) {
      table.setAttribute("data-kept", "1");
      table.setAttribute("data-kept-amount", totalAmount.textContent);
      table.setAttribute("data-kept-profit", totalProfit.textContent);
    }

    var query = normalise(box.value);
    var amount = 0, profit = 0, shown = 0;
    rows.forEach(function (row) {
      var hit = !query || normalise(row.getAttribute("data-name")).indexOf(query) !== -1;
      row.hidden = !hit;
      if (hit) {
        shown += 1;
        amount += Number(row.getAttribute("data-amount")) || 0;
        profit += Number(row.getAttribute("data-profit")) || 0;
      }
    });

    if (!query) {
      label.textContent = "همهٔ کالاها";
      totalAmount.textContent = table.getAttribute("data-kept-amount");
      totalProfit.textContent = table.getAttribute("data-kept-profit");
      summary.textContent = "";
      return;
    }
    label.textContent = "کالاهای نمایش‌داده‌شده";
    totalAmount.textContent = formatToman(amount);
    totalProfit.textContent = formatToman(profit);
    summary.textContent = shown
      ? shown.toLocaleString("fa-IR") + " از " + rows.length.toLocaleString("fa-IR") + " کالا؛ جمع پایین جدول فقط همین‌ها را می‌شمارد"
      : "کالایی با این نام در جدول نیست";
  });

  // ------------------------------------------------------------ user activity: no "apply" click for selects

  document.addEventListener("change", function (e) {
    var select = e.target;
    if (!select || select.tagName !== "SELECT" || !select.form || !select.form.hasAttribute("data-autosubmit")) return;
    // The apply button stays as the fallback; this only saves the click.
    if (select.form.requestSubmit) select.form.requestSubmit();
    else select.form.submit();
  });
})();

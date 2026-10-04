/* Cross-page UI behaviour that no single module owns: error state on fields,
   a visible answer when an htmx request fails, and what happens when the
   session expires in the middle of an htmx call. */
(function () {
  "use strict";

  var loginUrl = document.currentScript ? document.currentScript.dataset.loginUrl : "/login/";

  // The server marks a field with .field--invalid; the control itself must say so too.
  function markInvalid(root) {
    root.querySelectorAll(".field--invalid").forEach(function (field) {
      var control = field.querySelector("input, select, textarea");
      if (control) control.setAttribute("aria-invalid", "true");
    });
  }

  // One toast element, reused. role=alert so a screen reader hears it.
  var toast;
  function showToast(text, href, linkText) {
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      toast.setAttribute("role", "alert");
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = linkText;
      toast.append(" ", a);
    }
    toast.hidden = false;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(function () { toast.hidden = true; }, 8000);
  }


  // Persian/Arabic-Indic digits typed on a Persian keyboard become Latin ones in numeric
  // boxes (see NumericInput), so every script that parses a value keeps seeing ASCII.
  // Capture phase: it must run before any module script reads the new value.
  var DIGITS = {"۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
                "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
                "٫": ".", "٬": "", "،": ""};
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (!t.matches || !t.matches('input[inputmode="numeric"], input[inputmode="decimal"]')) return;
    var fixed = t.value.replace(/[۰-۹٠-٩٫٬،]/g, function (c) { return DIGITS[c]; });
    if (fixed !== t.value) t.value = fixed;
  }, true);

  document.addEventListener("DOMContentLoaded", function () { markInvalid(document); });
  document.body.addEventListener("htmx:afterSwap", function (e) { markInvalid(e.target); });

  // An expired session answers an htmx call with a redirect to the login page, which
  // htmx would swap into a dropdown or dialog. Swap nothing and say what happened.
  document.body.addEventListener("htmx:beforeSwap", function (e) {
    var xhr = e.detail.xhr;
    if (xhr && xhr.responseURL && xhr.responseURL.indexOf(loginUrl) !== -1) {
      e.detail.shouldSwap = false;
      showToast("نشست شما منقضی شده است؛ برای ادامه وارد شوید.", loginUrl, "ورود در برگهٔ جدید");
    }
  });

  // htmx drops 4xx/5xx and network failures silently (see base.html); never leave the user guessing.
  document.body.addEventListener("htmx:responseError", function (e) {
    if (e.detail.xhr && e.detail.xhr.status === 422) return;
    showToast("درخواست انجام نشد؛ دوباره تلاش کنید.");
  });
  document.body.addEventListener("htmx:sendError", function () {
    showToast("ارتباط با سرور برقرار نشد؛ اتصال را بررسی کنید.");
  });
})();

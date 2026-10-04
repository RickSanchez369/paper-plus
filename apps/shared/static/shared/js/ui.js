/* Cross-page UI behaviour that no single module owns: error state on fields,
   a visible answer when an htmx request fails, and what happens when the
   session expires in the middle of an htmx call. */
(function () {
  "use strict";

  var script = document.currentScript;
  var loginUrl = script ? script.dataset.loginUrl : "/login/";
  // The signed-in phone, so a re-login only needs the password (see reloginDialog).
  var phone = script ? (script.dataset.phone || "") : "";

  // The server marks a field with .field--invalid; the control itself must say so too.
  function markInvalid(root) {
    root.querySelectorAll(".field--invalid").forEach(function (field) {
      var control = field.querySelector("input, select, textarea");
      if (!control) return;
      control.setAttribute("aria-invalid", "true");
      var err = field.querySelector(".field__error[id]");
      if (err && !control.hasAttribute("aria-describedby")) control.setAttribute("aria-describedby", err.id);
    });
    // The "*" marker is aria-hidden, so the control itself must say it is required.
    root.querySelectorAll(".field__req").forEach(function (mark) {
      var control = mark.closest(".field").querySelector("input, select, textarea");
      if (control) control.setAttribute("aria-required", "true");
    });
  }

  // After a failed submit the page re-renders at the top; bring the error summary into view
  // and focus it so the failure is noticed (and announced) instead of looking like an inert button.
  function focusSummary(root) {
    var summary = root.querySelector("[data-error-summary]");
    if (!summary) return;
    // A summary link whose field is not on the page would be a dead link: show it as plain text.
    summary.querySelectorAll("a[href^='#']").forEach(function (a) {
      if (!document.getElementById(a.getAttribute("href").slice(1))) {
        var span = document.createElement("span");
        span.textContent = a.textContent;
        a.replaceWith(span);
      }
    });
    summary.focus({ preventScroll: true });
    var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    summary.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
  }

  // Summary links jump AND focus the field (an in-page hash alone only scrolls).
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest(".form-error__list a[href^='#']") : null;
    if (!a) return;
    var target = document.getElementById(a.getAttribute("href").slice(1));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ block: "center" });
    target.focus();
  });

  // One toast element, reused. role=alert so a screen reader hears it. It has a close
  // button, pauses while hovered or focused, and stays long enough to read a Persian sentence.
  var toast, toastText, toastTimer, leaveTimer, toastSticky = false;

  function hideToast() {
    if (!toast || toast.hidden) return;
    clearTimeout(toastTimer);
    toast.classList.add("is-leaving");           // CSS plays the exit; state, not animation, hides it
    leaveTimer = setTimeout(function () { toast.hidden = true; toast.classList.remove("is-leaving"); }, 140);
  }

  function armToast() {
    clearTimeout(toastTimer);
    if (toastSticky) return;
    // About 60ms per character with a 6s floor.
    toastTimer = setTimeout(hideToast, Math.max(6000, toastText.textContent.length * 60));
  }

  function showToast(text, href, linkText, sticky) {
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      toast.setAttribute("role", "alert");
      toastText = document.createElement("span");
      toastText.className = "toast__text";
      var close = document.createElement("button");
      close.type = "button";
      close.className = "toast__close";
      close.setAttribute("aria-label", "بستن پیام");
      close.textContent = "×";
      close.addEventListener("click", hideToast);
      toast.append(toastText, close);
      toast.addEventListener("mouseenter", function () { clearTimeout(toastTimer); });
      toast.addEventListener("mouseleave", armToast);
      toast.addEventListener("focusin", function () { clearTimeout(toastTimer); });
      toast.addEventListener("focusout", armToast);
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && toast && !toast.hidden && toast.contains(document.activeElement)) hideToast();
      });
      document.body.appendChild(toast);
    }
    toastSticky = !!sticky;
    toastText.textContent = "";                  // cleared first so identical text is announced again
    toastText.append(text);
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = linkText;
      toastText.append(" ", a);
    }
    clearTimeout(leaveTimer);                    // a show during the exit must not be hidden by it
    toast.classList.remove("is-leaving");
    toast.hidden = false;
    armToast();
  }


  // Persian/Arabic-Indic digits typed on a Persian keyboard become Latin ones in numeric
  // boxes (see NumericInput), so every script that parses a value keeps seeing ASCII.
  // Capture phase: it must run before any module script reads the new value.
  // Date boxes are left to jalali_picker.js, which keeps them in Persian digits like
  // everything the page prints (the server and every date parser accept both scripts).
  var DIGITS = {"۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
                "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
                "٫": ".", "٬": "", "،": ""};
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (!t.matches || !t.matches('input[inputmode="numeric"]:not(.js-jalali-date), input[inputmode="decimal"]')) return;
    var fixed = t.value.replace(/[۰-۹٠-٩٫٬،]/g, function (c) { return DIGITS[c]; });
    if (fixed !== t.value) t.value = fixed;
  }, true);

  // A slow POST that answers with a download (backup) never navigates, so nothing tells the user
  // it is working and a second click builds a second dump: disable the button for a while.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.dataset || !form.dataset.busyLabel) return;
    var btn = form.querySelector("[type=submit]");
    if (!btn) return;
    if (btn.disabled) { e.preventDefault(); return; }
    var label = btn.textContent;
    setTimeout(function () { btn.disabled = true; btn.textContent = form.dataset.busyLabel; }, 0);
    setTimeout(function () { btn.disabled = false; btn.textContent = label; }, 12000);
  });

  document.addEventListener("DOMContentLoaded", function () {
    markInvalid(document);
    focusSummary(document);
    upgradeBreadcrumbs(document);
    upgradeTerms(document);
  });
  document.body.addEventListener("htmx:afterSwap", function (e) {
    markInvalid(e.target);
    focusSummary(e.target);
    upgradeTerms(e.target);
    // A swap that replaces the focused control (the form that was just submitted)
    // drops focus on <body>; a fragment can name where it should land instead.
    // The quick-create confirmation is such a fragment (the product variant is left alone:
    // purchase_form.js moves focus into the new item row itself).
    var t = e.target, AUTO = "[data-autofocus], .quick-party--success:not([data-quick-product-created])";
    var spot = t && t.matches && t.matches(AUTO) ? t
      : (t && t.querySelector ? t.querySelector(AUTO) : null);
    if (spot) {
      if (!spot.hasAttribute("tabindex")) spot.setAttribute("tabindex", "-1");
      if (!spot.hasAttribute("role")) spot.setAttribute("role", "status");
      spot.focus({ preventScroll: true });
    }
  });

  // ------------------------------------------------ expired session
  // The session is a fixed two weeks, so it ends at a random moment, often with a half-filled
  // invoice on screen. Instead of a new tab (and a lost form), ask for the password in a dialog
  // on the same page: the form underneath is untouched, and Django's login view does the work
  // (throttle, CSRF and all). The CSRF token rotates at login, so the page's copies are refreshed.
  function csrfCookie() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  var relogin;
  function reloginDialog() {
    if (!window.HTMLDialogElement) {
      showToast("نشست شما منقضی شده است؛ برای ادامه وارد شوید.", loginUrl, "ورود در برگهٔ جدید", true);
      return;
    }
    if (relogin && relogin.open) return;
    if (!relogin) {
      relogin = document.createElement("dialog");
      relogin.className = "relogin";
      relogin.setAttribute("aria-labelledby", "relogin-title");
      relogin.innerHTML =
        '<form class="relogin__form" novalidate>' +
        '<h2 id="relogin-title" class="relogin__title">نشست شما منقضی شد</h2>' +
        '<p class="relogin__lede">گذرواژه را بزنید و همین‌جا ادامه دهید؛ آنچه نوشته‌اید حفظ می‌شود.</p>' +
        '<div class="form-error" role="alert" hidden></div>' +
        (phone ? "" :
          '<div class="field"><label class="field__label" for="relogin-phone">شمارهٔ موبایل</label>' +
          '<input id="relogin-phone" class="field__control" type="text" dir="ltr" inputmode="numeric" autocomplete="username"></div>') +
        '<div class="field"><label class="field__label" for="relogin-pw">گذرواژه</label>' +
        '<input id="relogin-pw" class="field__control" type="password" dir="ltr" autocomplete="current-password"></div>' +
        '<div class="field"><button type="submit" class="btn btn--lg btn--block">ورود و ادامه</button></div>' +
        '</form>';
      document.body.appendChild(relogin);
      // Esc must not hide the notice: the page behind it is no longer usable.
      relogin.addEventListener("cancel", function (e) { e.preventDefault(); });
      relogin.querySelector("form").addEventListener("submit", reloginSubmit);
    }
    relogin.showModal();
    relogin.querySelector("input").focus();
  }

  function reloginSubmit(e) {
    e.preventDefault();
    var err = relogin.querySelector(".form-error");
    var pw = relogin.querySelector("#relogin-pw");
    var phoneBox = relogin.querySelector("#relogin-phone");
    var btn = relogin.querySelector("button[type=submit]");
    var body = new URLSearchParams();
    body.set("username", phoneBox ? phoneBox.value : phone);
    body.set("password", pw.value);
    body.set("next", "");
    btn.disabled = true;
    fetch(loginUrl, {
      method: "POST", body: body, redirect: "manual", credentials: "same-origin",
      headers: { "X-CSRFToken": csrfCookie() }
    }).then(function (r) {
      if (r.type === "opaqueredirect") {         // 302: signed in
        var token = csrfCookie();
        document.body.setAttribute("hx-headers", JSON.stringify({ "X-CSRFToken": token }));
        document.querySelectorAll("input[name=csrfmiddlewaretoken]").forEach(function (i) { i.value = token; });
        pw.value = "";
        err.hidden = true;
        relogin.close();
        showToast("دوباره وارد شدید؛ ادامه دهید.");
      } else {                                   // 200: wrong password, 429: locked out
        err.hidden = false;
        err.textContent = r.status === 429
          ? "تلاش‌های ناموفق زیاد بوده است؛ چند دقیقه بعد دوباره تلاش کنید."
          : "گذرواژه درست نیست.";
        pw.select();
      }
    }).catch(function () {
      err.hidden = false;
      err.textContent = "ارتباط با سرور برقرار نشد؛ اتصال را بررسی کنید.";
    }).then(function () { btn.disabled = false; });
  }

  // GET /login/ answers 302 for a signed-in user (redirect_authenticated_user) and 200 once
  // the session is gone, so it doubles as a cheap "am I still signed in?" probe.
  function probeSession(timeoutMs) {
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, timeoutMs) : null;
    return fetch(loginUrl, { redirect: "manual", credentials: "same-origin", signal: ctl ? ctl.signal : undefined })
      .then(function (r) { clearTimeout(timer); return r.type !== "opaqueredirect" && r.status === 200; })
      .catch(function () { clearTimeout(timer); return false; });    // offline or slow: never block the user
  }

  function checkSession() {
    if (document.hidden || (relogin && relogin.open) || navigator.onLine === false) return;
    probeSession(8000).then(function (expired) { if (expired) reloginDialog(); });
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) checkSession(); });
  setInterval(checkSession, 5 * 60 * 1000);

  // Last-chance guard: a plain POST (the invoice forms) from an expired session is bounced to
  // the login page and the whole form is lost. Ask first; only when the session is gone is the
  // submit held back. Any doubt (offline, slow, no AbortController) lets the submit through.
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (!f || f.tagName !== "FORM" || !window.AbortController) return;
    if (f.dataset.sessionOk) return;             // the re-submit below
    if ((f.getAttribute("method") || "").toLowerCase() !== "post") return;
    if (f.matches("[hx-post], [hx-put], [hx-patch], [hx-delete]") || f.closest(".relogin, .header__user")) return;
    if (f.action && f.action.indexOf(window.location.origin) !== 0) return;
    // The check is asynchronous: a second click meanwhile must not become a second submit.
    e.preventDefault();
    e.stopImmediatePropagation();
    if (f.dataset.sessionChecking) return;
    f.dataset.sessionChecking = "1";
    var submitter = e.submitter;
    probeSession(4000).then(function (expired) {
      delete f.dataset.sessionChecking;
      if (expired) { reloginDialog(); return; }
      f.dataset.sessionOk = "1";
      try {
        if (!f.requestSubmit) f.submit();
        else if (submitter && submitter.form === f) f.requestSubmit(submitter);
        else f.requestSubmit();
      } finally {
        delete f.dataset.sessionOk;
      }
    });
  }, true);

  // An expired session answers an htmx call with a redirect to the login page, which
  // htmx would swap into a dropdown or dialog. Swap nothing and ask for the password in place.
  document.body.addEventListener("htmx:beforeSwap", function (e) {
    var xhr = e.detail.xhr;
    if (xhr && xhr.responseURL && xhr.responseURL.indexOf(loginUrl) !== -1) {
      e.detail.shouldSwap = false;
      reloginDialog();
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

  // ------------------------------------------------ htmx in flight
  // Until the response lands nothing on screen changed, so a slow link invites a second click on
  // a money form. While a request is out: the form's submit buttons are disabled (and re-enabled
  // on any outcome), and <html data-loading> lets CSS draw a thin progress line under the header.
  var inflight = [];
  var root = document.documentElement;
  var watchdog;

  function setLoading() {
    if (inflight.length) root.setAttribute("data-loading", ""); else root.removeAttribute("data-loading");
  }

  function lockForm(form) {
    form.querySelectorAll('button[type="submit"], button:not([type]), input[type="submit"]').forEach(function (b) {
      if (b.disabled) return;
      b.disabled = true;
      b.setAttribute("data-htmx-locked", "");
    });
  }

  function unlockForm(form) {
    form.querySelectorAll("[data-htmx-locked]").forEach(function (b) {
      b.disabled = false;
      b.removeAttribute("data-htmx-locked");
    });
  }

  document.body.addEventListener("htmx:beforeRequest", function (e) {
    if (e.defaultPrevented) return;              // another script cancelled it: nothing is in flight
    var xhr = e.detail.xhr, elt = e.detail.elt;
    if (xhr && inflight.indexOf(xhr) === -1) inflight.push(xhr);
    setLoading();
    // Never leave the page looking busy (or a button dead) if no end event ever arrives.
    clearTimeout(watchdog);
    watchdog = setTimeout(function () {
      inflight = [];
      setLoading();
      document.querySelectorAll("[data-htmx-locked]").forEach(function (b) {
        b.disabled = false;
        b.removeAttribute("data-htmx-locked");
      });
    }, 60000);
    // Writes only: a live filter form (hx-get on keyup) must not flicker its buttons.
    var verb = e.detail.requestConfig && e.detail.requestConfig.verb;
    if (elt && elt.tagName === "FORM" && verb && verb !== "get") lockForm(elt);
  });

  ["htmx:afterRequest", "htmx:sendError", "htmx:sendAbort", "htmx:timeout", "htmx:responseError"].forEach(function (name) {
    document.body.addEventListener(name, function (e) {
      var i = inflight.indexOf(e.detail && e.detail.xhr);
      if (i !== -1) inflight.splice(i, 1);
      setLoading();
      var elt = e.detail && e.detail.elt;
      if (elt && elt.tagName === "FORM") unlockForm(elt);
    });
  });

  // ------------------------------------------------ breadcrumbs
  // Older pages print the trail as `<p class="breadcrumbs"><a>..</a> / ..</p>`: a typed slash that
  // has no direction, no landmark and wraps badly. Rebuild it as <nav><ol> (same links, same text)
  // so CSS can draw a direction-aware chevron and the last crumb is marked as the current page.
  // Only a slash that starts a text node counts as a separator, so "1405/0001" inside a name is safe.
  function upgradeBreadcrumbs(scope) {
    scope.querySelectorAll("p.breadcrumbs").forEach(function (p) {
      var crumbs = [], cur = [];
      function flush() { if (cur.length) crumbs.push(cur); cur = []; }
      Array.prototype.slice.call(p.childNodes).forEach(function (n) {
        if (n.nodeType === 1) { cur.push(n); return; }
        if (n.nodeType !== 3) return;
        var text = n.textContent;
        if (/^\s*\//.test(text)) { flush(); text = text.replace(/^\s*\/\s*/, ""); }
        if (text.trim()) cur.push(document.createTextNode(text.replace(/\s+$/, "")));
      });
      flush();
      if (!crumbs.length) return;
      var nav = document.createElement("nav");
      nav.className = "breadcrumbs";
      nav.setAttribute("aria-label", "مسیر صفحه");
      var ol = document.createElement("ol");
      crumbs.forEach(function (nodes, i) {
        var li = document.createElement("li");
        var last = i === crumbs.length - 1;
        if (last) li.setAttribute("aria-current", "page");
        // <bdi>: a Latin or digit-bearing record name must not reorder its neighbours.
        var holder = last && nodes.every(function (n) { return n.nodeType === 3; }) ? document.createElement("bdi") : li;
        nodes.forEach(function (n) { holder.appendChild(n); });
        if (holder !== li) li.appendChild(holder);
        ol.appendChild(li);
      });
      nav.appendChild(ol);
      p.parentNode.replaceChild(nav, p);
    });
  }

  // ------------------------------------------------ term help
  // `<abbr class="term" tabindex="0" data-tip="...">` shows a short explanation on hover, keyboard
  // focus and phone tap (tabindex makes a tap focus it). One shared bubble, fixed-positioned so a
  // scrolling table card cannot clip it; Esc, blur and scroll close it.
  var TERMS = {
    "FIFO": "هر فروش از قدیمی‌ترین خریدِ باقی‌مانده کسر می‌شود؛ بهای همان خرید، بهای تمام‌شدهٔ فروش است."
  };
  var termPattern = new RegExp("\\b(" + Object.keys(TERMS).join("|") + ")\\b");

  // Known jargon in running text becomes a term without every template repeating the markup.
  function upgradeTerms(scope) {
    var host = scope.nodeType === 9 ? scope.querySelector("main.content") : scope;
    if (!host || !host.ownerDocument) return;
    var hits = [];
    var walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT, null);
    while (walker.nextNode()) {
      var n = walker.currentNode;
      if (!termPattern.test(n.nodeValue)) continue;
      var parent = n.parentNode;
      if (parent.closest && parent.closest("a, button, abbr, label, option, select, textarea, script, style, .term, [data-no-term]")) continue;
      hits.push(n);
    }
    hits.forEach(function (n) {
      var parts = n.nodeValue.split(termPattern);       // odd indexes are the matched terms
      var frag = document.createDocumentFragment();
      parts.forEach(function (part, i) {
        if (i % 2 === 0) { if (part) frag.appendChild(document.createTextNode(part)); return; }
        var abbr = document.createElement("abbr");
        abbr.className = "term";
        abbr.tabIndex = 0;
        abbr.setAttribute("data-tip", TERMS[part]);
        abbr.textContent = part;
        frag.appendChild(abbr);
      });
      n.parentNode.replaceChild(frag, n);
    });
  }

  var tip = null, tipFor = null;
  function hideTip() {
    if (!tip) return;
    if (tipFor) tipFor.removeAttribute("aria-describedby");
    tip.remove();
    tip = tipFor = null;
  }
  function showTip(el) {
    hideTip();
    tip = document.createElement("div");
    tip.className = "term-tip";
    tip.id = "term-tip";
    tip.setAttribute("role", "tooltip");
    tip.textContent = el.getAttribute("data-tip");
    document.body.appendChild(tip);
    tipFor = el;
    el.setAttribute("aria-describedby", "term-tip");
    var r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.min(Math.max(16, r.left + r.width / 2 - w / 2), window.innerWidth - w - 16);
    var top = r.top - h - 8;
    if (top < 8) top = r.bottom + 8;                 // no room above: flip below
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }
  function termOf(e) { return e.target.closest ? e.target.closest(".term[data-tip]") : null; }
  document.addEventListener("mouseover", function (e) { var t = termOf(e); if (t && t !== tipFor) showTip(t); });
  document.addEventListener("mouseout", function (e) { if (termOf(e)) hideTip(); });
  document.addEventListener("focusin", function (e) { var t = termOf(e); if (t) showTip(t); });
  document.addEventListener("focusout", hideTip);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideTip(); });
  window.addEventListener("scroll", hideTip, true);
})();

/* Presentation-only touches (css_foundation): colour money cells, name clipped text, fit big
   figures into their card. Nothing here changes a value; it only adds classes, titles and sizes. */
(function () {
  "use strict";

  function all(root, selector) {
    var scope = root && root.querySelectorAll ? root : document;
    var list = Array.prototype.slice.call(scope.querySelectorAll(selector));
    if (scope.matches && scope.matches(selector)) list.push(scope);
    return list;
  }

  // Quiet zeros and flag negatives in table money cells; the text itself is untouched.
  var ZERO = /^[\u06F0\u0660]\s*\u062A\u0648\u0645\u0627\u0646$/;      // "0 Toman" in Persian or Arabic-Indic digits
  var NEG = /^\u2066?[-\u2212]/;                                           // leading minus (the filter wraps it in LRI)
  function markMoney(root) {
    all(root, "td.num").forEach(function (td) {
      var t = td.textContent.replace(/\s+/g, " ").trim();
      td.classList.toggle("is-zero", ZERO.test(t));
      td.classList.toggle("is-neg", NEG.test(t));
    });
  }

  // A select clips a long label; the full text stays reachable as a tooltip / long-press.
  function titleSelect(select) {
    var option = select.options[select.selectedIndex];
    var text = option && select.value !== "" ? option.textContent.trim() : "";
    if (text) { select.title = text; select.setAttribute("data-auto-title", ""); }
    else if (select.hasAttribute("data-auto-title")) { select.removeAttribute("title"); select.removeAttribute("data-auto-title"); }
  }
  function titleSelects(root) {
    all(root, "select").forEach(function (select) {
      if (select.title && !select.hasAttribute("data-auto-title")) return;   // someone wrote a real title
      titleSelect(select);
    });
  }
  document.addEventListener("change", function (e) {
    if (e.target && e.target.tagName === "SELECT" && (!e.target.title || e.target.hasAttribute("data-auto-title"))) titleSelect(e.target);
  });

  // The phone header ellipsises the page title; keep the whole text reachable.
  function titleHeader() {
    var h = document.querySelector(".header__title");
    if (!h) return;
    if (h.scrollWidth > h.clientWidth + 1) h.title = h.textContent.replace(/\s+/g, " ").trim();
    else if (h.hasAttribute("data-auto-title")) h.removeAttribute("title");
    if (h.title) h.setAttribute("data-auto-title", "");
  }

  // A table card that scrolls sideways must be reachable and named for keyboard and screen-reader users.
  function markScrollRegions(root) {
    all(root, ".table-card").forEach(function (card) {
      if (card.scrollWidth <= card.clientWidth + 1) return;
      if (!card.hasAttribute("tabindex")) card.tabIndex = 0;
      if (!card.hasAttribute("role")) card.setAttribute("role", "region");
      if (!card.hasAttribute("aria-label")) {
        var host = card.closest(".card") || card.parentNode;
        var heading = host && host.querySelector("h1, h2, h3");
        card.setAttribute("aria-label", heading ? heading.textContent.replace(/\s+/g, " ").trim() : "جدول");
      }
    });
  }

  // A figure wider than its card shrinks to fit (never clips money); the full text goes in a title.
  var MIN_FIGURE = 12;
  function fitFigure(el) {
    if (el.hasAttribute("data-fitted")) { el.removeAttribute("data-fitted"); el.removeAttribute("title"); }
    el.style.fontSize = "";
    el.style.whiteSpace = "";
    if (!el.clientWidth) return;                  // hidden or not a block: nothing to measure
    var size = parseFloat(getComputedStyle(el).fontSize);
    var start = size;
    while (el.scrollWidth > el.clientWidth + 1 && size > MIN_FIGURE) {
      size -= 0.5;
      el.style.fontSize = size + "px";
    }
    if (size < start) {
      el.setAttribute("data-fitted", "");
      if (!el.title) el.title = el.textContent.replace(/\s+/g, " ").trim();
    }
    if (el.scrollWidth > el.clientWidth + 1) el.style.whiteSpace = "normal";   // last resort: wrap rather than clip
  }
  function fitFigures(root) {
    all(root, ".stat-card__value").forEach(fitFigure);
  }
  var observed = [];
  function observeStats(root) {
    if (!window.ResizeObserver) return;
    all(root, ".stats").forEach(function (grid) {
      if (observed.indexOf(grid) !== -1) return;
      observed.push(grid);
      var last = grid.clientWidth;
      // Width only: refitting changes heights, which must not trigger another round.
      new ResizeObserver(function () {
        if (Math.abs(grid.clientWidth - last) < 1) return;
        last = grid.clientWidth;
        fitFigures(grid);
      }).observe(grid);
    });
  }

  function refresh(root) {
    markMoney(root);
    titleSelects(root);
    markScrollRegions(root);
    fitFigures(root);
    observeStats(root);
  }

  function start() {
    refresh(document);
    titleHeader();
  }
  function startAfterFonts() {
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { fitFigures(document); markScrollRegions(document); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { start(); startAfterFonts(); });
  else { start(); startAfterFonts(); }

  document.body.addEventListener("htmx:afterSwap", function (e) { refresh(e.target); });

  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () { titleHeader(); markScrollRegions(document); }, 200);
  });

  // Esc closes an open inline form (receivables rows) so a forgotten panel does not keep its row blown up.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || e.defaultPrevented) return;
    var open = e.target && e.target.closest ? e.target.closest(".quick-party-disclosure[open]") : null;
    if (!open || open.closest("dialog[open]")) return;
    open.open = false;
    var summary = open.querySelector("summary");
    if (summary) summary.focus();
  });
})();

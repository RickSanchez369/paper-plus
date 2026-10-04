/*
 * Sign-in niceties (the page loads no other script): a show/hide control for the
 * password, a warning for the two silent causes of a wrong password (Caps Lock,
 * Persian keyboard layout), focus on the field that still needs input after a
 * failed attempt, and one POST per attempt.
 *
 * Every wrong password counts toward the 5-try lock (apps/users/throttle.py), so
 * catching the usual slips before the submit matters. Nothing here changes what
 * is posted; with JavaScript off the form works exactly as before.
 */
(function () {
  "use strict";

  var reveal = document.querySelector("[data-password-reveal]");
  var input = reveal ? document.getElementById(reveal.getAttribute("aria-controls")) : null;
  if (!input) return;

  var hint = document.querySelector("[data-password-hint]");
  var form = input.form;
  var user = form ? form.querySelector('input[name="username"]') : null;
  // Persian/Arabic letters and digits: never part of a Latin password typed on the wrong layout.
  var PERSIAN = /[\u0600-\u06ff]/;

  function say(text) {
    hint.textContent = text || "";
    hint.hidden = !text;
  }

  // After a failed attempt Django keeps the phone and clears the password: go to the password
  // (autofocus on the phone box stays as the no-JS default).
  if (user && user.value.trim() && input.value === "") input.focus();

  reveal.addEventListener("click", function () {
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    reveal.textContent = show ? "پنهان" : "نمایش";
    reveal.setAttribute("aria-pressed", show ? "true" : "false");
    input.focus();
  });

  input.addEventListener("keydown", function (e) {
    if (e.getModifierState && e.getModifierState("CapsLock")) {
      say("Caps Lock روشن است.");
    } else if (e.key && e.key.length === 1 && PERSIAN.test(e.key)) {
      say("صفحه‌کلید روی فارسی است؛ برای گذرواژه به انگلیسی برگردید (Alt+Shift).");
    } else {
      say("");
    }
  });
  input.addEventListener("blur", function () { say(""); });

  // One POST per attempt: a double click must not count as two failures.
  if (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector('button[type="submit"]');
      if (!button) return;
      var label = button.textContent;
      // After the submit has started, or the browser would skip a disabled button's own submit.
      setTimeout(function () {
        button.disabled = true;
        button.textContent = form.getAttribute("data-busy-label") || label;
      }, 0);
      // Back button (bfcache) must not bring back a dead button.
      window.addEventListener("pageshow", function () {
        button.disabled = false;
        button.textContent = label;
      }, { once: true });
    });
  }
})();

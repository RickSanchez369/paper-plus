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
})();

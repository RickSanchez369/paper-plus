/*
 * The menu drawer: closed by default, opened by the header's hamburger,
 * closed again by the overlay, the X, Esc, or following a link. No state is
 * kept between pages (a fresh page always starts closed).
 */
(function () {
  var body = document.body;
  var nav = document.getElementById("site-nav");
  var overlay = document.querySelector(".nav-overlay");
  var opener = document.querySelector("[data-nav-open]");
  if (!nav || !overlay || !opener) return;

  function setOpen(open) {
    body.classList.toggle("nav-open", open);
    nav.setAttribute("aria-hidden", open ? "false" : "true");
    // The drawer is modal in practice: the page behind it must not be tabbable or readable.
    var main = document.querySelector(".main");
    if (main) main.inert = open;
    opener.setAttribute("aria-expanded", open ? "true" : "false");
    // The scrim fades through body.nav-open in CSS; toggling `hidden` here would
    // cut the transition (display:none cannot animate).
    if (open) {
      var first = nav.querySelector(".nav-link, .sidebar__brand");
      if (first) first.focus({ preventScroll: true });
    } else {
      opener.focus({ preventScroll: true });
    }
  }

  // Back/forward can restore the page with the drawer still marked open.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted && body.classList.contains("nav-open")) setOpen(false);
  });

  opener.addEventListener("click", function () {
    setOpen(!body.classList.contains("nav-open"));
  });
  document.querySelectorAll("[data-nav-close]").forEach(function (el) {
    el.addEventListener("click", function () { setOpen(false); });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && body.classList.contains("nav-open")) setOpen(false);
  });
})();

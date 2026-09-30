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
    opener.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      overlay.hidden = false;
      var first = nav.querySelector(".nav-link, .sidebar__brand");
      if (first) first.focus({ preventScroll: true });
    } else {
      overlay.hidden = true;
      opener.focus({ preventScroll: true });
    }
  }

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

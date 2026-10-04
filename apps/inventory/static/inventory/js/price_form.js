/*
 * Price assistant for the product detail page: a live before -> after read-back
 * (carton equivalent, change, margin against the FIFO cost), "carton follows
 * retail", and one-tap percent raises. Display and convenience only: the POST,
 * its blank = leave alone / 0 = unset rules and every server check are unchanged.
 */
(function () {
  "use strict";

  var f = document.getElementById("price-form");
  if (!f) return;
  var retail = f.querySelector('[name="default_selling_price"]');
  var whole = f.querySelector('[name="wholesale_selling_price"]');
  var auto = document.getElementById("wholesale-auto");
  var box = document.getElementById("price-preview");
  var note = document.getElementById("price-note");
  var warn = document.getElementById("price-warn");
  var save = document.getElementById("price-save");
  if (!retail || !whole || !auto || !box || !note || !warn || !save) return;

  var pack = parseInt(f.dataset.pack, 10) || 1;
  var oldRetail = parseInt(f.dataset.oldRetail, 10) || 0;
  var oldCarton = parseInt(f.dataset.oldCarton, 10) || 0;
  var cost = f.dataset.cost === "" || f.dataset.cost === undefined ? null : parseInt(f.dataset.cost, 10);
  var unset = f.dataset.wholesaleUnset === "1";
  var fa = new Intl.NumberFormat("fa-IR");
  var defaultLabel = save.textContent;
  var confirmed = false;

  // Auto mode submits 0 (= "unset", follows the retail price) instead of the disabled box.
  var zero = document.createElement("input");
  zero.type = "hidden";
  zero.name = "wholesale_selling_price";
  zero.value = "0";

  function toman(n) { return fa.format(n) + " تومان"; }

  // ui.js already turns Persian digits into Latin ones; blank = leave that price alone.
  function val(el) {
    var s = String(el.value).replace(/[^0-9]/g, "");
    return s === "" ? null : parseInt(s, 10);
  }

  function margin(price, c) {
    if (!price || c === null || price < c) return "";
    return fa.format(Math.round((price - c) / price * 100)) + "٪";
  }

  function delta(el, a, b) {
    var d = b - a;
    el.className = "price-preview__delta num" + (d > 0 ? " is-up" : d < 0 ? " is-down" : "");
    el.textContent = d === 0 ? "بدون تغییر"
      : (d > 0 ? "+" : "−") + fa.format(Math.abs(d)) + (a ? " (" + fa.format(Math.round(Math.abs(d) / a * 100)) + "٪)" : "");
  }

  function row(name, oldV, newV) {
    var r = box.querySelector('[data-row="' + name + '"]');
    r.querySelector(".price-preview__old").textContent = toman(oldV);
    r.querySelector(".price-preview__new").textContent = toman(newV);
    delta(r.querySelector(".price-preview__delta"), oldV, newV);
  }

  function sync() {
    var r = val(retail);
    var newRetail = r === null ? oldRetail : r;
    if (auto.checked) {
      whole.disabled = true;
      whole.value = newRetail * pack;
      if (!zero.parentNode) f.appendChild(zero);
    } else {
      whole.disabled = false;
      if (zero.parentNode) zero.parentNode.removeChild(zero);
    }
    var w = val(whole);
    var newCarton = auto.checked ? newRetail * pack
      : w === null ? (unset ? newRetail * pack : oldCarton)
      : w > 0 ? w : newRetail * pack;

    confirmed = false;
    save.textContent = defaultLabel;

    var changed = newRetail !== oldRetail || newCarton !== oldCarton;
    box.hidden = !changed;
    if (!changed) { warn.hidden = true; return; }

    row("retail", oldRetail, newRetail);
    row("carton", oldCarton, newCarton);
    var text = (auto.checked || (w === null && unset))
      ? "قیمت کارتن همراه قیمت بسته است: " + fa.format(pack) + " × " + fa.format(newRetail) + " = " + toman(newCarton)
      : "هر کارتن معادل " + toman(Math.round(newCarton / pack)) + " برای هر بسته (" + fa.format(pack) + " بسته).";
    var m = cost === null ? "" : margin(newRetail, cost);
    if (m) text += " · حاشیه سود خرد نسبت به بهای FIFO: " + m;
    note.textContent = text;

    // Only what the person is changing is flagged, and never blocked: below-cost sales are legal.
    var msgs = [];
    if (newRetail !== oldRetail) {
      if (newRetail === 0) msgs.push("قیمت خرد صفر است؛ کالا رایگان فروخته می‌شود.");
      else if (cost !== null && newRetail < cost) msgs.push("قیمت خرد از بهای لایهٔ بعدی (" + toman(cost) + ") کمتر است؛ فروش بعدی با زیان ثبت می‌شود.");
      if (oldRetail > 0 && newRetail > 0 && (newRetail > oldRetail * 3 || newRetail * 3 < oldRetail)) {
        msgs.push("تغییر قیمت خرد بیش از ۳ برابر است؛ تعداد صفرها را بررسی کنید.");
      }
    }
    if (newCarton !== oldCarton && cost !== null && newCarton > 0 && newCarton < cost * pack) {
      msgs.push("قیمت کارتن از بهای " + fa.format(pack) + " بسته (" + toman(cost * pack) + ") کمتر است.");
    }
    warn.hidden = !msgs.length;
    warn.textContent = msgs.join(" ");
  }

  // Round to about three significant digits so the numbers stay clean (250000 -> 1000s, 2500 -> 10s).
  function scale(v, k) {
    var step = Math.pow(10, Math.max(String(v).length - 3, 0));
    return Math.round(v * k / step) * step;
  }

  f.querySelectorAll("[data-pct]").forEach(function (b) {
    b.addEventListener("click", function () {
      var k = 1 + parseInt(b.getAttribute("data-pct"), 10) / 100;
      var r = val(retail);
      retail.value = scale(r === null ? oldRetail : r, k);
      if (!auto.checked) {
        var w = val(whole);
        var base = w === null ? oldCarton : w;
        if (base > 0) whole.value = scale(base, k);
      }
      sync();
    });
  });

  [retail, whole, auto].forEach(function (el) {
    el.addEventListener("input", sync);
    el.addEventListener("change", sync);
  });

  // The first submit with a warning shows it (already visible) and asks again; the second goes through.
  f.addEventListener("submit", function (e) {
    if (!warn.hidden && !confirmed) {
      e.preventDefault();
      confirmed = true;
      save.textContent = "با همین قیمت‌ها ذخیره شود";
      warn.scrollIntoView({ block: "nearest" });
    }
  });

  // The assistant is an enhancement: its controls stay hidden without JS.
  f.querySelectorAll(".price-chips, .price-auto").forEach(function (el) { el.hidden = false; });
  sync();
  confirmed = false;

  // Arriving from the list's "تغییر قیمت‌ها" link: ready to type (not on touch, where it would pop the keyboard).
  if (location.hash === "#selling-price" && window.matchMedia && window.matchMedia("(pointer: fine)").matches) {
    retail.focus();
    retail.select();
  }
})();

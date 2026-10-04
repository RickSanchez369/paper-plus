/*
 * Live read-back of the new-product form: packaging, prices and the one-time
 * opening stock. Display only -- the server redoes every number on submit and
 * stays the authority. Only digits formatted here ever reach innerHTML.
 */
(function () {
  "use strict";

  var U = window.PaperUnits;
  var form = document.getElementById("product-form");
  var list = document.getElementById("product-summary");
  var btn = document.getElementById("product-submit");
  if (!form || !list || !btn || !U) return;
  var box = list.parentNode;

  // ui.js already turns Persian digits into Latin ones as they are typed.
  function num(name) {
    var el = form.elements[name];
    if (!el) return null;
    var v = parseInt(String(el.value).replace(/[^0-9]/g, ""), 10);
    return isNaN(v) ? null : v;
  }

  function n(v) { return v.toLocaleString("fa-IR"); }
  function toman(v) { return n(v) + " تومان"; }

  function render() {
    var ratio = Math.max(num("pack_per_carton") || 1, 1);
    var pack = num("default_selling_price");
    var carton = num("wholesale_selling_price");
    var oc = num("opening_cartons") || 0;
    var op = num("opening_packs") || 0;
    var cost = num("opening_unit_cost");
    var qty = oc * ratio + op;
    var rows = [];

    function add(text, cls) {
      rows.push("<li" + (cls ? ' class="' + cls + '"' : "") + ">" + text + "</li>");
    }

    add("بسته‌بندی: هر کارتن = <b>" + U.fa(ratio) + " بسته</b>");
    if (pack) add("قیمت فروش خرد: <b>" + toman(pack) + "</b> برای هر بسته");
    if (pack && !carton) {
      add("قیمت کارتن خودکار: " + n(ratio) + " × " + n(pack) + " = <b>" + toman(pack * ratio) + "</b>");
    } else if (carton) {
      add("قیمت فروش عمده: <b>" + toman(carton) + "</b> برای هر کارتن");
      if (pack && carton > pack * ratio) {
        add("قیمت کارتن از " + n(ratio) + " بستهٔ جدا گران‌تر است؛ مطمئنید؟", "is-warn");
      }
    }

    if (qty) {
      var line = "موجودی اولیه: <b>" + U.phrase(qty, ratio) + "</b>";
      if (cost !== null) line += " — ارزش انبار <b>" + toman(qty * cost) + "</b> (بها × تعداد بسته)";
      add(line);
      if (ratio > 1 && op >= ratio) {
        add("بسته‌های آزاد از یک کارتن بیشتر است؛ به‌صورت " + U.phrase(qty, ratio) + " ذخیره می‌شود.");
      }
      if (cost === null) {
        add("بهای خرید <b>هر بسته</b> را هم بنویسید تا ارزش انبار حساب شود.", "is-warn");
      } else if (pack && cost > pack) {
        add("بهای خرید هر بسته از قیمت فروش آن بیشتر است؛ بها باید برای یک <b>بسته</b> باشد، نه یک کارتن.", "is-warn");
      }
    } else if (cost !== null) {
      add("بها بدون مقدار موجودی ثبت نمی‌شود؛ تعداد کارتن یا بسته را بنویسید.", "is-warn");
    } else {
      add("بدون موجودی اولیه؛ موجودی با اولین فاکتور خرید ساخته می‌شود.", "is-muted");
    }

    list.innerHTML = rows.join("");
    box.hidden = false;
    // The button names the effect: opening stock is a one-time, hard-to-undo entry.
    btn.textContent = qty ? "ثبت کالا با موجودی اولیهٔ " + U.fa(qty) + " بسته" : btn.getAttribute("data-default-label");
  }

  form.addEventListener("input", render);
  render();
})();

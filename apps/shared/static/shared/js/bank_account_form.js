/*
 * Bank-account form: a live preview of the card the account will get on the list
 * page, a sentence saying where each type can be chosen, and Persian digits in
 * the account number folded to Latin so the unique check sees what the owner
 * sees. Presentation only; the server still validates every field.
 */
(function () {
  "use strict";

  var root = document.querySelector("[data-bank-form]");
  if (!root) return;

  var TYPES = {
    pos: {
      group: "کارت‌خوان",
      submit: "ثبت کارت‌خوان",
      effect: "از این پس در فروش و دریافت، گزینهٔ «کارت‌خوان» می‌تواند به این حساب واریز کند. برای پرداخت به تأمین‌کننده یا هزینه قابل انتخاب نیست."
    },
    current: {
      group: "حساب جاری",
      submit: "ثبت حساب جاری",
      effect: "از این پس برای حواله، چک و پرداخت به تأمین‌کننده و هزینه‌ها قابل انتخاب است. در گزینهٔ «کارت‌خوان» نمی‌آید."
    }
  };
  var FA = "۰۱۲۳۴۵۶۷۸۹";
  var AR = "٠١٢٣٤٥٦٧٨٩";

  function part(key) { return root.querySelector('[data-pv="' + key + '"]'); }
  function control(name) { return root.elements ? root.elements[name] : root.querySelector('[name="' + name + '"]'); }

  function latin(text) {
    return text.replace(/[۰-۹٠-٩]/g, function (c) {
      var i = FA.indexOf(c);
      return String(i > -1 ? i : AR.indexOf(c));
    });
  }

  function sync() {
    var checked = root.querySelector('input[name="account_type"]:checked');
    var type = TYPES[checked ? checked.value : "current"] || TYPES.current;
    var name = control("name").value.trim();
    var owner = control("owner").value.trim();
    var number = control("account_number").value.trim();

    part("group").textContent = type.group;
    part("effect").textContent = type.effect;
    part("name").textContent = name || "نام حساب";
    part("owner").textContent = owner;
    part("owner-wrap").hidden = !owner;
    part("number").textContent = number || "—";

    // Only the create page names the button after the type; edit keeps "ذخیره".
    var button = part("submit");
    if (button && button.textContent.indexOf("ثبت") === 0) button.textContent = type.submit;
  }

  root.addEventListener("input", function (event) {
    if (event.target.name === "account_number") {
      var fixed = latin(event.target.value);
      if (fixed !== event.target.value) event.target.value = fixed;
    }
    sync();
  });
  root.addEventListener("change", sync);
  sync();
})();

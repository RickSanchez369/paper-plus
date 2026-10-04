/*
 * Localised file picker (receipt on the expense form). The native <input type="file">
 * stays in the DOM, visually hidden but focusable, so the form post, enctype,
 * validation and keyboard use are unchanged; this only replaces the browser's English
 * "Choose File / No file chosen" chrome with Persian text, a file name, the size, a
 * clear action and drag-and-drop. Delegated enhancement: inputs that arrive later in an
 * htmx swap are picked up too.
 */
(function () {
  "use strict";

  function fa(n) {
    return String(n).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹".charAt(d); });
  }

  function sizeText(bytes) {
    if (bytes < 1024 * 1024) return fa(Math.max(1, Math.round(bytes / 1024))) + " کیلوبایت";
    return fa((bytes / 1048576).toFixed(1).replace(".", "٫")) + " مگابایت";
  }

  function enhance(input) {
    // Without an id the <label for> could not open the picker; leave such an input native.
    if (input.getAttribute("data-filepick") || !input.id) return;
    input.setAttribute("data-filepick", "1");

    var box = document.createElement("div");
    box.className = "filepick";
    var button = document.createElement("label");
    button.className = "btn btn--quiet filepick__btn";
    button.setAttribute("for", input.id);
    button.textContent = "انتخاب فایل";
    var name = document.createElement("span");
    name.className = "filepick__name";
    name.setAttribute("aria-live", "polite");
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "filepick__clear";
    clear.hidden = true;
    clear.setAttribute("aria-label", "حذف فایل انتخاب‌شده");
    clear.textContent = "×";

    input.parentNode.insertBefore(box, input);
    input.classList.add("filepick__input");
    box.append(input, button, name, clear);

    function render() {
      var file = input.files && input.files[0];
      box.classList.toggle("is-filled", !!file);
      clear.hidden = !file;
      name.textContent = "";
      if (!file) { name.textContent = "فایلی انتخاب نشده"; return; }
      // <bdi>: a Latin file name must not scramble its punctuation inside the RTL line.
      var label = document.createElement("bdi");
      label.textContent = file.name;
      var small = document.createElement("small");
      small.textContent = " · " + sizeText(file.size);
      name.append(label, small);
    }

    input.addEventListener("change", render);
    clear.addEventListener("click", function () {
      input.value = "";
      render();
      input.focus();
    });

    // Drop a receipt photo straight onto the box.
    ["dragenter", "dragover"].forEach(function (type) {
      box.addEventListener(type, function (e) { e.preventDefault(); box.classList.add("is-drag"); });
    });
    ["dragleave", "drop"].forEach(function (type) {
      box.addEventListener(type, function () { box.classList.remove("is-drag"); });
    });
    box.addEventListener("drop", function (e) {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        // The server validates type and size; tell any listener the value changed.
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    render();
  }

  function enhanceAll(root) {
    root.querySelectorAll('input[type="file"]').forEach(enhance);
  }

  document.addEventListener("DOMContentLoaded", function () { enhanceAll(document); });
  document.body.addEventListener("htmx:afterSwap", function (e) { if (e.target.querySelectorAll) enhanceAll(e.target); });
})();

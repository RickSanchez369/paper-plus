/*
 * Carton + pack wording for the invoice forms (D-081). Stock and every
 * stored quantity are in packs; a carton is `ratio` packs. This only builds
 * the text people read ("۶ کارتن + ۴ بسته (۳۴ بسته)") and does the same
 * arithmetic the server redoes on submit; it never decides anything.
 */
(function () {
  "use strict";

  function fa(value) {
    return String(value).replace(/[0-9]/g, function (d) {
      return String.fromCharCode(0x06f0 + Number(d));
    });
  }

  function split(quantity, ratio) {
    var r = Math.max(parseInt(ratio, 10) || 1, 1);
    var q = parseInt(quantity, 10) || 0;
    var sign = q < 0 ? -1 : 1;
    q = Math.abs(q);
    return { cartons: sign * Math.floor(q / r), packs: sign * (q % r) };
  }

  // "۶ کارتن + ۴ بسته", zero parts left out; "(۳۴ بسته)" appended once cartons are involved.
  function phrase(quantity, ratio) {
    // Oversold stock reads «منفی ۲ کارتن + ۴ بسته»: a minus before each part flips in an RTL run.
    if (parseInt(quantity, 10) < 0) return "منفی " + phrase(-parseInt(quantity, 10), ratio);
    var s = split(quantity, ratio);
    var parts = [];
    if (s.cartons) parts.push(fa(s.cartons) + " کارتن");
    if (s.packs || !s.cartons) parts.push(fa(s.packs) + " بسته");
    var text = parts.join(" + ");
    if (s.cartons) text += " (" + fa(parseInt(quantity, 10)) + " بسته)";
    return text;
  }

  window.PaperUnits = { fa: fa, split: split, phrase: phrase };
})();

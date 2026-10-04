/*
 * Jalali date picker for inputs carrying .js-jalali-date.
 *
 * Deliberately contains NO calendar arithmetic. An earlier version did, and
 * its leap-year rule disagreed with jdatetime's: the calendar offered
 * 30 Esfand 1404, which the server then refused to parse, while hiding
 * 30 Esfand 1403, which is real. Every month now comes from
 * /date-picker/month/ already rendered, and each day carries the exact
 * string the form field parses — so what you can click and what the server
 * accepts cannot drift apart. Caught in the browser; no backend check could
 * have seen it.
 *
 * What is left here is presentation only: open, close, position, and write
 * the chosen value back. Month navigation is integer arithmetic on
 * year/month, which the server clamps and rolls over.
 *
 * Progressive: the input is a plain text box that already accepts a typed
 * date. This only adds a calendar for people who would rather click.
 * Binding is delegated from the document, so inputs that arrive later in an
 * htmx swap work with no re-initialisation.
 */
(function () {
    "use strict";

    var ENDPOINT = "/date-picker/month/";

    var popup = null;
    var activeInput = null;
    var pending = null;
    // The month last asked for. Clicks arriving before the previous month
    // has finished loading must compound, not all step from the old grid.
    var view = null;

    function buildPopup() {
        var element = document.createElement("div");
        element.className = "jdp";
        element.setAttribute("dir", "rtl");
        element.hidden = true;
        element.addEventListener("mousedown", function (event) {
            // Keep focus on the input, so blur does not close us mid-click.
            event.preventDefault();
        });
        element.addEventListener("click", onPopupClick);
        document.body.appendChild(element);
        return element;
    }

    /* Pull year/month out of whatever is typed, without judging whether it
       is a real date -- the server decides that. */
    function readYearMonth(text) {
        var ascii = String(text || "").replace(/[۰-۹٠-٩]/g, function (digit) {
            var code = digit.charCodeAt(0);
            return String(code >= 0x06f0 ? code - 0x06f0 : code - 0x0660);
        });
        var match = ascii.match(/^\s*(\d{4})\s*[/\-.]\s*(\d{1,2})/);
        return match ? { year: +match[1], month: +match[2] } : null;
    }

    function currentGrid() {
        return popup.querySelector(".jdp__grid");
    }

    function load(year, month) {
        var url = ENDPOINT + "?year=" + year + "&month=" + month;
        // A stale response must not overwrite a newer one when someone
        // clicks through months quickly.
        var token = {};
        pending = token;
        return fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(function (response) {
                return response.ok ? response.text() : null;
            })
            .then(function (html) {
                if (pending !== token || html === null) return;
                popup.innerHTML = html;
                markSelected();
                position();
            })
            .catch(function () {
                /* Silent: the input still accepts a typed date. */
            });
    }

    function markSelected() {
        if (!activeInput || !activeInput.value) return;
        var wanted = activeInput.value.trim();
        popup.querySelectorAll("[data-value]").forEach(function (cell) {
            if (cell.getAttribute("data-value") === wanted) {
                cell.classList.add("is-selected");
            }
        });
    }

    function onPopupClick(event) {
        var target = event.target.closest("[data-jdp]");
        if (!target || !activeInput) return;
        var action = target.getAttribute("data-jdp");

        if (action === "prev" || action === "next") {
            var grid = currentGrid();
            if (!grid && !view) return;
            var base = view || {
                year: Number(grid.getAttribute("data-year")),
                month: Number(grid.getAttribute("data-month")),
            };
            var year = base.year;
            var month = base.month + (action === "prev" ? -1 : 1);
            if (month > 12) { month = 1; year += 1; }
            if (month < 1) { month = 12; year -= 1; }
            view = { year: year, month: month };
            load(year, month);
            return;
        }

        if (action === "today") {
            var today = popup.querySelector(".is-today");
            if (today) {
                commit(today.getAttribute("data-value"));
            } else {
                // Today is in another month; fetch the default month, which
                // is today's, then take it from there.
                load("", "").then(function () {
                    var cell = popup.querySelector(".is-today");
                    if (cell) commit(cell.getAttribute("data-value"));
                });
            }
            return;
        }

        if (action === "clear") {
            activeInput.value = "";
            activeInput.dispatchEvent(new Event("change", { bubbles: true }));
            close();
            return;
        }

        if (action === "day") {
            commit(target.getAttribute("data-value"));
        }
    }

    function commit(value) {
        activeInput.value = value;
        // Bubbles, so htmx triggers and any live-total listener see it.
        activeInput.dispatchEvent(new Event("change", { bubbles: true }));
        close();
    }

    function position() {
        if (!activeInput) return;
        var box = activeInput.getBoundingClientRect();
        // Flip above the input when there is no room below (bottom of a long form, phone keyboard).
        var below = window.innerHeight - box.bottom;
        var flip = below < popup.offsetHeight + 8 && box.top > popup.offsetHeight + 8;
        popup.style.top = window.scrollY + (flip ? box.top - popup.offsetHeight - 4 : box.bottom + 4) + "px";
        // RTL: align the popup's right edge with the input's right edge, then
        // pull it back inside the viewport if it would hang off the left.
        var left = window.scrollX + box.right - popup.offsetWidth;
        popup.style.left = Math.max(window.scrollX + 8, left) + "px";
    }

    function open(input) {
        if (!popup) popup = buildPopup();
        activeInput = input;
        view = null;
        popup.hidden = false;
        var parts = readYearMonth(input.value);
        load(parts ? parts.year : "", parts ? parts.month : "");
    }

    function close() {
        if (popup) popup.hidden = true;
        activeInput = null;
        pending = null;
    }

    function isDateInput(element) {
        return element && element.classList && element.classList.contains("js-jalali-date");
    }

    document.addEventListener("focusin", function (event) {
        if (isDateInput(event.target)) {
            open(event.target);
        } else if (popup && !popup.hidden && !popup.contains(event.target)) {
            close();
        }
    });

    document.addEventListener("click", function (event) {
        // The input keeps focus after a pick or Esc, so focusin never fires again:
        // a click on an already-focused date box must reopen the calendar.
        if (isDateInput(event.target)) {
            if (!popup || popup.hidden) open(event.target);
            return;
        }
        if (!popup || popup.hidden) return;
        if (popup.contains(event.target)) return;
        close();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && popup && !popup.hidden) {
            close();
        } else if (event.key === "ArrowDown" && isDateInput(event.target) && (!popup || popup.hidden)) {
            open(event.target);
            event.preventDefault();
        }
    });

    // Follow the input rather than closing. Closing on any scroll loses the
    // calendar the moment a long form is scrolled, which is the case where
    // a picker is most wanted.
    function reposition() {
        if (popup && !popup.hidden) position();
    }

    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
})();

"""Page matrix: every page state x every phone viewport, ~20 checks per load (status, JS/console/network errors, overflow, tap
targets, input sizes, names and labels, contrast, bottom bars, landmarks...)."""
import pathlib

from tools.qa.mobile_suite.lib import PHONE_NAMES, Watched, run_module

METRICS = (pathlib.Path(__file__).parent / "metrics.js").read_text(encoding="utf-8")
# Known, intentional exceptions (each with its reason); a page not listed here must be clean.
ERROR_PAGES = ("404", "404-uuid")


def body(a, rec, b):
    from tools.qa.mobile_suite.pages import all_pages
    pages = all_pages()
    jobs = [(vp, label, path) for vp in PHONE_NAMES for label, path in pages]
    jobs = [j for k, j in enumerate(jobs) if k % a.n == a.i]
    if a.limit:
        jobs = jobs[:a.limit]
    ctxs, watch = {}, {}
    for vp, label, path in jobs:
        if vp not in ctxs:
            ctxs[vp] = b.context(vp)
            watch[vp] = Watched(ctxs[vp], b.base)
        w = watch[vp]
        w.drain()
        tag = f"{label}@{vp}"
        is_err = label in ERROR_PAGES
        try:
            resp = w.goto(path)
        except Exception as exc:
            rec.check("load", f"{tag} loads", False, repr(exc)[:150])
            continue
        js, con, failed = w.drain()
        want = 404 if is_err else 200
        rec.check("status", f"{tag} status {want}", resp.status == want, resp.status)
        rec.check("js", f"{tag} no JS error", not js, js)
        failed = [f for f in failed if not (is_err and f.startswith("404 GET " + path))]
        rec.check("net", f"{tag} no failed request", not failed, failed)
        con = [c for c in con if not (is_err and "404" in c)]
        rec.check("console", f"{tag} no console error", not con, con)
        try:
            m = w.page.evaluate(METRICS)
        except Exception as exc:
            rec.check("metrics", f"{tag} measurable", False, repr(exc)[:150])
            continue
        if is_err:      # DEBUG shows Django's technical 404 (no app shell); the production 404 is covered by its own module
            continue
        rec.check("overflow", f"{tag} no page overflow", m["overflow_px"] <= 0, m["overflow_px"])
        rec.check("overflow", f"{tag} nothing off the edge", not m["offscreen"], m["offscreen"])
        rec.check("meta", f"{tag} viewport meta", "width=device-width" in m["viewport_meta"], m["viewport_meta"])
        rec.check("meta", f"{tag} zoom not locked", not m["scale_locked"], m["viewport_meta"])
        rec.check("meta", f"{tag} rtl + fa", m["dir"] == "rtl" and (m["lang"] or "").startswith("fa"), (m["dir"], m["lang"]))
        rec.check("meta", f"{tag} has a title", bool(m["title"].strip()) and "{{" not in m["title"], m["title"])
        rec.check("content", f"{tag} no None/undefined/raw template", not m["junk"], m["junk"])
        rec.check("a11y", f"{tag} one main landmark", m["mains"] == 1 or is_err, m["mains"])
        rec.check("targets", f"{tag} buttons >= 44px", not m["small44"], m["small44"])
        rec.check("inputs", f"{tag} inputs >= 16px (no iOS zoom)", not m["small_inputs"], m["small_inputs"])
        rec.check("a11y", f"{tag} links/buttons have names", not m["no_name"], m["no_name"])
        rec.check("a11y", f"{tag} fields have labels", not m["no_label"], m["no_label"])
        rec.check("a11y", f"{tag} unique ids", not m["dup_ids"], m["dup_ids"])
        rec.check("a11y", f"{tag} images have alt", m["img_no_alt"] == 0, m["img_no_alt"])
        rec.check("a11y", f"{tag} no positive tabindex", m["pos_tabindex"] == 0, m["pos_tabindex"])
        rec.check("text", f"{tag} no clipped button text", not m["clipped"], m["clipped"])
        rec.check("text", f"{tag} no text under 11.5px", not m["tiny_text"], m["tiny_text"])
        rec.check("contrast", f"{tag} text contrast (solid backgrounds)", m["low_contrast_n"] == 0, m["low_contrast"])
        rec.check("bars", f"{tag} bottom bar covers no content", m["bar_cover"] == 0, m["bar_cover"])
        rec.check("text", f"{tag} header title is not cut", not m["title_cut"], m["title_cut"])
        rec.check("text", f"{tag} no number or date split across lines", not m["split_tokens"], m["split_tokens"])
        rec.check("cards", f"{tag} card cells carry no paint of their own (row tint is one block)", not m["card_notch"], m["card_notch"])


if __name__ == "__main__":
    run_module("pages", body)

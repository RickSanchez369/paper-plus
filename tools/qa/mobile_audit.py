"""Mobile scorecard: measures every page at phone widths (and desktop widths as a regression guard).

    python tools/qa/mobile_audit.py --base http://localhost:8001 --login tools/qa/.qa_login.txt --label baseline
    python tools/qa/mobile_audit.py --base http://localhost:8101 --login tools/qa/.mobile/NAME.sqlite3.login.txt \
        --widths 390 --pages /sales/new/,/receivables/

Needs `pip install playwright` (a dev tool, deliberately not in requirements.txt) and Chrome installed; it drives
the installed Chrome headless, so no browser download. It only reads pages: it never submits a form.
Output: a table on screen and tools/qa/.mobile/audit-<label>.json. Rules and the 9/10 target: docs/UI_EVOLUTION.md.
"""
import argparse
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

root = pathlib.Path(__file__).resolve().parents[2]

STATIC_PAGES = [
    "/", "/sales/", "/sales/new/", "/purchasing/", "/purchasing/new/", "/inventory/", "/inventory/products/new/",
    "/returns/", "/receivables/", "/payables/", "/cheques/", "/bank-accounts/", "/expenses/", "/expenses/new/",
    "/expenses/recurring/", "/expenses/recurring/new/", "/customers/", "/reports/", "/user-activity/", "/backup/",
]
# First detail link found on a list page: (list page, regex for the href).
DETAIL_FROM = [
    ("/sales/", r"^/sales/[0-9a-f-]{36}/$"), ("/purchasing/", r"^/purchasing/[0-9a-f-]{36}/$"),
    ("/cheques/", r"^/cheques/[0-9a-f-]{36}/$"), ("/customers/", r"^/customers/[0-9a-f-]{36}/$"),
    ("/bank-accounts/", r"^/bank-accounts/[0-9a-f-]{36}/$"), ("/inventory/", r"^/inventory/[0-9a-f-]{36}/$"),
    ("/returns/", r"^/returns/(sales|purchases)/[0-9a-f-]{36}/$"),
]

# One evaluation per page load. Counts only what a phone user can actually see and tap (closed <details> bodies,
# sr-only text and zero-size boxes are skipped: Chromium still reports rects for closed details).
METRICS_JS = r"""
() => {
  const vw = innerWidth, de = document.documentElement;
  const shown = (e) => {
    const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false;
    const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    const d = e.closest('details'); if (d && !d.open && !e.closest('summary')) return false;
    if (e.closest('[hidden],[inert]')) return false;
    return true;
  };
  const inScroller = (e) => { for (let p = e.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll') return true; } return false; };
  const off = [...document.querySelectorAll('body *')].filter(e => shown(e) && !inScroller(e)).filter(e => {
    const r = e.getBoundingClientRect(); return r.right > vw + 1 || r.left < -1; })
    .map(e => e.tagName.toLowerCase() + '.' + String(e.className).split(' ')[0]).slice(0, 5);
  const tg = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary')].filter(shown);
  const primary = tg.filter(e => e.matches('.btn,button[type=submit],summary,.nav-toggle,.cmdk-trigger'));
  const small44 = primary.filter(e => { const r = e.getBoundingClientRect(); return r.height < 44; })
    .map(e => (e.textContent || e.name || '').trim().slice(0, 14) + ' ' + Math.round(e.getBoundingClientRect().height));
  const small24 = tg.filter(e => { const r = e.getBoundingClientRect(); if (r.width >= 24 && r.height >= 24) return false;
    if (e.matches('input[type=checkbox],input[type=radio]')) { const l = e.closest('label') || document.querySelector('label[for="' + e.id + '"]');
      if (l) { const q = l.getBoundingClientRect(); return q.width < 24 || q.height < 24; } }
    if (e.tagName === 'A' && getComputedStyle(e).display === 'inline' && e.closest('p,li,td')) return false; return true; }).length;
  const smallInputs = [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=submit]):not([type=button]),select,textarea')]
    .filter(shown).filter(e => parseFloat(getComputedStyle(e).fontSize) < 16)
    .map(e => (e.name || e.id || e.type) + ' ' + getComputedStyle(e).fontSize).slice(0, 6);
  const meta = (document.querySelector('meta[name=viewport]') || {}).content || '';
  return {
    overflowX: de.scrollWidth - de.clientWidth, offenders: off,
    targets: tg.length, primaryBelow44: small44.length, primarySample: small44.slice(0, 4),
    below24: small24, inputsBelow16: smallInputs.length, inputSample: smallInputs,
    viewportFit: /viewport-fit=cover/.test(meta), manifest: !!document.querySelector('link[rel=manifest]'),
    appleIcon: !!document.querySelector('link[rel=apple-touch-icon]'),
    pageHeight: de.scrollHeight, errorPage: /OperationalError|Traceback|Server Error/.test(document.title + document.body.innerText.slice(0, 400)),
  };
}
"""


def login(page, base, phone, password):
    """Sign in through the real form (test credentials of the throwaway database only)."""
    page.goto(base + "/login/")
    page.locator("input[type=text], input[type=tel]").first.fill(phone)
    page.locator("input[type=password]").first.fill(password)
    page.locator("form button[type=submit]").first.click()
    page.wait_for_url(lambda u: "/login" not in u, timeout=10000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--login", required=True, help="file with the phone on line 1 and the password on line 2")
    ap.add_argument("--widths", default="360,390,430,1024,1440")
    ap.add_argument("--pages", default="", help="comma-separated paths; default = every page plus first detail pages")
    ap.add_argument("--label", default="audit")
    args = ap.parse_args()
    phone, password = pathlib.Path(args.login).read_text(encoding="utf-8").split()[:2]
    widths = [int(w) for w in args.widths.split(",")]
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx0 = browser.new_context()
        pg0 = ctx0.new_page()
        login(pg0, args.base, phone, password)
        pages = [x for x in args.pages.split(",") if x] or list(STATIC_PAGES)
        if not args.pages:
            for lst, rx in DETAIL_FROM:
                pg0.goto(args.base + lst)
                hrefs = pg0.eval_on_selector_all("a", "els => els.map(e => e.getAttribute('href'))")
                hit = next((h for h in hrefs if h and re.match(rx, h)), None)
                if hit:
                    pages.append(hit)
        state = ctx0.storage_state()
        ctx0.close()
        for w in widths:
            mobile = w <= 600
            ctx = browser.new_context(
                storage_state=state, viewport={"width": w, "height": 844 if mobile else 900},
                is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1)
            pg = ctx.new_page()
            for path in pages:
                try:
                    pg.goto(args.base + path, wait_until="networkidle", timeout=20000)
                    m = pg.evaluate(METRICS_JS)
                except Exception as exc:  # noqa: BLE001 - report and keep going
                    m = {"error": str(exc)[:120]}
                m.update(width=w, page=re.sub(r"[0-9a-f-]{36}", "ID", path))
                results.append(m)
            ctx.close()
        browser.close()
    out = root / "tools" / "qa" / ".mobile"
    out.mkdir(exist_ok=True)
    (out / f"audit-{args.label}.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'page':34}{'w':>5} {'ovf':>4} {'off':>4} {'btn<44':>7} {'tap<24':>7} {'in<16':>6}")
    for m in results:
        if "error" in m:
            print(f"{m['page']:34}{m['width']:>5} ERROR {m['error']}")
            continue
        flag = " !" if (m["overflowX"] > 0 or m["errorPage"]) else ""
        print(f"{m['page']:34}{m['width']:>5} {m['overflowX']:>4} {len(m['offenders']):>4} {m['primaryBelow44']:>7} "
              f"{m['below24']:>7} {m['inputsBelow16']:>6}{flag}")
    for w in widths:
        rows = [m for m in results if m["width"] == w and "error" not in m]
        print(f"TOTAL w={w}: pages={len(rows)} overflow_pages={sum(1 for m in rows if m['overflowX'] > 0)} "
              f"primary<44={sum(m['primaryBelow44'] for m in rows)} tap<24={sum(m['below24'] for m in rows)} "
              f"inputs<16={sum(m['inputsBelow16'] for m in rows)}")
    shell = results[0] if results else {}
    print(f"shell: viewport-fit={shell.get('viewportFit')} manifest={shell.get('manifest')} apple-icon={shell.get('appleIcon')}")


if __name__ == "__main__":
    sys.exit(main())

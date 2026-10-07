"""Shared plumbing of the mobile suite: result recorder, browser sessions (phone emulation, error capture), DB reader.

Every test is one `rec.check(group, name, ok, detail)`; a module writes its rows to tools/qa/.mobile/suite/<module>.jsonl and
`run.py` adds them up. Nothing here touches a real database: the suite only ever talks to throwaway SQLite copies.
"""
import json
import os
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "tools" / "qa" / ".mobile" / "suite"

# name -> (width, height, extra context options)
VIEWPORTS = {
    "320x568": (320, 568, {}),                      # iPhone SE 1 / small Android
    "360x740": (360, 740, {}),                      # the common Android
    "390x844": (390, 844, {}),                      # iPhone 12-15
    "430x932": (430, 932, {}),                      # iPhone Pro Max
    "540x720": (540, 720, {}),                      # large phone / small foldable
    "768x1024": (768, 1024, {}),                    # tablet portrait
    "844x390": (844, 390, {}),                      # phone landscape
    "390x844@200": (390, 844, {"zoom": 2.0}),       # largest OS font size, emulated by doubling the root size
}
PHONE_NAMES = ["320x568", "360x740", "390x844", "430x932", "540x720", "768x1024", "844x390", "390x844@200"]


class Rec:
    def __init__(self, module):
        self.module = module
        OUT.mkdir(parents=True, exist_ok=True)
        self.path = OUT / f"{module}.jsonl"
        self.fh = open(self.path, "w", encoding="utf-8")
        self.total = 0
        self.failed = 0

    def check(self, group, name, ok, detail=""):
        ok = bool(ok)
        self.total += 1
        if not ok:
            self.failed += 1
            print(f"FAIL [{group}] {name}  {str(detail)[:200]}", flush=True)
        self.fh.write(json.dumps({"g": group, "n": name, "ok": ok, "d": str(detail)[:400]}, ensure_ascii=False) + "\n")
        self.fh.flush()
        return ok

    def done(self):
        self.fh.close()
        print(f"== {self.module}: {self.total - self.failed}/{self.total} passed, {self.failed} failed", flush=True)


def login_of(db_path):
    lines = pathlib.Path(str(db_path) + ".login.txt").read_text(encoding="utf-8").split()
    return lines[0], lines[1]


def django_for(db_path):
    """Open the throwaway DB read-only-ish through the ORM (for oracles); never the real database."""
    os.environ["DATABASE_URL"] = "sqlite:///" + pathlib.Path(db_path).as_posix()
    os.environ.setdefault("DEBUG", "True")
    os.environ.setdefault("SECRET_KEY", "throwaway-qa")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"       # Playwright's sync API runs an event loop; the ORM calls here are plain reads
    import sys
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import django
    django.setup()
    from django.db import connection
    connection.cursor().execute("PRAGMA busy_timeout=20000")


IGNORED_URL = re.compile(r"favicon|/__debug__/|hot-update")


class Browser:
    """One Chrome with phone emulation; contexts per viewport share one login (storage_state)."""

    def __init__(self, pw, base, phone, password):
        self.pw = pw
        self.base = base
        self.chrome = pw.chromium.launch(channel="chrome", headless=True)
        self.phone, self.password = phone, password
        self.state = None

    def close(self):
        self.chrome.close()

    def _login_state(self):
        ctx = self.chrome.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        pg.goto(self.base + "/login/")
        pg.locator("input[type=text], input[type=tel]").first.fill(self.phone)
        pg.locator("input[type=password]").first.fill(self.password)
        pg.locator("form button[type=submit]").first.click()
        pg.wait_for_url(lambda u: "/login" not in u)
        self.state = ctx.storage_state()
        ctx.close()

    def context(self, vp="390x844", touch=True, logged_in=True, **kw):
        w, h, extra = VIEWPORTS[vp] if vp in VIEWPORTS else (int(vp.split("x")[0]), int(vp.split("x")[1]), {})
        if logged_in and self.state is None:
            self._login_state()
        opts = dict(viewport={"width": w, "height": h}, is_mobile=touch, has_touch=touch, locale="fa-IR", device_scale_factor=1)
        if logged_in:
            opts["storage_state"] = self.state
        opts.update(kw)
        ctx = self.chrome.new_context(**opts)
        ctx.set_default_timeout(15000)
        ctx.zoom = extra.get("zoom")
        return ctx


class Watched:
    """A page that records JS errors, console errors and failed requests since the last `drain()`."""

    def __init__(self, ctx, base):
        self.page = ctx.new_page()
        self.base = base
        self.zoom = getattr(ctx, "zoom", None)
        self.js, self.console, self.failed = [], [], []
        p = self.page
        p.on("pageerror", lambda e: self.js.append(str(e)[:200]))
        p.on("console", lambda m: self.console.append(m.text[:200]) if m.type == "error" and not IGNORED_URL.search(m.text) else None)
        p.on("response", self._resp)
        p.on("requestfailed", lambda r: self.failed.append(f"FAILED {r.url.replace(base, '')} {r.failure}") if not IGNORED_URL.search(r.url) and "ERR_ABORTED" not in str(r.failure) else None)

    def _resp(self, r):
        if r.status >= 400 and not IGNORED_URL.search(r.url):
            self.failed.append(f"{r.status} {r.request.method} {r.url.replace(self.base, '')}")

    def drain(self):
        out = (self.js[:], self.console[:], self.failed[:])
        self.js.clear(); self.console.clear(); self.failed.clear()
        return out

    def goto(self, path, wait="networkidle"):
        resp = self.page.goto(self.base + path, wait_until=wait)
        if self.zoom:
            self.page.add_style_tag(content=f"html{{font-size:{int(self.zoom * 100)}%!important}}")
            self.page.wait_for_timeout(150)
        return resp


def now():
    return time.time()


def cli(module):
    """Common command line of every module: --db (throwaway sqlite), --base (its server), --shard i/n, --tag (output suffix)."""
    import argparse
    ap = argparse.ArgumentParser(module)
    ap.add_argument("--db", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--tag", default="")
    ap.add_argument("--limit", type=int, default=0, help="smoke runs: stop after this many units")
    a = ap.parse_args()
    a.i, a.n = (int(x) for x in a.shard.split("/"))
    a.rec_name = module + (f"-{a.tag}" if a.tag else "") + (f"-{a.i}" if a.n > 1 else "")
    return a


def run_module(module, body):
    """body(args, rec, browser) -> None. Opens Django on the DB, a Chrome session and the recorder, always closes them."""
    from playwright.sync_api import sync_playwright
    a = cli(module)
    django_for(a.db)
    rec = Rec(a.rec_name)
    phone, password = login_of(a.db)
    t0 = now()
    with sync_playwright() as pw:
        b = Browser(pw, a.base.rstrip("/"), phone, password)
        try:
            body(a, rec, b)
        except Exception as exc:                      # a crashed module must show up as a failure, not as silence
            import traceback
            traceback.print_exc()
            rec.check("module", "completed without crashing", False, repr(exc))
        finally:
            b.close()
    rec.done()
    print(f"   ({now() - t0:.0f}s)", flush=True)

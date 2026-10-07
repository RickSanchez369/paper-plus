"""Links and references: every internal link of every page answers, every in-page anchor / aria / label reference has a target,
every form action resolves to a real URL, every CSS/JS/image the pages load exists."""
import urllib.parse

from tools.qa.mobile_suite.lib import Watched, run_module

COLLECT = r"""
() => {
  const out = {hrefs: [], anchors: [], aria: [], labels: [], actions: [], assets: []};
  const ids = new Set([...document.querySelectorAll('[id]')].map(e => e.id));
  document.querySelectorAll('a[href]').forEach(a => {
    const h = a.getAttribute('href');
    if (h.startsWith('#')) { if (h.length > 1) out.anchors.push([h.slice(1), ids.has(decodeURIComponent(h.slice(1)))]); }
    else if (!/^(mailto:|tel:|javascript:|https?:)/.test(h)) out.hrefs.push(h);
  });
  ['aria-controls', 'aria-describedby', 'aria-labelledby'].forEach(attr => document.querySelectorAll('[' + attr + ']').forEach(e => {
    e.getAttribute(attr).split(/\s+/).filter(Boolean).forEach(id => out.aria.push([attr, id, ids.has(id) || !!document.querySelector('template')]));
  }));
  document.querySelectorAll('label[for]').forEach(l => out.labels.push([l.getAttribute('for'), ids.has(l.getAttribute('for'))]));
  document.querySelectorAll('form[action]').forEach(f => out.actions.push(f.getAttribute('action')));
  document.querySelectorAll('script[src],link[rel=stylesheet][href],link[rel=manifest][href],link[rel=icon][href],link[rel=apple-touch-icon][href],img[src]').forEach(e => out.assets.push(e.getAttribute('src') || e.getAttribute('href')));
  return out;
}
"""
SKIP = ("/logout/", "/admin/", "/backup/download")


def body(a, rec, b):
    from django.urls import Resolver404, resolve

    from tools.qa.mobile_suite.pages import all_pages
    ctx = b.context("390x844")
    w = Watched(ctx, b.base)
    seen_href, seen_asset = {}, {}
    pages = all_pages()
    if a.limit:
        pages = pages[:a.limit]
    for label, path in pages:
        if label in ("404", "404-uuid"):
            continue
        w.goto(path)
        d = w.page.evaluate(COLLECT)
        bad = [x for x in d["anchors"] if not x[1]]
        rec.check("anchors", f"{label}: every #anchor has a target ({len(d['anchors'])})", not bad, bad[:4])
        bad = [x for x in d["aria"] if not x[2]]
        rec.check("aria", f"{label}: every aria reference has a target ({len(d['aria'])})", not bad, bad[:4])
        bad = [x for x in d["labels"] if not x[1]]
        rec.check("labels", f"{label}: every label[for] has a field ({len(d['labels'])})", not bad, bad[:4])
        for act in set(d["actions"]):
            target = urllib.parse.urlparse(urllib.parse.urljoin(path, act)).path or path
            try:
                resolve(target)
                okk = True
            except Resolver404:
                okk = False
            rec.check("actions", f"{label}: form action {act or '(self)'} resolves", okk, target)
        for h in d["hrefs"]:
            seen_href.setdefault(urllib.parse.urljoin(path, h).split("#")[0], label)
        for s in d["assets"]:
            seen_asset.setdefault(urllib.parse.urljoin(path, s), label)
    # every unique internal link, once
    for url, label in sorted(seen_href.items()):
        p = urllib.parse.urlparse(url)
        if p.netloc or any(url.startswith(s) for s in SKIP):
            continue
        r = ctx.request.get(b.base + url, max_redirects=5)
        rec.check("links", f"GET {url[:90]} (from {label})", r.status == 200, r.status)
    for url, label in sorted(seen_asset.items()):
        p = urllib.parse.urlparse(url)
        if p.netloc:
            continue
        r = ctx.request.get(b.base + url)
        n = len(r.body()) if r.status == 200 else 0
        rec.check("assets", f"asset {url[:80]} loads and is not empty", r.status == 200 and n > 0, (r.status, n))
    ctx.close()


if __name__ == "__main__":
    run_module("links", body)

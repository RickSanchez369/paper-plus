() => {
  const vw = innerWidth, de = document.documentElement, phone = vw <= 720;
  const out = {};
  const shown = (e) => {
    const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false;
    const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    const d = e.closest('details'); if (d && !d.open && !e.closest('summary')) return false;
    if (e.closest('[hidden],[inert],template')) return false;
    if (e.closest('.sr-only')) return false;
    if (cs.clipPath && cs.clipPath.startsWith('inset(50%)')) return false;
    return true;
  };
  const inScroller = (e) => { for (let p = e.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden' && p !== document.body && p !== de) return true; } return false; };
  const label = (e) => e.tagName.toLowerCase() + '.' + String(e.className).split(' ')[0] + '#' + (e.id || '');

  out.overflow_px = de.scrollWidth - de.clientWidth;
  out.offscreen = [...document.querySelectorAll('body *')].filter(e => shown(e) && !inScroller(e) && getComputedStyle(e).position !== 'fixed').filter(e => {
    const r = e.getBoundingClientRect(); return r.right > vw + 1 || r.left < -1; }).map(label).slice(0, 5);

  const meta = document.querySelector('meta[name=viewport]');
  out.viewport_meta = meta ? meta.content : '';
  out.dir = de.getAttribute('dir'); out.lang = de.getAttribute('lang');
  out.title = document.title;
  const bodyText = document.body.innerText || '';
  out.junk = (bodyText.match(/\bNone\b|\bundefined\b|\bNaN\b|\{\{|\{%|\[object|\bnull\b/g) || []).slice(0, 4);
  out.mains = document.querySelectorAll('main').length;
  out.headers = document.querySelectorAll('body > .app header, body header.header, header').length;

  const tg = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary')].filter(shown);
  out.small44 = phone ? tg.filter(e => e.matches('.btn,button[type=submit],summary:not(.sr-only),.nav-toggle,.cmdk-trigger'))
    .filter(e => e.getBoundingClientRect().height < 43.5).map(e => label(e) + ' ' + Math.round(e.getBoundingClientRect().height)).slice(0, 6) : [];
  out.small_inputs = phone ? [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=submit]):not([type=button]):not([type=file]),select,textarea')]
    .filter(shown).filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).map(label).slice(0, 5) : [];

  const nameOf = (e) => {
    const t = (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.getAttribute('title') || '').trim();
    if (t) return t;
    if ((e.innerText || e.textContent || '').trim()) return 'text';
    if (e.tagName === 'INPUT' || e.tagName === 'SELECT' || e.tagName === 'TEXTAREA') {
      if (e.id && document.querySelector('label[for="' + CSS.escape(e.id) + '"]')) return 'label';
      if (e.closest('label')) return 'label';
      if (e.getAttribute('placeholder')) return 'placeholder';
    }
    if (e.querySelector('img[alt]:not([alt=""]), svg title')) return 'img';
    return '';
  };
  out.no_name = tg.filter(e => !['INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName) && !nameOf(e)).map(label).slice(0, 5);
  out.no_label = tg.filter(e => ['INPUT', 'SELECT', 'TEXTAREA'].includes(e.tagName) && !['submit', 'button'].includes(e.type) && !nameOf(e)).map(label).slice(0, 5);

  const ids = {}; document.querySelectorAll('[id]').forEach(e => { ids[e.id] = (ids[e.id] || 0) + 1; });
  out.dup_ids = Object.keys(ids).filter(k => ids[k] > 1 && !k.includes('__prefix__')).slice(0, 5);
  out.img_no_alt = [...document.querySelectorAll('img')].filter(i => shown(i) && !i.hasAttribute('alt')).length;
  out.clipped = [...document.querySelectorAll('.btn,button,.badge,.chip,.sf-chip,.status-badge')].filter(e => shown(e) && e.scrollWidth > e.clientWidth + 1
    && getComputedStyle(e).overflow !== 'visible').map(label).slice(0, 5);
  out.pos_tabindex = document.querySelectorAll('[tabindex]:not([tabindex="0"]):not([tabindex="-1"])').length;
  out.tiny_text = phone ? [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && (e.textContent || '').trim() && shown(e)
    && parseFloat(getComputedStyle(e).fontSize) < 11.5).map(e => label(e) + ' ' + getComputedStyle(e).fontSize).slice(0, 5) : [];

  // contrast (solid backgrounds only; gradients, images and opacity < 1 are skipped, not guessed)
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bgOf = (e) => { for (let p = e; p; p = p.parentElement) { const cs = getComputedStyle(p);
    if (cs.backgroundImage !== 'none') return null; const c = parse(cs.backgroundColor); if (c && c.a > 0.99) return c; if (c && c.a > 0) return null; } return { r: 255, g: 255, b: 255, a: 1 }; };
  const lowC = [];
  [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && (e.textContent || '').trim().length > 1 && shown(e)).forEach(e => {
    if (e.closest('button:disabled,[disabled],[aria-disabled=true],.is-disabled,svg')) return;
    for (let p = e; p; p = p.parentElement) { if (parseFloat(getComputedStyle(p).opacity) < 1) return; }
    const cs = getComputedStyle(e), fg = parse(cs.color), bg = bgOf(e); if (!fg || !bg || fg.a < 1) return;
    const L1 = lum(fg), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700, large = size >= 24 || (size >= 18.66 && bold);
    if (ratio < (large ? 3 : 4.5)) lowC.push(label(e) + ' ' + ratio.toFixed(2) + ' "' + e.textContent.trim().slice(0, 14) + '"');
  });
  out.low_contrast = lowC.slice(0, 6); out.low_contrast_n = lowC.length;

  // Round 4 (D-098): the header title shows in full (two lines at most), a short document number or date is never split across
  // lines, and a card row is tinted as one block (no painted cell next to an unpainted one).
  const ht = document.querySelector('.header__title');
  out.title_cut = phone && ht ? (ht.scrollWidth > ht.clientWidth + 1 || ht.scrollHeight > ht.clientHeight + 1) : false;
  out.split_tokens = [];
  if (phone) {
    const w = document.createTreeWalker(document.querySelector('main') || document.body, NodeFilter.SHOW_TEXT), re = /[^\s]*[0-9۰-۹][^\s]*/g;
    let n;
    while ((n = w.nextNode())) {
      const el = n.parentElement;
      if (!el || ['SCRIPT', 'STYLE', 'OPTION', 'TEXTAREA'].includes(el.tagName) || !shown(el)) continue;
      let m; const t = n.textContent;
      while ((m = re.exec(t))) {
        const tok = m[0];
        if (tok.length < 4 || tok.length > 22 || /[-()]/.test(tok)) continue;      // a hyphen is a normal break point
        let at = m.index;      // each piece between slashes must stay on one line; a break right after a slash is a normal one
        for (const piece of tok.split('/')) {
          if (piece.length >= 2) {
            const r = document.createRange(); r.setStart(n, at); r.setEnd(n, at + piece.length);
            const rects = [...r.getClientRects()].filter(x => x.width > 0);
            if (rects.length > 1 && new Set(rects.map(x => Math.round(x.top / 4))).size > 1) { out.split_tokens.push(tok); break; }
          }
          at += piece.length + 1;
        }
      }
    }
    out.split_tokens = out.split_tokens.slice(0, 5);
  }
  out.card_notch = phone ? [...document.querySelectorAll('table[data-cards] tbody tr:not([data-card-skip]) > td')].filter(shown)
    .filter(td => { const c = getComputedStyle(td).backgroundColor; const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return false; const a = m[1].split(',').map(parseFloat); return a.length === 3 ? true : a[3] > 0.01; })
    .map(td => label(td)).slice(0, 4) : [];

  // bottom clearance: scrolled to the end, the last piece of content must not sit under a fixed/sticky bottom bar
  scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'});
  const bars = [...document.querySelectorAll('.sale-dock, .undo-bar, [class*=dock], .toast')].filter(e => shown(e) && ['fixed', 'sticky'].includes(getComputedStyle(e).position));
  out.bar_cover = 0;
  if (bars.length) {
    const top = Math.min(...bars.map(b => b.getBoundingClientRect().top));
    const last = [...document.querySelectorAll('main *')].filter(e => shown(e) && e.children.length === 0 && !bars.some(b => b.contains(e))).map(e => e.getBoundingClientRect().bottom);
    const lowest = last.length ? Math.max(...last) : 0;
    out.bar_cover = lowest > top + 2 ? Math.round(lowest - top) : 0;
  }
  scrollTo({top: 0, behavior: 'instant'});
  out.scale_locked = /user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*1(\.0)?\b/.test(out.viewport_meta);
  return out;
}

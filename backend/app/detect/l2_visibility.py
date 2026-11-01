"""L2: outbound links hidden from human visitors, grouped by nearest wrapper."""

import html as html_lib
import re

from app.crawl.fetcher import BrowserPool, _host


HEAD = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
URLISH = re.compile(r"\S+://\S*|\b(?:[\w-]+\.)+[a-z]{2,}\b\S*", re.IGNORECASE)

# Runs inside the page; hrefs are compared here and never returned to Python.
FIND_HIDDEN = """
(baseHost) => {
  const path = (el) => {
    const parts = [];
    for (; el && el !== document.documentElement; el = el.parentElement) {
      if (el === document.body) { parts.unshift('body'); break; }
      let i = 1;
      for (let s = el.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === el.tagName) i++;
      parts.unshift(`${el.tagName.toLowerCase()}:nth-of-type(${i})`);
    }
    return parts.join(' > ');
  };
  const rgba = (color) => {
    const values = color.match(/[\\d.]+/g).map(Number);
    return [...values.slice(0, 3), values[3] ?? 1];
  };
  const background = (el) => {
    const layers = [];
    for (; el; el = el.parentElement) layers.push(rgba(getComputedStyle(el).backgroundColor));
    return layers.reverse().reduce((bg, c) => bg.map((v, i) => c[i] * c[3] + v * (1 - c[3])), [255, 255, 255]);
  };
  const reason = (a) => {
    if (!a.checkVisibility({opacityProperty: true, visibilityProperty: true})) {
      for (let e = a; e; e = e.parentElement) if (getComputedStyle(e).display === 'none') return 'display_none';
      if (getComputedStyle(a).visibility !== 'visible') return 'visibility_hidden';
      for (let e = a; e; e = e.parentElement) if (Number(getComputedStyle(e).opacity) === 0) return 'opacity_zero';
      return 'zero_size';
    }
    const style = getComputedStyle(a), rect = a.getBoundingClientRect();
    if (rect.left + scrollX < -1000 || rect.top + scrollY < -1000) return 'offscreen';
    if (parseFloat(style.fontSize) <= 1) return 'tiny_text';
    const fg = rgba(style.color), bg = background(a);
    if (fg[3] === 0 || fg.slice(0, 3).every((v, i) => Math.abs(v - bg[i]) < 0.5)) return 'same_color';
    if (rect.width === 0 || rect.height === 0) return 'zero_size';
    return null;
  };
  const groups = new Map();
  for (const a of document.querySelectorAll('a[href]')) {
    let url;
    try { url = new URL(a.href); } catch { continue; }
    const host = url.hostname.toLowerCase().replace(/\\.$/, '');
    if (!/^https?:$/.test(url.protocol) || host === baseHost) continue;
    const why = reason(a);
    if (!why) continue;
    const selector = path(a.parentElement || document.body);
    const key = selector + '|' + why;
    const group = groups.get(key) || {selector, reason: why, link_count: 0, texts: []};
    group.link_count++;
    group.texts.push(a.textContent.trim());
    groups.set(key, group);
  }
  return [...groups.values()].map(({texts, ...g}) => ({...g, text: texts.join(' ')}));
}
"""


def _snippet(text: str) -> str:
    return " ".join(URLISH.sub("[DISENSOR]", text).split())[:200]


async def analyze_hidden(pool: BrowserPool, html: str, base_url: str) -> dict:
    root = _host(base_url)
    base = f'<base href="{html_lib.escape(base_url, quote=True)}">'
    match = HEAD.search(html)
    html = html[:match.end()] + base + html[match.end():] if match else base + html

    context = await pool.browser.new_context(java_script_enabled=False, service_workers="block")
    try:
        # Inert replay: all resource requests blocked, including refreshes and CSS imports.
        await context.route("**/*", lambda route: route.abort())
        await context.route_web_socket("**/*", lambda socket: socket.close())
        page = await context.new_page()
        await page.set_content(html, wait_until="load", timeout=20_000)
        groups = await page.evaluate(FIND_HIDDEN, root)
    finally:
        await context.close()

    hidden = sum(group["link_count"] for group in groups)
    return {
        "status": "ok",
        "score": min(1.0, hidden / 5),
        "hidden_links": hidden,
        # Internal L3 input, not a public response field; never truncated like evidence snippets.
        "hidden_text": " ".join(g["text"] for g in groups),
        "evidence": [
            {"selector": g["selector"], "reason": g["reason"], "link_count": g["link_count"], "snippet": _snippet(g["text"])}
            for g in groups
        ],
    }

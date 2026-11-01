"""
GuardBit — pengumpul snapshot tiga profil (alat riset pra-Hacking Day).

Bukan bagian dari produk. Dipakai untuk membangun data uji berlabel sesuai
metodologi proposal (Bab 3.4). Dicatat di README bagian AI Use and
Third-Party Declaration.

Untuk setiap URL kandidat, halaman diambil dengan 3 profil x 2 kali:
  browser  : Chrome desktop biasa
  crawler  : user-agent Googlebot
  search   : Chrome desktop + referer google.com
Disimpan: HTML hasil render, screenshot, header respons, dan ringkasan.

Batas etika yang ditegakkan kode:
  - Hanya membaca halaman publik. Tanpa login, tanpa form, tanpa eksploitasi.
  - Jeda >= 3 detik antar-request ke host yang sama.
  - Request ke host NON-institusi (calon situs judol) diblokir dan hanya dicatat
    nama host-nya. Navigasi/redirect ke luar domain institusi juga diblokir.
  - Tautan keluar disimpan hanya sebagai nama host di ringkasan, bukan URL lengkap.

Pemakaian:
  pip install playwright
  playwright install chromium
  python research/snapshot/collect.py data/snapshots/_candidates.csv
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Route, Request

WIB = timezone(timedelta(hours=7))

# Domain institusi yang boleh dimuat. Semua host lain dianggap pihak luar.
INSTITUTION_SUFFIXES = (".ac.id", ".sch.id", ".go.id", ".desa.id", ".mil.id")
# CDN umum yang biasanya diperlukan agar halaman ter-render benar (CSS/JS framework).
ALLOWED_CDN = (
    "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "code.jquery.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "ajax.googleapis.com",
    "stackpath.bootstrapcdn.com", "maxcdn.bootstrapcdn.com", "use.fontawesome.com",
)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
GOOGLEBOT_UA = (
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; "
    "+http://www.google.com/bot.html) Chrome/130.0.0.0 Safari/537.36"
)

PROFILES = {
    "browser": {"user_agent": CHROME_UA, "referer": None},
    "crawler": {"user_agent": GOOGLEBOT_UA, "referer": None},
    "search": {"user_agent": CHROME_UA, "referer": "https://www.google.com/"},
}
REPEATS = 2
DELAY_SECONDS = 3.0
NAV_TIMEOUT_MS = 30_000

# Kata kunci kasar HANYA untuk triase label manual (bukan detektor L3 produk).
CHALLENGE_TITLES = re.compile(
    r"tunggu sebentar|just a moment|attention required|403 forbidden|access denied|"
    r"checking your browser|ddos protection",
    re.IGNORECASE,
)

TRIAGE_KEYWORDS = re.compile(
    r"slot\s*gacor|slot\s*88|slot\s*777|situs\s*toto|togel|maxwin|kasino\s*online|"
    r"judi\s*(online|bola)|live\s*hk|sbobet|mahjong\s*ways|rtp\s*live|toto\s*slot",
    re.IGNORECASE,
)


def is_institution(host: str) -> bool:
    host = host.lower()
    return any(host.endswith(s) or host == s.lstrip(".") for s in INSTITUTION_SUFFIXES)


def is_allowed(host: str, target_host: str) -> bool:
    host = host.lower()
    return host == target_host or host.endswith("." + target_host) or is_institution(host) or host in ALLOWED_CDN


@dataclass
class HostThrottle:
    last: dict[str, float] = field(default_factory=dict)

    async def wait(self, host: str) -> None:
        now = time.monotonic()
        delta = now - self.last.get(host, 0.0)
        if delta < DELAY_SECONDS:
            await asyncio.sleep(DELAY_SECONDS - delta)
        self.last[host] = time.monotonic()


async def fetch_one(browser, url: str, profile: str, out_dir: Path, n: int, throttle: HostThrottle) -> dict:
    target_host = urlparse(url).hostname or ""
    cfg = PROFILES[profile]
    blocked_hosts: set[str] = set()

    context = await browser.new_context(
        user_agent=cfg["user_agent"],
        viewport={"width": 1366, "height": 900},
        locale="id-ID",
        java_script_enabled=True,
        extra_http_headers={"Referer": cfg["referer"]} if cfg["referer"] else {},
    )

    redirect_attempts: set[str] = set()

    async def route_handler(route: Route, request: Request) -> None:
        host = urlparse(request.url).hostname or ""
        if is_allowed(host, target_host):
            await route.continue_()
        else:
            blocked_hosts.add(host)
            if request.is_navigation_request() and request.frame.parent_frame is None:
                redirect_attempts.add(host)  # halaman mencoba membawa pengunjung keluar
            await route.abort()

    await context.route("**/*", route_handler)
    page = await context.new_page()
    static_ctx = None

    record: dict = {"profile": profile, "n": n, "fetched_at": datetime.now(WIB).isoformat()}
    stem = out_dir / f"{profile}_{n}"
    try:
        # 1) HTML mentah dari server dengan profil yang sama (tanpa JS, tanpa ikut redirect keluar).
        await throttle.wait(target_host)
        raw_headers = {"User-Agent": cfg["user_agent"]}
        if cfg["referer"]:
            raw_headers["Referer"] = cfg["referer"]
        # Ikuti redirect manual (maks 5 hop), hanya di dalam domain yang diizinkan.
        cur = url
        hops = []
        for _ in range(6):
            raw = await context.request.get(cur, headers=raw_headers, max_redirects=0,
                                            timeout=NAV_TIMEOUT_MS, fail_on_status_code=False)
            location = raw.headers.get("location", "")
            if not (300 <= raw.status < 400 and location):
                break
            nxt = urljoin(cur, location)
            nxt_host = urlparse(nxt).hostname or ""
            hops.append({"status": raw.status, "to_host": nxt_host})
            if not is_allowed(nxt_host, target_host):
                redirect_attempts.add(nxt_host)
                break
            cur = nxt
        raw_html = await raw.text()
        stem.with_suffix(".raw.html").write_text(raw_html, encoding="utf-8")
        record["redirect_hops"] = hops
        stem.with_suffix(".headers.json").write_text(
            json.dumps({"status": raw.status, "headers": raw.headers}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 2) Render di browser untuk DOM akhir, screenshot, dan teks yang benar-benar terlihat.
        await throttle.wait(target_host)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            await page.wait_for_timeout(2500)  # beri waktu JS cloaking berjalan
        except Exception:  # noqa: BLE001 — navigasi keluar yang diblokir memicu error di sini
            pass

        if redirect_attempts or page.url.startswith("chrome-error://"):
            # Halaman mencoba membawa pengunjung ke luar. Tampilkan HTML mentah dengan JS mati.
            static_ctx = await browser.new_context(java_script_enabled=False,
                                                   viewport={"width": 1366, "height": 900})
            await static_ctx.route("**/*", route_handler)
            page = await static_ctx.new_page()
            await page.set_content(raw_html, wait_until="domcontentloaded")
            html = raw_html
        else:
            html = await page.content()
        stem.with_suffix(".html").write_text(html, encoding="utf-8")
        await page.screenshot(path=str(stem.with_suffix(".png")), full_page=True)

        text = await page.evaluate("document.body ? document.body.innerText : ''")
        # textContent ikut menghitung elemen tersembunyi; script/style dibuang dulu.
        body_all = await page.evaluate(
            "(() => { if (!document.body) return ''; const c = document.body.cloneNode(true);"
            " c.querySelectorAll('script,style,noscript').forEach(e => e.remove()); return c.textContent; })()"
        )
        hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        out_hosts = sorted({(urlparse(h).hostname or "") for h in hrefs} - {target_host, ""})
        title = await page.title()
        blocked = raw.status in (401, 403, 429, 503) or bool(CHALLENGE_TITLES.search(title or ""))
        record.update({
            "status": raw.status,
            "blocked_or_challenge": blocked,
            "redirect_attempt_hosts": sorted(redirect_attempts),
            "title": title,
            "raw_keyword_hits": len(TRIAGE_KEYWORDS.findall(raw_html)),
            "html_keyword_hits": len(TRIAGE_KEYWORDS.findall(html)),
            "body_keyword_hits": len(TRIAGE_KEYWORDS.findall(body_all)),
            "visible_keyword_hits": len(TRIAGE_KEYWORDS.findall(text)),
            "outbound_host_count": len(out_hosts),
            "outbound_hosts": out_hosts,
            "institution_hosts_linked": [h for h in out_hosts if is_institution(h)],
            "blocked_request_hosts": sorted(blocked_hosts),
        })
    except Exception as exc:  # noqa: BLE001 — catat lalu lanjut ke kandidat berikutnya
        record["error"] = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        if static_ctx is not None:
            await static_ctx.close()
        await context.close()
    return record


def triage(records: list[dict]) -> dict:
    """Ringkasan kasar untuk membantu pelabelan manual."""
    def mean(profile: str, key: str) -> float:
        vals = [r.get(key, 0) for r in records if r["profile"] == profile and "error" not in r]
        return sum(vals) / len(vals) if vals else 0.0

    blocked = {p: any(r.get("blocked_or_challenge") for r in records if r["profile"] == p) for p in PROFILES}
    hits = {p: mean(p, "html_keyword_hits") for p in PROFILES}
    body = {p: mean(p, "body_keyword_hits") for p in PROFILES}
    visible = {p: mean(p, "visible_keyword_hits") for p in PROFILES}
    links = {p: mean(p, "outbound_host_count") for p in PROFILES}
    hints = []
    for p, b in blocked.items():
        if b:
            hints.append(f"profil {p} DIBLOKIR/challenge (403/WAF) - bukan bukti bersih")
    if body["browser"] > visible["browser"] + 1:
        hints.append("ada kata kunci di HTML yang tidak terlihat oleh pengunjung (cek css_hidden/offscreen)")
    if not blocked["crawler"] and hits["crawler"] > hits["browser"] + 2 or links["crawler"] > links["browser"] + 3:
        hints.append("konten/tautan lebih banyak untuk Googlebot (cek cloak_ua)")
    if hits["search"] > hits["browser"] + 2 or links["search"] > links["browser"] + 3:
        hints.append("konten/tautan lebih banyak untuk referer Google (cek cloak_referer)")
    if any(r.get("redirect_attempt_hosts") for r in records):
        hints.append("redirect keluar domain institusi (cek redirect)")
    if max(hits.values()) == 0 and not any(blocked.values()):
        hints.append("tidak ada kata kunci triase di profil mana pun (mungkin bersih, sudah dibersihkan, atau cloaking berbasis IP)")
    return {"blocked": blocked, "keyword_hits": hits, "visible_hits": visible, "outbound_hosts": links, "hints": hints}


async def main(candidates_csv: Path) -> None:
    root = candidates_csv.parent
    rows = list(csv.DictReader(candidates_csv.open(encoding="utf-8")))
    throttle = HostThrottle()
    summary_rows = []

    async with async_playwright() as pw:
        extra_args = os.environ.get("GUARDBIT_CHROMIUM_ARGS", "").split("||") if os.environ.get("GUARDBIT_CHROMIUM_ARGS") else []
        browser = await pw.chromium.launch(args=extra_args)
        for i, row in enumerate(rows, 1):
            url, alias = row["url"].strip(), row["alias"].strip()
            if not is_institution(urlparse(url).hostname or ""):
                print(f"[lewati] bukan domain institusi: {alias}")
                continue
            page_id = row.get("page_id") or f"pg_{i:03d}"
            out_dir = root / alias / page_id
            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"[{i}/{len(rows)}] {alias}/{page_id}")

            records = []
            for n in range(1, REPEATS + 1):
                for profile in PROFILES:
                    records.append(await fetch_one(browser, url, profile, out_dir, n, throttle))
            t = triage(records)
            (out_dir / "summary.json").write_text(
                json.dumps({"page_id": page_id, "alias": alias, "records": records, "triage": t},
                           indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            summary_rows.append({
                "page_id": page_id, "alias": alias,
                "blocked": ",".join(p for p, b in t["blocked"].items() if b),
                "hits_browser": round(t["keyword_hits"]["browser"], 1),
                "hits_crawler": round(t["keyword_hits"]["crawler"], 1),
                "hits_search": round(t["keyword_hits"]["search"], 1),
                "visible_browser": round(t["visible_hits"]["browser"], 1),
                "hints": " | ".join(t["hints"]),
            })
        await browser.close()

    out = root / "_triage.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()) if summary_rows else ["page_id"])
        w.writeheader()
        w.writerows(summary_rows)
    print(f"\nSelesai. Ringkasan triase: {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Pemakaian: python research/snapshot/collect.py <candidates.csv>")
    asyncio.run(main(Path(sys.argv[1])))

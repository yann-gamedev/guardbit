import asyncio
import socket
import time
from threading import Thread

import httpx
import pytest
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import main
from app.api import quick_check as endpoint
from app.crawl.fetcher import BrowserPool
from app.crawl.public_http import UnsafeTarget, get_public, public_address
from app.detect.l2_visibility import analyze_hidden
from app.detect.l3_lite import score_text
from app.config import settings
from app.detect.score import risk


@pytest.fixture(scope="module")
def server():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with pytest.MonkeyPatch.context() as patch, socket.socket() as listener:
        patch.setattr(settings, "DEBUG", True)
        patch.setattr(main, "engine", engine)
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", access_log=False))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 30
            while not server.started:
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("Local server did not start")
                time.sleep(0.05)
            yield f"http://127.0.0.1:{listener.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(timeout=30)


def check(base, url):
    return httpx.post(f"{base}/quick-check", json={"url": url}, timeout=90)


@pytest.mark.parametrize("name,status", [
    ("css_hidden", "terindikasi"), ("offscreen", "terindikasi"), ("tiny_white", "terindikasi"),
    ("clean", "aman"), ("hardneg_news", "aman"), ("blocked_crawler", "aman"),
])
def test_replay(server, name, status):
    response = check(server, f"{server}/replay/{name}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "reasons", "pages_checked", "checked_at", "cached"}
    assert body["status"] == status
    assert body["pages_checked"] == 1 and body["checked_at"].endswith("+07:00")
    assert ("konten_judi_tersembunyi" in body["reasons"]) == (status == "terindikasi")
    assert "judol" not in response.text and "replay" not in response.text
    again = check(server, f"{server}/replay/{name}").json()
    assert again["cached"] is True and again["status"] == status


@pytest.mark.parametrize("url", [
    "http://localhost/", "http://10.0.0.1/", "http://192.168.1.1/", "http://169.254.169.254/",
    "http://[::1]/", "http://user:pass@example.com/", "ftp://example.com/",
])
def test_ssrf_rejected(server, url):
    assert check(server, url).status_code in {400, 422}


def test_loopback_rejected_without_debug(server, monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    assert check(server, "http://127.0.0.1:1/x").status_code == 400
    assert check(server, f"{server}/replay/clean").status_code == 400  # Cached DEBUG result.


def test_risk():
    assert risk(1, 1)[1] == "terindikasi"
    assert risk(1, 0)[1] == "terindikasi"  # 0.6 alone crosses 0.5
    assert risk(0, 0.5)[1] == "aman"
    assert risk(0, 0) == (0, "aman")


@pytest.mark.asyncio
async def test_visibility_reasons_and_inert_resources(local_site):
    base, requests = local_site
    pool = BrowserPool()
    await pool.start()
    try:
        cases = {
            "display_none": 'display:none', "visibility_hidden": 'visibility:hidden',
            "opacity_zero": 'opacity:0', "offscreen": 'position:absolute;left:-9999px',
            "tiny_text": 'font-size:1px', "same_color": 'color:white',
            "zero_size": 'display:inline-block;width:0;height:0',
        }
        for reason, style in cases.items():
            html = f'''<html><head></head><body style="background:white">
                <script>fetch('{base}/script')</script><img src="{base}/image">
                <div style="{style}"><a style="{style}" href="https://other.invalid/">slot gacor</a>
                <a style="{style}" href="https://other.invalid/">maxwin</a></div>
                <div style="display:none"><a href="/internal">slot</a></div>
                </body></html>'''
            result = await analyze_hidden(pool, html, base)
            assert result["hidden_links"] == 2 and result["score"] == 0.4
            assert len(result["evidence"]) == 1
            evidence = result["evidence"][0]
            assert evidence["reason"] == reason and evidence["link_count"] == 2
            assert "href" not in str(result) and "other.invalid" not in str(result)
        assert not requests  # JS, image, internal anchor never requested.
        long = 'informasi ' * 40 + '𝙎𝙇𝙊𝙏 g4c0r maxwin'
        result = await analyze_hidden(pool, f'<div hidden><a href="https://other.invalid/">{long}</a></div>', base)
        assert len(result["evidence"][0]["snippet"]) == 200
        assert score_text(result["hidden_text"]) == 1  # L3 must see beyond snippet truncation.
        dotted = await analyze_hidden(pool, '<div hidden><a href="https://other.invalid/">slot.gacor.maxwin</a></div>', base)
        assert score_text(dotted["hidden_text"]) == 1  # Evidence redaction must not erase classifier input.
        assert not pool.browser.contexts
    finally:
        await pool.stop()


@pytest.mark.parametrize("text", ["𝙎𝙇𝙊𝙏", "s.l.o.t", "g4c0r", "sl\u200bot", "ѕlоt", "4d"])
def test_lite_normalization(text):
    assert score_text(text) > 0


def test_lite_clean():
    assert score_text("Rp100 tahun 2024 beta") == 0


@pytest.mark.asyncio
async def test_dns_private_and_mixed_answers(monkeypatch):
    async def resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 0)) for ip in ("93.184.216.34", "10.0.0.1")]
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(UnsafeTarget):
        await public_address("https://public.example/")


@pytest.mark.asyncio
async def test_transport_pins_dns_and_tls_hostname(monkeypatch):
    seen = []
    async def address(url):
        return "93.184.216.34"
    async def get(self, url, **kwargs):
        seen.append((str(url), kwargs))
        return httpx.Response(200, text="ok")
    monkeypatch.setattr("app.crawl.public_http.public_address", address)
    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    await get_public("https://public.example/path", {"User-Agent": "test"})
    url, kwargs = seen[0]
    assert url == "https://93.184.216.34/path"
    assert kwargs["headers"]["Host"] == "public.example"
    assert kwargs["extensions"]["sni_hostname"] == "public.example"


def test_external_stylesheet_hiding_survives_inert_replay(server, local_site):
    body = check(server, local_site[0] + "/external-css").json()
    assert body["status"] == "terindikasi"
    assert "konten_judi_tersembunyi" in body["reasons"]


def test_blocked_browser(server, local_site):
    body = check(server, local_site[0] + "/status?code=403").json()
    assert body["status"] == "tidak_dapat_diperiksa"
    assert body["reasons"] == ["situs_memblokir_pemeriksaan"]


def test_timeout_is_safe_and_closes_context(server, monkeypatch):
    monkeypatch.setattr(endpoint, "CHECK_TIMEOUT", 0.1)
    body = check(server, f"{server}/replay/tiny_white?timeout=1").json()
    assert body["status"] == "tidak_dapat_diperiksa"
    assert not main.app.state.pool.browser.contexts


def test_cache_expiry(server, monkeypatch):
    monkeypatch.setattr(endpoint, "CACHE_SECONDS", 0)
    assert check(server, f"{server}/replay/clean").json()["cached"] is False


def test_hidden_obfuscation_reason(server, monkeypatch):
    from app.crawl.fetcher import FetchResult

    async def captured(pool, url, profile, out_dir, **kwargs):
        assert profile == "browser" and out_dir is None and kwargs["public_only"]
        return FetchResult(url=url, profile=profile, final_url=url, status=200,
            rendered_html='<div hidden><a href="https://other.invalid/">𝙎𝙇𝙊𝙏 g4c0r maxwin</a></div>')

    monkeypatch.setattr(endpoint, "fetch", captured)
    body = check(server, f"{server}/hidden-obfuscation").json()
    assert body["status"] == "terindikasi"
    assert body["reasons"] == ["konten_judi_tersembunyi", "teks_judi_tersamarkan"]

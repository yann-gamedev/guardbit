import json
import socket
import time
from html.parser import HTMLParser
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI

from app import replay
from app.config import settings
from app.crawl.fetcher import BrowserPool, PROFILES, fetch


MANIFEST = json.loads((replay.FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
NAMES = (
    "css_hidden", "offscreen", "tiny_white", "cloak_ua", "cloak_referer",
    "js_redirect", "obfuscated", "clean", "hardneg_news", "blocked_crawler",
)


@pytest.fixture(scope="module")
def replay_server():
    app = FastAPI()
    app.include_router(replay.router)
    with pytest.MonkeyPatch.context() as patch, socket.socket() as listener:
        patch.setattr(settings, "DEBUG", False)
        patch.setenv("REPLAY_ENABLED", "true")
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("Local replay server did not start")
                time.sleep(0.01)
            yield f"http://127.0.0.1:{listener.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def replay_pool():
    pool = BrowserPool()
    await pool.start()
    try:
        yield pool
    finally:
        await pool.stop()


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("profile", PROFILES)
async def test_replay_matrix(replay_server, replay_pool, tmp_path, name, profile):
    result = await fetch(replay_pool, f"{replay_server}/replay/{name}", profile, tmp_path)
    blocked = name == "blocked_crawler" and profile == "crawler"
    redirected = name == "js_redirect" and profile == "search"
    spam = (
        name in {"css_hidden", "offscreen", "tiny_white", "obfuscated"}
        or (name == "cloak_ua" and profile == "crawler")
        or (name == "cloak_referer" and profile == "search")
        or redirected
    )
    assert result.status == (403 if blocked else 200)
    assert result.blocked == blocked
    assert result.block_reason == ("http_403" if blocked else None)
    assert result.redirect_attempts == (["judol.invalid"] if redirected else [])
    assert result.blocked_request_hosts == (["judol.invalid"] if redirected else [])
    assert ("judol.invalid" in result.rendered_html) == spam
    assert "Jurnal Ruang Belajar" in result.rendered_html
    if redirected:
        assert result.rendered_html == result.raw_html
    assert Path(result.screenshot_path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not replay_pool.browser.contexts


@pytest.mark.parametrize("debug,enabled,expected", [
    (False, None, 404), (False, "false", 404), (False, "1", 404),
    (False, "true", 200), (False, "TRUE", 200), (True, None, 200),
    (True, "false", 200),
])
def test_replay_gate(client, monkeypatch, debug, enabled, expected):
    monkeypatch.setattr(settings, "DEBUG", debug)
    monkeypatch.delenv("REPLAY_ENABLED", raising=False)
    if enabled is not None:
        monkeypatch.setenv("REPLAY_ENABLED", enabled)
    assert client.get("/replay/clean").status_code == expected
    assert client.get("/replay/clean/article/view/42").status_code == expected


@pytest.mark.parametrize("referer,spam", [
    ("https://www.google.com/search?q=jurnal", True),
    ("https://google.com/", True),
    ("https://google.com.other.invalid/", False),
    ("https://other.invalid/google.com", False),
    ("https://notgoogle.com/", False),
    ("http://[", False),
])
def test_referer_selection(client, monkeypatch, referer, spam):
    monkeypatch.setenv("REPLAY_ENABLED", "true")
    response = client.get("/replay/cloak_referer", headers={"Referer": referer})
    assert response.status_code == 200
    assert ("judol.invalid" in response.text) == spam
    assert response.headers["cache-control"] == "no-store"
    assert {"user-agent", "referer"} <= {part.strip().lower() for part in response.headers["vary"].split(",")}


def test_crawler_precedes_referer_and_suffix_is_not_file(client, monkeypatch):
    monkeypatch.setenv("REPLAY_ENABLED", "true")
    headers = {"User-Agent": "Googlebot", "Referer": "https://www.google.com/"}
    assert client.get("/replay/blocked_crawler/article/view/2", headers=headers).status_code == 403
    assert "judol.invalid" not in client.get("/replay/cloak_referer", headers=headers).text
    base = client.get("/replay/cloak_ua").text
    for suffix in ("crawler.html", "article/view/42", "%2e%2e/%2e%2e/app/config.py", "..%5c..%5capp%5cconfig.py"):
        response = client.get("/replay/cloak_ua/" + suffix)
        assert response.status_code == 200 and response.text == base
    assert client.get("/replay/missing").status_code == 404
    assert client.get("/replay/manifest.json").status_code == 404


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_manifest_and_fixture_structure():
    assert set(MANIFEST) == set(NAMES)
    for name, entry in MANIFEST.items():
        assert set(entry) == {"default", "crawler", "search", "crawler_status", "expected"}
        assert entry["crawler_status"] == (403 if name == "blocked_crawler" else 200)
        assert set(entry["expected"]) == {"label", "teknik"}
        for filename in {entry["default"], entry["crawler"], entry["search"]} - {None}:
            html = (replay.FIXTURE_DIR / name / filename).read_text(encoding="utf-8")
            tags = Tags(html).tags
            assert {"header", "main", "footer"} <= {tag for tag, _ in tags}
            assert "Daftar Artikel" in html or "Daftar artikel" in html
            for _, attrs in tags:
                for attribute in ("href", "src"):
                    url = attrs.get(attribute, "")
                    if url and not url.startswith("#"):
                        assert urlsplit(url).scheme == "https"
                        assert urlsplit(url).hostname == "judol.invalid"
            assert not any(tag == "script" for tag, _ in tags) or (name, filename) == ("js_redirect", "search.html")


@pytest.mark.parametrize("name,count,style", [
    ("css_hidden", 10, "display:none"),
    ("offscreen", 10, "position:absolute;left:-9999px"),
    ("tiny_white", 15, "font-size:1px;color:#ffffff"),
    ("cloak_ua", 20, None),
    ("cloak_referer", 10, None),
])
def test_spam_counts_and_placement(name, count, style):
    entry = MANIFEST[name]
    filename = entry["crawler"] or entry["search"] or entry["default"]
    html = (replay.FIXTURE_DIR / name / filename).read_text(encoding="utf-8")
    tags = Tags(html).tags
    links = [attrs for tag, attrs in tags if tag == "a" and "judol.invalid" in attrs.get("href", "")]
    assert len(links) == count
    if name == "css_hidden":
        assert html.index('style="display:none"') < html.index("<header>")
        assert sum(tag == "div" and attrs.get("style") == style for tag, attrs in tags) == 1
    elif name == "offscreen":
        assert html.index('style="position:absolute') > html.index("</footer>")
        assert sum(tag == "div" and attrs.get("style") == style for tag, attrs in tags) == 10
    elif name == "tiny_white":
        assert all(attrs.get("style") == style for attrs in links)
        assert html.index("</article>") < html.index("judol.invalid") < html.rindex("<article>")
    else:
        assert not any("style" in attrs for attrs in links)


def test_obfuscation_and_hard_negative():
    html = (replay.FIXTURE_DIR / "obfuscated/default.html").read_text(encoding="utf-8")
    assert all(text in html for text in ("𝙎𝙇𝙊𝙏", "\u200b", "ѕlоt", "g4c0r"))
    news = (replay.FIXTURE_DIR / "hardneg_news/default.html").read_text(encoding="utf-8")
    assert "Sosialisasi Bahaya Judi Online" in news
    assert news.lower().count("judi") >= 10
    assert "judol.invalid" not in news

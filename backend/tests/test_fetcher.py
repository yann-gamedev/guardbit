import asyncio
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from app.crawl.fetcher import BrowserPool, HostThrottle, PROFILES, _host, _within, fetch


@pytest_asyncio.fixture
async def pool():
    instance = BrowserPool()
    await instance.start()
    try:
        yield instance
    finally:
        await instance.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", PROFILES)
async def test_ok(pool, local_site, tmp_path, profile):
    base, requests = local_site
    result = await fetch(pool, base + "/ok", profile, tmp_path)
    assert result.status == 200
    assert not result.blocked
    assert result.block_reason is None
    assert result.final_url == base + "/ok"
    assert "Konten asli" in result.raw_html and "Konten asli" in result.rendered_html
    assert result.title == "Halaman normal"
    assert result.fetched_at.utcoffset() == timedelta(hours=7)
    assert not result.redirect_attempts and not result.blocked_request_hosts
    screenshot = Path(result.screenshot_path)
    assert screenshot.name.startswith(profile + "_")
    assert screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert len(requests) >= 2
    for _, headers in requests:
        assert headers["user-agent"] == PROFILES[profile]["user_agent"]
        assert headers.get("referer") == ("https://www.google.com/" if profile == "search" else None)
    assert not pool.browser.contexts


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", PROFILES)
async def test_googlebot_blocked_only(pool, local_site, tmp_path, profile):
    result = await fetch(pool, local_site[0] + "/ua403", profile, tmp_path)
    assert result.blocked == (profile == "crawler")
    assert result.status == (403 if profile == "crawler" else 200)
    assert result.block_reason == ("http_403" if profile == "crawler" else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/jsout", "/httpout", "/renderout"])
async def test_outbound_navigation_never_requested(pool, local_site, tmp_path, path, monkeypatch):
    from playwright.async_api import Route

    original = Route.fetch
    forwarded = []

    async def checked_fetch(route, **kwargs):
        forwarded.append(route.request.url)
        assert _host(route.request.url) == "127.0.0.1"
        assert kwargs["max_redirects"] == 0
        return await original(route, **kwargs)

    monkeypatch.setattr(Route, "fetch", checked_fetch)
    result = await fetch(pool, local_site[0] + path, "browser", tmp_path)
    assert result.redirect_attempts == ["judol.invalid"]
    assert "judol.invalid" in result.blocked_request_hosts
    assert result.rendered_html == result.raw_html
    assert "Konten asli" in result.rendered_html
    assert result.title == "Halaman normal"
    assert Path(result.screenshot_path).is_file()
    assert not pool.browser.contexts
    if path != "/httpout":
        assert forwarded


@pytest.mark.asyncio
async def test_challenge(pool, local_site, tmp_path):
    result = await fetch(pool, local_site[0] + "/challenge", "browser", tmp_path)
    assert result.status == 200 and result.blocked
    assert result.block_reason == "challenge"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429, 503])
async def test_http_blocked(pool, local_site, tmp_path, status):
    result = await fetch(pool, f"{local_site[0]}/status?code={status}", "browser", tmp_path)
    assert result.status == status and result.blocked
    assert result.block_reason == (None if status == 401 else f"http_{status}")


@pytest.mark.asyncio
async def test_internal_redirect(pool, local_site, tmp_path):
    result = await fetch(pool, local_site[0] + "/redirect", "browser", tmp_path)
    assert result.status == 200
    assert result.final_url == local_site[0] + "/ok"
    assert not result.redirect_attempts


@pytest.mark.asyncio
async def test_external_resource_blocked(pool, local_site, tmp_path):
    result = await fetch(pool, local_site[0] + "/resources", "browser", tmp_path)
    assert result.blocked_request_hosts == ["other.invalid"]
    assert not result.redirect_attempts and not result.blocked


@pytest.mark.asyncio
async def test_raw_redirect_limit(pool, local_site, tmp_path):
    with pytest.raises(RuntimeError, match="redirect limit"):
        await fetch(pool, local_site[0] + "/chain?n=6", "browser", tmp_path)
    assert len(local_site[1]) == 6
    assert not pool.browser.contexts


@pytest.mark.asyncio
async def test_pool_lifecycle(pool):
    browser = pool.browser
    await asyncio.gather(pool.start(), pool.start())
    assert pool.browser is browser
    await pool.stop()
    await pool.stop()
    assert not browser.is_connected()
    await pool.start()
    assert pool.browser is not browser


@pytest.mark.asyncio
async def test_throttle_serializes_host_not_other_hosts(monkeypatch):
    from app.crawl import fetcher

    clock = [0.0]
    sleeps = []
    monkeypatch.setattr(fetcher.time, "monotonic", lambda: clock[0])

    async def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(fetcher.asyncio, "sleep", sleep)
    throttle = HostThrottle()
    await asyncio.gather(*(throttle.wait("target.invalid") for _ in range(3)))
    await throttle.wait("different.invalid")
    assert sleeps == [throttle.delay, throttle.delay]
    assert throttle.delay >= 2


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["dns", "timeout"])
async def test_network_failure_returns_blocked(pool, local_site, tmp_path, monkeypatch, reason):
    from playwright.async_api import APIRequestContext, Error, TimeoutError

    async def failed_get(*_args, **_kwargs):
        if reason == "timeout":
            raise TimeoutError("request timed out")
        raise Error("getaddrinfo ENOTFOUND")

    monkeypatch.setattr(APIRequestContext, "get", failed_get)
    result = await fetch(pool, local_site[0] + "/ok", "browser", tmp_path)
    assert result.blocked and result.block_reason == reason
    assert result.status is None
    assert not local_site[1]
    assert not pool.browser.contexts


@pytest.mark.asyncio
async def test_throttle_concurrent_requests():
    throttle = HostThrottle()
    loop = asyncio.get_running_loop()

    async def admitted():
        await throttle.wait("target.invalid")
        return loop.time()

    times = sorted(await asyncio.gather(admitted(), admitted()))
    assert times[1] - times[0] >= throttle.delay - 0.02


def test_host_boundary_and_profiles():
    assert _within("sub.target.invalid", "target.invalid")
    assert not _within("eviltarget.invalid", "target.invalid")
    assert not _within("target.invalid.evil.invalid", "target.invalid")
    assert _host("https://TARGET.invalid./ok") == "target.invalid"
    assert set(PROFILES) == {"browser", "crawler", "search"}


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["file:///secret", "https://user:pass@target.invalid/", "https://target.invalid:bad/", "https://target.invalid\\@other.invalid/"])
async def test_invalid_input_before_browser(url, tmp_path):
    with pytest.raises(ValueError):
        await fetch(BrowserPool(), url, "browser", tmp_path)

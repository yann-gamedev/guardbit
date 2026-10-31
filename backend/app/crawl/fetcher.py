"""Isolated multi-profile captures; callers must authorize and audit scan targets."""

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.async_api import (
    Browser,
    Error,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from app.config import settings


CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)
PROFILES = {
    "browser": {"user_agent": CHROME_UA, "extra_http_headers": {}},
    "crawler": {
        "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "extra_http_headers": {},
    },
    "search": {
        "user_agent": CHROME_UA,
        "extra_http_headers": {"Referer": "https://www.google.com/"},
    },
}
CDN_HOSTS = (
    "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "code.jquery.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "bootstrapcdn.com",
)
CHALLENGE = re.compile(
    r"tunggu sebentar|just a moment|attention required|checking your browser|access denied",
    re.IGNORECASE,
)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
WIB = timezone(timedelta(hours=7))


def _host(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"} or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or any(character.isspace() for character in url) or "\\" in url
    ):
        raise ValueError("Expected an HTTP(S) URL without credentials")
    parsed.port
    return parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")


def _within(host: str, root: str) -> bool:
    return host == root or host.endswith("." + root)


def _record(hosts: list[str], host: str) -> None:
    if host not in hosts:
        hosts.append(host)


class HostThrottle:
    def __init__(self) -> None:
        self.delay = settings.SCAN_DELAY_SECONDS
        self._locks: dict[str, asyncio.Lock] = {}
        self._last: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        host = host.lower().rstrip(".")
        async with self._locks.setdefault(host, asyncio.Lock()):
            now = time.monotonic()
            remaining = self.delay - (now - self._last.get(host, -float("inf")))
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last[host] = time.monotonic()


class BrowserPool:
    def __init__(self) -> None:
        self.browser: Browser | None = None
        self._playwright: Playwright | None = None
        self._lock = asyncio.Lock()
        self.throttle = HostThrottle()

    async def start(self) -> None:
        async with self._lock:
            if self.browser is not None:
                return
            self._playwright = await async_playwright().start()
            try:
                self.browser = await self._playwright.chromium.launch(
                    headless=True, chromium_sandbox=True,
                )
            except BaseException:
                await self._playwright.stop()
                self._playwright = None
                raise

    async def stop(self) -> None:
        async with self._lock:
            try:
                if self.browser is not None:
                    await self.browser.close()
            finally:
                self.browser = None
                if self._playwright is not None:
                    await self._playwright.stop()
                    self._playwright = None


@dataclass
class FetchResult:
    url: str
    profile: str
    status: int | None = None
    final_url: str = ""
    raw_html: str = ""
    rendered_html: str = ""
    title: str = ""
    blocked: bool = False
    block_reason: str | None = None
    redirect_attempts: list[str] = field(default_factory=list)
    blocked_request_hosts: list[str] = field(default_factory=list)
    screenshot_path: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(WIB))


def _network_reason(error: Error) -> str | None:
    if isinstance(error, PlaywrightTimeoutError) or "ERR_TIMED_OUT" in str(error):
        return "timeout"
    if any(marker in str(error) for marker in ("ERR_NAME_NOT_RESOLVED", "ENOTFOUND", "EAI_AGAIN")):
        return "dns"
    return None


async def fetch(pool: BrowserPool, url: str, profile: str, out_dir: str | Path) -> FetchResult:
    target = _host(url)
    if profile not in PROFILES:
        raise ValueError("Unknown fetch profile")
    if pool.browser is None:
        raise RuntimeError("BrowserPool.start() must be called before fetch")
    result = FetchResult(url=url, profile=profile, final_url=url)
    context = await pool.browser.new_context(**PROFILES[profile], service_workers="block")
    route_errors: list[Error] = []
    pending_navigation: list[str] = []

    async def guard(route) -> None:
        request = route.request
        navigation = request.is_navigation_request() and request.frame.parent_frame is None
        current = request.url
        for hop in range(6):
            try:
                host = _host(current)
            except ValueError:
                await route.abort()
                return
            internal = _within(host, target)
            if navigation and not internal:
                _record(result.redirect_attempts, host)
            if not internal and (navigation or not any(_within(host, cdn) for cdn in CDN_HOSTS)):
                _record(result.blocked_request_hosts, host)
                await route.abort()
                return
            if navigation and current != request.url:
                # Browser redirect hops bypass routing; restart an approved navigation instead.
                pending_navigation.append(current)
                await route.fulfill(status=200, content_type="text/html", body="")
                return
            await pool.throttle.wait(host)
            try:
                response = await route.fetch(url=current, max_redirects=0, timeout=30_000)
                try:
                    location = response.headers.get("location")
                    if response.status not in REDIRECT_STATUSES or not location:
                        await route.fulfill(response=response)
                        return
                    current = urljoin(current, location)
                finally:
                    await response.dispose()
            except Error as error:
                if navigation:
                    route_errors.append(error)
                await route.abort()
                return
        await route.abort()

    async def block_socket(socket) -> None:
        host = urlsplit(socket.url).hostname
        if host:
            _record(result.blocked_request_hosts, host)
        await socket.close()

    try:
        await context.route("**/*", guard)
        await context.route_web_socket("**/*", block_socket)
        current = url
        try:
            for hop in range(6):
                await pool.throttle.wait(_host(current))
                response = await context.request.get(current, max_redirects=0, timeout=30_000)
                try:
                    result.status = response.status
                    result.final_url = current
                    result.raw_html = await response.text()
                    location = response.headers.get("location")
                finally:
                    await response.dispose()
                if result.status not in REDIRECT_STATUSES or not location:
                    break
                destination = urljoin(current, location)
                host = _host(destination)
                if not _within(host, target):
                    _record(result.redirect_attempts, host)
                    _record(result.blocked_request_hosts, host)
                    break
                if hop == 5:
                    raise RuntimeError("HTTP redirect limit exceeded")
                current = destination
        except Error as error:
            result.block_reason = _network_reason(error)
            if result.block_reason is None:
                raise

        page = await context.new_page()
        if result.block_reason is None and not result.redirect_attempts:
            try:
                navigation_url = url
                for hop in range(6):
                    try:
                        response = await page.goto(navigation_url, wait_until="domcontentloaded", timeout=30_000)
                    except Error:
                        if not pending_navigation:
                            raise
                    if pending_navigation:
                        navigation_url = pending_navigation.pop()
                        if hop == 5:
                            raise RuntimeError("Rendered redirect limit exceeded")
                        continue
                    if response is not None:
                        result.status = response.status
                    break
                await page.wait_for_timeout(2_500)
                result.final_url = page.url
                result.rendered_html = await page.content()
                result.title = await page.title()
            except Error as error:
                # An intentionally aborted external navigation is evidence, not a DNS failure.
                if not result.redirect_attempts:
                    reason = _network_reason(route_errors[0] if route_errors else error)
                    if reason is None and not page.url.startswith("chrome-error://"):
                        raise
                    result.block_reason = reason
            if route_errors and not result.redirect_attempts:
                reason = _network_reason(route_errors[0])
                if reason is None:
                    raise route_errors[0]
                result.block_reason = result.block_reason or reason

        output = Path(out_dir)
        output.mkdir(parents=True, exist_ok=True)
        screenshot = output / f"{profile}_{time.time_ns()}.png"
        if result.redirect_attempts or page.url.startswith("chrome-error://") or result.block_reason:
            result.rendered_html = result.raw_html
            await page.close()
            # No live resources: raw HTML may contain scripts, refreshes, frames, or remote CSS.
            inert = await pool.browser.new_context(java_script_enabled=False, service_workers="block")
            try:
                await inert.route("**/*", lambda route: route.abort())
                preview = await inert.new_page()
                await preview.set_content(result.raw_html, wait_until="domcontentloaded")
                result.title = await preview.title()
                await preview.screenshot(path=str(screenshot), full_page=True)
            finally:
                await inert.close()
        else:
            await page.screenshot(path=str(screenshot), full_page=True)
        result.screenshot_path = str(screenshot)
        if result.status in {403, 429, 503}:
            result.block_reason = f"http_{result.status}"
        elif CHALLENGE.search(result.title):
            result.block_reason = "challenge"
        # 401 is blocked, but the specified reason vocabulary has no http_401.
        result.blocked = result.status in {401, 403, 429, 503} or result.block_reason is not None
        return result
    finally:
        await context.close()

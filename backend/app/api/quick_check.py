import asyncio
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Request
from playwright.async_api import Error as PlaywrightError

from app.crawl.fetcher import WIB, fetch
from app.crawl.public_http import public_address
from app.detect.l2_visibility import analyze_hidden
from app.detect.l3_lite import score_text
from app.detect.normalize import normalize
from app.detect.score import THRESHOLD, risk
from app.schemas import QuickCheckRequest, QuickCheckResponse

router = APIRouter(tags=["Cek Cepat"])
CACHE_SECONDS = 24 * 3600
CACHE_MAX = 1000
CHECK_TIMEOUT = 45


async def _check(pool, url: str) -> dict:
    result = await fetch(pool, url, "browser", None, public_only=True)
    if result.blocked:
        return _blocked()
    l2 = await analyze_hidden(pool, result.rendered_html or result.raw_html, result.final_url)
    hidden_text = l2["hidden_text"]
    s_text_hidden = score_text(hidden_text)
    _, status = risk(l2["score"], s_text_hidden)
    reasons = []
    if l2["score"] > 0 and s_text_hidden >= THRESHOLD:
        reasons.append("konten_judi_tersembunyi")
    if s_text_hidden >= THRESHOLD and normalize(hidden_text) != hidden_text:
        reasons.append("teks_judi_tersamarkan")
    return {"status": status, "reasons": reasons, "pages_checked": 1}


def _blocked() -> dict:
    return {"status": "tidak_dapat_diperiksa", "reasons": ["situs_memblokir_pemeriksaan"], "pages_checked": 1}


@router.post("/quick-check", response_model=QuickCheckResponse)
async def quick_check(body: QuickCheckRequest, request: Request):
    url = str(body.url)
    cache = request.app.state.quick_check_cache
    try:
        async with asyncio.timeout(CHECK_TIMEOUT):
            # Validate before cache: DEBUG results cannot bypass production SSRF checks.
            try:
                await public_address(url)
            except ValueError:
                raise HTTPException(status_code=400, detail="URL publik tidak valid atau alamat jaringan dilarang") from None
            except OSError:
                raise HTTPException(status_code=400, detail="Nama domain tidak dapat ditemukan") from None
            now = time.monotonic()
            hit = cache.get(url)
            if hit and now - hit[0] < CACHE_SECONDS:
                return {**hit[1], "cached": True}
            result = await _check(request.app.state.pool, url)
    except (TimeoutError, PlaywrightError, httpx.HTTPError, OSError, ValueError, RuntimeError):
        result = _blocked()
    response = {**result, "checked_at": datetime.now(WIB), "cached": False}
    if len(cache) >= CACHE_MAX:
        cache.pop(next(iter(cache)))
    cache[url] = (time.monotonic(), response)
    return response

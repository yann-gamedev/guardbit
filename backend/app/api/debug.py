from time import perf_counter

from fastapi import APIRouter, HTTPException
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from app.config import settings

router = APIRouter()


@router.get("/debug/playwright", include_in_schema=False)
def debug_playwright():
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not Found")

    try:
        with sync_playwright() as playwright:
            started = perf_counter()
            browser = playwright.chromium.launch(headless=True, timeout=30_000)
            launch_ms = (perf_counter() - started) * 1000
            try:
                page = browser.new_page()
                page.goto("about:blank", timeout=10_000)
                return {
                    "chromium_version": browser.version,
                    "launch_ms": round(launch_ms, 2),
                }
            finally:
                browser.close()
    except PlaywrightError:
        raise HTTPException(status_code=503, detail="Pemeriksaan Chromium gagal") from None

"""Serve synthetic fixtures only; never resolve request paths as filesystem paths."""

import json
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.config import settings


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
router = APIRouter(prefix="/replay", include_in_schema=False)


@lru_cache(maxsize=1)
def _manifest() -> dict:
    return json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


def _google_referer(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        return parsed.scheme in {"http", "https"} and (host == "google.com" or host.endswith(".google.com"))
    except ValueError:
        return False


@router.get("/{name}")
@router.get("/{name}/{path:path}")
def replay(request: Request, name: str, path: str = ""):
    if not settings.DEBUG and os.getenv("REPLAY_ENABLED", "").strip().lower() != "true":
        raise HTTPException(status_code=404, detail="Not Found")
    entry = _manifest().get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Not Found")
    profile = "default"
    if "googlebot" in request.headers.get("user-agent", "").lower():
        profile = "crawler"
    elif _google_referer(request.headers.get("referer", "")):
        profile = "search"
    # OJS-like suffixes are aliases of the selected fixture, never file selectors.
    filename = entry.get(profile) or entry["default"]
    root = (FIXTURE_DIR / name).resolve()
    source = (root / filename).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(
        source,
        media_type="text/html",
        status_code=entry["crawler_status"] if profile == "crawler" else 200,
        headers={"Cache-Control": "no-store", "Vary": "User-Agent, Referer"},
    )

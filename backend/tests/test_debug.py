from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error as PlaywrightError

from app.api import debug
from app.config import Settings


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_debug_setting(enabled, monkeypatch):
    monkeypatch.setenv("DEBUG", enabled)
    assert Settings(_env_file=None).DEBUG is (enabled == "true")


@pytest.fixture
def playwright(monkeypatch):
    factory = MagicMock()
    monkeypatch.setattr(debug, "sync_playwright", factory)
    return factory


def test_debug_disabled_does_not_start_playwright(client, monkeypatch, playwright):
    monkeypatch.setattr(debug.settings, "DEBUG", False)
    assert client.get("/debug/playwright").status_code == 404
    playwright.assert_not_called()
    assert "/debug/playwright" not in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("failure", [None, "launch", "new_page", "goto"])
def test_debug_launch_and_cleanup(client, monkeypatch, playwright, failure):
    monkeypatch.setattr(debug.settings, "DEBUG", True)
    chromium = playwright.return_value.__enter__.return_value.chromium
    browser = chromium.launch.return_value
    browser.version = "123.0.0.0"
    if failure == "launch":
        chromium.launch.side_effect = PlaywrightError("private launch details")
    elif failure == "new_page":
        browser.new_page.side_effect = PlaywrightError("private page details")
    elif failure == "goto":
        browser.new_page.return_value.goto.side_effect = PlaywrightError("private navigation details")

    response = client.get("/debug/playwright")
    chromium.launch.assert_called_once_with(headless=True, timeout=30_000)
    if failure:
        assert response.status_code == 503
        assert response.json() == {"detail": "Pemeriksaan Chromium gagal"}
    else:
        assert response.status_code == 200
        assert response.json()["chromium_version"] == "123.0.0.0"
        assert response.json()["launch_ms"] >= 0
        browser.new_page.return_value.goto.assert_called_once_with("about:blank", timeout=10_000)
    if failure != "launch":
        browser.close.assert_called_once()
    playwright.return_value.__exit__.assert_called_once()

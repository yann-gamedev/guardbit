import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app import main
from app.config import Settings, settings
from app.db import engine


EXPECTED_COLUMNS = {
    "sites": {"id", "domain", "alias", "site_alias", "tier", "token", "verified_at"},
    "scans": {"id", "site_id", "started_at", "finished_at", "status"},
    "pages": {"id", "scan_id", "url", "r_score", "label"},
    "findings": {"id", "page_id", "layer", "profile", "evidence_html", "detail_json"},
    "snapshots": {"id", "page_id", "profile", "html_path", "screenshot_path", "headers_json", "fetched_at"},
    "audit_log": {"id", "user", "site_alias", "action", "created_at"},
}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_startup_creates_exactly_six_tables(client):
    inspector = inspect(main.engine)
    assert set(inspector.get_table_names()) == set(EXPECTED_COLUMNS)
    for table, columns in EXPECTED_COLUMNS.items():
        assert {column["name"] for column in inspector.get_columns(table)} == columns
    for table in ("scans", "pages", "findings", "snapshots"):
        assert len(inspector.get_foreign_keys(table)) == 1


def test_sqlite_foreign_keys_enabled_without_touching_local_db():
    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite-specific constraint check")
    # Reuse the engine's connection listener on an isolated in-memory database.
    import sqlite3
    from app.db import enable_foreign_keys

    with sqlite3.connect(":memory:") as connection:
        enable_foreign_keys(connection, None)
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_invalid_tier_rejected_by_database(client):
    with main.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(
                "INSERT INTO sites (id, domain, alias, site_alias, tier) "
                "VALUES ('ste_01', 'kampus-a.example', 'Kampus A', 'Kampus A', 'invalid')"
            ))


def test_docs_and_openapi(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["version"] == "0.1.0"


def test_cors_allows_configured_origin_only(client):
    allowed = client.options("/quick-check", headers={
        "Origin": settings.FRONTEND_ORIGIN.split(",")[0],
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == settings.FRONTEND_ORIGIN.split(",")[0]
    denied = client.get("/health", headers={"Origin": "https://other.example"})
    assert "access-control-allow-origin" not in denied.headers


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://dashboard.example")
    monkeypatch.setenv("SCAN_MAX_PAGES", "12")
    monkeypatch.setenv("LLM_API_KEY", "test-secret")
    config = Settings(_env_file=None)
    assert config.FRONTEND_ORIGIN == "https://dashboard.example"
    assert config.SCAN_MAX_PAGES == 12
    assert "test-secret" not in repr(config)


@pytest.mark.parametrize("values", [{"SCAN_MAX_PAGES": 0}, {"SCAN_DELAY_SECONDS": 1}])
def test_settings_reject_unsafe_scan_limits(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)

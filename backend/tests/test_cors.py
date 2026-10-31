import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_origin_list_normalizes_whitespace_empty_items_and_duplicates():
    config = Settings(_env_file=None, FRONTEND_ORIGIN=" http://localhost:3000, https://dashboard.example , ,http://localhost:3000,")
    assert config.FRONTEND_ORIGIN == "http://localhost:3000,https://dashboard.example"


@pytest.mark.parametrize("value", ["", ", ,", "*", "https://*.example", "ftp://dashboard.example", "https://dashboard.example/path", "https://user:pass@dashboard.example", "https://dashboard.example:99999", "https://dashboard.example?q=1", "https://dashboard.example#fragment"])
def test_invalid_origins_rejected(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, FRONTEND_ORIGIN=value)


def test_cors_uses_both_env_origins_at_startup():
    result = subprocess.run(
        [sys.executable, "-c", '''
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
for origin in ("http://localhost:3000", "https://dashboard.example"):
    response = client.options("/quick-check", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,authorization"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert client.get("/health", headers={"Origin": origin}).headers["access-control-allow-origin"] == origin
response = client.options("/quick-check", headers={"Origin": "https://other.example", "Access-Control-Request-Method": "POST"})
assert response.status_code == 400
assert "access-control-allow-origin" not in response.headers
'''],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, FRONTEND_ORIGIN=" http://localhost:3000, https://dashboard.example, ", DATABASE_URL="sqlite://"),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr

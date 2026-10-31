from pathlib import Path

from sqlalchemy import create_engine
import yaml


def test_render_deployment_config():
    root = Path(__file__).resolve().parents[2]
    service, = yaml.safe_load((root / "render.yaml").read_text())["services"]
    assert service["runtime"] == "docker"
    assert service["plan"] == "1c-2g"
    assert service["healthCheckPath"] == "/health"
    assert service["autoDeployTrigger"] == "off"
    assert (root / service["dockerfilePath"]).is_file()
    assert (root / service["dockerContext"] / "requirements.txt").is_file()
    assert {item["key"] for item in service["envVars"]} == {"DEBUG", "FRONTEND_ORIGIN", "DATABASE_URL"}
    assert all(item == {"key": item["key"], "sync": False} for item in service["envVars"])


def test_postgresql_driver_loads_without_connecting():
    engine = create_engine("postgresql+psycopg://")
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()

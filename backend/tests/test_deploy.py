from pathlib import Path

from sqlalchemy import create_engine


def test_docker_build_context_and_runtime_port():
    backend = Path(__file__).resolve().parents[1]
    dockerfile = (backend / "Dockerfile").read_text()
    assert (backend / "requirements.txt").is_file()
    assert (backend / "app/main.py").is_file()
    assert "COPY requirements.txt ." in dockerfile
    assert "COPY --chown=pwuser:pwuser app ./app" in dockerfile
    assert "--host 0.0.0.0 --port ${PORT:-8000}" in dockerfile


def test_postgresql_driver_loads_without_connecting():
    engine = create_engine("postgresql+psycopg://")
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()

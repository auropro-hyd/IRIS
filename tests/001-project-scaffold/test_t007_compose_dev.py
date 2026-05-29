"""T007 acceptance tests for compose.dev.yaml and the /healthz endpoint.

Fast tests inspect compose.dev.yaml structure, the custom Postgres Dockerfile,
and the postgres-init.sql script, then hit /healthz via FastAPI TestClient.
The slow test runs ``make up`` / ``make down`` against a real Docker daemon.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "compose.dev.yaml"
POSTGRES_DOCKERFILE = REPO_ROOT / "docker" / "postgres.Dockerfile"
POSTGRES_INIT_SQL = REPO_ROOT / "docker" / "postgres-init.sql"

# Ports chosen to avoid collisions with default local stacks.
EXPECTED_DB_HOST_PORT = "5488"
EXPECTED_REDIS_HOST_PORT = "6399"


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text())


# ── compose.dev.yaml ──────────────────────────────────────────────────────────


def test_compose_dev_yaml_exists() -> None:
    assert COMPOSE_FILE.exists(), "compose.dev.yaml not found at repo root"


def test_compose_has_db_service() -> None:
    cfg = _load_compose()
    assert "db" in cfg.get("services", {}), "compose.dev.yaml is missing the 'db' service"


def test_compose_has_redis_service() -> None:
    cfg = _load_compose()
    assert "redis" in cfg.get("services", {}), "compose.dev.yaml is missing the 'redis' service"


def test_compose_db_port_remapped() -> None:
    cfg = _load_compose()
    ports = cfg["services"]["db"].get("ports", [])
    host_ports = [str(p).split(":")[0].strip('"') for p in ports]
    assert (
        EXPECTED_DB_HOST_PORT in host_ports
    ), f"db service should expose host port {EXPECTED_DB_HOST_PORT}; got {ports}"


def test_compose_redis_port_remapped() -> None:
    cfg = _load_compose()
    ports = cfg["services"]["redis"].get("ports", [])
    host_ports = [str(p).split(":")[0].strip('"') for p in ports]
    assert (
        EXPECTED_REDIS_HOST_PORT in host_ports
    ), f"redis service should expose host port {EXPECTED_REDIS_HOST_PORT}; got {ports}"


def test_compose_db_references_custom_dockerfile() -> None:
    cfg = _load_compose()
    build = cfg["services"]["db"].get("build", {})
    assert "postgres.Dockerfile" in build.get(
        "dockerfile", ""
    ), "db service 'build.dockerfile' should reference docker/postgres.Dockerfile"


def test_compose_named_volumes_declared() -> None:
    cfg = _load_compose()
    volumes = cfg.get("volumes", {})
    assert "db-data" in volumes, "compose.dev.yaml is missing the 'db-data' volume"
    assert "redis-data" in volumes, "compose.dev.yaml is missing the 'redis-data' volume"


# ── custom Postgres image ─────────────────────────────────────────────────────


def test_postgres_dockerfile_exists() -> None:
    assert POSTGRES_DOCKERFILE.exists(), "docker/postgres.Dockerfile not found"


def test_postgres_dockerfile_extends_pgvector() -> None:
    content = POSTGRES_DOCKERFILE.read_text()
    assert (
        "pgvector/pgvector" in content
    ), "docker/postgres.Dockerfile should base on pgvector/pgvector"


def test_postgres_dockerfile_installs_age() -> None:
    content = POSTGRES_DOCKERFILE.read_text()
    assert (
        "age" in content.lower()
    ), "docker/postgres.Dockerfile should install the Apache AGE extension"


def test_postgres_init_sql_exists() -> None:
    assert POSTGRES_INIT_SQL.exists(), "docker/postgres-init.sql not found"


def test_postgres_init_sql_enables_vector() -> None:
    content = POSTGRES_INIT_SQL.read_text()
    assert (
        "vector" in content.lower()
    ), "docker/postgres-init.sql should enable the vector extension"


def test_postgres_init_sql_enables_age() -> None:
    content = POSTGRES_INIT_SQL.read_text()
    assert "age" in content.lower(), "docker/postgres-init.sql should enable the age extension"


# ── /healthz endpoint ─────────────────────────────────────────────────────────


def test_healthz_returns_200() -> None:
    from fastapi.testclient import TestClient
    from iris_api.main import app

    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200, f"/healthz returned {response.status_code}, expected 200"


def test_healthz_body_is_status_ok() -> None:
    from fastapi.testclient import TestClient
    from iris_api.main import app

    client = TestClient(app)
    response = client.get("/healthz")
    assert response.json() == {
        "status": "ok"
    }, f"/healthz body was {response.json()!r}, expected {{'status': 'ok'}}"


def test_healthz_response_model_is_typed() -> None:
    from iris_api.main import HealthResponse

    assert hasattr(HealthResponse, "model_fields"), "HealthResponse should be a Pydantic BaseModel"
    assert "status" in HealthResponse.model_fields, "HealthResponse.status field is missing"


# ── make up / make down ───────────────────────────────────────────────────────


@pytest.mark.slow
def test_make_up_and_down_exit_zero() -> None:
    if shutil.which("make") is None:
        pytest.skip("make not available on this host")
    if shutil.which("docker") is None:
        pytest.skip("docker not available on this host")
    try:
        up = subprocess.run(
            ["make", "up"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert up.returncode == 0, (
            f"make up exited {up.returncode}\n" f"stdout:\n{up.stdout}\nstderr:\n{up.stderr}"
        )
    finally:
        subprocess.run(
            ["make", "down"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

"""Test GET /health endpoint."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_health_status_ok() -> None:
    """Done when: /health returns 200 with status 'ok'."""
    app = create_app(Settings(_env_file=None))  # type: ignore[call-arg]
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_response_shape() -> None:
    """Done when: /health response has exactly status, version, and env."""
    app = create_app(Settings(_env_file=None))  # type: ignore[call-arg]
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status", "version", "env"}


def test_health_version_from_settings() -> None:
    """Done when: /health version matches settings.git_sha."""
    settings = Settings(_env_file=None, git_sha="abc123")  # type: ignore[call-arg]
    app = create_app(settings)
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert data["version"] == "abc123"


def test_health_env_from_settings() -> None:
    """Done when: /health env matches settings.env."""
    settings = Settings(_env_file=None, env="dev")  # type: ignore[call-arg]
    app = create_app(settings)
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert data["env"] == "dev"


def test_docs_enabled_local() -> None:
    """Done when: /docs and /openapi.json are 200 in local."""
    settings = Settings(_env_file=None, env="local")  # type: ignore[call-arg]
    app = create_app(settings)
    client = TestClient(app)
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_enabled_dev() -> None:
    """Done when: /docs and /openapi.json are 200 in dev."""
    settings = Settings(_env_file=None, env="dev")  # type: ignore[call-arg]
    app = create_app(settings)
    client = TestClient(app)
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_disabled_prod() -> None:
    """Done when: /docs and /openapi.json are 404 in prod."""
    settings = Settings(_env_file=None, env="prod")  # type: ignore[call-arg]
    app = create_app(settings)
    client = TestClient(app)
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404

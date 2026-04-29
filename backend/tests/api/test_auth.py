from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import reset_database_state
from app.main import create_app


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "auth-test.db"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    monkeypatch.setenv("PENTAI_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    reset_database_state()

    app = create_app()
    with TestClient(app) as client:
        app.state.user_service.create_user(
            email="user@pentai.local",
            password="correct-horse-battery-staple",
            display_name="User",
            role="operator",
        )
        yield client

    get_settings.cache_clear()
    reset_database_state()


def test_protected_route_rejects_unauthenticated(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/engagements")
    assert response.status_code == 401


def test_login_invalid_credentials(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/auth/login",
        json={"email": "user@pentai.local", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"


def test_login_me_logout_round_trip(app_client: TestClient) -> None:
    login_response = app_client.post(
        "/api/v1/auth/login",
        json={"email": "user@pentai.local", "password": "correct-horse-battery-staple"},
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert body["user"]["email"] == "user@pentai.local"
    assert body["user"]["role"] == "operator"
    assert "expires_at" in body
    assert "pentai_session" in login_response.cookies

    me_response = app_client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@pentai.local"

    engagements_response = app_client.get("/api/v1/engagements")
    assert engagements_response.status_code == 200

    logout_response = app_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    follow_up = app_client.get("/api/v1/auth/me")
    assert follow_up.status_code == 401


def test_healthz_is_public(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/healthz")
    assert response.status_code == 200

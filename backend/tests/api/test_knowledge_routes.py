from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import reset_database_state
from app.knowledge.service import KnowledgeService
from app.main import create_app


class FakeEmbedder:
    def __init__(self, dim: int = 16) -> None:
        self._dim = dim

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token in text.lower().split():
            if token.isalnum():
                vector[hash(token) % self._dim] += 1.0
        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "pentai-test.db"
    artifacts_root = tmp_path / "artifacts"
    kb_root = tmp_path / "kb"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    monkeypatch.setenv("PENTAI_ARTIFACTS_ROOT", str(artifacts_root))
    monkeypatch.setenv("PENTAI_KNOWLEDGE_UPLOADS_ROOT", str(kb_root))
    get_settings.cache_clear()
    reset_database_state()

    app = create_app()
    with TestClient(app) as test_client:
        app.state.knowledge_service = KnowledgeService(
            session_factory=app.state.db_session_factory,
            embedder=FakeEmbedder(),
            embedding_model="fake-embed",
        )
        app.state.user_service.create_user(
            email="tester@pentai.local",
            password="test-password-123",
            display_name="Tester",
            role="admin",
        )
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "tester@pentai.local", "password": "test-password-123"},
        )
        assert login.status_code == 200, login.text
        yield test_client

    get_settings.cache_clear()
    reset_database_state()


def test_unauthenticated_requests_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "pentai-test.db"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    monkeypatch.setenv("PENTAI_KNOWLEDGE_UPLOADS_ROOT", str(tmp_path / "kb"))
    get_settings.cache_clear()
    reset_database_state()
    app = create_app()
    with TestClient(app) as test_client:
        resp = test_client.get("/api/v1/knowledge/search?q=nmap")
        assert resp.status_code == 401
    get_settings.cache_clear()
    reset_database_state()


def test_ingest_then_search_returns_hit(client: TestClient) -> None:
    body = (
        "# Recon Playbook\n\n"
        "Use nmap service scan against the engagement scope to enumerate ports "
        "and identify exposed services.\n"
    )
    resp = client.post(
        "/api/v1/knowledge/sources",
        json={"filename": "playbook.md", "content": body},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["chunks_written"] >= 1
    assert data["skipped"] is False

    resp = client.get("/api/v1/knowledge/search", params={"q": "nmap service scan", "top_k": 3})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["query"] == "nmap service scan"
    assert payload["hits"], "expected at least one hit"
    assert "nmap" in payload["hits"][0]["content"].lower()


def test_ingest_rejects_unsafe_filename(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/knowledge/sources",
        json={"filename": "../etc/passwd.md", "content": "# x\n\nbody"},
    )
    assert resp.status_code == 400


def test_search_validates_query(client: TestClient) -> None:
    resp = client.get("/api/v1/knowledge/search", params={"q": ""})
    assert resp.status_code == 422


def test_list_and_delete_sources(client: TestClient) -> None:
    body = "# Recon\n\nUse nmap service scan.\n"
    resp = client.post(
        "/api/v1/knowledge/sources",
        json={"filename": "playbook.md", "content": body},
    )
    assert resp.status_code == 201, resp.text
    source_path = resp.json()["source_path"]

    listing = client.get("/api/v1/knowledge/sources")
    assert listing.status_code == 200
    rows = listing.json()
    assert any(r["source_path"] == source_path for r in rows)
    assert all(r["chunk_count"] >= 1 for r in rows)

    deleted = client.delete(
        "/api/v1/knowledge/sources", params={"source_path": source_path}
    )
    assert deleted.status_code == 200, deleted.text
    payload = deleted.json()
    assert payload["chunks_deleted"] >= 1

    listing_after = client.get("/api/v1/knowledge/sources")
    assert all(r["source_path"] != source_path for r in listing_after.json())


def test_delete_unknown_source_returns_404(client: TestClient) -> None:
    resp = client.delete(
        "/api/v1/knowledge/sources", params={"source_path": "/nope/missing.md"}
    )
    assert resp.status_code == 404

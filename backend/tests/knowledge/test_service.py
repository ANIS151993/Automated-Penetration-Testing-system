from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers metadata)
from app.knowledge.retrieval import cosine_similarity
from app.knowledge.service import KnowledgeService
from app.models.base import Base


class FakeEmbedder:
    """Deterministic embedder: hashes tokens to dimensions in a small space."""

    def __init__(self, dim: int = 16) -> None:
        self._dim = dim

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        tokens = [t for t in text.lower().split() if t.isalnum()]
        for token in tokens:
            vector[hash(token) % self._dim] += 1.0
        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'kb.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def test_cosine_similarity_handles_zero_and_match() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_ingest_and_search_returns_relevant_chunk(tmp_path: Path, session_factory) -> None:
    doc = tmp_path / "playbook.md"
    recon_body = (
        "Use nmap service scan against the engagement scope. "
        "Capture banners and identify exposed services. "
    ) * 8
    reporting_body = (
        "Generate a final JSON report once findings stabilise. "
        "Cross-reference suggested findings against the audit trail. "
    ) * 8
    doc.write_text(
        f"# Recon\n\n{recon_body}\n\n# Reporting\n\n{reporting_body}\n",
        encoding="utf-8",
    )
    service = KnowledgeService(
        session_factory=session_factory,
        embedder=FakeEmbedder(),
        embedding_model="fake-embed",
    )

    result = asyncio.run(service.ingest_path(doc))
    assert result.chunks_written >= 1

    results = asyncio.run(service.search("nmap service scan", top_k=3))
    assert results
    assert "nmap" in results[0].content.lower()
    assert results[0].score > 0


def test_reingest_replaces_chunks(tmp_path: Path, session_factory) -> None:
    doc = tmp_path / "rotating.md"
    doc.write_text("# v1\n\noriginal content here.\n", encoding="utf-8")
    service = KnowledgeService(
        session_factory=session_factory,
        embedder=FakeEmbedder(),
        embedding_model="fake-embed",
    )
    asyncio.run(service.ingest_path(doc))
    assert len(service.repository.list_all()) == 1

    long_body = "replacement content for round two. " * 80
    doc.write_text(f"# v2\n\n{long_body}\n", encoding="utf-8")
    asyncio.run(service.ingest_path(doc))
    stored = service.repository.list_all()
    assert stored, "expected at least one chunk after re-ingest"
    assert all("original" not in chunk.content for chunk in stored)
    assert all(chunk.source_path == str(doc) for chunk in stored)


def test_search_context_formats_blocks(tmp_path: Path, session_factory) -> None:
    doc = tmp_path / "kb.md"
    doc.write_text("# Topic\n\nuseful nmap detail.\n", encoding="utf-8")
    service = KnowledgeService(
        session_factory=session_factory,
        embedder=FakeEmbedder(),
        embedding_model="fake-embed",
    )
    asyncio.run(service.ingest_path(doc))

    context = asyncio.run(service.search_context("nmap", top_k=1, min_score=0.0))
    assert "[1]" in context
    assert "useful nmap detail" in context

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session, sessionmaker

from app.knowledge.ingestors.markdown import IngestResult, MarkdownIngestor
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.retrieval import (
    Embedder,
    KnowledgeRetriever,
    RetrievedChunk,
    format_context,
)


class KnowledgeService:
    """High-level façade for KB ingestion and retrieval."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        embedder: Embedder,
        embedding_model: str,
    ) -> None:
        self._repository = KnowledgeRepository(session_factory)
        self._embedder = embedder
        self._embedding_model = embedding_model
        self._ingestor = MarkdownIngestor(
            repository=self._repository,
            embedder=embedder,
            embedding_model=embedding_model,
        )
        self._retriever = KnowledgeRetriever(
            repository=self._repository,
            embedder=embedder,
            embedding_model=embedding_model,
        )

    @property
    def repository(self) -> KnowledgeRepository:
        return self._repository

    async def ingest_path(
        self, path: Path, *, source_kind: str = "markdown", metadata: dict | None = None
    ) -> IngestResult:
        if path.is_dir():
            results = await self._ingestor.ingest_directory(
                path, source_kind=source_kind, metadata=metadata
            )
            total = sum(r.chunks_written for r in results)
            return IngestResult(source_path=str(path), chunks_written=total, skipped=False)
        return await self._ingestor.ingest_file(
            path, source_kind=source_kind, metadata=metadata
        )

    async def ingest_paths(
        self,
        paths: Iterable[Path],
        *,
        source_kind: str = "markdown",
        metadata: dict | None = None,
    ) -> list[IngestResult]:
        return await self._ingestor.ingest_paths(
            paths, source_kind=source_kind, metadata=metadata
        )

    async def search(
        self, query: str, *, top_k: int = 5, min_score: float = 0.0
    ) -> list[RetrievedChunk]:
        return await self._retriever.search(query, top_k=top_k, min_score=min_score)

    def list_sources(self) -> list[dict]:
        return self._repository.list_sources()

    def delete_source(self, source_path: str) -> int:
        return self._repository.delete_source(source_path)

    async def search_context(
        self, query: str, *, top_k: int = 5, min_score: float = 0.15
    ) -> str:
        chunks = await self.search(query, top_k=top_k, min_score=min_score)
        return format_context(chunks)

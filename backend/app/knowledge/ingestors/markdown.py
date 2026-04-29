from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from app.knowledge.chunker import Chunk, chunk_markdown
from app.knowledge.repository import KnowledgeRepository


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


@dataclass(slots=True)
class IngestResult:
    source_path: str
    chunks_written: int
    skipped: bool
    reason: str | None = None


class MarkdownIngestor:
    def __init__(
        self,
        *,
        repository: KnowledgeRepository,
        embedder: Embedder,
        embedding_model: str,
    ) -> None:
        self._repository = repository
        self._embedder = embedder
        self._embedding_model = embedding_model

    async def ingest_file(
        self,
        path: Path,
        *,
        source_kind: str = "markdown",
        metadata: dict | None = None,
    ) -> IngestResult:
        text = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text)
        if not chunks:
            return IngestResult(
                source_path=str(path),
                chunks_written=0,
                skipped=True,
                reason="no extractable content",
            )
        records = []
        for chunk in chunks:
            embedding = await self._embedder.embed(_embed_input(chunk))
            records.append(
                {
                    "title": chunk.title,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "embedding": embedding,
                    "chunk_metadata": metadata or {},
                }
            )
        written = self._repository.replace_source(
            source_path=str(path),
            source_kind=source_kind,
            embedding_model=self._embedding_model,
            records=records,
        )
        return IngestResult(source_path=str(path), chunks_written=written, skipped=False)

    async def ingest_paths(
        self,
        paths: Iterable[Path],
        *,
        source_kind: str = "markdown",
        metadata: dict | None = None,
    ) -> list[IngestResult]:
        results: list[IngestResult] = []
        for path in paths:
            results.append(
                await self.ingest_file(path, source_kind=source_kind, metadata=metadata)
            )
        return results

    async def ingest_directory(
        self,
        directory: Path,
        *,
        glob: str = "**/*.md",
        source_kind: str = "markdown",
        metadata: dict | None = None,
    ) -> list[IngestResult]:
        paths = sorted(p for p in directory.glob(glob) if p.is_file())
        return await self.ingest_paths(paths, source_kind=source_kind, metadata=metadata)


def _embed_input(chunk: Chunk) -> str:
    if chunk.title:
        return f"{chunk.title}\n\n{chunk.content}"
    return chunk.content


def run(coroutine):
    """Convenience helper for synchronous callers (CLI scripts, tests)."""
    return asyncio.run(coroutine)

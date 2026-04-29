from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from app.knowledge.repository import KnowledgeRepository, StoredChunk


class Embedder(Protocol):
    async def embed(self, text: str) -> list[float]: ...


@dataclass(slots=True)
class RetrievedChunk:
    source_path: str
    title: str
    content: str
    score: float
    chunk_metadata: dict


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class KnowledgeRetriever:
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

    async def search(
        self, query: str, *, top_k: int = 5, min_score: float = 0.0
    ) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        query_embedding = await self._embedder.embed(query)
        chunks = self._repository.list_for_model(self._embedding_model)
        scored: list[tuple[float, StoredChunk]] = []
        for chunk in chunks:
            score = cosine_similarity(query_embedding, chunk.embedding)
            if score >= min_score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedChunk(
                source_path=chunk.source_path,
                title=chunk.title,
                content=chunk.content,
                score=score,
                chunk_metadata=chunk.chunk_metadata,
            )
            for score, chunk in scored[:top_k]
        ]


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        header = f"[{index}] {chunk.source_path}"
        if chunk.title:
            header += f" :: {chunk.title}"
        blocks.append(f"{header}\n{chunk.content}")
    return "\n\n---\n\n".join(blocks)

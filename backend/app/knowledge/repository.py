from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.knowledge_chunk import KnowledgeChunkModel


@dataclass(slots=True)
class StoredChunk:
    id: str
    source_path: str
    source_kind: str
    title: str
    chunk_index: int
    content: str
    content_hash: str
    embedding: list[float]
    embedding_model: str
    chunk_metadata: dict[str, Any]


class KnowledgeRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def replace_source(
        self,
        *,
        source_path: str,
        source_kind: str,
        embedding_model: str,
        records: list[dict[str, Any]],
    ) -> int:
        with self._session_factory() as session:
            session.execute(
                delete(KnowledgeChunkModel).where(
                    KnowledgeChunkModel.source_path == source_path
                )
            )
            for record in records:
                session.add(
                    KnowledgeChunkModel(
                        source_path=source_path,
                        source_kind=source_kind,
                        title=record.get("title", ""),
                        chunk_index=record["chunk_index"],
                        content=record["content"],
                        content_hash=record["content_hash"],
                        embedding=record["embedding"],
                        embedding_model=embedding_model,
                        chunk_metadata=record.get("chunk_metadata", {}),
                    )
                )
            session.commit()
            return len(records)

    def list_all(self) -> list[StoredChunk]:
        with self._session_factory() as session:
            rows = session.scalars(select(KnowledgeChunkModel)).all()
            return [self._to_stored(row) for row in rows]

    def list_for_model(self, embedding_model: str) -> list[StoredChunk]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(KnowledgeChunkModel).where(
                    KnowledgeChunkModel.embedding_model == embedding_model
                )
            ).all()
            return [self._to_stored(row) for row in rows]

    def list_sources(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    KnowledgeChunkModel.source_path,
                    KnowledgeChunkModel.source_kind,
                    KnowledgeChunkModel.embedding_model,
                    func.count(KnowledgeChunkModel.id).label("chunk_count"),
                    func.max(KnowledgeChunkModel.updated_at).label("updated_at"),
                ).group_by(
                    KnowledgeChunkModel.source_path,
                    KnowledgeChunkModel.source_kind,
                    KnowledgeChunkModel.embedding_model,
                )
            ).all()
            return [
                {
                    "source_path": r.source_path,
                    "source_kind": r.source_kind,
                    "embedding_model": r.embedding_model,
                    "chunk_count": int(r.chunk_count),
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]

    def delete_source(self, source_path: str) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(KnowledgeChunkModel).where(
                    KnowledgeChunkModel.source_path == source_path
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    def count(self) -> int:
        with self._session_factory() as session:
            return session.scalar(
                select(KnowledgeChunkModel.id).limit(0)  # type: ignore[arg-type]
            ) or sum(1 for _ in session.scalars(select(KnowledgeChunkModel.id)))

    @staticmethod
    def _to_stored(row: KnowledgeChunkModel) -> StoredChunk:
        return StoredChunk(
            id=str(row.id),
            source_path=row.source_path,
            source_kind=row.source_kind,
            title=row.title,
            chunk_index=row.chunk_index,
            content=row.content,
            content_hash=row.content_hash,
            embedding=list(row.embedding),
            embedding_model=row.embedding_model,
            chunk_metadata=dict(row.chunk_metadata or {}),
        )

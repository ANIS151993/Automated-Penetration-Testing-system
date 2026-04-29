from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.knowledge.service import KnowledgeService


knowledge_router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.md$")


class IngestSourceRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    metadata: dict | None = None


class IngestSourceResponse(BaseModel):
    source_path: str
    chunks_written: int
    skipped: bool


class KnowledgeSource(BaseModel):
    source_path: str
    source_kind: str
    embedding_model: str
    chunk_count: int
    updated_at: str | None = None


class DeleteSourceResponse(BaseModel):
    source_path: str
    chunks_deleted: int


class SearchHit(BaseModel):
    source_path: str
    title: str
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


def _get_service(request: Request) -> KnowledgeService:
    service = getattr(request.app.state, "knowledge_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="knowledge_service_unavailable",
        )
    return service


@knowledge_router.post(
    "/sources",
    response_model=IngestSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_source(
    payload: IngestSourceRequest, request: Request
) -> IngestSourceResponse:
    if not _SAFE_NAME.match(payload.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filename must match [A-Za-z0-9._-]+.md",
        )
    service = _get_service(request)
    settings = request.app.state.settings
    root = Path(settings.knowledge_uploads_root)
    root.mkdir(parents=True, exist_ok=True)
    target = (root / payload.filename).resolve()
    if root.resolve() not in target.parents and target.parent != root.resolve():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_path"
        )
    target.write_text(payload.content, encoding="utf-8")
    result = await service.ingest_path(target, metadata=payload.metadata)
    return IngestSourceResponse(
        source_path=result.source_path,
        chunks_written=result.chunks_written,
        skipped=result.skipped,
    )


@knowledge_router.get("/sources", response_model=list[KnowledgeSource])
def list_sources(request: Request) -> list[KnowledgeSource]:
    service = _get_service(request)
    return [KnowledgeSource(**row) for row in service.list_sources()]


@knowledge_router.delete(
    "/sources", response_model=DeleteSourceResponse
)
def delete_source(
    request: Request, source_path: str = Query(min_length=1, max_length=500)
) -> DeleteSourceResponse:
    service = _get_service(request)
    deleted = service.delete_source(source_path)
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="source_not_found"
        )
    settings = request.app.state.settings
    root = Path(settings.knowledge_uploads_root).resolve()
    try:
        candidate = Path(source_path).resolve()
        if candidate.is_file() and (
            root == candidate.parent or root in candidate.parents
        ):
            candidate.unlink()
    except OSError:
        pass
    return DeleteSourceResponse(source_path=source_path, chunks_deleted=deleted)


@knowledge_router.get("/search", response_model=SearchResponse)
async def search_knowledge(
    request: Request,
    q: str = Query(min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=20),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
) -> SearchResponse:
    service = _get_service(request)
    chunks = await service.search(q, top_k=top_k, min_score=min_score)
    hits = [
        SearchHit(
            source_path=c.source_path,
            title=c.title,
            content=c.content,
            score=c.score,
        )
        for c in chunks
    ]
    return SearchResponse(query=q, hits=hits)

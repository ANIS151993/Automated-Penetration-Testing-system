"""Bulk-ingest markdown documents into the knowledge base.

Usage:
    uv run python scripts/ingest_kb.py <path> [<path> ...]

`<path>` may be a file or a directory (recursive *.md). Requires Ollama
reachable at PENTAI_OLLAMA_URL with the embedding model available.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.database import initialize_database, session_factory_from_settings
from app.core.llm_client import MODEL_ROUTING, LLMClient
from app.knowledge.service import KnowledgeService


async def main(paths: list[Path]) -> int:
    settings = get_settings()
    factory = session_factory_from_settings()
    initialize_database(factory)

    async with LLMClient(base_url=settings.ollama_url) as llm:
        service = KnowledgeService(
            session_factory=factory,
            embedder=llm,
            embedding_model=MODEL_ROUTING["embed"],
        )
        for path in paths:
            print(f"[kb] ingesting {path}")
            if path.is_dir():
                from app.knowledge.ingestors.markdown import MarkdownIngestor

                ingestor = MarkdownIngestor(
                    repository=service.repository,
                    embedder=llm,
                    embedding_model=MODEL_ROUTING["embed"],
                )
                results = await ingestor.ingest_directory(path)
                for result in results:
                    status = "skipped" if result.skipped else f"{result.chunks_written} chunks"
                    print(f"[kb]   {result.source_path}: {status}")
            else:
                result = await service.ingest_path(path)
                status = "skipped" if result.skipped else f"{result.chunks_written} chunks"
                print(f"[kb]   {result.source_path}: {status}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main([Path(arg).resolve() for arg in sys.argv[1:]])))

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(slots=True)
class Chunk:
    title: str
    content: str
    chunk_index: int

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def chunk_markdown(
    text: str,
    *,
    max_chars: int = 1800,
    min_chars: int = 200,
) -> list[Chunk]:
    """Split markdown into roughly heading-aligned chunks.

    Preserves headings as chunk titles. Combines short sections under the same
    parent heading until they exceed `min_chars`, and splits long sections at
    paragraph boundaries near `max_chars`.
    """
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match is not None:
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
                current_lines = []
            current_title = match.group(2).strip()
            continue
        current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))

    chunks: list[Chunk] = []
    buffered_title = ""
    buffered_body = ""

    def flush() -> None:
        nonlocal buffered_title, buffered_body
        body = buffered_body.strip()
        if body:
            chunks.append(Chunk(title=buffered_title, content=body, chunk_index=len(chunks)))
        buffered_title = ""
        buffered_body = ""

    for title, body in sections:
        if not body:
            continue
        if not buffered_title:
            buffered_title = title
        candidate = (buffered_body + "\n\n" + body).strip() if buffered_body else body
        if len(candidate) <= max_chars or len(buffered_body) < min_chars:
            buffered_body = candidate
            continue
        flush()
        buffered_title = title
        buffered_body = body

    if buffered_body:
        flush()

    expanded: list[Chunk] = []
    for chunk in chunks:
        if len(chunk.content) <= max_chars:
            expanded.append(chunk)
            continue
        for piece in _split_long(chunk.content, max_chars):
            expanded.append(
                Chunk(title=chunk.title, content=piece, chunk_index=len(expanded))
            )
    for index, chunk in enumerate(expanded):
        chunk.chunk_index = index
    return expanded


def _split_long(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    pieces: list[str] = []
    buf = ""
    for paragraph in paragraphs:
        if not buf:
            buf = paragraph
            continue
        if len(buf) + 2 + len(paragraph) <= max_chars:
            buf = f"{buf}\n\n{paragraph}"
        else:
            pieces.append(buf)
            buf = paragraph
    if buf:
        pieces.append(buf)
    return pieces

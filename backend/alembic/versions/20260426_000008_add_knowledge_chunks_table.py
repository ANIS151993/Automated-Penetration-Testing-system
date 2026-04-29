"""Add knowledge_chunks table for retrieval-augmented planning."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260426_000008"
down_revision = "20260425_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "knowledge_chunks" not in table_names:
        op.create_table(
            "knowledge_chunks",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("source_path", sa.String(length=512), nullable=False),
            sa.Column("source_kind", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("embedding", sa.JSON(), nullable=False),
            sa.Column("chunk_metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("embedding_model", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = {idx["name"] for idx in inspect(bind).get_indexes("knowledge_chunks")}
    if op.f("ix_knowledge_chunks_source_path") not in indexes:
        op.create_index(
            op.f("ix_knowledge_chunks_source_path"),
            "knowledge_chunks",
            ["source_path"],
        )
    if op.f("ix_knowledge_chunks_content_hash") not in indexes:
        op.create_index(
            op.f("ix_knowledge_chunks_content_hash"),
            "knowledge_chunks",
            ["content_hash"],
        )
    if "ix_knowledge_chunks_source_path_chunk_index" not in indexes:
        op.create_index(
            "ix_knowledge_chunks_source_path_chunk_index",
            "knowledge_chunks",
            ["source_path", "chunk_index"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "knowledge_chunks" not in inspector.get_table_names():
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("knowledge_chunks")}
    for name in (
        "ix_knowledge_chunks_source_path_chunk_index",
        op.f("ix_knowledge_chunks_content_hash"),
        op.f("ix_knowledge_chunks_source_path"),
    ):
        if name in indexes:
            op.drop_index(name, table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

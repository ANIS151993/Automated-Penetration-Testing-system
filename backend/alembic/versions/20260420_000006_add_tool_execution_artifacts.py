"""Add tool execution artifact tracking."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260420_000006"
down_revision = "20260420_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "tool_executions" not in table_names:
        op.create_table(
            "tool_executions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("engagement_id", sa.Uuid(), nullable=False),
            sa.Column("invocation_id", sa.Uuid(), nullable=False),
            sa.Column("tool_name", sa.String(length=120), nullable=False),
            sa.Column("operation_name", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column("exit_code", sa.Integer(), nullable=True),
            sa.Column("stdout_lines", sa.Integer(), nullable=False),
            sa.Column("stderr_lines", sa.Integer(), nullable=False),
            sa.Column("artifact_path", sa.String(length=512), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    index_names = {index["name"] for index in inspect(bind).get_indexes("tool_executions")}
    engagement_index_name = op.f("ix_tool_executions_engagement_id")
    invocation_index_name = op.f("ix_tool_executions_invocation_id")
    if engagement_index_name not in index_names:
        op.create_index(
            engagement_index_name,
            "tool_executions",
            ["engagement_id"],
            unique=False,
        )
    if invocation_index_name not in index_names:
        op.create_index(
            invocation_index_name,
            "tool_executions",
            ["invocation_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "tool_executions" not in table_names:
        return

    index_names = {index["name"] for index in inspector.get_indexes("tool_executions")}
    for index_name in (
        op.f("ix_tool_executions_engagement_id"),
        op.f("ix_tool_executions_invocation_id"),
    ):
        if index_name in index_names:
            op.drop_index(index_name, table_name="tool_executions")

    op.drop_table("tool_executions")

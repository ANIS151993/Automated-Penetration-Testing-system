"""Relax legacy tool_invocations constraints for evidence persistence."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260420_000004"
down_revision = "20260420_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "tool_invocations" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("tool_invocations")}
    for column_name in ("scope_check", "prev_hash", "evidence_hash"):
        if column_name not in columns:
            continue
        op.alter_column(
            "tool_invocations",
            column_name,
            existing_type=sa.Text(),
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "tool_invocations" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("tool_invocations")}
    for column_name, default in (
        ("scope_check", "validated"),
        ("prev_hash", "legacy"),
        ("evidence_hash", "legacy"),
    ):
        if column_name not in columns:
            continue
        op.execute(
            sa.text(
                f"UPDATE tool_invocations SET {column_name} = '{default}' "
                f"WHERE {column_name} IS NULL"
            )
        )
        op.alter_column(
            "tool_invocations",
            column_name,
            existing_type=sa.Text(),
            nullable=False,
        )

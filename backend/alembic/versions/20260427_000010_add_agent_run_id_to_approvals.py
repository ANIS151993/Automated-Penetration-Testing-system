"""Add nullable agent_run_id link to approvals."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260427_000010"
down_revision = "20260427_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "approvals" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("approvals")}
    if "agent_run_id" not in columns:
        op.add_column(
            "approvals",
            sa.Column("agent_run_id", sa.Uuid(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "approvals" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("approvals")}
    if "agent_run_id" in columns:
        op.drop_column("approvals", "agent_run_id")

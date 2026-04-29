"""Add agent_runs table for persisted supervisor pipeline executions."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260427_000009"
down_revision = "20260426_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "agent_runs" not in table_names:
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("engagement_id", sa.Uuid(), nullable=False),
            sa.Column("operator_goal", sa.Text(), nullable=False),
            sa.Column("intent", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("current_phase", sa.String(length=64), nullable=False),
            sa.Column("planned_steps", sa.JSON(), nullable=False),
            sa.Column("step_results", sa.JSON(), nullable=False),
            sa.Column("executed_step_ids", sa.JSON(), nullable=False),
            sa.Column("findings", sa.JSON(), nullable=False),
            sa.Column("errors", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    index_names = {idx["name"] for idx in inspect(bind).get_indexes("agent_runs")}
    target_index = op.f("ix_agent_runs_engagement_id")
    if target_index not in index_names:
        op.create_index(
            target_index,
            "agent_runs",
            ["engagement_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "agent_runs" not in table_names:
        return

    index_names = {idx["name"] for idx in inspector.get_indexes("agent_runs")}
    target_index = op.f("ix_agent_runs_engagement_id")
    if target_index in index_names:
        op.drop_index(target_index, table_name="agent_runs")
    op.drop_table("agent_runs")

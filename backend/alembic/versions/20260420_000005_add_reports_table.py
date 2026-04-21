"""Add reports table for generated engagement artifacts."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260420_000005"
down_revision = "20260420_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "reports" not in table_names:
        op.create_table(
            "reports",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("engagement_id", sa.Uuid(), nullable=False),
            sa.Column("report_format", sa.String(length=24), nullable=False),
            sa.Column("artifact_path", sa.String(length=512), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    index_names = {index["name"] for index in inspect(bind).get_indexes("reports")}
    report_index_name = op.f("ix_reports_engagement_id")
    if report_index_name not in index_names:
        op.create_index(
            report_index_name,
            "reports",
            ["engagement_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "reports" not in table_names:
        return

    index_names = {index["name"] for index in inspector.get_indexes("reports")}
    report_index_name = op.f("ix_reports_engagement_id")
    if report_index_name in index_names:
        op.drop_index(report_index_name, table_name="reports")

    op.drop_table("reports")

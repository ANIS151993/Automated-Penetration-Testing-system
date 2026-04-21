"""Add findings table."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260419_000002"
down_revision = "20260419_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "findings" not in table_names:
        op.create_table(
            "findings",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("engagement_id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("severity", sa.String(length=24), nullable=False),
            sa.Column("attack_technique", sa.String(length=120), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("reported_by", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        column_names = {column["name"] for column in inspector.get_columns("findings")}
        if "reported_by" not in column_names:
            op.add_column(
                "findings",
                sa.Column(
                    "reported_by",
                    sa.String(length=120),
                    nullable=True,
                    server_default="unknown",
                ),
            )
            op.execute(
                sa.text(
                    "UPDATE findings SET reported_by = 'unknown' "
                    "WHERE reported_by IS NULL"
                )
            )
            op.alter_column(
                "findings",
                "reported_by",
                existing_type=sa.String(length=120),
                nullable=False,
                server_default=None,
            )

    index_names = {index["name"] for index in inspector.get_indexes("findings")}
    findings_index_name = op.f("ix_findings_engagement_id")
    if findings_index_name not in index_names:
        op.create_index(
            findings_index_name,
            "findings",
            ["engagement_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "findings" not in table_names:
        return

    index_names = {index["name"] for index in inspector.get_indexes("findings")}
    findings_index_name = op.f("ix_findings_engagement_id")
    if findings_index_name in index_names:
        op.drop_index(findings_index_name, table_name="findings")

    column_names = {column["name"] for column in inspector.get_columns("findings")}
    if "reported_by" in column_names:
        op.drop_column("findings", "reported_by")

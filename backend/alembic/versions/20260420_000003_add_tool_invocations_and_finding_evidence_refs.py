"""Add tool invocation evidence storage and finding evidence refs."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260420_000003"
down_revision = "20260419_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "tool_invocations" not in table_names:
        op.create_table(
            "tool_invocations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("engagement_id", sa.Uuid(), nullable=False),
            sa.Column("tool_name", sa.String(length=120), nullable=False),
            sa.Column("operation_name", sa.String(length=120), nullable=False),
            sa.Column("risk_level", sa.String(length=24), nullable=False),
            sa.Column("args", sa.JSON(), nullable=False),
            sa.Column("command_preview", sa.JSON(), nullable=False),
            sa.Column("targets", sa.JSON(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        _ensure_text_column("tool_invocations", "operation_name", 120, "unknown")
        _ensure_text_column("tool_invocations", "risk_level", 24, "low")
        _ensure_json_column("tool_invocations", "args", "{}")
        if not _has_column("tool_invocations", "targets"):
            op.add_column(
                "tool_invocations",
                sa.Column(
                    "targets",
                    sa.JSON(),
                    nullable=True,
                    server_default=_json_default("[]"),
                ),
            )
            if _has_column("tool_invocations", "target_ip"):
                op.execute(
                    sa.text(
                        "UPDATE tool_invocations SET targets = "
                        + _json_array_value("target_ip")
                        + " WHERE target_ip IS NOT NULL"
                    )
                )
            op.execute(
                sa.text(
                    "UPDATE tool_invocations SET targets = "
                    + _json_default_literal("[]")
                    + " WHERE targets IS NULL"
                )
            )
            op.alter_column(
                "tool_invocations",
                "targets",
                existing_type=sa.JSON(),
                nullable=False,
                server_default=None,
            )

    if "findings" in table_names and not _has_column("findings", "evidence_refs"):
        op.add_column(
            "findings",
            sa.Column(
                "evidence_refs",
                sa.JSON(),
                nullable=True,
                server_default=_json_default("[]"),
            ),
        )
        op.execute(
            sa.text(
                "UPDATE findings SET evidence_refs = "
                + _json_default_literal("[]")
                + " WHERE evidence_refs IS NULL"
            )
        )
        op.alter_column(
            "findings",
            "evidence_refs",
            existing_type=sa.JSON(),
            nullable=False,
            server_default=None,
        )

    tool_invocation_indexes = {
        index["name"] for index in inspect(bind).get_indexes("tool_invocations")
    }
    index_name = op.f("ix_tool_invocations_engagement_id")
    if index_name not in tool_invocation_indexes:
        op.create_index(
            index_name,
            "tool_invocations",
            ["engagement_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "tool_invocations" in table_names:
        index_names = {
            index["name"] for index in inspector.get_indexes("tool_invocations")
        }
        index_name = op.f("ix_tool_invocations_engagement_id")
        if index_name in index_names:
            op.drop_index(index_name, table_name="tool_invocations")

        for column_name in ("targets", "args", "risk_level", "operation_name"):
            if _has_column("tool_invocations", column_name):
                op.drop_column("tool_invocations", column_name)

    if "findings" in table_names and _has_column("findings", "evidence_refs"):
        op.drop_column("findings", "evidence_refs")


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _ensure_text_column(
    table_name: str,
    column_name: str,
    length: int,
    default: str,
) -> None:
    if _has_column(table_name, column_name):
        return
    op.add_column(
        table_name,
        sa.Column(
            column_name,
            sa.String(length=length),
            nullable=True,
            server_default=default,
        ),
    )
    op.execute(
        sa.text(
            f"UPDATE {table_name} SET {column_name} = '{default}' "
            f"WHERE {column_name} IS NULL"
        )
    )
    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.String(length=length),
        nullable=False,
        server_default=None,
    )


def _ensure_json_column(
    table_name: str,
    column_name: str,
    empty_literal: str,
) -> None:
    if _has_column(table_name, column_name):
        return
    op.add_column(
        table_name,
        sa.Column(
            column_name,
            sa.JSON(),
            nullable=True,
            server_default=_json_default(empty_literal),
        ),
    )
    op.execute(
        sa.text(
            f"UPDATE {table_name} SET {column_name} = "
            + _json_default_literal(empty_literal)
            + f" WHERE {column_name} IS NULL"
        )
    )
    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.JSON(),
        nullable=False,
        server_default=None,
    )


def _json_default(value: str):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text(f"'{value}'::jsonb")
    return sa.text(f"'{value}'")


def _json_default_literal(value: str) -> str:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return f"'{value}'::jsonb"
    return f"'{value}'"


def _json_array_value(column_name: str) -> str:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return f"jsonb_build_array({column_name})"
    return f"'[\"' || {column_name} || '\"]'"

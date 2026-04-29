"""Add users table for authentication."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260425_000007"
down_revision = "20260420_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "users" not in table_names:
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=24), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    index_names = {index["name"] for index in inspect(bind).get_indexes("users")}
    email_index_name = op.f("ix_users_email")
    if email_index_name not in index_names:
        op.create_index(
            email_index_name,
            "users",
            ["email"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    index_names = {index["name"] for index in inspector.get_indexes("users")}
    email_index_name = op.f("ix_users_email")
    if email_index_name in index_names:
        op.drop_index(email_index_name, table_name="users")

    op.drop_table("users")

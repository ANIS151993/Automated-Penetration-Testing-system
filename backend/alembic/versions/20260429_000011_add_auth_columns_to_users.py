"""Add password_hash, role, is_active, last_login_at to existing users table."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20260429_000011"
down_revision = "20260427_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("users")}

    if "password_hash" not in existing:
        op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
        # Set a locked placeholder so NOT NULL can be applied after
        op.execute(text("UPDATE users SET password_hash = '' WHERE password_hash IS NULL"))
        op.alter_column("users", "password_hash", nullable=False)

    if "role" not in existing:
        op.add_column("users", sa.Column("role", sa.String(24), nullable=True))
        op.execute(text("UPDATE users SET role = 'operator' WHERE role IS NULL"))
        op.alter_column("users", "role", nullable=False)

    if "is_active" not in existing:
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=True))
        op.execute(text("UPDATE users SET is_active = TRUE WHERE is_active IS NULL"))
        op.alter_column("users", "is_active", nullable=False)

    if "last_login_at" not in existing:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("users")}

    for col in ("last_login_at", "is_active", "role", "password_hash"):
        if col in existing:
            op.drop_column("users", col)

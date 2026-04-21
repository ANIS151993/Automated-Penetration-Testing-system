"""Create the initial backend schema."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "engagements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope_cidrs", sa.JSON(), nullable=False),
        sa.Column("authorization_confirmed", sa.Boolean(), nullable=False),
        sa.Column("authorizer_name", sa.String(length=120), nullable=False),
        sa.Column("operator_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("requested_action", sa.String(length=120), nullable=False),
        sa.Column("risk_level", sa.String(length=24), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("approved_by", sa.String(length=120), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("operation_name", sa.String(length=120), nullable=False),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_approvals_engagement_id"),
        "approvals",
        ["engagement_id"],
        unique=False,
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_events_engagement_id"),
        "audit_events",
        ["engagement_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_engagement_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_approvals_engagement_id"), table_name="approvals")
    op.drop_table("approvals")
    op.drop_table("engagements")

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRunModel(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    engagement_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    operator_goal: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    current_phase: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_steps: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    step_results: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    executed_step_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    findings: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    errors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

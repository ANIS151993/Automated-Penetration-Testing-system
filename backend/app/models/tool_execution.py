from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ToolExecutionModel(Base):
    __tablename__ = "tool_executions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    engagement_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    invocation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    operation_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stderr_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

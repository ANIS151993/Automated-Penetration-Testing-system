from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ToolInvocationModel(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    engagement_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    operation_name: Mapped[str] = mapped_column(String(120), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False)
    args: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    command_preview: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    targets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        "started_at",
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReportModel(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    engagement_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    report_format: Mapped[str] = mapped_column(String(24), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

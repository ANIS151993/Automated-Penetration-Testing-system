from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FindingModel(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    engagement_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    attack_technique: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reported_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

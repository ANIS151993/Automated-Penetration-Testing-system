from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.audit import GENESIS_HASH, build_audit_record
from app.models.audit_event import AuditEventModel


@dataclass(slots=True)
class AuditEventRecord:
    event_type: str
    engagement_id: UUID
    payload: dict
    prev_hash: str
    evidence_hash: str
    occurred_at: datetime
    actor: str | None


class AuditService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record_event(
        self,
        *,
        engagement_id: UUID,
        event_type: str,
        payload: dict,
        actor: str | None = None,
    ) -> AuditEventRecord:
        with self._session_factory() as session:
            prev_hash = self._latest_hash(session, engagement_id)
            record = build_audit_record(
                event_type=event_type,
                payload=payload,
                prev_hash=prev_hash,
            )
            model = AuditEventModel(
                engagement_id=engagement_id,
                event_type=record["event_type"],
                payload=record["payload"],
                prev_hash=record["prev_hash"],
                evidence_hash=record["evidence_hash"],
                occurred_at=record["occurred_at"],
                actor=actor,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return AuditEventRecord(
                event_type=model.event_type,
                engagement_id=model.engagement_id,
                payload=dict(model.payload),
                prev_hash=model.prev_hash,
                evidence_hash=model.evidence_hash,
                occurred_at=model.occurred_at,
                actor=model.actor,
            )

    def list_for_engagement(self, engagement_id: UUID) -> list[AuditEventRecord]:
        with self._session_factory() as session:
            items = session.scalars(
                select(AuditEventModel)
                .where(AuditEventModel.engagement_id == engagement_id)
                .order_by(AuditEventModel.occurred_at)
            ).all()
            return [
                AuditEventRecord(
                    event_type=item.event_type,
                    engagement_id=item.engagement_id,
                    payload=dict(item.payload),
                    prev_hash=item.prev_hash,
                    evidence_hash=item.evidence_hash,
                    occurred_at=item.occurred_at,
                    actor=item.actor,
                )
                for item in items
            ]

    def _latest_hash(self, session: Session, engagement_id: UUID) -> str:
        item = session.scalars(
            select(AuditEventModel.evidence_hash)
            .where(AuditEventModel.engagement_id == engagement_id)
            .order_by(AuditEventModel.occurred_at.desc())
        ).first()
        return item or GENESIS_HASH

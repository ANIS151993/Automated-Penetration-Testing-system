from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.audit_service import AuditService
from app.core.tool_invocations import (
    ToolInvocationService,
    format_invocation_evidence,
)
from app.models.finding import FindingModel
from app.schemas.findings import FindingCreate, FindingRead


@dataclass(slots=True)
class FindingEntity:
    id: UUID
    engagement_id: UUID
    title: str
    severity: str
    attack_technique: str | None
    summary: str
    evidence: list[str]
    evidence_refs: list[str]
    reported_by: str
    created_at: datetime

    def to_read_model(self) -> FindingRead:
        return FindingRead(
            id=self.id,
            engagement_id=self.engagement_id,
            title=self.title,
            severity=self.severity,
            attack_technique=self.attack_technique,
            summary=self.summary,
            evidence=self.evidence,
            evidence_refs=[UUID(value) for value in self.evidence_refs],
            reported_by=self.reported_by,
            created_at=self.created_at,
        )


class FindingRepository(Protocol):
    def list_for_engagement(self, engagement_id: UUID) -> list[FindingEntity]: ...

    def save(self, finding: FindingEntity) -> FindingEntity: ...


def _to_entity(model: FindingModel) -> FindingEntity:
    return FindingEntity(
        id=model.id,
        engagement_id=model.engagement_id,
        title=model.title,
        severity=model.severity,
        attack_technique=model.attack_technique,
        summary=model.summary,
        evidence=list(model.evidence),
        evidence_refs=list(model.evidence_refs),
        reported_by=model.reported_by,
        created_at=model.created_at,
    )


class SqlAlchemyFindingRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_engagement(self, engagement_id: UUID) -> list[FindingEntity]:
        with self._session_factory() as session:
            items = session.scalars(
                select(FindingModel)
                .where(FindingModel.engagement_id == engagement_id)
                .order_by(FindingModel.created_at.desc())
            ).all()
            return [_to_entity(item) for item in items]

    def save(self, finding: FindingEntity) -> FindingEntity:
        with self._session_factory() as session:
            model = FindingModel(
                id=finding.id,
                engagement_id=finding.engagement_id,
                title=finding.title,
                severity=finding.severity,
                attack_technique=finding.attack_technique,
                summary=finding.summary,
                evidence=finding.evidence,
                evidence_refs=finding.evidence_refs,
                reported_by=finding.reported_by,
                created_at=finding.created_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_entity(model)


class FindingService:
    def __init__(
        self,
        repository: FindingRepository,
        audit_service: AuditService | None = None,
        tool_invocation_service: ToolInvocationService | None = None,
    ) -> None:
        self._repository = repository
        self._audit_service = audit_service
        self._tool_invocation_service = tool_invocation_service

    def list_for_engagement(self, engagement_id: UUID) -> list[FindingRead]:
        return [
            finding.to_read_model()
            for finding in self._repository.list_for_engagement(engagement_id)
        ]

    def create(
        self,
        *,
        engagement_id: UUID,
        payload: FindingCreate,
    ) -> FindingRead:
        evidence_refs = [str(item) for item in payload.evidence_refs]
        linked_invocations = (
            self._resolve_evidence_refs(engagement_id, payload.evidence_refs)
            if payload.evidence_refs
            else []
        )
        evidence = list(payload.evidence)
        for invocation in linked_invocations:
            rendered = format_invocation_evidence(invocation)
            if rendered not in evidence:
                evidence.append(rendered)

        finding = FindingEntity(
            id=uuid4(),
            engagement_id=engagement_id,
            title=payload.title,
            severity=payload.severity,
            attack_technique=payload.attack_technique,
            summary=payload.summary,
            evidence=evidence,
            evidence_refs=evidence_refs,
            reported_by=payload.reported_by,
            created_at=datetime.now(timezone.utc),
        )
        saved = self._repository.save(finding).to_read_model()
        if self._audit_service is not None:
            self._audit_service.record_event(
                engagement_id=engagement_id,
                event_type="finding_recorded",
                payload={
                    "finding_id": str(saved.id),
                    "title": saved.title,
                    "severity": saved.severity,
                    "attack_technique": saved.attack_technique,
                    "evidence_count": len(saved.evidence),
                    "evidence_ref_count": len(saved.evidence_refs),
                },
                actor=saved.reported_by,
            )
        return saved

    def _resolve_evidence_refs(
        self,
        engagement_id: UUID,
        evidence_refs: list[UUID],
    ):
        if self._tool_invocation_service is None:
            raise ValueError("Evidence references are not available")
        return self._tool_invocation_service.require_for_engagement(
            engagement_id,
            evidence_refs,
        )

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.audit_service import AuditService
from app.models.approval import ApprovalModel
from app.schemas.approvals import ApprovalCreate, ApprovalDecision, ApprovalRead


@dataclass(slots=True)
class ApprovalEntity:
    id: UUID
    engagement_id: UUID
    requested_action: str
    risk_level: str
    requested_by: str
    approved: bool
    approved_by: str | None
    decision_reason: str | None
    tool_name: str
    operation_name: str
    args: dict
    created_at: datetime
    decided_at: datetime | None
    agent_run_id: UUID | None = None

    def to_read_model(self) -> ApprovalRead:
        return ApprovalRead(
            id=self.id,
            engagement_id=self.engagement_id,
            requested_action=self.requested_action,
            risk_level=self.risk_level,
            requested_by=self.requested_by,
            approved=self.approved,
            approved_by=self.approved_by,
            decision_reason=self.decision_reason,
            tool_name=self.tool_name,
            operation_name=self.operation_name,
            args=self.args,
            created_at=self.created_at,
            decided_at=self.decided_at,
            agent_run_id=self.agent_run_id,
        )


class ApprovalRepository(Protocol):
    def list_for_engagement(self, engagement_id: UUID) -> list[ApprovalEntity]: ...

    def get_approval(self, approval_id: UUID) -> ApprovalEntity | None: ...

    def save(self, approval: ApprovalEntity) -> ApprovalEntity: ...

    def find_matching_approved(
        self,
        *,
        engagement_id: UUID,
        tool_name: str,
        operation_name: str,
        args: dict,
    ) -> ApprovalEntity | None: ...


def _to_entity(model: ApprovalModel) -> ApprovalEntity:
    return ApprovalEntity(
        id=model.id,
        engagement_id=model.engagement_id,
        requested_action=model.requested_action,
        risk_level=model.risk_level,
        requested_by=model.requested_by,
        approved=model.approved,
        approved_by=model.approved_by,
        decision_reason=model.decision_reason,
        tool_name=model.tool_name,
        operation_name=model.operation_name,
        args=dict(model.args),
        created_at=model.created_at,
        decided_at=model.decided_at,
        agent_run_id=model.agent_run_id,
    )


class SqlAlchemyApprovalRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_engagement(self, engagement_id: UUID) -> list[ApprovalEntity]:
        with self._session_factory() as session:
            items = session.scalars(
                select(ApprovalModel)
                .where(ApprovalModel.engagement_id == engagement_id)
                .order_by(ApprovalModel.created_at)
            ).all()
            return [_to_entity(item) for item in items]

    def get_approval(self, approval_id: UUID) -> ApprovalEntity | None:
        with self._session_factory() as session:
            item = session.get(ApprovalModel, approval_id)
            return _to_entity(item) if item else None

    def save(self, approval: ApprovalEntity) -> ApprovalEntity:
        with self._session_factory() as session:
            existing = session.get(ApprovalModel, approval.id)
            if existing is None:
                existing = ApprovalModel(id=approval.id)
                session.add(existing)

            existing.engagement_id = approval.engagement_id
            existing.requested_action = approval.requested_action
            existing.risk_level = approval.risk_level
            existing.requested_by = approval.requested_by
            existing.approved = approval.approved
            existing.approved_by = approval.approved_by
            existing.decision_reason = approval.decision_reason
            existing.tool_name = approval.tool_name
            existing.operation_name = approval.operation_name
            existing.args = approval.args
            existing.created_at = approval.created_at
            existing.decided_at = approval.decided_at
            existing.agent_run_id = approval.agent_run_id

            session.commit()
            session.refresh(existing)
            return _to_entity(existing)

    def find_matching_approved(
        self,
        *,
        engagement_id: UUID,
        tool_name: str,
        operation_name: str,
        args: dict,
    ) -> ApprovalEntity | None:
        canonical_args = json.dumps(args, sort_keys=True)
        with self._session_factory() as session:
            items = session.scalars(
                select(ApprovalModel).where(
                    ApprovalModel.engagement_id == engagement_id,
                    ApprovalModel.tool_name == tool_name,
                    ApprovalModel.operation_name == operation_name,
                    ApprovalModel.approved.is_(True),
                )
            ).all()
            for item in items:
                if json.dumps(item.args, sort_keys=True) == canonical_args:
                    return _to_entity(item)
        return None


class ApprovalService:
    def __init__(
        self,
        repository: ApprovalRepository,
        audit_service: AuditService | None = None,
    ) -> None:
        self._repository = repository
        self._audit_service = audit_service

    def list_for_engagement(self, engagement_id: UUID) -> list[ApprovalRead]:
        return [
            approval.to_read_model()
            for approval in self._repository.list_for_engagement(engagement_id)
        ]

    def create(
        self,
        *,
        engagement_id: UUID,
        payload: ApprovalCreate,
        risk_level: str,
    ) -> ApprovalRead:
        now = datetime.now(timezone.utc)
        approval = ApprovalEntity(
            id=uuid4(),
            engagement_id=engagement_id,
            requested_action=payload.requested_action,
            risk_level=risk_level,
            requested_by=payload.requested_by,
            approved=False,
            approved_by=None,
            decision_reason=None,
            tool_name=payload.tool_name,
            operation_name=payload.operation_name,
            args=payload.args,
            created_at=now,
            decided_at=None,
            agent_run_id=payload.agent_run_id,
        )
        saved = self._repository.save(approval).to_read_model()
        if self._audit_service is not None:
            self._audit_service.record_event(
                engagement_id=engagement_id,
                event_type="approval_requested",
                payload={
                    "approval_id": str(saved.id),
                    "tool_name": saved.tool_name,
                    "operation_name": saved.operation_name,
                    "risk_level": saved.risk_level,
                    "requested_action": saved.requested_action,
                },
                actor=saved.requested_by,
            )
        return saved

    def decide(
        self,
        *,
        approval_id: UUID,
        payload: ApprovalDecision,
    ) -> ApprovalRead | None:
        current = self._repository.get_approval(approval_id)
        if current is None:
            return None

        updated = ApprovalEntity(
            id=current.id,
            engagement_id=current.engagement_id,
            requested_action=current.requested_action,
            risk_level=current.risk_level,
            requested_by=current.requested_by,
            approved=payload.approved,
            approved_by=payload.approved_by,
            decision_reason=payload.decision_reason,
            tool_name=current.tool_name,
            operation_name=current.operation_name,
            args=current.args,
            created_at=current.created_at,
            decided_at=datetime.now(timezone.utc),
            agent_run_id=current.agent_run_id,
        )
        saved = self._repository.save(updated).to_read_model()
        if self._audit_service is not None:
            self._audit_service.record_event(
                engagement_id=saved.engagement_id,
                event_type="approval_decided",
                payload={
                    "approval_id": str(saved.id),
                    "approved": saved.approved,
                    "tool_name": saved.tool_name,
                    "operation_name": saved.operation_name,
                    "decision_reason": saved.decision_reason,
                },
                actor=saved.approved_by,
            )
        return saved

    def ensure_matching_approval(
        self,
        *,
        engagement_id: UUID,
        tool_name: str,
        operation_name: str,
        args: dict,
    ) -> ApprovalRead | None:
        approval = self._repository.find_matching_approved(
            engagement_id=engagement_id,
            tool_name=tool_name,
            operation_name=operation_name,
            args=args,
        )
        return approval.to_read_model() if approval else None

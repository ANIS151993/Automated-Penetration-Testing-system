from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.audit_service import AuditService
from app.models.agent_run import AgentRunModel
from app.schemas.agent_runs import AgentRunResponse, AgentRunSummary


@dataclass(slots=True)
class AgentRunRecord:
    id: UUID
    engagement_id: UUID
    operator_goal: str
    intent: str
    current_phase: str
    planned_steps: list[dict]
    step_results: list[dict]
    executed_step_ids: list[str]
    findings: list[dict]
    errors: list[str]
    created_at: datetime


class AgentRunRepository(Protocol):
    def save(self, record: AgentRunRecord) -> AgentRunRecord: ...
    def list_for_engagement(self, engagement_id: UUID) -> list[AgentRunRecord]: ...
    def get(self, run_id: UUID) -> AgentRunRecord | None: ...
    def append_step_result(self, run_id: UUID, result: dict) -> None: ...


def _to_record(model: AgentRunModel) -> AgentRunRecord:
    return AgentRunRecord(
        id=model.id,
        engagement_id=model.engagement_id,
        operator_goal=model.operator_goal,
        intent=model.intent,
        current_phase=model.current_phase,
        planned_steps=list(model.planned_steps or []),
        step_results=list(model.step_results or []),
        executed_step_ids=list(model.executed_step_ids or []),
        findings=list(model.findings or []),
        errors=list(model.errors or []),
        created_at=model.created_at,
    )


class SqlAlchemyAgentRunRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save(self, record: AgentRunRecord) -> AgentRunRecord:
        with self._session_factory() as session:
            model = AgentRunModel(
                id=record.id,
                engagement_id=record.engagement_id,
                operator_goal=record.operator_goal,
                intent=record.intent,
                current_phase=record.current_phase,
                planned_steps=record.planned_steps,
                step_results=record.step_results,
                executed_step_ids=record.executed_step_ids,
                findings=record.findings,
                errors=record.errors,
                created_at=record.created_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_record(model)

    def list_for_engagement(self, engagement_id: UUID) -> list[AgentRunRecord]:
        with self._session_factory() as session:
            items = session.scalars(
                select(AgentRunModel)
                .where(AgentRunModel.engagement_id == engagement_id)
                .order_by(AgentRunModel.created_at.desc())
            ).all()
            return [_to_record(m) for m in items]

    def get(self, run_id: UUID) -> AgentRunRecord | None:
        with self._session_factory() as session:
            item = session.get(AgentRunModel, run_id)
            return _to_record(item) if item else None

    def append_step_result(self, run_id: UUID, result: dict) -> None:
        from sqlalchemy import update as sa_update
        from sqlalchemy.orm.attributes import flag_modified

        with self._session_factory() as session:
            item = session.get(AgentRunModel, run_id)
            if item is None:
                return
            current = list(item.step_results or [])
            current.append(result)
            item.step_results = current
            flag_modified(item, "step_results")
            session.commit()


class AgentRunService:
    def __init__(
        self,
        repository: AgentRunRepository,
        audit_service: AuditService | None = None,
    ) -> None:
        self._repository = repository
        self._audit_service = audit_service

    def persist(
        self,
        *,
        engagement_id: UUID,
        operator_goal: str,
        response: AgentRunResponse,
        actor: str | None = None,
    ) -> AgentRunRecord:
        record = AgentRunRecord(
            id=uuid4(),
            engagement_id=engagement_id,
            operator_goal=operator_goal,
            intent=response.intent,
            current_phase=response.current_phase,
            planned_steps=[s.model_dump(mode="json") for s in response.planned_steps],
            step_results=[r.model_dump(mode="json") for r in response.step_results],
            executed_step_ids=list(response.executed_step_ids),
            findings=[f.model_dump(mode="json") for f in response.findings],
            errors=list(response.errors),
            created_at=datetime.now(timezone.utc),
        )
        saved = self._repository.save(record)
        if self._audit_service is not None:
            self._audit_service.record_event(
                engagement_id=engagement_id,
                event_type="agent_run_completed",
                payload={
                    "agent_run_id": str(saved.id),
                    "intent": saved.intent,
                    "current_phase": saved.current_phase,
                    "planned_steps_count": len(saved.planned_steps),
                    "step_results_count": len(saved.step_results),
                    "findings_count": len(saved.findings),
                    "errors_count": len(saved.errors),
                },
                actor=actor,
            )
        return saved

    def list_for_engagement(self, engagement_id: UUID) -> list[AgentRunSummary]:
        return [
            AgentRunSummary(
                id=r.id,
                engagement_id=r.engagement_id,
                operator_goal=r.operator_goal,
                intent=r.intent,
                current_phase=r.current_phase,
                created_at=r.created_at,
                planned_steps_count=len(r.planned_steps),
                step_results_count=len(r.step_results),
                findings_count=len(r.findings),
                errors_count=len(r.errors),
            )
            for r in self._repository.list_for_engagement(engagement_id)
        ]

    def get(self, run_id: UUID) -> AgentRunRecord | None:
        return self._repository.get(run_id)

    def append_step_result(self, run_id: UUID, result: dict) -> None:
        self._repository.append_step_result(run_id, result)

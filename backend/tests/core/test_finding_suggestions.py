from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.agent_runs import AgentRunRecord
from app.core.finding_suggestions import FindingSuggestionService
from app.schemas.agent_runs import AgentRunSummary


class _StubExecutionService:
    def list_for_engagement(self, engagement_id: UUID):
        return []

    def get_document(self, *, engagement_id: UUID, execution_id: UUID):
        return None


class _StubAgentRunService:
    def __init__(self, record: AgentRunRecord) -> None:
        self._record = record

    def list_for_engagement(self, engagement_id: UUID) -> list[AgentRunSummary]:
        return [
            AgentRunSummary(
                id=self._record.id,
                engagement_id=self._record.engagement_id,
                operator_goal=self._record.operator_goal,
                intent=self._record.intent,
                current_phase=self._record.current_phase,
                created_at=self._record.created_at,
                planned_steps_count=len(self._record.planned_steps),
                step_results_count=len(self._record.step_results),
                findings_count=len(self._record.findings),
                errors_count=len(self._record.errors),
            )
        ]

    def get(self, run_id: UUID) -> AgentRunRecord | None:
        return self._record if run_id == self._record.id else None


def test_finding_suggestions_includes_agent_run_findings() -> None:
    engagement_id = uuid4()
    execution_id = uuid4()
    invocation_id = uuid4()

    record = AgentRunRecord(
        id=uuid4(),
        engagement_id=engagement_id,
        operator_goal="full pentest",
        intent="full_pentest",
        current_phase="vulnerability_mapping",
        planned_steps=[],
        step_results=[
            {
                "tool_name": "nmap",
                "operation_name": "service_scan",
                "args": {},
                "status": "completed",
                "exit_code": 0,
                "stdout": "nginx 1.18.0",
                "stderr": "",
                "invocation_id": str(invocation_id),
                "execution_id": str(execution_id),
                "error": None,
            }
        ],
        executed_step_ids=[str(invocation_id)],
        findings=[
            {
                "title": "Outdated nginx",
                "severity": "medium",
                "attack_technique": "T1190",
                "summary": "nginx 1.18.0 visible.",
                "evidence_refs": [str(invocation_id)],
                "citations": [],
            }
        ],
        errors=[],
        created_at=datetime.now(timezone.utc),
    )

    svc = FindingSuggestionService(
        tool_execution_service=_StubExecutionService(),
        agent_run_service=_StubAgentRunService(record),
    )
    out = svc.list_for_engagement(engagement_id)
    assert len(out) == 1
    s = out[0]
    assert s.title == "Outdated nginx"
    assert s.severity == "medium"
    assert s.execution_id == execution_id
    assert s.invocation_id == invocation_id
    assert s.evidence_refs == [invocation_id]
    assert s.suggestion_id.startswith("agent-run:")


def test_finding_suggestions_skips_agent_findings_without_matching_step() -> None:
    engagement_id = uuid4()
    record = AgentRunRecord(
        id=uuid4(),
        engagement_id=engagement_id,
        operator_goal="x",
        intent="full_pentest",
        current_phase="vulnerability_mapping",
        planned_steps=[],
        step_results=[],
        executed_step_ids=[],
        findings=[
            {
                "title": "Orphan",
                "severity": "high",
                "attack_technique": "T1",
                "summary": "no step",
                "evidence_refs": [str(uuid4())],
                "citations": [],
            }
        ],
        errors=[],
        created_at=datetime.now(timezone.utc),
    )
    svc = FindingSuggestionService(
        tool_execution_service=_StubExecutionService(),
        agent_run_service=_StubAgentRunService(record),
    )
    assert svc.list_for_engagement(engagement_id) == []

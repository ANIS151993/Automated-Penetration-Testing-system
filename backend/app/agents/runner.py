from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.agents.executors.gateway import GatewayExecutor
from app.agents.nodes.tool_caller import ToolCallerDeps
from app.agents.state import EngagementState
from app.agents.supervisor import SupervisorDeps, run_full_pipeline
from app.core.engagements import EngagementService
from app.core.gateway_validation import GatewayValidationService
from app.core.llm_client import LLMClient
from app.knowledge.service import KnowledgeService
from app.schemas.agent_runs import (
    AgentRunResponse,
    FindingRead,
    PlannedStepRead,
    StepResultRead,
)


class AgentRunError(Exception):
    """Raised when an agent run cannot start (e.g. missing engagement)."""


@dataclass(slots=True)
class AgentRunDeps:
    engagement_service: EngagementService
    gateway_service: GatewayValidationService
    llm: LLMClient
    knowledge: KnowledgeService | None = None


async def run_agent_pipeline(
    *,
    engagement_id: UUID,
    operator_goal: str,
    deps: AgentRunDeps,
) -> EngagementState:
    engagement = deps.engagement_service.get_engagement(engagement_id)
    if engagement is None:
        raise AgentRunError("Engagement not found")

    state = EngagementState(
        engagement_id=str(engagement_id),
        scope_cidrs=list(engagement.scope_cidrs),
        operator_goal=operator_goal,
    )
    executor = GatewayExecutor(
        service=deps.gateway_service,
        engagement_id=engagement_id,
    )
    supervisor_deps = SupervisorDeps(
        llm=deps.llm,
        tool_caller=ToolCallerDeps(executor=executor),
        knowledge=deps.knowledge,
    )
    return await run_full_pipeline(state, supervisor_deps)


def serialize_state(state: EngagementState) -> AgentRunResponse:
    return AgentRunResponse(
        engagement_id=state.engagement_id,
        intent=state.intent,
        current_phase=state.current_phase.value,
        planned_steps=[
            PlannedStepRead(
                tool_name=s.tool_name,
                operation_name=s.operation_name,
                args=s.args,
                reason=s.reason,
                phase=s.phase.value,
                citations=list(s.citations),
            )
            for s in state.planned_steps
        ],
        step_results=[
            StepResultRead(
                tool_name=r.tool_name,
                operation_name=r.operation_name,
                args=r.args,
                status=r.status,
                exit_code=r.exit_code,
                stdout=r.stdout,
                stderr=r.stderr,
                invocation_id=r.invocation_id,
                execution_id=r.execution_id,
                error=r.error,
            )
            for r in state.step_results
        ],
        executed_step_ids=list(state.executed_step_ids),
        findings=[
            FindingRead(
                title=f["title"],
                severity=f["severity"],
                attack_technique=f["attack_technique"],
                summary=f["summary"],
                evidence_refs=list(f.get("evidence_refs", [])),
                citations=list(f.get("citations", [])),
            )
            for f in state.findings
        ],
        errors=list(state.errors),
    )

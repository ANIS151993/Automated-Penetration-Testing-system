from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    operator_goal: str = Field(min_length=3, max_length=2000)


class PlannedStepRead(BaseModel):
    tool_name: str
    operation_name: str
    args: dict
    reason: str
    phase: str
    citations: list[str]


class StepResultRead(BaseModel):
    tool_name: str
    operation_name: str
    args: dict
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    invocation_id: str | None
    execution_id: str | None
    error: str | None


class FindingRead(BaseModel):
    title: str
    severity: str
    attack_technique: str
    summary: str
    evidence_refs: list[str]
    citations: list[str]


class AgentRunResponse(BaseModel):
    id: UUID | None = None
    engagement_id: str
    intent: str
    current_phase: str
    operator_goal: str = ""
    created_at: datetime | None = None
    planned_steps: list[PlannedStepRead]
    step_results: list[StepResultRead]
    executed_step_ids: list[str]
    findings: list[FindingRead] = Field(default_factory=list)
    errors: list[str]


class AgentRunSummary(BaseModel):
    id: UUID
    engagement_id: UUID
    operator_goal: str
    intent: str
    current_phase: str
    created_at: datetime
    planned_steps_count: int
    step_results_count: int
    findings_count: int
    errors_count: int

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phase(str, Enum):
    RECONNAISSANCE = "reconnaissance"
    ENUMERATION = "enumeration"
    VULN_MAPPING = "vulnerability_mapping"
    EXPLOITATION = "exploitation"
    REPORTING = "reporting"


@dataclass(slots=True)
class PlannedStep:
    tool_name: str
    operation_name: str
    args: dict
    reason: str
    phase: Phase
    citations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StepResult:
    tool_name: str
    operation_name: str
    args: dict
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    invocation_id: str | None = None
    execution_id: str | None = None
    error: str | None = None


@dataclass(slots=True)
class EngagementState:
    engagement_id: str
    scope_cidrs: list[str]
    operator_goal: str
    current_phase: Phase = Phase.RECONNAISSANCE
    intent: str = ""
    planned_steps: list[PlannedStep] = field(default_factory=list)
    executed_step_ids: list[str] = field(default_factory=list)
    step_results: list[StepResult] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

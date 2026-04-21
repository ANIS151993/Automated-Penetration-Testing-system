from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from app.agents.state import EngagementState, PlannedStep, StepResult
from app.core.llm_client import format_tool_output_for_prompt


@dataclass(slots=True)
class ExecutorResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    invocation_id: str | None = None
    execution_id: str | None = None


Executor = Callable[[PlannedStep], Awaitable[ExecutorResult]]


@dataclass(slots=True)
class ToolCallerDeps:
    executor: Executor


async def call_tools(
    state: EngagementState,
    deps: ToolCallerDeps,
) -> EngagementState:
    for step in state.planned_steps:
        try:
            result = await deps.executor(step)
        except Exception as exc:  # noqa: BLE001 — surfaced into state, not raised
            state.errors.append(
                f"{step.tool_name}.{step.operation_name}: {exc}"
            )
            state.step_results.append(
                StepResult(
                    tool_name=step.tool_name,
                    operation_name=step.operation_name,
                    args=step.args,
                    status="failed",
                    exit_code=None,
                    stdout="",
                    stderr="",
                    error=str(exc),
                )
            )
            continue

        state.step_results.append(
            StepResult(
                tool_name=step.tool_name,
                operation_name=step.operation_name,
                args=step.args,
                status=result.status,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                invocation_id=result.invocation_id,
                execution_id=result.execution_id,
            )
        )
        if result.invocation_id:
            state.executed_step_ids.append(result.invocation_id)
    return state


def wrap_step_output_for_prompt(result: StepResult) -> str:
    body = result.stdout if result.stdout else result.stderr
    return format_tool_output_for_prompt(
        f"{result.tool_name}.{result.operation_name}",
        body,
    )

from __future__ import annotations

import pytest

from app.agents.nodes.tool_caller import (
    ExecutorResult,
    ToolCallerDeps,
    call_tools,
    wrap_step_output_for_prompt,
)
from app.agents.state import EngagementState, Phase, PlannedStep, StepResult


def _state_with_steps(steps: list[PlannedStep]) -> EngagementState:
    return EngagementState(
        engagement_id="eng-1",
        scope_cidrs=["172.20.32.0/18"],
        operator_goal="recon",
        intent="recon_and_enum",
        planned_steps=steps,
    )


@pytest.mark.asyncio
async def test_call_tools_records_success_results():
    step = PlannedStep(
        tool_name="nmap",
        operation_name="service_scan",
        args={"target": "172.20.32.59", "ports": "22,80"},
        reason="recon",
        phase=Phase.RECONNAISSANCE,
    )

    async def executor(_: PlannedStep) -> ExecutorResult:
        return ExecutorResult(
            status="completed",
            exit_code=0,
            stdout="22/tcp open ssh",
            stderr="",
            invocation_id="inv-1",
            execution_id="exec-1",
        )

    state = _state_with_steps([step])
    out = await call_tools(state, ToolCallerDeps(executor=executor))

    assert len(out.step_results) == 1
    assert out.step_results[0].status == "completed"
    assert out.step_results[0].exit_code == 0
    assert out.step_results[0].stdout == "22/tcp open ssh"
    assert out.executed_step_ids == ["inv-1"]
    assert out.errors == []


@pytest.mark.asyncio
async def test_call_tools_captures_executor_exception():
    step = PlannedStep(
        tool_name="nmap",
        operation_name="service_scan",
        args={"target": "172.20.32.59"},
        reason="recon",
        phase=Phase.RECONNAISSANCE,
    )

    async def executor(_: PlannedStep) -> ExecutorResult:
        raise RuntimeError("gateway offline")

    state = _state_with_steps([step])
    out = await call_tools(state, ToolCallerDeps(executor=executor))

    assert len(out.step_results) == 1
    assert out.step_results[0].status == "failed"
    assert out.step_results[0].error == "gateway offline"
    assert out.executed_step_ids == []
    assert out.errors == ["nmap.service_scan: gateway offline"]


def test_wrap_step_output_tags_as_untrusted():
    result = StepResult(
        tool_name="nmap",
        operation_name="service_scan",
        args={},
        status="completed",
        exit_code=0,
        stdout="22/tcp open ssh",
        stderr="",
    )
    wrapped = wrap_step_output_for_prompt(result)
    assert 'trust="untrusted"' in wrapped
    assert "nmap.service_scan" in wrapped
    assert "22/tcp open ssh" in wrapped

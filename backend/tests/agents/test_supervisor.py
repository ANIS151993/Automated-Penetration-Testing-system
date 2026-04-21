from __future__ import annotations

import json

import httpx
import pytest

from app.agents.nodes.tool_caller import ExecutorResult, ToolCallerDeps
from app.agents.state import EngagementState, Phase, PlannedStep
from app.agents.supervisor import SupervisorDeps, run_recon_pipeline
from app.core.llm_client import LLMClient, LLMError


def _mock_llm_transport(responses: dict[str, dict]) -> httpx.MockTransport:
    """Route Ollama chat calls by model name to a canned JSON content payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        model = payload["model"]
        content = responses.get(model)
        if content is None:
            return httpx.Response(500, json={"error": f"no mock for {model}"})
        return httpx.Response(
            200,
            json={
                "model": model,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content),
                },
            },
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_run_recon_pipeline_happy_path():
    responses = {
        "llama3.2:3b-instruct-q4_K_M": {
            "intent": "recon_and_enum",
            "justification": "operator wants open services",
        },
        "qwen2.5:7b-instruct-q4_K_M": {
            "steps": [
                {
                    "tool_name": "nmap",
                    "operation_name": "service_scan",
                    "args": {"target": "172.20.32.59", "ports": "22,80"},
                    "reason": "recon",
                    "phase": "reconnaissance",
                }
            ]
        },
    }

    async def executor(step: PlannedStep) -> ExecutorResult:
        return ExecutorResult(
            status="completed",
            exit_code=0,
            stdout=f"ran {step.tool_name}.{step.operation_name}",
            stderr="",
            invocation_id="inv-1",
        )

    async with httpx.AsyncClient(transport=_mock_llm_transport(responses)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="Find open services on 172.20.32.59",
        )
        deps = SupervisorDeps(
            llm=llm,
            tool_caller=ToolCallerDeps(executor=executor),
        )
        out = await run_recon_pipeline(state, deps)

        assert out.intent == "recon_and_enum"
        assert len(out.planned_steps) == 1
        assert len(out.step_results) == 1
        assert out.step_results[0].status == "completed"
        assert out.current_phase is Phase.RECONNAISSANCE
        assert out.executed_step_ids == ["inv-1"]


@pytest.mark.asyncio
async def test_run_recon_pipeline_rejects_non_recon_intent():
    responses = {
        "llama3.2:3b-instruct-q4_K_M": {
            "intent": "unsupported",
            "justification": "goal is unclear",
        },
    }

    async def executor(_: PlannedStep) -> ExecutorResult:
        raise AssertionError("executor should not run for unsupported intent")

    async with httpx.AsyncClient(transport=_mock_llm_transport(responses)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="???",
        )
        deps = SupervisorDeps(
            llm=llm,
            tool_caller=ToolCallerDeps(executor=executor),
        )
        with pytest.raises(LLMError):
            await run_recon_pipeline(state, deps)

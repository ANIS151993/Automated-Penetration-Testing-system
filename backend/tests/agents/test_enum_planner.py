from __future__ import annotations

import json

import httpx
import pytest

from app.agents.nodes.enum_planner import EnumPlannerDeps, plan_enumeration
from app.agents.state import EngagementState, Phase, StepResult
from app.core.llm_client import LLMClient, LLMError


def _mock_plan(steps: list[dict]) -> httpx.MockTransport:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"steps": steps}),
                }
            },
        )

    transport = httpx.MockTransport(handler)
    transport.captured = captured  # type: ignore[attr-defined]
    return transport


def _state_with_recon() -> EngagementState:
    state = EngagementState(
        engagement_id="eng-1",
        scope_cidrs=["172.20.32.0/18"],
        operator_goal="enumerate the target",
        intent="recon_and_enum",
    )
    state.step_results = [
        StepResult(
            tool_name="nmap",
            operation_name="service_scan",
            args={"target": "172.20.32.59", "ports": "22,80,443"},
            status="completed",
            exit_code=0,
            stdout="80/tcp open  http   nginx 1.24.0",
            stderr="",
            invocation_id="inv-recon-1",
        )
    ]
    return state


@pytest.mark.asyncio
async def test_plan_enumeration_accepts_in_scope_steps():
    steps = [
        {
            "tool_name": "whatweb",
            "operation_name": "fingerprint",
            "args": {"target": "http://172.20.32.59/"},
            "reason": "Fingerprint nginx banner observed in recon.",
            "phase": "enumeration",
        },
        {
            "tool_name": "sslscan",
            "operation_name": "tls_audit",
            "args": {"target": "172.20.32.59:443"},
            "reason": "Audit TLS on port 443 from recon.",
            "phase": "enumeration",
        },
    ]
    transport = _mock_plan(steps)
    async with httpx.AsyncClient(transport=transport) as http:
        llm = LLMClient("http://ollama", client=http)
        out = await plan_enumeration(_state_with_recon(), EnumPlannerDeps(llm=llm))
        assert out.current_phase is Phase.ENUMERATION
        assert len(out.planned_steps) == 2
        assert all(step.phase is Phase.ENUMERATION for step in out.planned_steps)
        body = transport.captured["body"]  # type: ignore[attr-defined]
        assert "tool_output" in body
        assert "nginx" in body


@pytest.mark.asyncio
async def test_plan_enumeration_rejects_out_of_scope_target():
    steps = [
        {
            "tool_name": "whatweb",
            "operation_name": "fingerprint",
            "args": {"target": "http://8.8.8.8/"},
            "reason": "nope",
            "phase": "enumeration",
        }
    ]
    async with httpx.AsyncClient(transport=_mock_plan(steps)) as http:
        llm = LLMClient("http://ollama", client=http)
        with pytest.raises(LLMError):
            await plan_enumeration(_state_with_recon(), EnumPlannerDeps(llm=llm))


@pytest.mark.asyncio
async def test_plan_enumeration_handles_empty_recon_state():
    """No prior recon results — the planner must still produce a valid plan."""
    steps = [
        {
            "tool_name": "dnsx",
            "operation_name": "resolve",
            "args": {"target": "172.20.32.59"},
            "reason": "Resolve scope IP since no recon ran.",
            "phase": "enumeration",
        }
    ]
    async with httpx.AsyncClient(transport=_mock_plan(steps)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="enum",
            intent="recon_and_enum",
        )
        out = await plan_enumeration(state, EnumPlannerDeps(llm=llm))
        assert out.planned_steps[0].tool_name == "dnsx"
        assert out.current_phase is Phase.ENUMERATION

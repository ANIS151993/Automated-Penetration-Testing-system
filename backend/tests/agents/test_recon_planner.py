from __future__ import annotations

import json

import httpx
import pytest

from app.agents.nodes.recon_planner import PlannerDeps, plan_recon
from app.agents.state import EngagementState, Phase
from app.core.llm_client import LLMClient, LLMError


def _mock_plan(steps: list[dict]) -> httpx.MockTransport:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"steps": steps}),
                }
            },
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_plan_recon_accepts_in_scope_steps():
    steps = [
        {
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22,80,443"},
            "reason": "Identify live services on the target.",
            "phase": "reconnaissance",
        },
        {
            "tool_name": "http_probe",
            "operation_name": "fetch_headers",
            "args": {"url": "http://172.20.32.59/"},
            "reason": "Probe for a web banner on the target.",
            "phase": "reconnaissance",
        },
    ]
    async with httpx.AsyncClient(transport=_mock_plan(steps)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="recon the target",
            intent="recon_and_enum",
        )
        out = await plan_recon(state, PlannerDeps(llm=llm))
        assert len(out.planned_steps) == 2
        assert out.planned_steps[0].tool_name == "nmap"
        assert out.current_phase is Phase.RECONNAISSANCE


@pytest.mark.asyncio
async def test_plan_recon_rejects_out_of_scope_target():
    steps = [
        {
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "8.8.8.8", "ports": "22,80,443"},
            "reason": "Boom.",
            "phase": "reconnaissance",
        }
    ]
    async with httpx.AsyncClient(transport=_mock_plan(steps)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="recon",
            intent="recon_only",
        )
        with pytest.raises(LLMError):
            await plan_recon(state, PlannerDeps(llm=llm))


@pytest.mark.asyncio
async def test_plan_recon_rejects_unknown_tool():
    steps = [
        {
            "tool_name": "metasploit",
            "operation_name": "exploit",
            "args": {"target": "172.20.32.59"},
            "reason": "nope",
            "phase": "reconnaissance",
        }
    ]
    async with httpx.AsyncClient(transport=_mock_plan(steps)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="goal",
            intent="full_pentest",
        )
        with pytest.raises(LLMError):
            await plan_recon(state, PlannerDeps(llm=llm))

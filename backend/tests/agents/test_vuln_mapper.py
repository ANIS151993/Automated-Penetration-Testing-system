from __future__ import annotations

import json

import httpx
import pytest

from app.agents.nodes.vuln_mapper import VulnMapperDeps, map_vulnerabilities
from app.agents.state import EngagementState, Phase, StepResult
from app.core.llm_client import LLMClient, LLMError


def _mock(payload: dict) -> httpx.MockTransport:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(payload),
                }
            },
        )

    transport = httpx.MockTransport(handler)
    transport.captured = captured  # type: ignore[attr-defined]
    return transport


def _state_with_results() -> EngagementState:
    state = EngagementState(
        engagement_id="eng-1",
        scope_cidrs=["172.20.32.0/18"],
        operator_goal="map vulns",
        intent="full_pentest",
    )
    state.step_results = [
        StepResult(
            tool_name="nmap",
            operation_name="service_scan",
            args={"target": "172.20.32.59", "ports": "22,80,443"},
            status="completed",
            exit_code=0,
            stdout="80/tcp open  http   nginx 1.18.0",
            stderr="",
            invocation_id="inv-1",
        ),
        StepResult(
            tool_name="whatweb",
            operation_name="fingerprint",
            args={"target": "http://172.20.32.59/"},
            status="completed",
            exit_code=0,
            stdout="nginx[1.18.0]",
            stderr="",
            invocation_id="inv-2",
        ),
    ]
    return state


@pytest.mark.asyncio
async def test_map_vulnerabilities_happy_path():
    payload = {
        "candidates": [
            {
                "title": "Outdated nginx 1.18.0",
                "severity": "medium",
                "attack_technique": "T1190",
                "summary": "nginx 1.18.0 is end-of-life and exposes known CVEs.",
                "evidence_refs": ["inv-1", "inv-2"],
                "citations": ["docs/playbooks/web.md"],
            }
        ]
    }
    transport = _mock(payload)
    async with httpx.AsyncClient(transport=transport) as http:
        llm = LLMClient("http://ollama", client=http)
        out = await map_vulnerabilities(_state_with_results(), VulnMapperDeps(llm=llm))
        assert out.current_phase is Phase.VULN_MAPPING
        assert len(out.findings) == 1
        f = out.findings[0]
        assert f["severity"] == "medium"
        assert "inv-1" in f["evidence_refs"]
        body = transport.captured["body"]  # type: ignore[attr-defined]
        assert "tool_output" in body


@pytest.mark.asyncio
async def test_map_vulnerabilities_rejects_unknown_evidence_ref():
    payload = {
        "candidates": [
            {
                "title": "Bogus",
                "severity": "high",
                "attack_technique": "T1190",
                "summary": "claims evidence that does not exist",
                "evidence_refs": ["inv-does-not-exist"],
            }
        ]
    }
    async with httpx.AsyncClient(transport=_mock(payload)) as http:
        llm = LLMClient("http://ollama", client=http)
        with pytest.raises(LLMError):
            await map_vulnerabilities(_state_with_results(), VulnMapperDeps(llm=llm))


@pytest.mark.asyncio
async def test_map_vulnerabilities_rejects_invalid_severity():
    payload = {
        "candidates": [
            {
                "title": "Bad sev",
                "severity": "catastrophic",
                "attack_technique": "T1190",
                "summary": "invalid severity value",
                "evidence_refs": ["inv-1"],
            }
        ]
    }
    async with httpx.AsyncClient(transport=_mock(payload)) as http:
        llm = LLMClient("http://ollama", client=http)
        with pytest.raises(LLMError):
            await map_vulnerabilities(_state_with_results(), VulnMapperDeps(llm=llm))


@pytest.mark.asyncio
async def test_map_vulnerabilities_rejects_non_list():
    async with httpx.AsyncClient(transport=_mock({"candidates": "nope"})) as http:
        llm = LLMClient("http://ollama", client=http)
        with pytest.raises(LLMError):
            await map_vulnerabilities(_state_with_results(), VulnMapperDeps(llm=llm))

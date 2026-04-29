from __future__ import annotations

import json

import httpx
import pytest

from app.agents.nodes.tool_caller import ExecutorResult, ToolCallerDeps
from app.agents.state import EngagementState, Phase, PlannedStep
from app.agents.supervisor import (
    SupervisorDeps,
    run_full_pipeline,
    run_recon_pipeline,
)
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


class _FakeKnowledge:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(self, query: str, *, top_k: int, min_score: float):
        from app.knowledge.retrieval import RetrievedChunk

        self.queries.append(query)
        return [
            RetrievedChunk(
                source_path="docs/playbooks/recon.md",
                title="Recon",
                content="Use nmap.",
                score=0.9,
                chunk_metadata={},
            )
        ]


@pytest.mark.asyncio
async def test_supervisor_forwards_knowledge_to_planner():
    responses = {
        "llama3.2:3b-instruct-q4_K_M": {
            "intent": "recon_and_enum",
            "justification": "x",
        },
        "qwen2.5:7b-instruct-q4_K_M": {
            "steps": [
                {
                    "tool_name": "nmap",
                    "operation_name": "service_scan",
                    "args": {"target": "172.20.32.59", "ports": "22"},
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
            stdout="ok",
            stderr="",
            invocation_id="inv-1",
        )

    kb = _FakeKnowledge()
    async with httpx.AsyncClient(transport=_mock_llm_transport(responses)) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="recon target",
        )
        deps = SupervisorDeps(
            llm=llm,
            tool_caller=ToolCallerDeps(executor=executor),
            knowledge=kb,
        )
        out = await run_recon_pipeline(state, deps)
        assert kb.queries, "supervisor should forward knowledge to planner"
        assert out.planned_steps[0].citations == ["docs/playbooks/recon.md"]


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


def _full_pipeline_transport() -> httpx.MockTransport:
    """Routes by inspecting system prompt content to distinguish planner stages."""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        model = payload["model"]
        system_text = payload["messages"][0]["content"]

        if model == "llama3.2:3b-instruct-q4_K_M":
            content = {"intent": "full_pentest", "justification": "x"}
        elif "exploit-prep planner" in system_text:
            content = {
                "steps": [
                    {
                        "tool_name": "nuclei",
                        "operation_name": "targeted_scan",
                        "args": {
                            "target": "http://172.20.32.59/",
                            "templates": ["cve-2021-41773"],
                        },
                        "reason": "verify nginx CVE",
                        "phase": "exploitation",
                        "finding_refs": [0],
                    }
                ]
            }
        elif "vulnerability mapper" in system_text:
            content = {
                "candidates": [
                    {
                        "title": "Outdated nginx",
                        "severity": "medium",
                        "attack_technique": "T1190",
                        "summary": "nginx 1.18.0 visible.",
                        "evidence_refs": ["inv-recon"],
                    }
                ]
            }
        elif "enumeration planner" in system_text:
            content = {
                "steps": [
                    {
                        "tool_name": "whatweb",
                        "operation_name": "fingerprint",
                        "args": {"target": "http://172.20.32.59/"},
                        "reason": "fingerprint",
                        "phase": "enumeration",
                    }
                ]
            }
        else:
            content = {
                "steps": [
                    {
                        "tool_name": "nmap",
                        "operation_name": "service_scan",
                        "args": {"target": "172.20.32.59", "ports": "80"},
                        "reason": "recon",
                        "phase": "reconnaissance",
                    }
                ]
            }

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
async def test_run_full_pipeline_produces_findings():
    counter = {"n": 0}

    async def executor(step: PlannedStep) -> ExecutorResult:
        counter["n"] += 1
        return ExecutorResult(
            status="completed",
            exit_code=0,
            stdout=f"nginx 1.18.0 ({step.tool_name})",
            stderr="",
            invocation_id="inv-recon" if counter["n"] == 1 else f"inv-{counter['n']}",
        )

    async with httpx.AsyncClient(transport=_full_pipeline_transport()) as http:
        llm = LLMClient("http://ollama", client=http)
        state = EngagementState(
            engagement_id="eng-1",
            scope_cidrs=["172.20.32.0/18"],
            operator_goal="full pentest of 172.20.32.59",
        )
        deps = SupervisorDeps(
            llm=llm,
            tool_caller=ToolCallerDeps(executor=executor),
        )
        out = await run_full_pipeline(state, deps)

        assert out.intent == "full_pentest"
        assert out.current_phase is Phase.EXPLOITATION
        assert len(out.step_results) == 2  # recon step + enum step (no exec)
        assert counter["n"] == 2
        assert len(out.planned_steps) == 1
        assert out.planned_steps[0].tool_name == "nuclei"
        assert len(out.findings) == 1
        assert out.findings[0]["evidence_refs"] == ["inv-recon"]
        assert out.findings[0]["severity"] == "medium"

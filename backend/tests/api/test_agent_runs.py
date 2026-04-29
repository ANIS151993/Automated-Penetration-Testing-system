from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import reset_database_state
from app.core.gateway_validation import GatewayValidationService
from app.main import create_app


def _llm_responses() -> dict[str, dict]:
    return {
        "llama3.2:3b-instruct-q4_K_M": {
            "intent": "recon_only",
            "justification": "operator wants services",
        },
        "qwen2.5:7b-instruct-q4_K_M": {
            "steps": [
                {
                    "tool_name": "nmap",
                    "operation_name": "service_scan",
                    "args": {"target": "172.20.32.59", "ports": "22"},
                    "reason": "find services",
                    "phase": "reconnaissance",
                }
            ]
        },
    }


def _llm_handler(responses: dict[str, dict]):
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        model = body["model"]
        content = responses.get(model)
        if content is None:
            return httpx.Response(500, json={"error": f"no mock for {model}"})
        return httpx.Response(
            200,
            json={
                "model": model,
                "message": {"role": "assistant", "content": json.dumps(content)},
            },
        )

    return handler


def _gateway_handler(request: httpx.Request) -> httpx.Response:
    parsed = json.loads(request.content.decode())
    if request.url.path.endswith("/execute-invocation"):
        body = "\n".join(
            [
                json.dumps(
                    {
                        "type": "started",
                        "execution_id": parsed.get("execution_id"),
                    }
                ),
                json.dumps({"type": "stdout", "line": "22/tcp open ssh"}),
                json.dumps(
                    {"type": "completed", "status": "completed", "exit_code": 0}
                ),
            ]
        )
        return httpx.Response(200, text=f"{body}\n")
    return httpx.Response(
        200,
        json={
            "status": "validated",
            "tool": parsed["tool_name"],
            "operation": parsed["operation_name"],
            "command_preview": ["nmap", "-sV", "172.20.32.59"],
            "targets": ["172.20.32.59"],
        },
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "pentai-test.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    monkeypatch.setenv("PENTAI_ARTIFACTS_ROOT", str(artifacts_root))
    get_settings.cache_clear()
    reset_database_state()

    app = create_app()
    app.state.gateway_validation_service = GatewayValidationService(
        settings=get_settings(),
        engagement_service=app.state.engagement_service,
        approval_service=app.state.approval_service,
        audit_service=app.state.audit_service,
        tool_invocation_service=app.state.tool_invocation_service,
        tool_execution_service=app.state.tool_execution_service,
        http_client=httpx.Client(transport=httpx.MockTransport(_gateway_handler)),
    )

    with TestClient(app) as test_client:
        # Replace the lifespan-created LLM client's transport with a mock so
        # complete_json never hits a real Ollama backend.
        llm = app.state.llm_client
        llm._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            transport=httpx.MockTransport(_llm_handler(_llm_responses()))
        )
        app.state.knowledge_service = None

        app.state.user_service.create_user(
            email="tester@pentai.local",
            password="test-password-123",
            display_name="Tester",
            role="admin",
        )
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "tester@pentai.local", "password": "test-password-123"},
        )
        assert login.status_code == 200, login.text
        yield test_client

    get_settings.cache_clear()
    reset_database_state()


def _create_engagement(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/engagements",
        json={
            "name": "Agent Run",
            "description": "Pipeline test",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_agent_run_executes_pipeline(client: TestClient) -> None:
    engagement = _create_engagement(client)
    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/agent-runs",
        json={"operator_goal": "find open services on 172.20.32.59"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["intent"] == "recon_only"
    assert data["current_phase"] == "reconnaissance"
    assert len(data["planned_steps"]) == 1
    assert data["planned_steps"][0]["tool_name"] == "nmap"
    assert len(data["step_results"]) == 1
    assert data["step_results"][0]["status"] == "completed"
    assert "22/tcp open ssh" in data["step_results"][0]["stdout"]
    assert data["id"] is not None
    assert data["created_at"] is not None


def test_agent_run_persists_and_lists(client: TestClient) -> None:
    engagement = _create_engagement(client)
    run = client.post(
        f"/api/v1/engagements/{engagement['id']}/agent-runs",
        json={"operator_goal": "find open services on 172.20.32.59"},
    ).json()

    listing = client.get(f"/api/v1/engagements/{engagement['id']}/agent-runs")
    assert listing.status_code == 200, listing.text
    summaries = listing.json()
    assert len(summaries) == 1
    assert summaries[0]["id"] == run["id"]
    assert summaries[0]["planned_steps_count"] == 1
    assert summaries[0]["step_results_count"] == 1

    detail = client.get(f"/api/v1/agent-runs/{run['id']}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == run["id"]
    assert body["operator_goal"] == "find open services on 172.20.32.59"
    assert len(body["planned_steps"]) == 1


def test_agent_run_records_audit_event(client: TestClient) -> None:
    engagement = _create_engagement(client)
    run = client.post(
        f"/api/v1/engagements/{engagement['id']}/agent-runs",
        json={"operator_goal": "find open services on 172.20.32.59"},
    ).json()

    audit = client.get(
        f"/api/v1/engagements/{engagement['id']}/audit-events"
    ).json()
    completed = [e for e in audit if e["event_type"] == "agent_run_completed"]
    assert len(completed) == 1
    payload = completed[0]["payload"]
    assert payload["agent_run_id"] == run["id"]
    assert payload["intent"] == "recon_only"
    assert payload["step_results_count"] == 1
    assert completed[0]["actor"] == "Analyst One"


def _full_pentest_handler(responses_holder: dict[str, dict]):
    """Routes by inspecting system prompt content for full_pentest pipelines."""

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        model = body["model"]
        system_text = body["messages"][0]["content"]
        if model == "llama3.2:3b-instruct-q4_K_M":
            content = {"intent": "full_pentest", "justification": "x"}
        elif "exploit-prep planner" in system_text:
            content = {
                "steps": [
                    {
                        "tool_name": "nuclei",
                        "operation_name": "targeted_scan",
                        "args": {"target": "http://172.20.32.59/"},
                        "reason": "verify",
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
                        "summary": "nginx 1.18.0",
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
                        "reason": "fp",
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
                "message": {"role": "assistant", "content": json.dumps(content)},
            },
        )

    responses_holder["handler"] = handler
    return handler


def test_agent_run_full_pentest_auto_creates_approvals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "pentai-test.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    monkeypatch.setenv("PENTAI_ARTIFACTS_ROOT", str(artifacts_root))
    get_settings.cache_clear()
    reset_database_state()

    counter = {"n": 0}

    def gateway_handler(request: httpx.Request) -> httpx.Response:
        parsed = json.loads(request.content.decode())
        if request.url.path.endswith("/execute-invocation"):
            counter["n"] += 1
            inv = "inv-recon" if counter["n"] == 1 else f"inv-{counter['n']}"
            body = "\n".join(
                [
                    json.dumps({"type": "started", "execution_id": inv}),
                    json.dumps({"type": "stdout", "line": "nginx 1.18.0"}),
                    json.dumps(
                        {"type": "completed", "status": "completed", "exit_code": 0}
                    ),
                ]
            )
            return httpx.Response(200, text=f"{body}\n")
        return httpx.Response(
            200,
            json={
                "status": "validated",
                "tool": parsed["tool_name"],
                "operation": parsed["operation_name"],
                "command_preview": ["x"],
                "targets": ["172.20.32.59"],
            },
        )

    app = create_app()
    app.state.gateway_validation_service = GatewayValidationService(
        settings=get_settings(),
        engagement_service=app.state.engagement_service,
        approval_service=app.state.approval_service,
        audit_service=app.state.audit_service,
        tool_invocation_service=app.state.tool_invocation_service,
        tool_execution_service=app.state.tool_execution_service,
        http_client=httpx.Client(transport=httpx.MockTransport(gateway_handler)),
    )

    with TestClient(app) as test_client:
        holder: dict[str, dict] = {}
        llm = app.state.llm_client
        llm._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            transport=httpx.MockTransport(_full_pentest_handler(holder))
        )
        app.state.knowledge_service = None
        app.state.user_service.create_user(
            email="tester@pentai.local",
            password="test-password-123",
            display_name="Tester",
            role="admin",
        )
        test_client.post(
            "/api/v1/auth/login",
            json={"email": "tester@pentai.local", "password": "test-password-123"},
        )
        engagement = _create_engagement(test_client)
        run = test_client.post(
            f"/api/v1/engagements/{engagement['id']}/agent-runs",
            json={"operator_goal": "full pentest of 172.20.32.59"},
        )
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["current_phase"] == "exploitation"
        assert len(body["planned_steps"]) == 1
        assert body["planned_steps"][0]["tool_name"] == "nuclei"

        approvals = test_client.get(
            f"/api/v1/engagements/{engagement['id']}/approvals"
        ).json()
        assert len(approvals) == 1
        assert approvals[0]["tool_name"] == "nuclei"
        assert approvals[0]["operation_name"] == "targeted_scan"
        assert approvals[0]["risk_level"] == "high"
        assert approvals[0]["approved"] is False
        assert approvals[0]["requested_action"].startswith("exploit-prep:")
        assert approvals[0]["agent_run_id"] == body["id"]

    get_settings.cache_clear()
    reset_database_state()


def test_agent_run_detail_404(client: TestClient) -> None:
    response = client.get("/api/v1/agent-runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_agent_run_returns_404_for_unknown_engagement(client: TestClient) -> None:
    response = client.post(
        "/api/v1/engagements/00000000-0000-0000-0000-000000000000/agent-runs",
        json={"operator_goal": "scan something"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Engagement not found"


def test_agent_run_rejects_unsupported_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "pentai-test.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    monkeypatch.setenv("PENTAI_ARTIFACTS_ROOT", str(artifacts_root))
    get_settings.cache_clear()
    reset_database_state()

    app = create_app()
    app.state.gateway_validation_service = GatewayValidationService(
        settings=get_settings(),
        engagement_service=app.state.engagement_service,
        approval_service=app.state.approval_service,
        audit_service=app.state.audit_service,
        tool_invocation_service=app.state.tool_invocation_service,
        tool_execution_service=app.state.tool_execution_service,
        http_client=httpx.Client(transport=httpx.MockTransport(_gateway_handler)),
    )

    with TestClient(app) as test_client:
        responses = _llm_responses()
        responses["llama3.2:3b-instruct-q4_K_M"] = {
            "intent": "unsupported",
            "justification": "no",
        }
        llm = app.state.llm_client
        llm._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            transport=httpx.MockTransport(_llm_handler(responses))
        )
        app.state.knowledge_service = None
        app.state.user_service.create_user(
            email="tester@pentai.local",
            password="test-password-123",
            display_name="Tester",
            role="admin",
        )
        test_client.post(
            "/api/v1/auth/login",
            json={"email": "tester@pentai.local", "password": "test-password-123"},
        )
        engagement = _create_engagement(test_client)
        response = test_client.post(
            f"/api/v1/engagements/{engagement['id']}/agent-runs",
            json={"operator_goal": "???"},
        )
        assert response.status_code == 422
        assert "does not authorize" in response.json()["detail"]

    get_settings.cache_clear()
    reset_database_state()

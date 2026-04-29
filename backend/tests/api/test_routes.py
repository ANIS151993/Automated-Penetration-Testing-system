import json
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import reset_database_state
from app.core.gateway_validation import GatewayValidationService
from app.main import create_app


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
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                _mock_gateway_validation
            )
        ),
    )

    with TestClient(app) as test_client:
        app.state.user_service.create_user(
            email="tester@pentai.local",
            password="test-password-123",
            display_name="Tester",
            role="admin",
        )
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "tester@pentai.local", "password": "test-password-123"},
        )
        assert login_response.status_code == 200, login_response.text
        yield test_client

    get_settings.cache_clear()
    reset_database_state()


def _mock_gateway_validation(request: httpx.Request) -> httpx.Response:
    parsed = json.loads(request.content.decode())
    if request.url.path.endswith("/cancel-execution"):
        return httpx.Response(
            202,
            json={
                "status": "cancellation_requested",
                "detail": "Gateway accepted the cancellation request.",
                "execution_id": parsed["execution_id"],
            },
        )
    if request.url.path.endswith("/execute-invocation"):
        body = "\n".join(
            [
                json.dumps(
                    {
                        "type": "started",
                        "status": "running",
                        "execution_id": parsed.get("execution_id"),
                        "tool": parsed["tool_name"],
                        "operation": parsed["operation_name"],
                        "targets": ["172.20.32.59"],
                        "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                        "timestamp": "2026-04-20T00:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "type": "stdout",
                        "execution_id": parsed.get("execution_id"),
                        "line": "22/tcp open ssh",
                        "tool": parsed["tool_name"],
                        "operation": parsed["operation_name"],
                        "targets": ["172.20.32.59"],
                        "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                        "timestamp": "2026-04-20T00:00:01Z",
                    }
                ),
                json.dumps(
                    {
                        "type": "completed",
                        "status": "completed",
                        "execution_id": parsed.get("execution_id"),
                        "exit_code": 0,
                        "stdout_lines": 1,
                        "stderr_lines": 0,
                        "tool": parsed["tool_name"],
                        "operation": parsed["operation_name"],
                        "targets": ["172.20.32.59"],
                        "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                        "timestamp": "2026-04-20T00:00:02Z",
                    }
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
            "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
            "targets": ["172.20.32.59"],
        },
    )


def test_healthz_exposes_scope_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["allowed_network"] == "172.20.32.0/18"
    assert payload["database_status"] == "ok"


def test_engagement_crud_round_trip(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/engagements",
        json={
            "name": "Target Node Validation",
            "description": "Initial safe engagement",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    )

    assert create_response.status_code == 201
    engagement = create_response.json()

    get_response = client.get(f"/api/v1/engagements/{engagement['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["scope_cidrs"] == ["172.20.32.59/32"]

    patch_response = client.patch(
        f"/api/v1/engagements/{engagement['id']}/status",
        json={"status": "active"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "active"


def test_approval_flow_and_tool_validation(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Tool Validation",
            "description": "Gateway validation flow",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    approval = client.post(
        f"/api/v1/engagements/{engagement['id']}/approvals",
        json={
            "requested_action": "Run high-risk scan",
            "requested_by": "Analyst One",
            "tool_name": "nmap",
            "operation_name": "os_detection",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )
    assert approval.status_code == 201

    decided = client.patch(
        f"/api/v1/approvals/{approval.json()['id']}",
        json={
            "approved": True,
            "approved_by": "Lab Owner",
            "decision_reason": "Approved for lab validation",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["approved"] is True

    validated = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "os_detection",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )
    assert validated.status_code == 200
    assert validated.json()["risk_level"] == "high"
    assert validated.json()["operation"] == "os_detection"
    assert validated.json()["invocation_id"] is not None


def test_list_approvals_status_filter(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Approval filter",
            "description": "list filter",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    pending = client.post(
        f"/api/v1/engagements/{engagement['id']}/approvals",
        json={
            "requested_action": "exploit-prep:nuclei.targeted_scan",
            "requested_by": "agent",
            "tool_name": "nuclei",
            "operation_name": "targeted_scan",
            "args": {"target": "http://172.20.32.59/"},
        },
    ).json()

    decided_seed = client.post(
        f"/api/v1/engagements/{engagement['id']}/approvals",
        json={
            "requested_action": "exploit-prep:gobuster.dir",
            "requested_by": "agent",
            "tool_name": "gobuster",
            "operation_name": "dir",
            "args": {"target": "http://172.20.32.59/"},
        },
    ).json()
    client.patch(
        f"/api/v1/approvals/{decided_seed['id']}",
        json={
            "approved": True,
            "approved_by": "Lab Owner",
            "decision_reason": "ok",
        },
    )

    all_rows = client.get(
        f"/api/v1/engagements/{engagement['id']}/approvals"
    ).json()
    assert len(all_rows) == 2

    pending_rows = client.get(
        f"/api/v1/engagements/{engagement['id']}/approvals?status=pending"
    ).json()
    assert [r["id"] for r in pending_rows] == [pending["id"]]

    decided_rows = client.get(
        f"/api/v1/engagements/{engagement['id']}/approvals?status=decided"
    ).json()
    assert [r["id"] for r in decided_rows] == [decided_seed["id"]]

    bad = client.get(
        f"/api/v1/engagements/{engagement['id']}/approvals?status=bogus"
    )
    assert bad.status_code == 400


def test_low_risk_tool_validation_succeeds(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Low Risk Validation",
            "description": "Low risk path",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )

    assert response.status_code == 200
    assert response.json()["operation"] == "service_scan"
    assert response.json()["invocation_id"] is not None


def test_tool_validation_rejects_missing_high_risk_approval(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Approval Required",
            "description": "High-risk path",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "os_detection",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )

    assert response.status_code == 409


def test_tool_validation_checks_scope_before_gateway(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Scope Check",
            "description": "Out of scope request",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.60", "ports": "22"},
        },
    )

    assert response.status_code == 400


def test_findings_and_audit_timeline_round_trip(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Finding Flow",
            "description": "Finding capture and audit timeline",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    validation = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22,80-81"},
        },
    )
    assert validation.status_code == 200
    invocation_id = validation.json()["invocation_id"]
    assert invocation_id is not None

    finding = client.post(
        f"/api/v1/engagements/{engagement['id']}/findings",
        json={
            "title": "Open SSH service",
            "severity": "medium",
            "attack_technique": "T1046",
            "summary": "The target exposes SSH on the scoped host.",
            "evidence": ["OpenSSH banner captured"],
            "evidence_refs": [invocation_id],
            "reported_by": "Analyst One",
        },
    )

    assert finding.status_code == 201
    assert finding.json()["severity"] == "medium"
    assert finding.json()["evidence_refs"] == [invocation_id]
    assert any("nmap.service_scan" in item for item in finding.json()["evidence"])

    findings = client.get(f"/api/v1/engagements/{engagement['id']}/findings")
    assert findings.status_code == 200
    assert findings.json()[0]["title"] == "Open SSH service"

    tool_invocations = client.get(
        f"/api/v1/engagements/{engagement['id']}/tool-invocations"
    )
    assert tool_invocations.status_code == 200
    assert tool_invocations.json()[0]["id"] == invocation_id

    inventory = client.get(f"/api/v1/engagements/{engagement['id']}/inventory")
    assert inventory.status_code == 200
    assert inventory.json()["hosts"][0]["target"] == "172.20.32.59"
    assert [item["port"] for item in inventory.json()["services"]] == [22, 80, 81]

    audit_events = client.get(f"/api/v1/engagements/{engagement['id']}/audit-events")
    assert audit_events.status_code == 200
    assert any(
        item["event_type"] == "finding_recorded" for item in audit_events.json()
    )


def test_report_generation_round_trip(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Reporting Flow",
            "description": "Stored artifact generation",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    validation = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )
    assert validation.status_code == 200

    finding = client.post(
        f"/api/v1/engagements/{engagement['id']}/findings",
        json={
            "title": "Validated SSH surface",
            "severity": "medium",
            "attack_technique": "T1046",
            "summary": "The scoped target exposes an SSH service in the validated request set.",
            "evidence": ["Operator confirmed the SSH exposure during review."],
            "evidence_refs": [validation.json()["invocation_id"]],
            "reported_by": "Analyst One",
        },
    )
    assert finding.status_code == 201

    report = client.post(
        f"/api/v1/engagements/{engagement['id']}/reports",
        json={"report_format": "json"},
    )
    assert report.status_code == 201
    assert report.json()["artifact_path"].endswith(".json")

    reports = client.get(f"/api/v1/engagements/{engagement['id']}/reports")
    assert reports.status_code == 200
    assert reports.json()[0]["id"] == report.json()["id"]

    document = client.get(f"/api/v1/reports/{report.json()['id']}")
    assert document.status_code == 200
    payload = document.json()["content"]
    assert payload["summary"]["findings_total"] == 1
    assert payload["summary"]["validated_requests"] == 1
    assert payload["findings"][0]["evidence_refs"] == [validation.json()["invocation_id"]]

    audit_events = client.get(f"/api/v1/engagements/{engagement['id']}/audit-events")
    assert audit_events.status_code == 200
    assert any(
        item["event_type"] == "report_generated" for item in audit_events.json()
    )
    assert "agent_runs" in payload
    assert "agent_findings" in payload
    assert payload["summary"]["agent_runs_total"] == 0
    assert payload["summary"]["agent_findings_total"] == 0


def test_execute_stream_round_trip(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Execution Flow",
            "description": "Streaming execution from validated invocation",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    validation = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )
    invocation_id = validation.json()["invocation_id"]

    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-invocations/{invocation_id}/execute-stream"
    )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line]
    assert any('"type": "started"' in line for line in lines)
    assert any('"type": "stdout"' in line for line in lines)
    assert any('"type": "completed"' in line for line in lines)

    executions = client.get(f"/api/v1/engagements/{engagement['id']}/tool-executions")
    assert executions.status_code == 200
    assert len(executions.json()) == 1
    execution = executions.json()[0]
    assert execution["invocation_id"] == invocation_id
    assert execution["status"] == "completed"
    assert execution["artifact_path"].endswith(".json")

    artifact = client.get(
        f"/api/v1/engagements/{engagement['id']}/tool-executions/{execution['id']}"
    )
    assert artifact.status_code == 200
    assert artifact.json()["execution"]["id"] == execution["id"]
    assert artifact.json()["content"]["events"][1]["line"] == "22/tcp open ssh"
    assert artifact.json()["content"]["parsed"]["services"][0]["service_name"] == "ssh"

    suggestions = client.get(
        f"/api/v1/engagements/{engagement['id']}/finding-suggestions"
    )
    assert suggestions.status_code == 200
    assert suggestions.json()[0]["title"].startswith("Open ssh service")
    assert suggestions.json()[0]["evidence_refs"] == [invocation_id]

    inventory = client.get(f"/api/v1/engagements/{engagement['id']}/inventory")
    assert inventory.status_code == 200
    assert inventory.json()["services"][0]["service_name"] == "ssh"
    assert "nmap.service_scan" in inventory.json()["services"][0]["operations"]

    audit_events = client.get(f"/api/v1/engagements/{engagement['id']}/audit-events")
    event_types = [item["event_type"] for item in audit_events.json()]
    assert "tool_execution_started" in event_types
    assert "tool_execution_completed" in event_types

    report = client.post(
        f"/api/v1/engagements/{engagement['id']}/reports",
        json={"report_format": "json"},
    )
    assert report.status_code == 201
    document = client.get(f"/api/v1/reports/{report.json()['id']}")
    assert document.status_code == 200
    payload = document.json()["content"]
    assert payload["summary"]["suggested_findings_total"] == 1
    assert payload["summary"]["executions_total"] == 1
    assert payload["summary"]["completed_executions"] == 1
    assert payload["summary"]["parsed_diagnostics_total"] == 0
    assert payload["tool_executions"][0]["id"] == execution["id"]
    assert payload["tool_execution_artifacts"][0]["events"][1]["line"] == "22/tcp open ssh"
    assert payload["finding_suggestions"][0]["title"].startswith("Open ssh service")


def test_cancel_running_execution_requests_gateway_stop(client: TestClient) -> None:
    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Cancellation Flow",
            "description": "Cancelling a running execution",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    validation = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )
    invocation_id = validation.json()["invocation_id"]
    invocation = client.app.state.tool_invocation_service.get_for_engagement(
        UUID(engagement["id"]),
        UUID(invocation_id),
    )
    execution = client.app.state.tool_execution_service.start_execution(invocation)

    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-executions/{execution.id}/cancel"
    )

    assert response.status_code == 202
    assert response.json()["status"] == "cancellation_requested"

    audit_events = client.get(f"/api/v1/engagements/{engagement['id']}/audit-events")
    event_types = [item["event_type"] for item in audit_events.json()]
    assert "tool_execution_cancel_requested" in event_types


def test_execute_stream_records_timeout_status(client: TestClient) -> None:
    def timeout_transport(request: httpx.Request) -> httpx.Response:
        parsed = json.loads(request.content.decode())
        if request.url.path.endswith("/execute-invocation"):
            body = "\n".join(
                [
                    json.dumps(
                        {
                            "type": "started",
                            "status": "running",
                            "execution_id": parsed.get("execution_id"),
                            "tool": parsed["tool_name"],
                            "operation": parsed["operation_name"],
                            "targets": ["172.20.32.59"],
                            "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                            "timestamp": "2026-04-20T00:00:00Z",
                            "timeout_seconds": 120,
                        }
                    ),
                    json.dumps(
                        {
                            "type": "timed_out",
                            "status": "timed_out",
                            "execution_id": parsed.get("execution_id"),
                            "error": "Command timed out after 120 seconds",
                            "exit_code": -9,
                            "stdout_lines": 0,
                            "stderr_lines": 0,
                            "tool": parsed["tool_name"],
                            "operation": parsed["operation_name"],
                            "targets": ["172.20.32.59"],
                            "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                            "timestamp": "2026-04-20T00:02:00Z",
                        }
                    ),
                ]
            )
            return httpx.Response(200, text=f"{body}\n")
        return _mock_gateway_validation(request)

    client.app.state.gateway_validation_service.http_client = httpx.Client(
        transport=httpx.MockTransport(timeout_transport)
    )

    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Timeout Flow",
            "description": "Execution timeout handling",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    validation = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )
    invocation_id = validation.json()["invocation_id"]

    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-invocations/{invocation_id}/execute-stream"
    )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line]
    assert any('"type": "timed_out"' in line for line in lines)

    executions = client.get(f"/api/v1/engagements/{engagement['id']}/tool-executions")
    execution = executions.json()[0]
    assert execution["status"] == "timed_out"

    audit_events = client.get(f"/api/v1/engagements/{engagement['id']}/audit-events")
    event_types = [item["event_type"] for item in audit_events.json()]
    assert "tool_execution_timed_out" in event_types


def test_execute_stream_records_cancelled_status(client: TestClient) -> None:
    def cancelled_transport(request: httpx.Request) -> httpx.Response:
        parsed = json.loads(request.content.decode())
        if request.url.path.endswith("/execute-invocation"):
            body = "\n".join(
                [
                    json.dumps(
                        {
                            "type": "started",
                            "status": "running",
                            "execution_id": parsed.get("execution_id"),
                            "tool": parsed["tool_name"],
                            "operation": parsed["operation_name"],
                            "targets": ["172.20.32.59"],
                            "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                            "timestamp": "2026-04-20T00:00:00Z",
                            "timeout_seconds": 120,
                        }
                    ),
                    json.dumps(
                        {
                            "type": "cancelled",
                            "status": "cancelled",
                            "execution_id": parsed.get("execution_id"),
                            "error": "Command cancelled by operator request",
                            "exit_code": -15,
                            "stdout_lines": 1,
                            "stderr_lines": 0,
                            "tool": parsed["tool_name"],
                            "operation": parsed["operation_name"],
                            "targets": ["172.20.32.59"],
                            "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                            "timestamp": "2026-04-20T00:00:02Z",
                        }
                    ),
                ]
            )
            return httpx.Response(200, text=f"{body}\n")
        return _mock_gateway_validation(request)

    client.app.state.gateway_validation_service.http_client = httpx.Client(
        transport=httpx.MockTransport(cancelled_transport)
    )

    engagement = client.post(
        "/api/v1/engagements",
        json={
            "name": "Cancelled Flow",
            "description": "Execution cancellation handling",
            "scope_cidrs": ["172.20.32.59/32"],
            "authorization_confirmed": True,
            "authorizer_name": "Lab Owner",
            "operator_name": "Analyst One",
        },
    ).json()

    validation = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-validations",
        json={
            "tool_name": "nmap",
            "operation_name": "service_scan",
            "args": {"target": "172.20.32.59", "ports": "22"},
        },
    )
    invocation_id = validation.json()["invocation_id"]

    response = client.post(
        f"/api/v1/engagements/{engagement['id']}/tool-invocations/{invocation_id}/execute-stream"
    )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line]
    assert any('"type": "cancelled"' in line for line in lines)

    executions = client.get(f"/api/v1/engagements/{engagement['id']}/tool-executions")
    execution = executions.json()[0]
    assert execution["status"] == "cancelled"

    audit_events = client.get(f"/api/v1/engagements/{engagement['id']}/audit-events")
    event_types = [item["event_type"] for item in audit_events.json()]
    assert "tool_execution_cancelled" in event_types

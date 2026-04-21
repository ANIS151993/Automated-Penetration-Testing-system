from pathlib import Path

import pytest

from app.core.approvals import ApprovalService, SqlAlchemyApprovalRepository
from app.core.audit_service import AuditService
from app.core.config import get_settings
from app.core.database import initialize_database, reset_database_state, session_factory_from_settings
from app.core.engagements import EngagementService, SqlAlchemyEngagementRepository
from app.core.findings import FindingService, SqlAlchemyFindingRepository
from app.core.finding_suggestions import FindingSuggestionService
from app.core.reports import ReportService, SqlAlchemyReportRepository
from app.core.tool_executions import (
    SqlAlchemyToolExecutionRepository,
    ToolExecutionService,
)
from app.core.tool_invocations import (
    InventoryService,
    SqlAlchemyToolInvocationRepository,
    ToolInvocationService,
)
from app.schemas.engagements import EngagementCreate
from app.schemas.findings import FindingCreate
from app.schemas.reports import ReportCreate


@pytest.fixture
def report_service(tmp_path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "pentai-report.db"
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    monkeypatch.setenv("PENTAI_ARTIFACTS_ROOT", str(artifacts_root))
    get_settings.cache_clear()
    reset_database_state()

    session_factory = session_factory_from_settings()
    initialize_database(session_factory)

    audit_service = AuditService(session_factory)
    engagement_service = EngagementService(SqlAlchemyEngagementRepository(session_factory))
    approval_service = ApprovalService(
        SqlAlchemyApprovalRepository(session_factory),
        audit_service=audit_service,
    )
    tool_invocation_service = ToolInvocationService(
        SqlAlchemyToolInvocationRepository(session_factory)
    )
    tool_execution_service = ToolExecutionService(
        SqlAlchemyToolExecutionRepository(session_factory),
        artifacts_root=str(artifacts_root),
    )
    finding_suggestion_service = FindingSuggestionService(tool_execution_service)
    finding_service = FindingService(
        SqlAlchemyFindingRepository(session_factory),
        audit_service=audit_service,
        tool_invocation_service=tool_invocation_service,
    )
    service = ReportService(
        SqlAlchemyReportRepository(session_factory),
        engagement_service=engagement_service,
        approval_service=approval_service,
        finding_service=finding_service,
        finding_suggestion_service=finding_suggestion_service,
        tool_invocation_service=tool_invocation_service,
        tool_execution_service=tool_execution_service,
        inventory_service=InventoryService(
            tool_invocation_service,
            tool_execution_service=tool_execution_service,
        ),
        audit_service=audit_service,
        artifacts_root=str(artifacts_root),
    )
    yield (
        service,
        engagement_service,
        finding_service,
        tool_invocation_service,
        tool_execution_service,
        Path(artifacts_root),
    )

    get_settings.cache_clear()
    reset_database_state()


def test_report_service_generates_stored_json_artifact(report_service) -> None:
    (
        service,
        engagement_service,
        finding_service,
        tool_invocation_service,
        tool_execution_service,
        artifacts_root,
    ) = report_service

    engagement = engagement_service.create_engagement(
        EngagementCreate(
            name="Reporting",
            description="Artifact generation",
            scope_cidrs=["172.20.32.59/32"],
            authorization_confirmed=True,
            authorizer_name="Lab Owner",
            operator_name="Analyst One",
        )
    )
    invocation = tool_invocation_service.record_validation(
        engagement_id=engagement.id,
        tool_name="nmap",
        operation_name="service_scan",
        risk_level="low",
        args={"target": "172.20.32.59", "ports": "22"},
        command_preview=["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
        targets=["172.20.32.59"],
    )
    execution = tool_execution_service.start_execution(invocation)
    tool_execution_service.finalize_execution(
        execution_id=execution.id,
        invocation=invocation,
        events=[
            {
                "type": "started",
                "status": "running",
                "timestamp": "2026-04-20T00:00:00Z",
            },
            {
                "type": "stdout",
                "line": "22/tcp open ssh",
                "timestamp": "2026-04-20T00:00:01Z",
            },
            {
                "type": "completed",
                "status": "completed",
                "exit_code": 0,
                "stdout_lines": 1,
                "stderr_lines": 0,
                "timestamp": "2026-04-20T00:00:02Z",
            },
        ],
        status="completed",
        exit_code=0,
        stdout_lines=1,
        stderr_lines=0,
    )
    finding_service.create(
        engagement_id=engagement.id,
        payload=FindingCreate(
            title="Validated SSH surface",
            severity="medium",
            attack_technique="T1046",
            summary="The scoped target exposes an SSH service in the validated request set.",
            evidence=["Operator confirmed the SSH exposure during review."],
            evidence_refs=[invocation.id],
            reported_by="Analyst One",
        ),
    )

    report = service.generate(
        engagement_id=engagement.id,
        payload=ReportCreate(report_format="json"),
    )
    document = service.get_document(report.id)

    assert document is not None
    assert document.content["summary"]["findings_total"] == 1
    assert document.content["summary"]["suggested_findings_total"] == 1
    assert document.content["summary"]["validated_requests"] == 1
    assert document.content["summary"]["executions_total"] == 1
    assert document.content["summary"]["parsed_diagnostics_total"] == 0
    assert document.content["tool_executions"][0]["status"] == "completed"
    assert document.content["tool_execution_artifacts"][0]["events"][1]["line"] == "22/tcp open ssh"
    assert document.content["finding_suggestions"][0]["title"].startswith("Open ssh service")
    assert Path(report.artifact_path).is_file()
    assert str(artifacts_root) in report.artifact_path

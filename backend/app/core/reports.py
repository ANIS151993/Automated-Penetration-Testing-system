from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.agent_runs import AgentRunService
from app.core.approvals import ApprovalService
from app.core.audit_service import AuditService
from app.core.engagements import EngagementService
from app.core.findings import FindingService
from app.core.finding_suggestions import FindingSuggestionService
from app.core.tool_executions import ToolExecutionService
from app.core.tool_invocations import InventoryService, ToolInvocationService
from app.models.report import ReportModel
from app.schemas.reports import ReportCreate, ReportDocumentRead, ReportRead


@dataclass(slots=True)
class ReportEntity:
    id: UUID
    engagement_id: UUID
    report_format: str
    artifact_path: str
    created_at: datetime

    def to_read_model(self) -> ReportRead:
        return ReportRead(
            id=self.id,
            engagement_id=self.engagement_id,
            report_format=self.report_format,
            artifact_path=self.artifact_path,
            created_at=self.created_at,
        )


class ReportRepository(Protocol):
    def list_for_engagement(self, engagement_id: UUID) -> list[ReportEntity]: ...

    def get_report(self, report_id: UUID) -> ReportEntity | None: ...

    def save(self, report: ReportEntity) -> ReportEntity: ...


def _to_entity(model: ReportModel) -> ReportEntity:
    return ReportEntity(
        id=model.id,
        engagement_id=model.engagement_id,
        report_format=model.report_format,
        artifact_path=model.artifact_path,
        created_at=model.created_at,
    )


class SqlAlchemyReportRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_engagement(self, engagement_id: UUID) -> list[ReportEntity]:
        with self._session_factory() as session:
            items = session.scalars(
                select(ReportModel)
                .where(ReportModel.engagement_id == engagement_id)
                .order_by(ReportModel.created_at.desc())
            ).all()
            return [_to_entity(item) for item in items]

    def get_report(self, report_id: UUID) -> ReportEntity | None:
        with self._session_factory() as session:
            item = session.get(ReportModel, report_id)
            return _to_entity(item) if item else None

    def save(self, report: ReportEntity) -> ReportEntity:
        with self._session_factory() as session:
            model = ReportModel(
                id=report.id,
                engagement_id=report.engagement_id,
                report_format=report.report_format,
                artifact_path=report.artifact_path,
                created_at=report.created_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_entity(model)


class ReportService:
    def __init__(
        self,
        repository: ReportRepository,
        engagement_service: EngagementService,
        approval_service: ApprovalService,
        finding_service: FindingService,
        finding_suggestion_service: FindingSuggestionService,
        tool_invocation_service: ToolInvocationService,
        tool_execution_service: ToolExecutionService,
        inventory_service: InventoryService,
        audit_service: AuditService,
        artifacts_root: str,
        agent_run_service: AgentRunService | None = None,
    ) -> None:
        self._repository = repository
        self._engagement_service = engagement_service
        self._approval_service = approval_service
        self._finding_service = finding_service
        self._finding_suggestion_service = finding_suggestion_service
        self._tool_invocation_service = tool_invocation_service
        self._tool_execution_service = tool_execution_service
        self._inventory_service = inventory_service
        self._audit_service = audit_service
        self._artifacts_root = Path(artifacts_root)
        self._agent_run_service = agent_run_service

    def list_for_engagement(self, engagement_id: UUID) -> list[ReportRead]:
        return [
            item.to_read_model()
            for item in self._repository.list_for_engagement(engagement_id)
        ]

    def generate(
        self,
        *,
        engagement_id: UUID,
        payload: ReportCreate,
    ) -> ReportRead:
        engagement = self._engagement_service.get_engagement(engagement_id)
        if engagement is None:
            raise ValueError("Engagement not found")

        report_id = uuid4()
        created_at = datetime.now(timezone.utc)
        document = self._build_document(engagement_id, report_id, created_at)
        artifact_path = self._write_document(
            engagement_id=engagement_id,
            report_id=report_id,
            created_at=created_at,
            document=document,
        )
        report = self._repository.save(
            ReportEntity(
                id=report_id,
                engagement_id=engagement_id,
                report_format=payload.report_format,
                artifact_path=str(artifact_path),
                created_at=created_at,
            )
        ).to_read_model()
        self._audit_service.record_event(
            engagement_id=engagement_id,
            event_type="report_generated",
            payload={
                "report_id": str(report.id),
                "report_format": report.report_format,
                "artifact_path": report.artifact_path,
            },
            actor=engagement.operator_name,
        )
        return report

    def get_document(self, report_id: UUID) -> ReportDocumentRead | None:
        report = self._repository.get_report(report_id)
        if report is None:
            return None
        artifact_path = Path(report.artifact_path)
        content = json.loads(artifact_path.read_text(encoding="utf-8"))
        return ReportDocumentRead(
            report=report.to_read_model(),
            content=content,
        )

    def _build_document(
        self,
        engagement_id: UUID,
        report_id: UUID,
        created_at: datetime,
    ) -> dict:
        engagement = self._engagement_service.get_engagement(engagement_id)
        if engagement is None:
            raise ValueError("Engagement not found")

        approvals = self._approval_service.list_for_engagement(engagement_id)
        findings = self._finding_service.list_for_engagement(engagement_id)
        agent_runs = (
            self._agent_run_service.list_for_engagement(engagement_id)
            if self._agent_run_service is not None
            else []
        )
        # Collect all agent-pipeline findings across runs, tagged with source run id
        agent_findings: list[dict] = []
        for run in agent_runs:
            full = self._agent_run_service.get(run.id)  # type: ignore[union-attr]
            if full is None:
                continue
            for finding in full.findings:
                agent_findings.append({"agent_run_id": str(run.id), **finding})
        finding_suggestions = self._finding_suggestion_service.list_for_engagement(
            engagement_id
        )
        tool_invocations = self._tool_invocation_service.list_for_engagement(engagement_id)
        tool_executions = self._tool_execution_service.list_for_engagement(engagement_id)
        inventory = self._inventory_service.build_inventory(engagement_id)
        audit_events = self._audit_service.list_for_engagement(engagement_id)
        execution_artifacts = [
            item.content
            for item in (
                self._tool_execution_service.get_document(
                    engagement_id=engagement_id,
                    execution_id=execution.id,
                )
                for execution in tool_executions
            )
            if item is not None
        ]
        parsed_hosts_total = sum(
            len(item.get("parsed", {}).get("hosts", []))
            for item in execution_artifacts
            if isinstance(item.get("parsed"), dict)
        )
        parsed_services_total = sum(
            len(item.get("parsed", {}).get("services", []))
            for item in execution_artifacts
            if isinstance(item.get("parsed"), dict)
        )
        parsed_web_total = sum(
            len(item.get("parsed", {}).get("web", []))
            for item in execution_artifacts
            if isinstance(item.get("parsed"), dict)
        )
        parsed_fingerprints_total = sum(
            len(item.get("parsed", {}).get("fingerprints", []))
            for item in execution_artifacts
            if isinstance(item.get("parsed"), dict)
        )
        parsed_diagnostics_total = sum(
            len(item.get("parsed", {}).get("diagnostics", []))
            for item in execution_artifacts
            if isinstance(item.get("parsed"), dict)
        )

        finding_severity_counts: dict[str, int] = {}
        for finding in findings:
            finding_severity_counts[finding.severity] = (
                finding_severity_counts.get(finding.severity, 0) + 1
            )

        return {
            "report_id": str(report_id),
            "generated_at": created_at.isoformat(),
            "engagement": engagement.model_dump(mode="json"),
            "summary": {
                "findings_total": len(findings),
                "agent_findings_total": len(agent_findings),
                "agent_runs_total": len(agent_runs),
                "suggested_findings_total": len(finding_suggestions),
                "findings_by_severity": finding_severity_counts,
                "approved_actions": len([item for item in approvals if item.approved]),
                "pending_approvals": len([item for item in approvals if not item.approved]),
                "validated_requests": len(tool_invocations),
                "executions_total": len(tool_executions),
                "completed_executions": len(
                    [item for item in tool_executions if item.status == "completed"]
                ),
                "failed_executions": len(
                    [item for item in tool_executions if item.status != "completed"]
                ),
                "parsed_hosts_total": parsed_hosts_total,
                "parsed_services_total": parsed_services_total,
                "parsed_web_total": parsed_web_total,
                "parsed_fingerprints_total": parsed_fingerprints_total,
                "parsed_diagnostics_total": parsed_diagnostics_total,
                "inventory_hosts": len(inventory.hosts),
                "inventory_services": len(inventory.services),
                "audit_events": len(audit_events),
            },
            "findings": [item.model_dump(mode="json") for item in findings],
            "agent_runs": [item.model_dump(mode="json") for item in agent_runs],
            "agent_findings": agent_findings,
            "finding_suggestions": [
                item.model_dump(mode="json") for item in finding_suggestions
            ],
            "approvals": [item.model_dump(mode="json") for item in approvals],
            "tool_invocations": [item.model_dump(mode="json") for item in tool_invocations],
            "tool_executions": [item.model_dump(mode="json") for item in tool_executions],
            "tool_execution_artifacts": execution_artifacts,
            "inventory": inventory.model_dump(mode="json"),
            "audit_events": [
                {
                    "event_type": item.event_type,
                    "engagement_id": str(item.engagement_id),
                    "payload": item.payload,
                    "prev_hash": item.prev_hash,
                    "evidence_hash": item.evidence_hash,
                    "occurred_at": item.occurred_at.isoformat(),
                    "actor": item.actor,
                }
                for item in audit_events
            ],
        }

    def _write_document(
        self,
        *,
        engagement_id: UUID,
        report_id: UUID,
        created_at: datetime,
        document: dict,
    ) -> Path:
        report_dir = self._artifacts_root / "reports" / str(engagement_id)
        report_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{created_at.strftime('%Y%m%dT%H%M%SZ')}-{report_id}.json"
        artifact_path = report_dir / filename
        artifact_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return artifact_path

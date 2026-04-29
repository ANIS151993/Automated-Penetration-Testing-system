from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.tool_executions import ToolExecutionService
from app.schemas.findings import FindingSuggestionRead

ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}


def _parse_uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


@dataclass(slots=True)
class FindingSuggestionService:
    tool_execution_service: ToolExecutionService
    agent_run_service: object | None = None

    def list_for_engagement(self, engagement_id: UUID) -> list[FindingSuggestionRead]:
        suggestions: list[FindingSuggestionRead] = []
        executions = self.tool_execution_service.list_for_engagement(engagement_id)
        for execution in executions:
            artifact = self.tool_execution_service.get_document(
                engagement_id=engagement_id,
                execution_id=execution.id,
            )
            if artifact is None:
                continue
            parsed = artifact.content.get("parsed")
            if not isinstance(parsed, dict):
                continue
            raw_suggestions = parsed.get("suggested_findings")
            if not isinstance(raw_suggestions, list):
                continue
            for index, raw in enumerate(raw_suggestions):
                if not isinstance(raw, dict):
                    continue
                suggestions.append(
                    FindingSuggestionRead(
                        suggestion_id=f"{execution.id}:{index}",
                        execution_id=execution.id,
                        invocation_id=execution.invocation_id,
                        title=str(raw.get("title", "Parser-derived finding")),
                        severity=str(raw.get("severity", "info")),
                        attack_technique=(
                            str(raw["attack_technique"])
                            if raw.get("attack_technique") is not None
                            else None
                        ),
                        summary=str(raw.get("summary", "Execution parser suggestion.")),
                        evidence=[
                            str(item)
                            for item in raw.get("evidence", [])
                            if isinstance(item, str)
                        ],
                        evidence_refs=[execution.invocation_id],
                    )
                )

        if self.agent_run_service is not None:
            runs = self.agent_run_service.list_for_engagement(engagement_id)  # type: ignore[attr-defined]
            for summary in runs:
                if summary.findings_count == 0:
                    continue
                record = self.agent_run_service.get(summary.id)  # type: ignore[attr-defined]
                if record is None:
                    continue
                inv_to_exec: dict[UUID, UUID] = {}
                for r in record.step_results:
                    inv = _parse_uuid(r.get("invocation_id"))
                    exe = _parse_uuid(r.get("execution_id"))
                    if inv is not None and exe is not None:
                        inv_to_exec[inv] = exe
                for index, finding in enumerate(record.findings):
                    if not isinstance(finding, dict):
                        continue
                    refs_raw = finding.get("evidence_refs", [])
                    if not isinstance(refs_raw, list):
                        continue
                    inv_uuids = [
                        u for u in (_parse_uuid(r) for r in refs_raw) if u is not None
                    ]
                    matched_inv = next(
                        (u for u in inv_uuids if u in inv_to_exec), None
                    )
                    if matched_inv is None:
                        continue
                    severity = str(finding.get("severity", "info"))
                    if severity not in ALLOWED_SEVERITIES:
                        severity = "info"
                    technique_raw = finding.get("attack_technique")
                    suggestions.append(
                        FindingSuggestionRead(
                            suggestion_id=f"agent-run:{record.id}:{index}",
                            execution_id=inv_to_exec[matched_inv],
                            invocation_id=matched_inv,
                            title=str(finding.get("title", "Agent finding")),
                            severity=severity,
                            attack_technique=(
                                str(technique_raw) if technique_raw is not None else None
                            ),
                            summary=str(finding.get("summary", "Agent vuln-mapper output.")),
                            evidence=[],
                            evidence_refs=inv_uuids,
                        )
                    )
        return suggestions

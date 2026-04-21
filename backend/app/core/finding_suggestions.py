from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.tool_executions import ToolExecutionService
from app.schemas.findings import FindingSuggestionRead


@dataclass(slots=True)
class FindingSuggestionService:
    tool_execution_service: ToolExecutionService

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
        return suggestions

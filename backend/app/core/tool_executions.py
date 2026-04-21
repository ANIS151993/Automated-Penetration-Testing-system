from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.execution_parsers import enrich_execution_document
from app.models.tool_execution import ToolExecutionModel
from app.schemas.tools import ToolExecutionArtifactRead, ToolExecutionRead, ToolInvocationRead


@dataclass(slots=True)
class ToolExecutionEntity:
    id: UUID
    engagement_id: UUID
    invocation_id: UUID
    tool_name: str
    operation_name: str
    status: str
    exit_code: int | None
    stdout_lines: int
    stderr_lines: int
    artifact_path: str | None
    started_at: datetime
    completed_at: datetime | None

    def to_read_model(self) -> ToolExecutionRead:
        return ToolExecutionRead(
            id=self.id,
            engagement_id=self.engagement_id,
            invocation_id=self.invocation_id,
            tool_name=self.tool_name,
            operation_name=self.operation_name,
            status=self.status,
            exit_code=self.exit_code,
            stdout_lines=self.stdout_lines,
            stderr_lines=self.stderr_lines,
            artifact_path=self.artifact_path,
            started_at=self.started_at,
            completed_at=self.completed_at,
        )


class ToolExecutionRepository(Protocol):
    def list_for_engagement(self, engagement_id: UUID) -> list[ToolExecutionEntity]: ...

    def get(self, execution_id: UUID) -> ToolExecutionEntity | None: ...

    def get_for_engagement(
        self,
        engagement_id: UUID,
        execution_id: UUID,
    ) -> ToolExecutionEntity | None: ...

    def save(self, execution: ToolExecutionEntity) -> ToolExecutionEntity: ...

    def update(self, execution: ToolExecutionEntity) -> ToolExecutionEntity: ...


def _to_entity(model: ToolExecutionModel) -> ToolExecutionEntity:
    return ToolExecutionEntity(
        id=model.id,
        engagement_id=model.engagement_id,
        invocation_id=model.invocation_id,
        tool_name=model.tool_name,
        operation_name=model.operation_name,
        status=model.status,
        exit_code=model.exit_code,
        stdout_lines=model.stdout_lines,
        stderr_lines=model.stderr_lines,
        artifact_path=model.artifact_path,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )


class SqlAlchemyToolExecutionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_engagement(self, engagement_id: UUID) -> list[ToolExecutionEntity]:
        with self._session_factory() as session:
            items = session.scalars(
                select(ToolExecutionModel)
                .where(ToolExecutionModel.engagement_id == engagement_id)
                .order_by(ToolExecutionModel.started_at.desc())
            ).all()
            return [_to_entity(item) for item in items]

    def get(self, execution_id: UUID) -> ToolExecutionEntity | None:
        with self._session_factory() as session:
            item = session.get(ToolExecutionModel, execution_id)
            return _to_entity(item) if item else None

    def get_for_engagement(
        self,
        engagement_id: UUID,
        execution_id: UUID,
    ) -> ToolExecutionEntity | None:
        with self._session_factory() as session:
            item = session.scalar(
                select(ToolExecutionModel).where(
                    ToolExecutionModel.engagement_id == engagement_id,
                    ToolExecutionModel.id == execution_id,
                )
            )
            return _to_entity(item) if item else None

    def save(self, execution: ToolExecutionEntity) -> ToolExecutionEntity:
        with self._session_factory() as session:
            model = ToolExecutionModel(
                id=execution.id,
                engagement_id=execution.engagement_id,
                invocation_id=execution.invocation_id,
                tool_name=execution.tool_name,
                operation_name=execution.operation_name,
                status=execution.status,
                exit_code=execution.exit_code,
                stdout_lines=execution.stdout_lines,
                stderr_lines=execution.stderr_lines,
                artifact_path=execution.artifact_path,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_entity(model)

    def update(self, execution: ToolExecutionEntity) -> ToolExecutionEntity:
        with self._session_factory() as session:
            model = session.get(ToolExecutionModel, execution.id)
            if model is None:
                raise ValueError("Tool execution not found")
            model.status = execution.status
            model.exit_code = execution.exit_code
            model.stdout_lines = execution.stdout_lines
            model.stderr_lines = execution.stderr_lines
            model.artifact_path = execution.artifact_path
            model.started_at = execution.started_at
            model.completed_at = execution.completed_at
            session.commit()
            session.refresh(model)
            return _to_entity(model)


class ToolExecutionService:
    def __init__(
        self,
        repository: ToolExecutionRepository,
        artifacts_root: str,
    ) -> None:
        self._repository = repository
        self._artifacts_root = Path(artifacts_root)

    def start_execution(self, invocation: ToolInvocationRead) -> ToolExecutionRead:
        execution = ToolExecutionEntity(
            id=uuid4(),
            engagement_id=invocation.engagement_id,
            invocation_id=invocation.id,
            tool_name=invocation.tool_name,
            operation_name=invocation.operation_name,
            status="running",
            exit_code=None,
            stdout_lines=0,
            stderr_lines=0,
            artifact_path=None,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
        )
        return self._repository.save(execution).to_read_model()

    def finalize_execution(
        self,
        *,
        execution_id: UUID,
        invocation: ToolInvocationRead,
        events: list[dict[str, Any]],
        status: str,
        exit_code: int | None,
        stdout_lines: int,
        stderr_lines: int,
    ) -> ToolExecutionRead:
        existing = self._repository.get(execution_id)
        if existing is None:
            raise ValueError("Tool execution not found")

        completed_at = datetime.now(timezone.utc)
        artifact_path = self._write_artifact(
            execution=existing,
            invocation=invocation,
            events=events,
            status=status,
            exit_code=exit_code,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            completed_at=completed_at,
        )
        updated = replace(
            existing,
            status=status,
            exit_code=exit_code,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            artifact_path=str(artifact_path),
            completed_at=completed_at,
        )
        return self._repository.update(updated).to_read_model()

    def list_for_engagement(self, engagement_id: UUID) -> list[ToolExecutionRead]:
        return [
            item.to_read_model()
            for item in self._repository.list_for_engagement(engagement_id)
        ]

    def get_for_engagement(
        self,
        *,
        engagement_id: UUID,
        execution_id: UUID,
    ) -> ToolExecutionRead | None:
        execution = self._repository.get_for_engagement(engagement_id, execution_id)
        return execution.to_read_model() if execution is not None else None

    def get_document(
        self,
        *,
        engagement_id: UUID,
        execution_id: UUID,
    ) -> ToolExecutionArtifactRead | None:
        execution = self._repository.get_for_engagement(engagement_id, execution_id)
        if execution is None or execution.artifact_path is None:
            return None
        artifact_path = Path(execution.artifact_path)
        if not artifact_path.is_file():
            return None
        content = json.loads(artifact_path.read_text(encoding="utf-8"))
        content = enrich_execution_document(content)
        return ToolExecutionArtifactRead(
            execution=execution.to_read_model(),
            content=content,
        )

    def _write_artifact(
        self,
        *,
        execution: ToolExecutionEntity,
        invocation: ToolInvocationRead,
        events: list[dict[str, Any]],
        status: str,
        exit_code: int | None,
        stdout_lines: int,
        stderr_lines: int,
        completed_at: datetime,
    ) -> Path:
        artifact_dir = self._artifacts_root / "executions" / str(execution.engagement_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{execution.started_at.strftime('%Y%m%dT%H%M%SZ')}-{execution.id}.json"
        artifact_path = artifact_dir / filename
        document = {
            "execution_id": str(execution.id),
            "engagement_id": str(execution.engagement_id),
            "invocation_id": str(execution.invocation_id),
            "tool_name": execution.tool_name,
            "operation_name": execution.operation_name,
            "status": status,
            "exit_code": exit_code,
            "stdout_lines": stdout_lines,
            "stderr_lines": stderr_lines,
            "started_at": execution.started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "invocation": invocation.model_dump(mode="json"),
            "events": events,
        }
        document = enrich_execution_document(document)
        artifact_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return artifact_path

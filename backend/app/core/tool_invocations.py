from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.tool_executions import ToolExecutionService
from app.models.tool_invocation import ToolInvocationModel
from app.schemas.inventory import InventoryHostRead, InventoryRead, InventoryServiceRead
from app.schemas.tools import ToolInvocationRead


@dataclass(slots=True)
class ToolInvocationEntity:
    id: UUID
    engagement_id: UUID
    tool_name: str
    operation_name: str
    risk_level: str
    args: dict
    command_preview: list[str]
    targets: list[str]
    created_at: datetime

    def to_read_model(self) -> ToolInvocationRead:
        return ToolInvocationRead(
            id=self.id,
            engagement_id=self.engagement_id,
            tool_name=self.tool_name,
            operation_name=self.operation_name,
            risk_level=self.risk_level,
            args=self.args,
            command_preview=self.command_preview,
            targets=self.targets,
            created_at=self.created_at,
        )


class ToolInvocationRepository(Protocol):
    def list_for_engagement(self, engagement_id: UUID) -> list[ToolInvocationEntity]: ...

    def get_for_engagement(
        self,
        engagement_id: UUID,
        invocation_id: UUID,
    ) -> ToolInvocationEntity | None: ...

    def list_for_ids(
        self,
        engagement_id: UUID,
        invocation_ids: list[UUID],
    ) -> list[ToolInvocationEntity]: ...

    def save(self, invocation: ToolInvocationEntity) -> ToolInvocationEntity: ...


def _to_entity(model: ToolInvocationModel) -> ToolInvocationEntity:
    return ToolInvocationEntity(
        id=model.id,
        engagement_id=model.engagement_id,
        tool_name=model.tool_name,
        operation_name=model.operation_name,
        risk_level=model.risk_level,
        args=dict(model.args),
        command_preview=list(model.command_preview),
        targets=list(model.targets),
        created_at=model.created_at,
    )


class SqlAlchemyToolInvocationRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_engagement(self, engagement_id: UUID) -> list[ToolInvocationEntity]:
        with self._session_factory() as session:
            items = session.scalars(
                select(ToolInvocationModel)
                .where(ToolInvocationModel.engagement_id == engagement_id)
                .order_by(ToolInvocationModel.created_at.desc())
            ).all()
            return [_to_entity(item) for item in items]

    def get_for_engagement(
        self,
        engagement_id: UUID,
        invocation_id: UUID,
    ) -> ToolInvocationEntity | None:
        with self._session_factory() as session:
            item = session.scalar(
                select(ToolInvocationModel).where(
                    ToolInvocationModel.engagement_id == engagement_id,
                    ToolInvocationModel.id == invocation_id,
                )
            )
            return _to_entity(item) if item else None

    def list_for_ids(
        self,
        engagement_id: UUID,
        invocation_ids: list[UUID],
    ) -> list[ToolInvocationEntity]:
        if not invocation_ids:
            return []
        with self._session_factory() as session:
            items = session.scalars(
                select(ToolInvocationModel)
                .where(ToolInvocationModel.engagement_id == engagement_id)
                .where(ToolInvocationModel.id.in_(invocation_ids))
            ).all()
            return [_to_entity(item) for item in items]

    def save(self, invocation: ToolInvocationEntity) -> ToolInvocationEntity:
        with self._session_factory() as session:
            model = ToolInvocationModel(
                id=invocation.id,
                engagement_id=invocation.engagement_id,
                tool_name=invocation.tool_name,
                operation_name=invocation.operation_name,
                risk_level=invocation.risk_level,
                args=invocation.args,
                command_preview=invocation.command_preview,
                targets=invocation.targets,
                created_at=invocation.created_at,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_entity(model)


class ToolInvocationService:
    def __init__(self, repository: ToolInvocationRepository) -> None:
        self._repository = repository

    def record_validation(
        self,
        *,
        engagement_id: UUID,
        tool_name: str,
        operation_name: str,
        risk_level: str,
        args: dict,
        command_preview: list[str],
        targets: list[str],
    ) -> ToolInvocationRead:
        invocation = ToolInvocationEntity(
            id=uuid4(),
            engagement_id=engagement_id,
            tool_name=tool_name,
            operation_name=operation_name,
            risk_level=risk_level,
            args=args,
            command_preview=command_preview,
            targets=targets,
            created_at=datetime.now(timezone.utc),
        )
        return self._repository.save(invocation).to_read_model()

    def list_for_engagement(self, engagement_id: UUID) -> list[ToolInvocationRead]:
        return [
            item.to_read_model()
            for item in self._repository.list_for_engagement(engagement_id)
        ]

    def get_for_engagement(
        self,
        engagement_id: UUID,
        invocation_id: UUID,
    ) -> ToolInvocationRead | None:
        item = self._repository.get_for_engagement(engagement_id, invocation_id)
        return item.to_read_model() if item else None

    def require_for_engagement(
        self,
        engagement_id: UUID,
        invocation_ids: list[UUID],
    ) -> list[ToolInvocationRead]:
        unique_ids = list(dict.fromkeys(invocation_ids))
        records = [
            item.to_read_model()
            for item in self._repository.list_for_ids(engagement_id, unique_ids)
        ]
        if len(records) != len(unique_ids):
            raise ValueError(
                "One or more evidence references do not belong to the selected engagement"
            )
        return records


class InventoryService:
    def __init__(
        self,
        tool_invocation_service: ToolInvocationService,
        tool_execution_service: ToolExecutionService | None = None,
    ) -> None:
        self._tool_invocation_service = tool_invocation_service
        self._tool_execution_service = tool_execution_service

    def build_inventory(self, engagement_id: UUID) -> InventoryRead:
        invocations = self._tool_invocation_service.list_for_engagement(engagement_id)
        host_index: dict[str, dict[str, object]] = {}
        service_index: dict[tuple[str, int, str], dict[str, object]] = {}

        if self._tool_execution_service is not None:
            for execution in self._tool_execution_service.list_for_engagement(engagement_id):
                artifact = self._tool_execution_service.get_document(
                    engagement_id=engagement_id,
                    execution_id=execution.id,
                )
                if artifact is None:
                    continue
                parsed = artifact.content.get("parsed")
                if not isinstance(parsed, dict):
                    continue
                for host in parsed.get("hosts", []):
                    if not isinstance(host, dict):
                        continue
                    target = _normalize_target(str(host.get("target", "")))
                    if not target:
                        continue
                    operation = str(host.get("operation", "unknown"))
                    last_observed_at = _coerce_datetime(
                        host.get("last_observed_at"),
                        fallback=execution.completed_at or execution.started_at,
                    )
                    host_entry = host_index.setdefault(
                        target,
                        {
                            "target": target,
                            "operations": set(),
                            "last_validated_at": last_observed_at,
                            "os_guess": None,
                        },
                    )
                    host_entry["operations"].add(operation)
                    if last_observed_at > host_entry["last_validated_at"]:
                        host_entry["last_validated_at"] = last_observed_at
                    os_guess = host.get("os_guess")
                    if isinstance(os_guess, str) and os_guess:
                        host_entry["os_guess"] = os_guess

                for service in parsed.get("services", []):
                    if not isinstance(service, dict):
                        continue
                    target = _normalize_target(str(service.get("target", "")))
                    port = service.get("port")
                    protocol = str(service.get("protocol", "tcp"))
                    if not target or not isinstance(port, int):
                        continue
                    last_observed_at = _coerce_datetime(
                        service.get("last_observed_at"),
                        fallback=execution.completed_at or execution.started_at,
                    )
                    key = (target, port, protocol)
                    service_entry = service_index.setdefault(
                        key,
                        {
                            "target": target,
                            "port": port,
                            "protocol": protocol,
                            "operations": set(),
                            "last_validated_at": last_observed_at,
                            "service_name": None,
                            "details": None,
                        },
                    )
                    service_entry["operations"].add(str(service.get("operation", "unknown")))
                    if last_observed_at > service_entry["last_validated_at"]:
                        service_entry["last_validated_at"] = last_observed_at
                    service_name = service.get("service_name")
                    if isinstance(service_name, str) and service_name:
                        service_entry["service_name"] = service_name
                    details = service.get("details")
                    if isinstance(details, str) and details:
                        service_entry["details"] = details

        for invocation in invocations:
            operation_label = f"{invocation.tool_name}.{invocation.operation_name}"
            invocation_observed_at = _coerce_datetime(
                invocation.created_at,
                fallback=invocation.created_at,
            )
            ports = _parse_ports(invocation.args.get("ports"))
            for raw_target in invocation.targets:
                target = _normalize_target(raw_target)
                host = host_index.setdefault(
                    target,
                    {
                        "target": target,
                        "operations": set(),
                        "last_validated_at": invocation_observed_at,
                        "os_guess": None,
                    },
                )
                host["operations"].add(operation_label)
                if invocation_observed_at > host["last_validated_at"]:
                    host["last_validated_at"] = invocation_observed_at

                for port in ports:
                    key = (target, port, "tcp")
                    service = service_index.setdefault(
                        key,
                        {
                            "target": target,
                            "port": port,
                            "protocol": "tcp",
                            "operations": set(),
                            "last_validated_at": invocation_observed_at,
                            "service_name": None,
                            "details": None,
                        },
                    )
                    service["operations"].add(operation_label)
                    if invocation_observed_at > service["last_validated_at"]:
                        service["last_validated_at"] = invocation_observed_at

        hosts = [
            InventoryHostRead(
                target=item["target"],
                operations=sorted(item["operations"]),
                last_validated_at=item["last_validated_at"],
                os_guess=item["os_guess"],
            )
            for item in sorted(host_index.values(), key=lambda row: row["target"])
        ]
        services = [
            InventoryServiceRead(
                target=item["target"],
                port=item["port"],
                protocol=item["protocol"],
                operations=sorted(item["operations"]),
                last_validated_at=item["last_validated_at"],
                service_name=item["service_name"],
                details=item["details"],
            )
            for item in sorted(
                service_index.values(),
                key=lambda row: (row["target"], row["port"], row["protocol"]),
            )
        ]
        return InventoryRead(hosts=hosts, services=services)


def format_invocation_evidence(invocation: ToolInvocationRead) -> str:
    targets = ", ".join(invocation.targets) if invocation.targets else "no targets"
    return (
        f"{invocation.tool_name}.{invocation.operation_name} "
        f"[{invocation.risk_level}] {targets} :: "
        f"{' '.join(invocation.command_preview)}"
    )


def _normalize_target(target: str) -> str:
    if "://" not in target:
        return target
    parsed = urlparse(target)
    return parsed.hostname or target


def _coerce_datetime(value: object, *, fallback: datetime) -> datetime:
    if fallback.tzinfo is None:
        fallback = fallback.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return fallback
    return fallback


def _parse_ports(value: object) -> list[int]:
    if not isinstance(value, str):
        return []

    ports: set[int] = set()
    for chunk in value.split(","):
        token = chunk.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                continue
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            for port in range(start, min(end, 65535) + 1):
                if 1 <= port <= 65535:
                    ports.add(port)
            continue
        if token.isdigit():
            port = int(token)
            if 1 <= port <= 65535:
                ports.add(port)
    return sorted(ports)

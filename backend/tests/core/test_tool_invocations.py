from datetime import datetime, timezone
from uuid import uuid4

from app.core.tool_executions import ToolExecutionEntity, ToolExecutionService
from app.core.tool_invocations import (
    InventoryService,
    ToolInvocationEntity,
    ToolInvocationService,
    format_invocation_evidence,
)


class InMemoryToolInvocationRepository:
    def __init__(self) -> None:
        self.items: list[ToolInvocationEntity] = []

    def list_for_engagement(self, engagement_id):
        return [
            item for item in self.items if item.engagement_id == engagement_id
        ]

    def list_for_ids(self, engagement_id, invocation_ids):
        wanted = set(invocation_ids)
        return [
            item
            for item in self.items
            if item.engagement_id == engagement_id and item.id in wanted
        ]

    def save(self, invocation):
        self.items.append(invocation)
        return invocation

    def get_for_engagement(self, engagement_id, invocation_id):
        for item in self.items:
            if item.engagement_id == engagement_id and item.id == invocation_id:
                return item
        return None


class InMemoryToolExecutionRepository:
    def __init__(self) -> None:
        self.items: list[ToolExecutionEntity] = []

    def list_for_engagement(self, engagement_id):
        return [item for item in self.items if item.engagement_id == engagement_id]

    def get(self, execution_id):
        for item in self.items:
            if item.id == execution_id:
                return item
        return None

    def get_for_engagement(self, engagement_id, execution_id):
        for item in self.items:
            if item.engagement_id == engagement_id and item.id == execution_id:
                return item
        return None

    def save(self, execution):
        self.items.append(execution)
        return execution

    def update(self, execution):
        for index, item in enumerate(self.items):
            if item.id == execution.id:
                self.items[index] = execution
                return execution
        raise ValueError("Tool execution not found")


def test_inventory_is_derived_from_validated_tool_invocations() -> None:
    repository = InMemoryToolInvocationRepository()
    service = ToolInvocationService(repository)
    inventory_service = InventoryService(service)
    engagement_id = uuid4()

    first = service.record_validation(
        engagement_id=engagement_id,
        tool_name="nmap",
        operation_name="service_scan",
        risk_level="low",
        args={"target": "172.20.32.59", "ports": "22,80-81"},
        command_preview=["nmap", "-Pn", "-sV", "-p", "22,80-81", "172.20.32.59"],
        targets=["172.20.32.59"],
    )
    repository.items[0].created_at = datetime(2026, 4, 20, tzinfo=timezone.utc)

    second = service.record_validation(
        engagement_id=engagement_id,
        tool_name="http_probe",
        operation_name="fetch_headers",
        risk_level="low",
        args={"url": "http://172.20.32.59"},
        command_preview=["curl", "-I", "http://172.20.32.59"],
        targets=["http://172.20.32.59"],
    )
    repository.items[1].created_at = datetime(2026, 4, 20, 0, 5, tzinfo=timezone.utc)

    inventory = inventory_service.build_inventory(engagement_id)

    assert [item.target for item in inventory.hosts] == ["172.20.32.59"]
    assert inventory.hosts[0].operations == [
        "http_probe.fetch_headers",
        "nmap.service_scan",
    ]
    assert [item.port for item in inventory.services] == [22, 80, 81]
    assert first.id != second.id


def test_require_for_engagement_and_format_evidence() -> None:
    repository = InMemoryToolInvocationRepository()
    service = ToolInvocationService(repository)
    engagement_id = uuid4()
    other_engagement_id = uuid4()

    invocation = service.record_validation(
        engagement_id=engagement_id,
        tool_name="nmap",
        operation_name="service_scan",
        risk_level="low",
        args={"target": "172.20.32.59", "ports": "22"},
        command_preview=["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
        targets=["172.20.32.59"],
    )
    service.record_validation(
        engagement_id=other_engagement_id,
        tool_name="nmap",
        operation_name="service_scan",
        risk_level="low",
        args={"target": "172.20.32.60", "ports": "22"},
        command_preview=["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.60"],
        targets=["172.20.32.60"],
    )

    resolved = service.require_for_engagement(engagement_id, [invocation.id])

    assert resolved[0].id == invocation.id
    assert "nmap.service_scan" in format_invocation_evidence(resolved[0])


def test_inventory_uses_parsed_execution_artifacts_when_present(tmp_path) -> None:
    invocation_repository = InMemoryToolInvocationRepository()
    invocation_service = ToolInvocationService(invocation_repository)
    execution_repository = InMemoryToolExecutionRepository()
    execution_service = ToolExecutionService(
        execution_repository,
        artifacts_root=str(tmp_path),
    )
    inventory_service = InventoryService(
        invocation_service,
        tool_execution_service=execution_service,
    )
    engagement_id = uuid4()

    invocation = invocation_service.record_validation(
        engagement_id=engagement_id,
        tool_name="nmap",
        operation_name="service_scan",
        risk_level="low",
        args={"target": "172.20.32.59", "ports": "22"},
        command_preview=["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
        targets=["172.20.32.59"],
    )
    execution = execution_service.start_execution(invocation)
    execution_service.finalize_execution(
        execution_id=execution.id,
        invocation=invocation,
        events=[
            {"type": "stdout", "line": "22/tcp open ssh OpenSSH 9.6p1 Ubuntu"},
            {"type": "completed", "status": "completed"},
        ],
        status="completed",
        exit_code=0,
        stdout_lines=1,
        stderr_lines=0,
    )

    inventory = inventory_service.build_inventory(engagement_id)

    assert inventory.hosts[0].target == "172.20.32.59"
    assert inventory.services[0].port == 22
    assert inventory.services[0].service_name == "ssh"
    assert "OpenSSH 9.6p1 Ubuntu" in (inventory.services[0].details or "")

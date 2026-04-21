from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator
from uuid import UUID, uuid4

import pytest

from app.agents.executors.gateway import GatewayExecutor
from app.agents.state import Phase, PlannedStep
from app.schemas.tools import ToolInvocationRequest, ToolInvocationResponse


@dataclass
class _FakeGateway:
    invocation_id: UUID
    events: list[dict]
    last_request: ToolInvocationRequest | None = None

    def validate_tool_invocation(
        self, *, engagement_id: UUID, payload: ToolInvocationRequest
    ) -> ToolInvocationResponse:
        self.last_request = payload
        return ToolInvocationResponse(
            invocation_id=self.invocation_id,
            status="validated",
            tool=payload.tool_name,
            operation=payload.operation_name,
            risk_level="low",
            command_preview=["nmap", "-sV", "172.20.32.59"],
            targets=["172.20.32.59"],
        )

    def stream_tool_execution(
        self, *, engagement_id: UUID, invocation_id: UUID
    ) -> Iterator[bytes]:
        for event in self.events:
            yield (json.dumps(event) + "\n").encode("utf-8")


@pytest.mark.asyncio
async def test_gateway_executor_assembles_stdout_and_terminal_status():
    execution_id = uuid4()
    invocation_id = uuid4()
    gateway = _FakeGateway(
        invocation_id=invocation_id,
        events=[
            {"type": "started", "execution_id": str(execution_id)},
            {"type": "stdout", "line": "22/tcp open ssh"},
            {"type": "stdout", "line": "80/tcp closed http"},
            {"type": "stderr", "line": "warning: partial result"},
            {"type": "completed", "status": "completed", "exit_code": 0},
        ],
    )

    executor = GatewayExecutor(service=gateway, engagement_id=uuid4())
    step = PlannedStep(
        tool_name="nmap",
        operation_name="service_scan",
        args={"target": "172.20.32.59", "ports": "22,80"},
        reason="recon",
        phase=Phase.RECONNAISSANCE,
    )

    result = await executor(step)

    assert result.status == "completed"
    assert result.exit_code == 0
    assert "22/tcp open ssh" in result.stdout
    assert "80/tcp closed http" in result.stdout
    assert "warning: partial result" in result.stderr
    assert result.invocation_id == str(invocation_id)
    assert result.execution_id == str(execution_id)
    assert gateway.last_request is not None
    assert gateway.last_request.tool_name == "nmap"


@pytest.mark.asyncio
async def test_gateway_executor_reports_failed_terminal_event():
    gateway = _FakeGateway(
        invocation_id=uuid4(),
        events=[
            {"type": "started", "execution_id": str(uuid4())},
            {"type": "stderr", "line": "nmap: permission denied"},
            {"type": "failed", "status": "failed", "exit_code": 1},
        ],
    )
    executor = GatewayExecutor(service=gateway, engagement_id=uuid4())
    step = PlannedStep(
        tool_name="nmap",
        operation_name="service_scan",
        args={"target": "172.20.32.59"},
        reason="recon",
        phase=Phase.RECONNAISSANCE,
    )

    result = await executor(step)

    assert result.status == "failed"
    assert result.exit_code == 1
    assert "permission denied" in result.stderr
    assert result.stdout == ""

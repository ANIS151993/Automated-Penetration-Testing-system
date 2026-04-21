from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.agents.nodes.tool_caller import ExecutorResult
from app.agents.state import PlannedStep
from app.schemas.tools import ToolInvocationRequest


class _GatewayService(Protocol):
    def validate_tool_invocation(
        self, *, engagement_id: UUID, payload: ToolInvocationRequest
    ): ...

    def stream_tool_execution(self, *, engagement_id: UUID, invocation_id: UUID): ...


@dataclass(slots=True)
class GatewayExecutor:
    """Async adapter from agent PlannedStep to the sync GatewayValidationService.

    The underlying service is synchronous; we offload both the validate call and
    the NDJSON stream consumption to a worker thread so the agent event loop is
    not blocked.
    """

    service: _GatewayService
    engagement_id: UUID

    async def __call__(self, step: PlannedStep) -> ExecutorResult:
        return await asyncio.to_thread(self._run_sync, step)

    def _run_sync(self, step: PlannedStep) -> ExecutorResult:
        invocation = self.service.validate_tool_invocation(
            engagement_id=self.engagement_id,
            payload=ToolInvocationRequest(
                tool_name=step.tool_name,
                operation_name=step.operation_name,
                args=dict(step.args),
            ),
        )
        if invocation.invocation_id is None:
            return ExecutorResult(
                status="failed",
                exit_code=None,
                stdout="",
                stderr="",
                error="gateway did not return an invocation id",
            )

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        terminal: dict | None = None
        execution_id: str | None = None

        stream = self.service.stream_tool_execution(
            engagement_id=self.engagement_id,
            invocation_id=invocation.invocation_id,
        )
        for chunk in stream:
            for line in chunk.splitlines():
                if not line:
                    continue
                event = json.loads(line)
                etype = event.get("type")
                if etype == "started" and event.get("execution_id"):
                    execution_id = str(event["execution_id"])
                elif etype == "stdout":
                    stdout_parts.append(str(event.get("line", "")))
                elif etype == "stderr":
                    stderr_parts.append(str(event.get("line", "")))
                elif etype in {"completed", "failed", "cancelled", "timed_out"}:
                    terminal = event

        status = str(terminal.get("status")) if terminal else "unknown"
        exit_code_raw = terminal.get("exit_code") if terminal else None
        exit_code = int(exit_code_raw) if isinstance(exit_code_raw, int) else None

        return ExecutorResult(
            status=status,
            exit_code=exit_code,
            stdout="\n".join(stdout_parts),
            stderr="\n".join(stderr_parts),
            invocation_id=str(invocation.invocation_id),
            execution_id=execution_id,
        )

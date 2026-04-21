from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
from typing import Iterator
from uuid import UUID

import httpx

from app.core.approvals import ApprovalService
from app.core.audit_service import AuditService
from app.core.config import Settings
from app.core.engagements import EngagementService
from app.core.gateway_tokens import issue_gateway_token
from app.core.scope import ScopeViolation, extract_targets_from_command, validate_target_in_scope
from app.core.tool_executions import ToolExecutionService
from app.core.tool_policies import get_tool_policy
from app.core.tool_invocations import ToolInvocationService
from app.schemas.tools import (
    ToolExecutionCancelResponse,
    ToolInvocationRequest,
    ToolInvocationResponse,
)


class ToolValidationError(Exception):
    """Raised when the backend cannot validate or forward a tool invocation."""


@dataclass(slots=True)
class GatewayValidationService:
    settings: Settings
    engagement_service: EngagementService
    approval_service: ApprovalService
    audit_service: AuditService | None = None
    tool_invocation_service: ToolInvocationService | None = None
    tool_execution_service: ToolExecutionService | None = None
    http_client: httpx.Client | None = None

    def validate_tool_invocation(
        self,
        *,
        engagement_id: UUID,
        payload: ToolInvocationRequest,
    ) -> ToolInvocationResponse:
        engagement = self.engagement_service.get_engagement(engagement_id)
        if engagement is None:
            raise ToolValidationError("Engagement not found")

        try:
            policy = get_tool_policy(payload.tool_name, payload.operation_name)
            targets = extract_targets_from_command(payload.tool_name, payload.args)
            for target in targets:
                validate_target_in_scope(target, engagement.scope_cidrs)
        except (KeyError, ScopeViolation) as exc:
            raise ToolValidationError(str(exc)) from exc

        if policy.requires_approval:
            approval = self.approval_service.ensure_matching_approval(
                engagement_id=engagement_id,
                tool_name=payload.tool_name,
                operation_name=payload.operation_name,
                args=payload.args,
            )
            if approval is None:
                raise ToolValidationError(
                    "Approved authorization is required for this high-risk action"
                )

        token = issue_gateway_token(
            subject=self.settings.operator_name,
            audience=self.settings.gateway_audience,
            secret=self.settings.gateway_jwt_secret,
        )

        try:
            response = self._client().post(
                self._gateway_validate_url(),
                json={
                    "token": token,
                    "scope_cidrs": engagement.scope_cidrs,
                    "tool_name": payload.tool_name,
                    "operation_name": payload.operation_name,
                    "args": payload.args,
                },
            )
        except httpx.HTTPError as exc:
            raise ToolValidationError("Gateway request failed") from exc
        if response.status_code >= 400:
            detail = response.json().get("error", "Gateway validation failed")
            raise ToolValidationError(detail)

        gateway_payload = response.json()
        invocation = None
        if self.tool_invocation_service is not None:
            invocation = self.tool_invocation_service.record_validation(
                engagement_id=engagement_id,
                tool_name=gateway_payload["tool"],
                operation_name=gateway_payload["operation"],
                risk_level=policy.risk_level,
                args=payload.args,
                command_preview=gateway_payload["command_preview"],
                targets=gateway_payload["targets"],
            )
        result = ToolInvocationResponse(
            invocation_id=invocation.id if invocation is not None else None,
            status=gateway_payload["status"],
            tool=gateway_payload["tool"],
            operation=gateway_payload["operation"],
            risk_level=policy.risk_level,
            command_preview=gateway_payload["command_preview"],
            targets=gateway_payload["targets"],
        )
        if self.audit_service is not None:
            audit_payload = {
                "tool_name": result.tool,
                "operation_name": result.operation,
                "risk_level": result.risk_level,
                "targets": result.targets,
                "command_preview": result.command_preview,
            }
            if invocation is not None:
                audit_payload["invocation_id"] = str(invocation.id)
            self.audit_service.record_event(
                engagement_id=engagement_id,
                event_type="tool_validation_succeeded",
                payload=audit_payload,
                actor=self.settings.operator_name,
            )
        return result

    def stream_tool_execution(
        self,
        *,
        engagement_id: UUID,
        invocation_id: UUID,
    ) -> Iterator[bytes]:
        engagement = self.engagement_service.get_engagement(engagement_id)
        if engagement is None:
            raise ToolValidationError("Engagement not found")
        if self.tool_invocation_service is None:
            raise ToolValidationError("Tool execution is not available")

        invocation = self.tool_invocation_service.get_for_engagement(
            engagement_id,
            invocation_id,
        )
        if invocation is None:
            raise ToolValidationError("Validated invocation not found")
        if self.tool_execution_service is None:
            raise ToolValidationError("Tool execution storage is not available")

        token = issue_gateway_token(
            subject=self.settings.operator_name,
            audience=self.settings.gateway_audience,
            secret=self.settings.gateway_jwt_secret,
        )
        execution = self.tool_execution_service.start_execution(invocation)

        if self.audit_service is not None:
            self.audit_service.record_event(
                engagement_id=engagement_id,
                event_type="tool_execution_started",
                payload={
                    "execution_id": str(execution.id),
                    "invocation_id": str(invocation.id),
                    "tool_name": invocation.tool_name,
                    "operation_name": invocation.operation_name,
                    "targets": invocation.targets,
                },
                actor=self.settings.operator_name,
            )

        try:
            with self._client().stream(
                "POST",
                self._gateway_execute_url(),
                json={
                    "token": token,
                    "execution_id": str(execution.id),
                    "scope_cidrs": engagement.scope_cidrs,
                    "tool_name": invocation.tool_name,
                    "operation_name": invocation.operation_name,
                    "args": invocation.args,
                },
            ) as response:
                if response.status_code >= 400:
                    detail = self._error_detail(response)
                    raise ToolValidationError(detail)

                events: list[dict] = []
                stdout_lines = 0
                stderr_lines = 0
                terminal_event: dict | None = None

                for line in response.iter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    events.append(event)
                    if event.get("type") == "stdout":
                        stdout_lines += 1
                    elif event.get("type") == "stderr":
                        stderr_lines += 1
                    if event.get("type") in {"completed", "failed", "cancelled", "timed_out"}:
                        terminal_event = event
                    yield (json.dumps(event) + "\n").encode("utf-8")

                final_status = (
                    str(terminal_event.get("status"))
                    if terminal_event is not None and terminal_event.get("status") is not None
                    else "unknown"
                )
                exit_code = (
                    int(terminal_event["exit_code"])
                    if terminal_event is not None
                    and terminal_event.get("exit_code") is not None
                    else None
                )
                stored_execution = self.tool_execution_service.finalize_execution(
                    execution_id=execution.id,
                    invocation=invocation,
                    events=events,
                    status=final_status,
                    exit_code=exit_code,
                    stdout_lines=stdout_lines,
                    stderr_lines=stderr_lines,
                )
                if self.audit_service is not None:
                    self.audit_service.record_event(
                        engagement_id=engagement_id,
                        event_type=self._audit_event_for_execution_status(
                            stored_execution.status
                        ),
                        payload={
                            "execution_id": str(stored_execution.id),
                            "invocation_id": str(invocation.id),
                            "tool_name": invocation.tool_name,
                            "operation_name": invocation.operation_name,
                            "status": stored_execution.status,
                            "exit_code": stored_execution.exit_code,
                            "stdout_lines": stdout_lines,
                            "stderr_lines": stderr_lines,
                            "artifact_path": stored_execution.artifact_path,
                        },
                        actor=self.settings.operator_name,
                    )
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            stored_execution = self.tool_execution_service.finalize_execution(
                execution_id=execution.id,
                invocation=invocation,
                events=[
                    {
                        "type": "failed",
                        "status": "failed",
                        "error": str(exc),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ],
                status="failed",
                exit_code=None,
                stdout_lines=0,
                stderr_lines=1,
            )
            if self.audit_service is not None:
                self.audit_service.record_event(
                    engagement_id=engagement_id,
                    event_type="tool_execution_failed",
                    payload={
                        "execution_id": str(stored_execution.id),
                        "invocation_id": str(invocation.id),
                        "tool_name": invocation.tool_name,
                        "operation_name": invocation.operation_name,
                        "error": str(exc),
                        "artifact_path": stored_execution.artifact_path,
                    },
                    actor=self.settings.operator_name,
                )
            raise ToolValidationError("Gateway execution request failed") from exc

    def cancel_tool_execution(
        self,
        *,
        engagement_id: UUID,
        execution_id: UUID,
    ) -> ToolExecutionCancelResponse:
        engagement = self.engagement_service.get_engagement(engagement_id)
        if engagement is None:
            raise ToolValidationError("Engagement not found")
        if self.tool_execution_service is None:
            raise ToolValidationError("Tool execution storage is not available")

        execution = self.tool_execution_service.get_for_engagement(
            engagement_id=engagement_id,
            execution_id=execution_id,
        )
        if execution is None:
            raise ToolValidationError("Tool execution not found")
        if execution.status != "running":
            raise ToolValidationError("Tool execution is not running")

        token = issue_gateway_token(
            subject=self.settings.operator_name,
            audience=self.settings.gateway_audience,
            secret=self.settings.gateway_jwt_secret,
        )
        try:
            response = self._client().post(
                self._gateway_cancel_url(),
                json={
                    "token": token,
                    "execution_id": str(execution_id),
                },
            )
        except httpx.HTTPError as exc:
            raise ToolValidationError("Gateway cancellation request failed") from exc
        if response.status_code == 404:
            raise ToolValidationError("Active execution not found on gateway")
        if response.status_code >= 400:
            detail = self._error_detail(response)
            raise ToolValidationError(detail)

        if self.audit_service is not None:
            self.audit_service.record_event(
                engagement_id=engagement_id,
                event_type="tool_execution_cancel_requested",
                payload={
                    "execution_id": str(execution.id),
                    "invocation_id": str(execution.invocation_id),
                    "tool_name": execution.tool_name,
                    "operation_name": execution.operation_name,
                },
                actor=self.settings.operator_name,
            )

        response_payload = response.json()
        return ToolExecutionCancelResponse(
            execution_id=execution.id,
            status=response_payload.get("status", "cancellation_requested"),
            detail=response_payload.get(
                "detail",
                "Cancellation requested from the weapon node.",
            ),
        )

    def _gateway_validate_url(self) -> str:
        base_url = self.settings.weapon_node_url.rstrip("/")
        return f"{base_url}/api/v1/validate-invocation"

    def _gateway_execute_url(self) -> str:
        base_url = self.settings.weapon_node_url.rstrip("/")
        return f"{base_url}/api/v1/execute-invocation"

    def _gateway_cancel_url(self) -> str:
        base_url = self.settings.weapon_node_url.rstrip("/")
        return f"{base_url}/api/v1/cancel-execution"

    def _client(self) -> httpx.Client:
        timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)
        if self.http_client is not None:
            return self.http_client

        if self.settings.weapon_node_url.startswith("https://"):
            self._assert_tls_material_exists()
            tls_context = ssl.create_default_context(
                cafile=self.settings.gateway_ca_cert_path
            )
            tls_context.load_cert_chain(
                certfile=self.settings.gateway_client_cert_path,
                keyfile=self.settings.gateway_client_key_path,
            )
            return httpx.Client(timeout=timeout, verify=tls_context)

        return httpx.Client(timeout=timeout, verify=False)

    def _assert_tls_material_exists(self) -> None:
        paths = [
            self.settings.gateway_ca_cert_path,
            self.settings.gateway_client_cert_path,
            self.settings.gateway_client_key_path,
        ]
        missing = [path for path in paths if not Path(path).exists()]
        if missing:
            raise ToolValidationError(
                f"Missing gateway TLS material: {', '.join(missing)}"
            )

    def _error_detail(self, response: httpx.Response) -> str:
        try:
            return response.json().get("error", "Gateway request failed")
        except ValueError:
            return "Gateway request failed"

    def _audit_event_for_execution_status(self, status: str) -> str:
        if status == "cancelled":
            return "tool_execution_cancelled"
        if status == "timed_out":
            return "tool_execution_timed_out"
        if status == "completed":
            return "tool_execution_completed"
        return "tool_execution_failed"

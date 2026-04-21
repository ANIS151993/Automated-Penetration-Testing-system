from uuid import UUID

import httpx
import pytest

from app.core.approvals import ApprovalService
from app.core.config import Settings
from app.core.engagements import EngagementService, InMemoryEngagementRepository
from app.core.gateway_validation import GatewayValidationService, ToolValidationError
from app.schemas.engagements import EngagementCreate
from app.schemas.tools import ToolInvocationRequest


class NullApprovalRepository:
    def list_for_engagement(self, engagement_id: UUID):
        return []

    def get_approval(self, approval_id: UUID):
        return None

    def save(self, approval):
        return approval

    def find_matching_approved(
        self,
        *,
        engagement_id: UUID,
        tool_name: str,
        operation_name: str,
        args: dict,
    ):
        return None


class RecordingAuditService:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_event(
        self,
        *,
        engagement_id: UUID,
        event_type: str,
        payload: dict,
        actor: str | None = None,
    ) -> None:
        self.events.append(
            {
                "engagement_id": engagement_id,
                "event_type": event_type,
                "payload": payload,
                "actor": actor,
            }
        )


def build_validation_service(
    *,
    settings: Settings,
    http_client: httpx.Client | None = None,
    audit_service: RecordingAuditService | None = None,
) -> tuple[GatewayValidationService, UUID]:
    engagement_service = EngagementService(InMemoryEngagementRepository())
    engagement = engagement_service.create_engagement(
        EngagementCreate(
            name="Validation",
            description="Gateway validation tests",
            scope_cidrs=["172.20.32.59/32"],
            authorization_confirmed=True,
            authorizer_name="Lab Owner",
            operator_name="Analyst One",
        )
    )
    approval_service = ApprovalService(NullApprovalRepository())
    service = GatewayValidationService(
        settings=settings,
        engagement_service=engagement_service,
        approval_service=approval_service,
        audit_service=audit_service,
        http_client=http_client,
    )
    return service, engagement.id


def test_gateway_validation_requires_tls_material_for_https(tmp_path) -> None:
    settings = Settings(
        weapon_node_url="https://172.20.32.68:5000",
        gateway_ca_cert_path=str(tmp_path / "missing-ca.pem"),
        gateway_client_cert_path=str(tmp_path / "missing-client-cert.pem"),
        gateway_client_key_path=str(tmp_path / "missing-client-key.pem"),
    )
    service, engagement_id = build_validation_service(settings=settings)

    with pytest.raises(ToolValidationError, match="Missing gateway TLS material"):
        service.validate_tool_invocation(
            engagement_id=engagement_id,
            payload=ToolInvocationRequest(
                tool_name="nmap",
                operation_name="service_scan",
                args={"target": "172.20.32.59", "ports": "22"},
            ),
        )


def test_gateway_validation_records_audit_event_on_success() -> None:
    audit_service = RecordingAuditService()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "validated",
                "tool": "nmap",
                "operation": "service_scan",
                "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
                "targets": ["172.20.32.59"],
            },
        )

    service, engagement_id = build_validation_service(
        settings=Settings(weapon_node_url="http://weapon-node.local:5000"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        audit_service=audit_service,
    )

    result = service.validate_tool_invocation(
        engagement_id=engagement_id,
        payload=ToolInvocationRequest(
            tool_name="nmap",
            operation_name="service_scan",
            args={"target": "172.20.32.59", "ports": "22"},
        ),
    )

    assert result.status == "validated"
    assert audit_service.events == [
        {
            "engagement_id": engagement_id,
            "event_type": "tool_validation_succeeded",
            "payload": {
                "tool_name": "nmap",
                "operation_name": "service_scan",
                "risk_level": "low",
                "targets": ["172.20.32.59"],
                "command_preview": ["nmap", "-Pn", "-sV", "-p", "22", "172.20.32.59"],
            },
            "actor": "lab-operator",
        }
    ]

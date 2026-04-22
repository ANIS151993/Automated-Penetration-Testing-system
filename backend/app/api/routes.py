import json
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse

from app.core.ws_tickets import TicketError, TicketScope, WSTicketStore
from app.websocket.execution_bus import ExecutionBus

from app.core.approvals import ApprovalService
from app.core.audit_service import AuditService
from app.core.config import get_settings
from app.core.database import check_database_health
from app.core.engagements import EngagementService
from app.core.findings import FindingService
from app.core.finding_suggestions import FindingSuggestionService
from app.core.gateway_validation import GatewayValidationService, ToolValidationError
from app.core.reports import ReportService
from app.core.tool_executions import ToolExecutionService
from app.core.tool_invocations import InventoryService, ToolInvocationService
from app.schemas.audit_events import AuditEventRead
from app.core.tool_policies import get_tool_policy
from app.schemas.approvals import ApprovalCreate, ApprovalDecision, ApprovalRead
from app.schemas.engagements import (
    EngagementCreate,
    EngagementRead,
    EngagementStatusUpdate,
    HealthResponse,
)
from app.schemas.findings import FindingCreate, FindingRead, FindingSuggestionRead
from app.schemas.inventory import InventoryRead
from app.schemas.reports import ReportCreate, ReportDocumentRead, ReportRead
from app.schemas.tools import (
    ToolExecutionCancelResponse,
    ToolExecutionStreamTicket,
    ToolInvocationRead,
    ToolInvocationRequest,
    ToolInvocationResponse,
    ToolExecutionArtifactRead,
    ToolExecutionRead,
)

router = APIRouter(prefix="/api/v1")


def get_engagement_service(request: Request) -> EngagementService:
    return request.app.state.engagement_service


def get_approval_service(request: Request) -> ApprovalService:
    return request.app.state.approval_service


def get_gateway_validation_service(request: Request) -> GatewayValidationService:
    return request.app.state.gateway_validation_service


def get_finding_service(request: Request) -> FindingService:
    return request.app.state.finding_service


def get_finding_suggestion_service(request: Request) -> FindingSuggestionService:
    return request.app.state.finding_suggestion_service


def get_audit_service(request: Request) -> AuditService:
    return request.app.state.audit_service


def get_tool_invocation_service(request: Request) -> ToolInvocationService:
    return request.app.state.tool_invocation_service


def get_tool_execution_service(request: Request) -> ToolExecutionService:
    return request.app.state.tool_execution_service


def get_inventory_service(request: Request) -> InventoryService:
    return request.app.state.inventory_service


def get_report_service(request: Request) -> ReportService:
    return request.app.state.report_service


def get_ticket_store(request: Request) -> WSTicketStore:
    return request.app.state.ws_ticket_store


def get_execution_bus(request: Request) -> ExecutionBus:
    return request.app.state.execution_bus


@router.get("/healthz", response_model=HealthResponse)
async def healthz(request: Request) -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        allowed_network=settings.allowed_network,
        weapon_node_url=settings.weapon_node_url,
        database_status=check_database_health(request.app.state.db_session_factory),
    )


@router.get("/engagements", response_model=list[EngagementRead])
async def list_engagements(request: Request) -> list[EngagementRead]:
    return get_engagement_service(request).list_engagements()


@router.post(
    "/engagements",
    response_model=EngagementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_engagement(
    payload: EngagementCreate,
    request: Request,
) -> EngagementRead:
    return get_engagement_service(request).create_engagement(payload)


@router.get("/engagements/{engagement_id}", response_model=EngagementRead)
async def get_engagement(
    engagement_id: UUID,
    request: Request,
) -> EngagementRead:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return engagement


@router.patch("/engagements/{engagement_id}/status", response_model=EngagementRead)
async def update_engagement_status(
    engagement_id: UUID,
    payload: EngagementStatusUpdate,
    request: Request,
) -> EngagementRead:
    engagement = get_engagement_service(request).update_status(
        engagement_id=engagement_id,
        status=payload.status,
    )
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return engagement


@router.get(
    "/engagements/{engagement_id}/findings",
    response_model=list[FindingRead],
)
async def list_findings(
    engagement_id: UUID,
    request: Request,
) -> list[FindingRead]:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_finding_service(request).list_for_engagement(engagement_id)


@router.get(
    "/engagements/{engagement_id}/finding-suggestions",
    response_model=list[FindingSuggestionRead],
)
async def list_finding_suggestions(
    engagement_id: UUID,
    request: Request,
) -> list[FindingSuggestionRead]:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_finding_suggestion_service(request).list_for_engagement(engagement_id)


@router.post(
    "/engagements/{engagement_id}/findings",
    response_model=FindingRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_finding(
    engagement_id: UUID,
    payload: FindingCreate,
    request: Request,
) -> FindingRead:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        return get_finding_service(request).create(
            engagement_id=engagement_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/engagements/{engagement_id}/audit-events",
    response_model=list[AuditEventRead],
)
async def list_audit_events(
    engagement_id: UUID,
    request: Request,
) -> list[AuditEventRead]:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return [
        AuditEventRead(
            event_type=item.event_type,
            engagement_id=item.engagement_id,
            payload=item.payload,
            prev_hash=item.prev_hash,
            evidence_hash=item.evidence_hash,
            occurred_at=item.occurred_at,
            actor=item.actor,
        )
        for item in get_audit_service(request).list_for_engagement(engagement_id)
    ]


@router.get(
    "/engagements/{engagement_id}/tool-invocations",
    response_model=list[ToolInvocationRead],
)
async def list_tool_invocations(
    engagement_id: UUID,
    request: Request,
) -> list[ToolInvocationRead]:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_tool_invocation_service(request).list_for_engagement(engagement_id)


@router.get(
    "/engagements/{engagement_id}/tool-executions",
    response_model=list[ToolExecutionRead],
)
async def list_tool_executions(
    engagement_id: UUID,
    request: Request,
) -> list[ToolExecutionRead]:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_tool_execution_service(request).list_for_engagement(engagement_id)


@router.get(
    "/engagements/{engagement_id}/tool-executions/{execution_id}",
    response_model=ToolExecutionArtifactRead,
)
async def get_tool_execution_artifact(
    engagement_id: UUID,
    execution_id: UUID,
    request: Request,
) -> ToolExecutionArtifactRead:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    artifact = get_tool_execution_service(request).get_document(
        engagement_id=engagement_id,
        execution_id=execution_id,
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return artifact


@router.get(
    "/engagements/{engagement_id}/inventory",
    response_model=InventoryRead,
)
async def get_inventory(
    engagement_id: UUID,
    request: Request,
) -> InventoryRead:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_inventory_service(request).build_inventory(engagement_id)


@router.get(
    "/engagements/{engagement_id}/reports",
    response_model=list[ReportRead],
)
async def list_reports(
    engagement_id: UUID,
    request: Request,
) -> list[ReportRead]:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_report_service(request).list_for_engagement(engagement_id)


@router.post(
    "/engagements/{engagement_id}/reports",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    engagement_id: UUID,
    payload: ReportCreate,
    request: Request,
) -> ReportRead:
    try:
        return get_report_service(request).generate(
            engagement_id=engagement_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/reports/{report_id}", response_model=ReportDocumentRead)
async def get_report_document(
    report_id: UUID,
    request: Request,
) -> ReportDocumentRead:
    report = get_report_service(request).get_document(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return report


@router.get(
    "/engagements/{engagement_id}/approvals",
    response_model=list[ApprovalRead],
)
async def list_approvals(
    engagement_id: UUID,
    request: Request,
) -> list[ApprovalRead]:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_approval_service(request).list_for_engagement(engagement_id)


@router.post(
    "/engagements/{engagement_id}/approvals",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_approval(
    engagement_id: UUID,
    payload: ApprovalCreate,
    request: Request,
) -> ApprovalRead:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        policy = get_tool_policy(payload.tool_name, payload.operation_name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return get_approval_service(request).create(
        engagement_id=engagement_id,
        payload=payload,
        risk_level=policy.risk_level,
    )


@router.patch("/approvals/{approval_id}", response_model=ApprovalRead)
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecision,
    request: Request,
) -> ApprovalRead:
    approval = get_approval_service(request).decide(
        approval_id=approval_id,
        payload=payload,
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return approval


@router.post(
    "/engagements/{engagement_id}/tool-validations",
    response_model=ToolInvocationResponse,
)
async def validate_tool_invocation(
    engagement_id: UUID,
    payload: ToolInvocationRequest,
    request: Request,
) -> ToolInvocationResponse:
    try:
        return get_gateway_validation_service(request).validate_tool_invocation(
            engagement_id=engagement_id,
            payload=payload,
        )
    except ToolValidationError as exc:
        detail = str(exc)
        if detail == "Engagement not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail == "Approved authorization is required for this high-risk action":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.post("/engagements/{engagement_id}/tool-invocations/{invocation_id}/execute-stream")
async def execute_tool_invocation_stream(
    engagement_id: UUID,
    invocation_id: UUID,
    request: Request,
) -> StreamingResponse:
    try:
        stream = get_gateway_validation_service(request).stream_tool_execution(
            engagement_id=engagement_id,
            invocation_id=invocation_id,
        )
    except ToolValidationError as exc:
        detail = str(exc)
        if detail in {"Engagement not found", "Validated invocation not found"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    return StreamingResponse(stream, media_type="application/x-ndjson")


@router.post(
    "/engagements/{engagement_id}/tool-executions/{execution_id}/cancel",
    response_model=ToolExecutionCancelResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_tool_execution(
    engagement_id: UUID,
    execution_id: UUID,
    request: Request,
) -> ToolExecutionCancelResponse:
    try:
        return get_gateway_validation_service(request).cancel_tool_execution(
            engagement_id=engagement_id,
            execution_id=execution_id,
        )
    except ToolValidationError as exc:
        detail = str(exc)
        if detail in {"Engagement not found", "Tool execution not found"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail == "Tool execution is not running":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.post(
    "/engagements/{engagement_id}/tool-executions/{execution_id}/stream-ticket",
    response_model=ToolExecutionStreamTicket,
    status_code=status.HTTP_201_CREATED,
)
async def issue_stream_ticket(
    engagement_id: UUID,
    execution_id: UUID,
    request: Request,
) -> ToolExecutionStreamTicket:
    engagement = get_engagement_service(request).get_engagement(engagement_id)
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found"
        )
    execution_service = get_tool_execution_service(request)
    execution = execution_service.get_for_engagement(
        engagement_id=engagement_id,
        execution_id=execution_id,
    )
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool execution not found"
        )
    scope = TicketScope(engagement_id=engagement_id, execution_id=execution_id)
    ticket = get_ticket_store(request).issue(scope)
    return ToolExecutionStreamTicket(
        ticket=ticket,
        engagement_id=engagement_id,
        execution_id=execution_id,
        expires_in_seconds=60,
    )


@router.websocket(
    "/ws/engagements/{engagement_id}/tool-executions/{execution_id}/stream"
)
async def websocket_execution_stream(
    websocket: WebSocket,
    engagement_id: UUID,
    execution_id: UUID,
    ticket: str = "",
) -> None:
    if not ticket:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing ticket")
        return

    ticket_store: WSTicketStore = websocket.app.state.ws_ticket_store
    expected = TicketScope(engagement_id=engagement_id, execution_id=execution_id)
    try:
        ticket_store.redeem(ticket, expected=expected)
    except TicketError:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="invalid ticket"
        )
        return

    await websocket.accept()
    bus: ExecutionBus = websocket.app.state.execution_bus
    subscription = bus.subscribe(str(execution_id))
    try:
        async for event in subscription:
            await websocket.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    finally:
        await subscription.aclose()
        # send_text can raise if the client already hung up; swallow to avoid noise
        try:
            await websocket.close()
        except RuntimeError:
            pass

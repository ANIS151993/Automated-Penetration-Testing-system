from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.approvals import ApprovalService, SqlAlchemyApprovalRepository
from app.core.audit_service import AuditService
from app.core.config import get_settings
from app.core.database import check_database_health, initialize_database, session_factory_from_settings
from app.core.engagements import EngagementService, SqlAlchemyEngagementRepository
from app.core.findings import FindingService, SqlAlchemyFindingRepository
from app.core.finding_suggestions import FindingSuggestionService
from app.core.gateway_validation import GatewayValidationService
from app.core.reports import ReportService, SqlAlchemyReportRepository
from app.core.tool_executions import (
    SqlAlchemyToolExecutionRepository,
    ToolExecutionService,
)
from app.core.tool_invocations import (
    InventoryService,
    SqlAlchemyToolInvocationRepository,
    ToolInvocationService,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory = session_factory_from_settings()
    initialize_database(session_factory)
    app.state.db_session_factory = session_factory
    app.state.db_status = check_database_health(session_factory)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    session_factory = session_factory_from_settings()
    audit_service = AuditService(session_factory)
    engagement_service = EngagementService(
        SqlAlchemyEngagementRepository(session_factory)
    )
    approval_service = ApprovalService(
        SqlAlchemyApprovalRepository(session_factory),
        audit_service=audit_service,
    )
    tool_invocation_service = ToolInvocationService(
        SqlAlchemyToolInvocationRepository(session_factory)
    )
    tool_execution_service = ToolExecutionService(
        SqlAlchemyToolExecutionRepository(session_factory),
        artifacts_root=settings.artifacts_root,
    )
    inventory_service = InventoryService(
        tool_invocation_service,
        tool_execution_service=tool_execution_service,
    )
    finding_suggestion_service = FindingSuggestionService(tool_execution_service)
    finding_service = FindingService(
        SqlAlchemyFindingRepository(session_factory),
        audit_service=audit_service,
        tool_invocation_service=tool_invocation_service,
    )
    report_service = ReportService(
        SqlAlchemyReportRepository(session_factory),
        engagement_service=engagement_service,
        approval_service=approval_service,
        finding_service=finding_service,
        finding_suggestion_service=finding_suggestion_service,
        tool_invocation_service=tool_invocation_service,
        tool_execution_service=tool_execution_service,
        inventory_service=inventory_service,
        audit_service=audit_service,
        artifacts_root=settings.artifacts_root,
    )
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.engagement_service = engagement_service
    app.state.approval_service = approval_service
    app.state.tool_invocation_service = tool_invocation_service
    app.state.tool_execution_service = tool_execution_service
    app.state.inventory_service = inventory_service
    app.state.finding_suggestion_service = finding_suggestion_service
    app.state.finding_service = finding_service
    app.state.report_service = report_service
    app.state.audit_service = audit_service
    app.state.gateway_validation_service = GatewayValidationService(
        settings=settings,
        engagement_service=engagement_service,
        approval_service=approval_service,
        audit_service=audit_service,
        tool_invocation_service=tool_invocation_service,
        tool_execution_service=tool_execution_service,
    )
    app.include_router(router)
    return app


app = create_app()

import asyncio
from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth_routes import auth_router
from app.api.knowledge_routes import knowledge_router
from app.api.routes import router
from app.core.llm_client import MODEL_ROUTING, LLMClient
from app.knowledge.service import KnowledgeService
from app.core.agent_runs import AgentRunService, SqlAlchemyAgentRunRepository
from app.core.approvals import ApprovalService, SqlAlchemyApprovalRepository
from app.core.auth import UserService
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
from app.core.ws_tickets import WSTicketStore
from app.websocket.execution_bus import ExecutionBus


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory = session_factory_from_settings()
    initialize_database(session_factory)
    app.state.db_session_factory = session_factory
    app.state.db_status = check_database_health(session_factory)
    app.state.execution_bus.bind_loop(asyncio.get_running_loop())
    settings = app.state.settings
    llm = LLMClient(base_url=settings.ollama_url)
    await llm.__aenter__()
    app.state.llm_client = llm
    app.state.knowledge_service = KnowledgeService(
        session_factory=session_factory,
        embedder=llm,
        embedding_model=MODEL_ROUTING["embed"],
    )
    try:
        yield
    finally:
        await llm.__aexit__(None, None, None)


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
    agent_run_service = AgentRunService(
        SqlAlchemyAgentRunRepository(session_factory),
        audit_service=audit_service,
    )
    finding_suggestion_service = FindingSuggestionService(
        tool_execution_service,
        agent_run_service=agent_run_service,
    )
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
        agent_run_service=agent_run_service,
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
    app.state.agent_run_service = agent_run_service
    app.state.audit_service = audit_service
    app.state.user_service = UserService(session_factory)
    app.state.settings = settings
    execution_bus = ExecutionBus()
    app.state.execution_bus = execution_bus
    app.state.ws_ticket_store = WSTicketStore()
    app.state.gateway_validation_service = GatewayValidationService(
        settings=settings,
        engagement_service=engagement_service,
        approval_service=approval_service,
        audit_service=audit_service,
        tool_invocation_service=tool_invocation_service,
        tool_execution_service=tool_execution_service,
        execution_bus=execution_bus,
    )
    cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    public_paths = {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/healthz",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    @app.middleware("http")
    async def require_session(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in public_paths or path.startswith("/api/v1/ws/"):
            return await call_next(request)

        # Bearer path — try Supabase JWT first, then legacy JWT
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            bearer_token = auth_header.split(" ", 1)[1].strip()
            # Try Supabase JWT
            try:
                jwt.decode(
                    bearer_token,
                    settings.supabase_jwt_secret,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
                return await call_next(request)
            except jwt.PyJWTError:
                pass
            # Try legacy JWT
            try:
                jwt.decode(bearer_token, settings.auth_jwt_secret, algorithms=["HS256"])
                return await call_next(request)
            except jwt.PyJWTError:
                pass
            return JSONResponse({"detail": "invalid_token"}, status_code=401)

        # Cookie fallback (legacy sessions)
        token = request.cookies.get(settings.auth_cookie_name)
        if not token:
            return JSONResponse({"detail": "not_authenticated"}, status_code=401)
        try:
            jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return JSONResponse({"detail": "invalid_session"}, status_code=401)
        return await call_next(request)

    app.include_router(auth_router)
    app.include_router(knowledge_router)
    app.include_router(router)
    return app


app = create_app()

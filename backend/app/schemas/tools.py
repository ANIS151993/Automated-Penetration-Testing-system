from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ToolInvocationRequest(BaseModel):
    tool_name: str = Field(min_length=2, max_length=120)
    operation_name: str = Field(min_length=2, max_length=120)
    args: dict


class ToolInvocationResponse(BaseModel):
    invocation_id: UUID | None = None
    status: str
    tool: str
    operation: str
    risk_level: str
    command_preview: list[str]
    targets: list[str]


class ToolInvocationRead(BaseModel):
    id: UUID
    engagement_id: UUID
    tool_name: str
    operation_name: str
    risk_level: str
    args: dict
    command_preview: list[str]
    targets: list[str]
    created_at: datetime


class ToolExecutionRead(BaseModel):
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


class ToolExecutionArtifactRead(BaseModel):
    execution: ToolExecutionRead
    content: dict[str, Any]


class ToolExecutionCancelResponse(BaseModel):
    execution_id: UUID
    status: str
    detail: str

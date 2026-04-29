from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class EngagementStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ABORTED = "aborted"
    ARCHIVED = "archived"


class EngagementCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    scope_cidrs: list[str] = Field(min_length=1)
    authorization_confirmed: bool
    authorizer_name: str = Field(min_length=2, max_length=120)
    operator_name: str = Field(min_length=2, max_length=120)


class EngagementRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    scope_cidrs: list[str]
    authorization_confirmed: bool
    authorizer_name: str
    operator_name: str
    status: EngagementStatus
    created_at: datetime
    updated_at: datetime


class EngagementStatusUpdate(BaseModel):
    status: EngagementStatus


class HealthResponse(BaseModel):
    status: str
    environment: str
    allowed_network: str
    weapon_node_url: str
    database_status: str
    ollama_status: str = "unknown"
    ollama_models: list[str] = []

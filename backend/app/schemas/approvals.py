from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalCreate(BaseModel):
    requested_action: str = Field(min_length=4, max_length=120)
    requested_by: str = Field(min_length=2, max_length=120)
    tool_name: str = Field(min_length=2, max_length=120)
    operation_name: str = Field(min_length=2, max_length=120)
    args: dict


class ApprovalDecision(BaseModel):
    approved: bool
    approved_by: str = Field(min_length=2, max_length=120)
    decision_reason: str | None = Field(default=None, max_length=1000)


class ApprovalRead(BaseModel):
    id: UUID
    engagement_id: UUID
    requested_action: str
    risk_level: str
    requested_by: str
    approved: bool
    approved_by: str | None
    decision_reason: str | None
    tool_name: str
    operation_name: str
    args: dict
    created_at: datetime
    decided_at: datetime | None

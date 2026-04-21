from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class FindingSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCreate(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    severity: FindingSeverity
    attack_technique: str | None = Field(default=None, max_length=120)
    summary: str = Field(min_length=8, max_length=4000)
    evidence: list[str] = Field(default_factory=list)
    evidence_refs: list[UUID] = Field(default_factory=list)
    reported_by: str = Field(min_length=2, max_length=120)


class FindingRead(BaseModel):
    id: UUID
    engagement_id: UUID
    title: str
    severity: FindingSeverity
    attack_technique: str | None
    summary: str
    evidence: list[str]
    evidence_refs: list[UUID]
    reported_by: str
    created_at: datetime


class FindingSuggestionRead(BaseModel):
    suggestion_id: str
    execution_id: UUID
    invocation_id: UUID
    title: str
    severity: FindingSeverity
    attack_technique: str | None
    summary: str
    evidence: list[str]
    evidence_refs: list[UUID]

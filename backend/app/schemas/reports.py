from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    report_format: str = Field(default="json", pattern="^json$")


class ReportRead(BaseModel):
    id: UUID
    engagement_id: UUID
    report_format: str
    artifact_path: str
    created_at: datetime


class ReportDocumentRead(BaseModel):
    report: ReportRead
    content: dict[str, Any]

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    event_type: str
    engagement_id: UUID
    payload: dict
    prev_hash: str
    evidence_hash: str
    occurred_at: datetime
    actor: str | None

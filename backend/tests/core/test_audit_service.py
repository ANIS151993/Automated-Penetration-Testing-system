from uuid import uuid4

import pytest

from app.core.audit import GENESIS_HASH, validate_hash_chain
from app.core.audit_service import AuditService
from app.core.config import get_settings
from app.core.database import (
    initialize_database,
    reset_database_state,
    session_factory_from_settings,
)


@pytest.fixture
def audit_service(tmp_path, monkeypatch: pytest.MonkeyPatch) -> AuditService:
    database_path = tmp_path / "pentai-audit.db"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    reset_database_state()

    session_factory = session_factory_from_settings()
    initialize_database(session_factory)
    yield AuditService(session_factory)

    get_settings.cache_clear()
    reset_database_state()


def test_audit_service_persists_hash_chain(audit_service: AuditService) -> None:
    engagement_id = uuid4()

    first = audit_service.record_event(
        engagement_id=engagement_id,
        event_type="approval_requested",
        payload={"tool_name": "nmap", "operation_name": "os_detection"},
        actor="Analyst One",
    )
    second = audit_service.record_event(
        engagement_id=engagement_id,
        event_type="tool_validation_succeeded",
        payload={"tool_name": "nmap", "operation_name": "service_scan"},
        actor="lab-operator",
    )

    records = audit_service.list_for_engagement(engagement_id)

    assert len(records) == 2
    assert first.prev_hash == GENESIS_HASH
    assert second.prev_hash == first.evidence_hash
    assert validate_hash_chain(
        [
            {
                "event_type": record.event_type,
                "payload": record.payload,
                "prev_hash": record.prev_hash,
                "evidence_hash": record.evidence_hash,
                "occurred_at": record.occurred_at,
            }
            for record in records
        ]
    )

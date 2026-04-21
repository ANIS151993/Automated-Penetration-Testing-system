from datetime import datetime, timezone

from app.core.audit import GENESIS_HASH, build_audit_record, validate_hash_chain


def test_hash_chain_detects_tampering() -> None:
    first = build_audit_record(
        event_type="tool_invocation",
        payload={"tool_name": "nmap", "target": "172.20.32.59"},
        prev_hash=GENESIS_HASH,
        occurred_at=datetime(2026, 4, 19, 5, 0, tzinfo=timezone.utc),
    )
    second = build_audit_record(
        event_type="llm_call",
        payload={"task": "reason", "model": "qwen2.5:7b-instruct-q4_K_M"},
        prev_hash=first["evidence_hash"],
        occurred_at=datetime(2026, 4, 19, 5, 1, tzinfo=timezone.utc),
    )

    assert validate_hash_chain([first, second]) is True

    second["payload"]["model"] = "tampered"
    assert validate_hash_chain([first, second]) is False

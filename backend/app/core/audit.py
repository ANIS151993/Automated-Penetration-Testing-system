from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

GENESIS_HASH = "0" * 64


def canonicalize_audit_payload(
    *,
    event_type: str,
    payload: dict[str, Any],
    prev_hash: str,
    occurred_at: datetime,
) -> str:
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)

    document = {
        "event_type": event_type,
        "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
        "payload": payload,
        "prev_hash": prev_hash,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def compute_chain_hash(
    *,
    event_type: str,
    payload: dict[str, Any],
    prev_hash: str = GENESIS_HASH,
    occurred_at: datetime | None = None,
) -> str:
    timestamp = occurred_at or datetime.now(timezone.utc)
    canonical = canonicalize_audit_payload(
        event_type=event_type,
        payload=payload,
        prev_hash=prev_hash,
        occurred_at=timestamp,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_audit_record(
    *,
    event_type: str,
    payload: dict[str, Any],
    prev_hash: str = GENESIS_HASH,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = occurred_at or datetime.now(timezone.utc)
    return {
        "event_type": event_type,
        "occurred_at": timestamp,
        "payload": payload,
        "prev_hash": prev_hash,
        "evidence_hash": compute_chain_hash(
            event_type=event_type,
            payload=payload,
            prev_hash=prev_hash,
            occurred_at=timestamp,
        ),
    }


def validate_hash_chain(records: list[dict[str, Any]]) -> bool:
    previous_hash = GENESIS_HASH
    for record in records:
        expected = compute_chain_hash(
            event_type=record["event_type"],
            payload=record["payload"],
            prev_hash=previous_hash,
            occurred_at=record["occurred_at"],
        )
        if record["prev_hash"] != previous_hash or record["evidence_hash"] != expected:
            return False
        previous_hash = record["evidence_hash"]
    return True

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.core.database import (
    engine_from_settings,
    initialize_database,
    reset_database_state,
    session_factory_from_settings,
)


def test_initialize_database_reconciles_legacy_approval_columns(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "legacy-bootstrap.db"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    reset_database_state()

    engine = engine_from_settings()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE approvals (
                    id TEXT PRIMARY KEY,
                    engagement_id TEXT NOT NULL,
                    requested_action TEXT NOT NULL,
                    approved BOOLEAN NOT NULL DEFAULT FALSE,
                    requested_by TEXT NOT NULL,
                    approved_by TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )
                """
            )
        )

    initialize_database(session_factory_from_settings())

    columns = {
        column["name"] for column in inspect(engine).get_columns("approvals")
    }

    assert {
        "risk_level",
        "decision_reason",
        "tool_name",
        "operation_name",
        "args",
    }.issubset(columns)

    get_settings.cache_clear()
    reset_database_state()


def test_initialize_database_reconciles_legacy_findings_and_tool_invocations(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "legacy-evidence.db"
    monkeypatch.setenv("PENTAI_POSTGRES_DSN", f"sqlite:///{database_path}")
    get_settings.cache_clear()
    reset_database_state()

    engine = engine_from_settings()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE findings (
                    id TEXT PRIMARY KEY,
                    engagement_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    attack_technique TEXT,
                    summary TEXT NOT NULL,
                    evidence JSON NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE tool_invocations (
                    id TEXT PRIMARY KEY,
                    engagement_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    command_preview JSON NOT NULL,
                    target_ip TEXT,
                    scope_check TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    evidence_hash TEXT NOT NULL,
                    started_at TEXT NOT NULL
                )
                """
            )
        )

    initialize_database(session_factory_from_settings())

    findings_columns = {
        column["name"] for column in inspect(engine).get_columns("findings")
    }
    tool_invocation_columns = {
        column["name"] for column in inspect(engine).get_columns("tool_invocations")
    }

    assert {"reported_by", "evidence_refs"}.issubset(findings_columns)
    assert {
        "operation_name",
        "risk_level",
        "args",
        "targets",
    }.issubset(tool_invocation_columns)

    get_settings.cache_clear()
    reset_database_state()

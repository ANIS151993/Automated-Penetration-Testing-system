from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.base import Base


def _sqlite_connect_args(dsn: str) -> dict[str, object]:
    if dsn.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


@lru_cache
def engine_from_settings() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.postgres_dsn,
        future=True,
        connect_args=_sqlite_connect_args(settings.postgres_dsn),
    )


@lru_cache
def session_factory_from_settings() -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine_from_settings(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def initialize_database(session_factory: sessionmaker[Session]) -> None:
    import app.models  # noqa: F401

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(bind=engine)
    reconcile_bootstrap_schema(engine)


def reconcile_bootstrap_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    for table_name, definitions in (
        ("approvals", _approval_column_definitions(engine)),
        ("findings", _finding_column_definitions(engine)),
        ("tool_invocations", _tool_invocation_column_definitions(engine)),
    ):
        if table_name not in inspector.get_table_names():
            continue
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for column_name, definition in definitions.items():
            if column_name in existing_columns:
                continue
            with engine.begin() as connection:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {definition}")
                )
                if table_name == "findings" and column_name == "reported_by":
                    connection.execute(
                        text(
                            "UPDATE findings SET reported_by = 'unknown' "
                            "WHERE reported_by IS NULL"
                        )
                    )
                if table_name == "tool_invocations" and column_name == "targets":
                    connection.execute(
                        text(
                            "UPDATE tool_invocations SET targets = "
                            "CASE "
                            "WHEN target_ip IS NOT NULL THEN "
                            + _json_array_expression(engine, "target_ip")
                            + " ELSE "
                            + _empty_json_array_expression(engine)
                            + " END "
                            "WHERE targets IS NULL"
                        )
                    )


def _approval_column_definitions(engine: Engine) -> dict[str, str]:
    if engine.dialect.name == "postgresql":
        json_definition = "args JSONB NOT NULL DEFAULT '{}'::jsonb"
    else:
        json_definition = "args JSON NOT NULL DEFAULT '{}'"

    return {
        "risk_level": "risk_level VARCHAR(24) NOT NULL DEFAULT 'high'",
        "decision_reason": "decision_reason TEXT",
        "tool_name": "tool_name VARCHAR(120) NOT NULL DEFAULT 'unknown'",
        "operation_name": "operation_name VARCHAR(120) NOT NULL DEFAULT 'unknown'",
        "args": json_definition,
    }


def _finding_column_definitions(engine: Engine) -> dict[str, str]:
    if engine.dialect.name == "postgresql":
        evidence_refs_definition = "evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb"
    else:
        evidence_refs_definition = "evidence_refs JSON NOT NULL DEFAULT '[]'"

    return {
        "reported_by": "reported_by VARCHAR(120) NOT NULL DEFAULT 'unknown'",
        "evidence_refs": evidence_refs_definition,
    }


def _tool_invocation_column_definitions(engine: Engine) -> dict[str, str]:
    if engine.dialect.name == "postgresql":
        args_definition = "args JSONB NOT NULL DEFAULT '{}'::jsonb"
        targets_definition = "targets JSONB NOT NULL DEFAULT '[]'::jsonb"
    else:
        args_definition = "args JSON NOT NULL DEFAULT '{}'"
        targets_definition = "targets JSON NOT NULL DEFAULT '[]'"

    return {
        "operation_name": "operation_name VARCHAR(120) NOT NULL DEFAULT 'unknown'",
        "risk_level": "risk_level VARCHAR(24) NOT NULL DEFAULT 'low'",
        "args": args_definition,
        "targets": targets_definition,
    }


def _json_array_expression(engine: Engine, column_name: str) -> str:
    if engine.dialect.name == "postgresql":
        return f"jsonb_build_array({column_name})"
    return f"'[\"' || {column_name} || '\"]'"


def _empty_json_array_expression(engine: Engine) -> str:
    if engine.dialect.name == "postgresql":
        return "'[]'::jsonb"
    return "'[]'"


def check_database_health(session_factory: sessionmaker[Session]) -> str:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return "ok"
    except SQLAlchemyError:
        return "error"


def reset_database_state() -> None:
    session_factory_from_settings.cache_clear()
    engine_from_settings.cache_clear()

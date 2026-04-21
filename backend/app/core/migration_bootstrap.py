from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy import inspect

from app.core.database import engine_from_settings

CORE_TABLES = {"engagements", "approvals", "audit_events"}
BASELINE_REVISION = "20260419_000001"


def choose_alembic_commands(existing_tables: set[str]) -> list[list[str]]:
    if "alembic_version" in existing_tables:
        return [["upgrade", "head"]]
    if CORE_TABLES.intersection(existing_tables):
        return [["stamp", BASELINE_REVISION], ["upgrade", "head"]]
    return [["upgrade", "head"]]


def main() -> None:
    engine = engine_from_settings()
    existing_tables = set(inspect(engine).get_table_names())
    project_root = Path(__file__).resolve().parents[2]
    for command in choose_alembic_commands(existing_tables):
        subprocess.run(
            ["alembic", "-c", str(project_root / "alembic.ini"), *command],
            check=True,
            cwd=project_root,
        )


if __name__ == "__main__":
    main()

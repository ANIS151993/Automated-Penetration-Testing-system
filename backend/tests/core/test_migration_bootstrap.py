from app.core.migration_bootstrap import BASELINE_REVISION, choose_alembic_commands


def test_choose_alembic_upgrade_for_empty_database() -> None:
    assert choose_alembic_commands(set()) == [["upgrade", "head"]]


def test_choose_alembic_stamp_for_legacy_database() -> None:
    assert choose_alembic_commands({"engagements", "approvals"}) == [
        ["stamp", BASELINE_REVISION],
        ["upgrade", "head"],
    ]


def test_choose_alembic_upgrade_for_managed_database() -> None:
    assert choose_alembic_commands({"alembic_version", "engagements"}) == [
        ["upgrade", "head"]
    ]

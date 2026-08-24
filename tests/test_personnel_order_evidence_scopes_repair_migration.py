from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "n1o2p3q4r5s6_repair_personnel_order_evidence_scopes.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("poes_repair_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RecordingBind:
    def __init__(self, *, fail_on: int | None = None) -> None:
        self.statements: list[str] = []
        self.fail_on = fail_on

    def execute(self, statement):
        self.statements.append(str(statement))
        if self.fail_on == len(self.statements):
            raise RuntimeError("simulated incompatible scope schema")


def test_missing_scope_table_is_created_and_backfilled() -> None:
    migration = _migration_module()
    bind = _RecordingBind()

    migration.repair_personnel_order_evidence_scopes(bind)

    assert "CREATE TABLE IF NOT EXISTS public.personnel_order_evidence_scopes" in bind.statements[0]
    assert "INSERT INTO public.personnel_order_evidence_scopes(order_id, generation)" in bind.statements[2]
    assert "SELECT order_id, 1" in bind.statements[2]


def test_existing_correct_scope_table_is_only_backfilled_without_mutation() -> None:
    migration = _migration_module()
    bind = _RecordingBind()

    migration.repair_personnel_order_evidence_scopes(bind)

    backfill = bind.statements[2]
    assert "ON CONFLICT (order_id) DO NOTHING" in backfill
    assert "UPDATE public.personnel_order_evidence_scopes" not in backfill
    assert "DELETE FROM public.personnel_order_evidence_scopes" not in backfill


def test_incompatible_existing_structure_stops_before_backfill() -> None:
    migration = _migration_module()
    bind = _RecordingBind(fail_on=2)

    with pytest.raises(RuntimeError, match="incompatible scope schema"):
        migration.repair_personnel_order_evidence_scopes(bind)

    assert len(bind.statements) == 2
    assert all("INSERT INTO public.personnel_order_evidence_scopes" not in sql for sql in bind.statements)


def test_repeated_backfill_is_idempotent() -> None:
    migration = _migration_module()
    bind = _RecordingBind()

    migration.repair_personnel_order_evidence_scopes(bind)
    migration.repair_personnel_order_evidence_scopes(bind)

    backfills = [sql for sql in bind.statements if "INSERT INTO public.personnel_order_evidence_scopes" in sql]
    assert len(backfills) == 2
    assert all("ON CONFLICT (order_id) DO NOTHING" in sql for sql in backfills)

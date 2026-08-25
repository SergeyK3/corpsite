"""Contract tests for the Oserova HR enrollment migration."""
from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "p1q2r3s4t5u6_oserova_hr_reg_enrollment_grant.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("oserova_hr_reg_grant_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_is_code_and_login_based_and_keeps_grant_personal(monkeypatch) -> None:
    migration = _load_migration_module()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    assert migration.down_revision == "o1p2q3r4s5t6"
    assert len(statements) == 3
    sql = "\n".join(statements)
    assert "VALUES ('HR_reg', 'сотрудник1 ОК', TRUE)" in sql
    assert "ON CONFLICT (code)" in sql
    assert "lower(u.login) = 'oserova.aa'" in sql
    assert "r.code = 'HR_reg'" in sql
    assert "ar.code = 'HR_ENROLLMENT_MANAGER'" in sql
    assert "'USER'" in sql
    assert "'GLOBAL'" in sql
    assert "target_type = 'ROLE'" not in statements[2]
    assert "existing.active_flag = TRUE" in statements[2]
    assert "existing.target_id = target.user_id" in statements[2]
    assert "ends_at" in statements[2]
    assert "NULL" in statements[2]


def test_downgrade_only_removes_the_migration_owned_grant(monkeypatch) -> None:
    migration = _load_migration_module()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.downgrade()

    assert len(statements) == 1
    assert "Seed: Oserova personal HR_ENROLLMENT_MANAGER grant" in statements[0]
    assert "lower(target.login) = 'oserova.aa'" in statements[0]

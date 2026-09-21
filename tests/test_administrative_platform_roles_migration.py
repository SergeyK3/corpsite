"""PostgreSQL contract for canonical administrative Platform Role catalog."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from scripts.align_employee_accounts import CheckedRoleChangeSpec, align
from tests.conftest import create_user
from tests.ppr.conftest import insert_employee, ppr_db_available, require_ppr_schema


_MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "adm001_canonical_administrative_platform_roles.py"
_SPEC = importlib.util.spec_from_file_location("adm001_canonical_administrative_platform_roles", _MIGRATION_PATH)
assert _SPEC is not None and _SPEC.loader is not None
migration = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(migration)


def _roles(conn) -> dict[str, dict]:
    return {
        str(row["code"]): dict(row)
        for row in conn.execute(
            text("SELECT role_id, code, name, is_active FROM public.roles WHERE code = ANY(:codes)"),
            {"codes": [code for code, _name in migration.CANONICAL_ADMINISTRATIVE_ROLES]},
        ).mappings()
    }


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    "dep_admin_name",
    [migration.DEP_ADMIN_PRODUCTION_NAME, migration.DEP_ADMIN_LEGACY_NAME],
    ids=["production-title", "legacy-title"],
)
def test_administrative_catalog_upgrade_is_idempotent_preserves_existing_dep_admin_and_has_no_grants(dep_admin_name: str) -> None:
    """Exercise downgrade/upgrade/upgrade in a rolled-back integration transaction."""
    require_ppr_schema()
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            migration._upgrade_connection(conn)
            migration._downgrade_connection(conn)
            assert _roles(conn) == {}

            dep_admin_id = int(
                conn.execute(
                    text("INSERT INTO public.roles (code, name, is_active) VALUES ('DEP_ADMIN', :name, FALSE) RETURNING role_id"),
                    {"name": dep_admin_name},
                ).scalar_one()
            )
            migration._upgrade_connection(conn)
            first = _roles(conn)
            migration._upgrade_connection(conn)
            second = _roles(conn)

            assert first == second
            assert set(first) == {code for code, _name in migration.CANONICAL_ADMINISTRATIVE_ROLES}
            assert first["DEP_ADMIN"] == {
                "role_id": dep_admin_id,
                "code": "DEP_ADMIN",
                "name": dep_admin_name,
                "is_active": False,
            }
            for code, expected_name in migration.CANONICAL_ADMINISTRATIVE_ROLES:
                expected_names = {dep_admin_name} if code == "DEP_ADMIN" else {expected_name}
                assert first[code]["name"] in expected_names
                if code != "DEP_ADMIN":
                    assert first[code]["is_active"] is True
                grants = conn.execute(
                    text("SELECT COUNT(*) FROM public.access_grants WHERE target_type='ROLE' AND target_id=:role_id"),
                    {"role_id": int(first[code]["role_id"])},
                ).scalar_one()
                assert grants == 0

            migration._downgrade_connection(conn)
            remaining = _roles(conn)
            assert remaining == {
                "DEP_ADMIN": {
                    "role_id": dep_admin_id,
                    "code": "DEP_ADMIN",
                    "name": dep_admin_name,
                    "is_active": False,
                }
            }
        finally:
            transaction.rollback()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize(
    ("code", "unexpected_name"),
    [("DEP_ADMIN", "Неизвестное имя"), ("DIRECTOR", "Unexpected name")],
    ids=["dep-admin-unknown-title", "director-strict-title"],
)
def test_administrative_catalog_code_name_conflict_fails_closed(code: str, unexpected_name: str) -> None:
    require_ppr_schema()
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            migration._upgrade_connection(conn)
            migration._downgrade_connection(conn)
            conn.execute(text("INSERT INTO public.roles (code, name, is_active) VALUES (:code, :name, TRUE)"), {"code": code, "name": unexpected_name})
            with pytest.raises(RuntimeError, match=f"{code} has unexpected name"):
                migration._upgrade_connection(conn)
        finally:
            transaction.rollback()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_alignment_preflight_resolves_canonical_admin_roles_after_migration(seed) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    role_id = None
    employee_ids: list[int] = []
    user_ids: list[int] = []
    target_codes = ["DIRECTOR", "DEP_MED", "DEP_OUTPATIENT_AUDIT", "DEP_STRATEGY"]
    try:
        with engine.begin() as conn:
            migration._upgrade_connection(conn)
            role_id = int(conn.execute(text("SELECT role_id FROM public.roles WHERE code='DEP_ADMIN'" )).scalar_one())
            for index, target_code in enumerate(target_codes, start=1):
                employee_id = insert_employee(conn, full_name=f"Canonical Role {index} {suffix}", person_id=None, operational_status="active")
                conn.execute(text("UPDATE public.employees SET org_unit_id=:unit_id WHERE employee_id=:employee_id"), {"unit_id": int(seed["unit_id"]), "employee_id": employee_id})
                user_id = create_user(conn, full_name=f"Canonical Role {index} {suffix}", role_id=role_id, unit_id=int(seed["unit_id"]))
                conn.execute(text("UPDATE public.users SET employee_id=:employee_id, login=:login WHERE user_id=:user_id"), {"employee_id": employee_id, "login": f"canonical_role_{index}_{suffix}", "user_id": user_id})
                employee_ids.append(employee_id)
                user_ids.append(user_id)

        result = align(
            checked_role_changes=tuple(
                CheckedRoleChangeSpec(user_id, employee_id, f"canonical_role_{index}_{suffix}", "DEP_ADMIN", target_code)
                for index, (user_id, employee_id, target_code) in enumerate(zip(user_ids, employee_ids, target_codes, strict=True), start=1)
            )
        )
        assert result["status"] == "dry_run_ok"
        assert [row["to"] for row in result["checked_role_changes"]] == target_codes
    finally:
        if user_ids:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id = ANY(:user_ids)"), {"user_ids": user_ids})
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = ANY(:employee_ids)"), {"employee_ids": employee_ids})

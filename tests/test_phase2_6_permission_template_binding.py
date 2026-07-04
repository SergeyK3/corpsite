"""Tests for ADR-053 Phase 2.6a — Permission Template binding engineering support.

Scope: schema, idempotent backfill mechanism, resolver read-path, shadow taxonomy.
Does not assert production binding completeness (Phase 2.6b; ADR-053 AC3 Pending).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from app.db.engine import engine
from app.services.access_resolver_service import resolve_effective_access
from app.services.cabinet_access_resolver_service import resolve_effective_permissions
from app.services.cabinet_access_shadow_service import compare_legacy_and_cabinet_access
from tests.conftest import get_columns, insert_returning_id, table_exists
from tests.test_cabinet_access_resolver import (
    _create_adr050_chain,
    _create_employee,
    _insert_position,
    _require_phase2,
)
from tests.test_phase2_position_cabinet_backfill import _db_available

SCHEMA_REVISION = "m7n8o9p0q1r2"
BACKFILL_REVISION = "n8o9p0q1r2s3"

PHASE26_TABLES = (
    "permission_template_contour_rule",
)


def _phase26_schema_available() -> bool:
    with engine.begin() as conn:
        cols = get_columns(conn, "permission_template")
        if "access_role_id" not in cols:
            return False
        return all(table_exists(conn, table) for table in PHASE26_TABLES)


def _require_phase26() -> None:
    _require_phase2()
    if not _phase26_schema_available():
        pytest.skip(
            f"ADR-053 Phase 2.6a schema missing — run: alembic upgrade head "
            f"(revisions {SCHEMA_REVISION}, {BACKFILL_REVISION})"
        )


def _load_migration_module(filename: str):
    path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(f"_adr053_mod_{filename}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_migration(conn, mod, *, direction: str) -> None:
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        getattr(mod, direction)()


def _access_role_id(conn, code: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT access_role_id
            FROM public.access_roles
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": code},
    ).scalar_one()
    return int(row)


def _role_code(conn, role_id: int) -> str:
    return str(
        conn.execute(
            text("SELECT code FROM public.roles WHERE role_id = :id"),
            {"id": int(role_id)},
        ).scalar_one()
    )


def _insert_contour_rule(
    conn,
    *,
    org_unit_id: int,
    catalog_position_id: int,
    access_role_id: int,
) -> int:
    return insert_returning_id(
        conn,
        table="permission_template_contour_rule",
        id_col="contour_rule_id",
        values={
            "client_scope_id": 1,
            "org_unit_id": int(org_unit_id),
            "catalog_position_id": int(catalog_position_id),
            "access_role_id": int(access_role_id),
            "is_active": True,
        },
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_schema_access_role_id_column_and_contour_rule_table():
    _require_phase26()
    with engine.connect() as conn:
        cols = get_columns(conn, "permission_template")
        assert "access_role_id" in cols
        assert table_exists(conn, "permission_template_contour_rule")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_schema_downgrade_removes_phase26_artifacts():
    if not _phase26_schema_available():
        pytest.skip("Phase 2.6a schema not applied")

    schema_mod = _load_migration_module(
        "m7n8o9p0q1r2_adr053_phase2_6_permission_template_binding_schema.py"
    )
    backfill_mod = _load_migration_module(
        "n8o9p0q1r2s3_adr053_phase2_6_permission_template_binding_backfill.py"
    )

    with engine.begin() as conn:
        _run_migration(conn, backfill_mod, direction="downgrade")
        _run_migration(conn, schema_mod, direction="downgrade")

    with engine.begin() as conn:
        cols = get_columns(conn, "permission_template")
        assert "access_role_id" not in cols
        assert not table_exists(conn, "permission_template_contour_rule")

    with engine.begin() as conn:
        _run_migration(conn, schema_mod, direction="upgrade")
        _run_migration(conn, backfill_mod, direction="upgrade")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_applies_contour_rule_idempotently(seed):
    _require_phase26()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_ptcr_{suffix}")
            chain = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
            )
            hr_role_id = _access_role_id(conn, "HR_ENROLLMENT_MANAGER")
            _insert_contour_rule(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                access_role_id=hr_role_id,
            )

            backfill_mod = _load_migration_module(
                "n8o9p0q1r2s3_adr053_phase2_6_permission_template_binding_backfill.py"
            )
            _run_migration(conn, backfill_mod, direction="upgrade")
            bound = conn.execute(
                text(
                    """
                    SELECT access_role_id
                    FROM public.permission_template
                    WHERE permission_template_id = :id
                    """
                ),
                {"id": int(chain["permission_template_id"])},
            ).scalar_one()
            assert int(bound) == hr_role_id

            _run_migration(conn, backfill_mod, direction="upgrade")
            bound_again = conn.execute(
                text(
                    """
                    SELECT access_role_id
                    FROM public.permission_template
                    WHERE permission_template_id = :id
                    """
                ),
                {"id": int(chain["permission_template_id"])},
            ).scalar_one()
            assert int(bound_again) == hr_role_id
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_backfill_does_not_use_users_or_grants(seed):
    _require_phase26()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    task_role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_a = _insert_position(conn, name=f"pytest_pos_a_{suffix}")
            position_b = _insert_position(conn, name=f"pytest_pos_b_{suffix}")
            chain_a = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_a,
                role_id=task_role_id,
            )
            chain_b = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_b,
            )

            observer_id = _access_role_id(conn, "ACCESS_OBSERVER")
            _insert_contour_rule(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_b,
                access_role_id=observer_id,
            )

            user_id = insert_returning_id(
                conn,
                table="users",
                id_col="user_id",
                values={
                    "full_name": f"Grant User {suffix}",
                    "login": f"grant_{suffix}@pytest.local",
                    "google_login": f"grant_{suffix}@pytest.local",
                    "role_id": task_role_id,
                    "unit_id": unit_id,
                    "is_active": True,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants (
                        access_role_id,
                        target_type,
                        target_id,
                        scope_type,
                        active_flag,
                        granted_by_user_id
                    )
                    VALUES (
                        (SELECT access_role_id FROM public.access_roles WHERE code = 'ACCESS_ADMIN'),
                        'USER',
                        :uid,
                        'GLOBAL',
                        TRUE,
                        :uid
                    )
                    """
                ),
                {"uid": user_id},
            )

            backfill_mod = _load_migration_module(
                "n8o9p0q1r2s3_adr053_phase2_6_permission_template_binding_backfill.py"
            )
            _run_migration(conn, backfill_mod, direction="upgrade")

            bound_a = conn.execute(
                text(
                    "SELECT access_role_id FROM public.permission_template WHERE permission_template_id = :id"
                ),
                {"id": int(chain_a["permission_template_id"])},
            ).scalar_one()
            bound_b = conn.execute(
                text(
                    "SELECT access_role_id FROM public.permission_template WHERE permission_template_id = :id"
                ),
                {"id": int(chain_b["permission_template_id"])},
            ).scalar_one()

            assert bound_a is None
            assert int(bound_b) == observer_id
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolver_access_role_precedence_over_role_id(seed):
    _require_phase26()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    task_role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_prec_{suffix}")
            hr_role_id = _access_role_id(conn, "HR_ENROLLMENT_MANAGER")
            chain = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                role_id=task_role_id,
            )
            conn.execute(
                text(
                    """
                    UPDATE public.permission_template
                    SET access_role_id = :access_role_id
                    WHERE permission_template_id = :id
                    """
                ),
                {
                    "access_role_id": hr_role_id,
                    "id": int(chain["permission_template_id"]),
                },
            )

            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )
            effective = resolve_effective_permissions(employee_id=employee_id, conn=conn)

            assert effective["resolved"] is True
            assert len(effective["effective_permissions"]) == 1
            perm = effective["effective_permissions"][0]
            assert perm["permission_code"] == "HR_ENROLLMENT_MANAGER"
            assert perm["source"] == "permission_template_access_role"
            assert perm["access_role_id"] == hr_role_id
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_resolver_falls_back_to_role_id_when_access_role_unset(seed):
    _require_phase26()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    task_role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_role_fb_{suffix}")
            chain = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                role_id=task_role_id,
            )
            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )
            effective = resolve_effective_permissions(employee_id=employee_id, conn=conn)
            role_code = _role_code(conn, task_role_id)

            assert effective["resolved"] is True
            assert effective["effective_permissions"][0]["permission_code"] == role_code
            assert effective["effective_permissions"][0]["source"] == "permission_template_role"
            assert chain["permission_template_id"] is not None
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_shadow_compare_unmapped_template_diagnostic():
    legacy = {
        "effective_role_code": "HR_ENROLLMENT_MANAGER",
        "matched_grants": [{"access_role_code": "HR_ENROLLMENT_MANAGER"}],
    }
    cabinet = {
        "resolved": True,
        "effective_permissions": [],
        "permission_template": {
            "access_role_id": None,
            "role_id": None,
            "is_active": True,
        },
        "reason": None,
    }

    diagnostic = compare_legacy_and_cabinet_access(
        legacy_result=legacy,
        cabinet_result=cabinet,
        user_id=17,
        employee_id=100,
        org_unit_id=44,
        catalog_position_id=64,
    )

    assert diagnostic["outcome"] == "mismatch"
    assert diagnostic["mismatch_type"] == "permission_template_unmapped"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_shadow_compare_access_role_namespace_match():
    diagnostic = compare_legacy_and_cabinet_access(
        legacy_result={
            "effective_role_code": "HR_ENROLLMENT_MANAGER",
            "matched_grants": [],
        },
        cabinet_result={
            "resolved": True,
            "effective_permissions": [
                {
                    "permission_code": "HR_ENROLLMENT_MANAGER",
                    "source": "permission_template_access_role",
                }
            ],
            "permission_template": {"access_role_id": 1, "role_id": 13},
            "reason": None,
        },
        user_id=17,
        employee_id=100,
        org_unit_id=44,
        catalog_position_id=64,
    )

    assert diagnostic["outcome"] == "match"
    assert diagnostic["mismatch_type"] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_cabinet_invariants_unchanged_after_binding(seed):
    _require_phase26()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            violation = conn.execute(
                text(
                    """
                    SELECT pc.position_cabinet_id, COUNT(pt.permission_template_id) AS c
                    FROM public.position_cabinet pc
                    LEFT JOIN public.permission_template pt
                      ON pt.position_cabinet_id = pc.position_cabinet_id
                    GROUP BY pc.position_cabinet_id
                    HAVING COUNT(pt.permission_template_id) <> 1
                    LIMIT 5
                    """
                )
            ).fetchall()
            assert violation == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_legacy_resolver_unchanged_with_shadow(seed, monkeypatch):
    _require_phase26()
    _require_access = table_exists
    with engine.begin() as conn:
        if not _require_access(conn, "access_grants"):
            pytest.skip("access_grants missing")

    monkeypatch.setenv("CABINET_ACCESS_SHADOW_MODE", "true")
    user_id = int(seed["executor_user_id"])
    result = resolve_effective_access(user_id)
    assert "access_level" in result
    assert result["user_id"] == user_id

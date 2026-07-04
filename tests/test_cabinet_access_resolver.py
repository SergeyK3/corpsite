"""Tests for ADR-051 Phase 2.3 Cabinet Access Resolver (read path only)."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.cabinet_access_resolver_service import (
    resolve_effective_permissions,
    resolve_permission_template,
    resolve_position_cabinet,
)
from tests.conftest import get_columns, insert_returning_id, table_exists

PHASE2_TABLES = (
    "org_unique_position",
    "position_cabinet",
    "permission_template",
    "legacy_position_mapping",
)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_phase2() -> None:
    with engine.begin() as conn:
        for table in PHASE2_TABLES:
            if not table_exists(conn, table):
                pytest.skip(f"ADR-050 Phase 2 table missing: {table}")


def _insert_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: dict = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(
        conn,
        table="positions",
        id_col="position_id",
        values=values,
    )


def _create_adr050_chain(
    conn,
    *,
    org_unit_id: int,
    catalog_position_id: int,
    lifecycle_status: str = "active",
    template_active: bool = True,
    role_id: int | None = None,
    include_cabinet: bool = True,
    include_template: bool = True,
    include_mapping: bool = True,
) -> dict[str, int | None]:
    oup_id = insert_returning_id(
        conn,
        table="org_unique_position",
        id_col="org_unique_position_id",
        values={
            "client_scope_id": 1,
            "org_unit_id": org_unit_id,
            "catalog_position_id": catalog_position_id,
            "lifecycle_status": lifecycle_status,
        },
    )

    pc_id: int | None = None
    if include_cabinet:
        pc_id = insert_returning_id(
            conn,
            table="position_cabinet",
            id_col="position_cabinet_id",
            values={"org_unique_position_id": oup_id},
        )

    pt_id: int | None = None
    if include_cabinet and include_template and pc_id is not None:
        template_values: dict = {
            "position_cabinet_id": pc_id,
            "is_active": template_active,
        }
        if role_id is not None:
            template_values["role_id"] = role_id
        pt_id = insert_returning_id(
            conn,
            table="permission_template",
            id_col="permission_template_id",
            values=template_values,
        )

    lpm_id: int | None = None
    if include_mapping:
        lpm_id = insert_returning_id(
            conn,
            table="legacy_position_mapping",
            id_col="legacy_position_mapping_id",
            values={
                "client_scope_id": 1,
                "org_unit_id": org_unit_id,
                "catalog_position_id": catalog_position_id,
                "org_unique_position_id": oup_id,
            },
        )

    return {
        "org_unique_position_id": oup_id,
        "position_cabinet_id": pc_id,
        "permission_template_id": pt_id,
        "legacy_position_mapping_id": lpm_id,
    }


def _create_employee(
    conn,
    *,
    org_unit_id: int,
    catalog_position_id: int,
    suffix: str,
) -> int:
    cols = get_columns(conn, "employees")
    values: dict = {
        "full_name": f"Cabinet Resolver Employee {suffix}",
        "org_unit_id": org_unit_id,
        "position_id": catalog_position_id,
        "is_active": True,
    }
    if "operational_status" in cols:
        values["operational_status"] = "active"
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_successful_cabinet_resolution(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_resolver_pos_{suffix}")
            chain = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                role_id=role_id,
            )

            cabinet = resolve_position_cabinet(
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                conn=conn,
            )
            template = resolve_permission_template(
                position_cabinet_id=int(chain["position_cabinet_id"]),
                conn=conn,
            )
            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )
            effective = resolve_effective_permissions(employee_id=employee_id, conn=conn)

            assert cabinet["resolved"] is True
            assert cabinet["position_cabinet"]["position_cabinet_id"] == chain["position_cabinet_id"]
            assert cabinet["org_unique_position"]["lifecycle_status"] == "active"

            assert template["resolved"] is True
            assert template["permission_template"]["role_id"] == role_id

            assert effective["resolved"] is True
            assert effective["position_cabinet"]["position_cabinet_id"] == chain["position_cabinet_id"]
            assert len(effective["effective_permissions"]) == 1
            assert effective["effective_permissions"][0]["permission_code"]
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_missing_cabinet_returns_empty_resolution(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_missing_cabinet_{suffix}")
            _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                include_cabinet=False,
            )

            result = resolve_position_cabinet(
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                conn=conn,
            )

            assert result["resolved"] is False
            assert result["reason"] == "position_cabinet_not_found"
            assert result["org_unique_position"] is not None
            assert result["position_cabinet"] is None
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_missing_template_returns_empty_effective_permissions(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_missing_template_{suffix}")
            chain = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                include_template=False,
            )
            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )

            template = resolve_permission_template(
                position_cabinet_id=int(chain["position_cabinet_id"]),
                conn=conn,
            )
            effective = resolve_effective_permissions(employee_id=employee_id, conn=conn)

            assert template["resolved"] is False
            assert template["reason"] == "permission_template_not_found"
            assert effective["resolved"] is False
            assert effective["reason"] == "permission_template_not_found"
            assert effective["effective_permissions"] == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_inactive_template_returns_empty_effective_permissions(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_inactive_template_{suffix}")
            chain = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                role_id=role_id,
                template_active=False,
            )
            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )

            template = resolve_permission_template(
                position_cabinet_id=int(chain["position_cabinet_id"]),
                conn=conn,
            )
            effective = resolve_effective_permissions(employee_id=employee_id, conn=conn)

            assert template["resolved"] is False
            assert template["reason"] == "permission_template_inactive"
            assert template["permission_template"]["is_active"] is False
            assert effective["resolved"] is False
            assert effective["reason"] == "permission_template_inactive"
            assert effective["effective_permissions"] == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_multiple_employees_share_same_position_cabinet(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_shared_pos_{suffix}")
            _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                role_id=role_id,
            )
            employee_a = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=f"{suffix}a",
            )
            employee_b = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=f"{suffix}b",
            )

            result_a = resolve_effective_permissions(employee_id=employee_a, conn=conn)
            result_b = resolve_effective_permissions(employee_id=employee_b, conn=conn)

            assert result_a["resolved"] is True
            assert result_b["resolved"] is True
            assert result_a["position_cabinet"] == result_b["position_cabinet"]
            assert result_a["org_unique_position"] == result_b["org_unique_position"]
            assert result_a["effective_permissions"] == result_b["effective_permissions"]
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_vacant_position_returns_cabinet_without_permissions(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_vacant_pos_{suffix}")
            chain = _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                lifecycle_status="vacant",
                role_id=role_id,
            )
            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )

            cabinet = resolve_position_cabinet(
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                conn=conn,
            )
            effective = resolve_effective_permissions(employee_id=employee_id, conn=conn)

            assert cabinet["resolved"] is True
            assert cabinet["org_unique_position"]["lifecycle_status"] == "vacant"
            assert effective["resolved"] is False
            assert effective["reason"] == "position_vacant"
            assert effective["position_cabinet"]["position_cabinet_id"] == chain["position_cabinet_id"]
            assert effective["effective_permissions"] == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_liquidated_position_returns_empty_resolution(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_liquidated_pos_{suffix}")
            _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                lifecycle_status="liquidated",
                role_id=role_id,
            )
            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )

            cabinet = resolve_position_cabinet(
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                conn=conn,
            )
            effective = resolve_effective_permissions(employee_id=employee_id, conn=conn)

            assert cabinet["resolved"] is False
            assert cabinet["reason"] == "position_liquidated"
            assert effective["resolved"] is False
            assert effective["reason"] == "position_liquidated"
            assert effective["effective_permissions"] == []
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_missing_legacy_mapping_never_raises(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_unmapped_{suffix}")

            cabinet = resolve_position_cabinet(
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                conn=conn,
            )
            effective = resolve_effective_permissions(
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                conn=conn,
            )

            assert cabinet["resolved"] is False
            assert cabinet["reason"] == "legacy_mapping_not_found"
            assert effective["resolved"] is False
            assert effective["reason"] == "legacy_mapping_not_found"
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_deterministic_resolution(seed):
    _require_phase2()
    suffix = uuid4().hex[:8]
    unit_id = int(seed["unit_id"])
    role_id = int(seed["executor_role_id"])

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            position_id = _insert_position(conn, name=f"pytest_deterministic_{suffix}")
            _create_adr050_chain(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                role_id=role_id,
            )
            employee_id = _create_employee(
                conn,
                org_unit_id=unit_id,
                catalog_position_id=position_id,
                suffix=suffix,
            )

            first = resolve_effective_permissions(employee_id=employee_id, conn=conn)
            second = resolve_effective_permissions(employee_id=employee_id, conn=conn)

            assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
                second, sort_keys=True, default=str
            )
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_runtime_auth_path_unchanged(seed):
    """Confirm legacy access resolver still works and new resolver is not wired into auth."""
    _require_phase2()

    from app.services import access_resolver_service

    assert not hasattr(access_resolver_service, "resolve_position_cabinet")
    assert callable(access_resolver_service.resolve_effective_access)

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": f"Resolver Isolation User {suffix}",
                "google_login": f"resolver_iso_{suffix}@pytest.local",
                "login": f"resolver_iso_{suffix}@pytest.local",
                "role_id": int(seed["executor_role_id"]),
                "unit_id": int(seed["unit_id"]),
                "is_active": True,
            },
        )

    try:
        result = access_resolver_service.resolve_effective_access(user_id)
        assert "access_level" in result
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": user_id})

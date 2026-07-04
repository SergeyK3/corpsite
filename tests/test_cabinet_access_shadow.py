"""Tests for ADR-051 Phase 2.4 cabinet access shadow-mode integration."""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.auth import _enrich_user_context
from app.config import cabinet_access_shadow_mode_enabled
from app.db.engine import engine
from app.services.access_resolver_service import resolve_effective_access
from app.services.cabinet_access_shadow_service import (
    compare_legacy_and_cabinet_access,
    maybe_run_cabinet_access_shadow,
)
from tests.conftest import get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_access_tables() -> None:
    with engine.begin() as conn:
        for table in ("access_roles", "access_grants", "users"):
            if not table_exists(conn, table):
                pytest.skip(f"Required table missing: {table}")


def _create_user(conn, seed, suffix: str, *, employee_id: int | None = None) -> int:
    values = {
        "full_name": f"Shadow User {suffix}",
        "google_login": f"shadow_{suffix}@pytest.local",
        "login": f"shadow_{suffix}@pytest.local",
        "role_id": int(seed["executor_role_id"]),
        "unit_id": int(seed["unit_id"]),
        "is_active": True,
    }
    if employee_id is not None:
        values["employee_id"] = int(employee_id)
    return insert_returning_id(
        conn,
        table="users",
        id_col="user_id",
        values=values,
    )


def _create_employee(conn, seed, suffix: str) -> int:
    cols = get_columns(conn, "employees")
    values: dict = {
        "full_name": f"Shadow Employee {suffix}",
        "org_unit_id": int(seed["unit_id"]),
        "is_active": True,
    }
    if "operational_status" in cols:
        values["operational_status"] = "active"
    pos_id = conn.execute(
        text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
    ).scalar_one()
    values["position_id"] = int(pos_id)
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values=values,
    )


def _create_user_with_employee(conn, seed, suffix: str) -> tuple[int, int]:
    employee_id = _create_employee(conn, seed, suffix)
    user_id = _create_user(conn, seed, suffix, employee_id=employee_id)
    return user_id, employee_id


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_feature_flag_defaults_off():
    assert cabinet_access_shadow_mode_enabled() is False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_shadow_mode_off_does_not_invoke_cabinet_resolver(seed, monkeypatch):
    _require_access_tables()
    monkeypatch.delenv("CABINET_ACCESS_SHADOW_MODE", raising=False)

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        user_id = _create_user(conn, seed, suffix)

    try:
        with patch(
            "app.services.cabinet_access_shadow_service.resolve_effective_permissions"
        ) as cabinet_resolve:
            result = resolve_effective_access(user_id)

        cabinet_resolve.assert_not_called()
        assert "access_level" in result
        assert result["user_id"] == user_id
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": user_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_shadow_mode_on_returns_legacy_result_and_invokes_cabinet(seed, monkeypatch):
    _require_access_tables()
    monkeypatch.setenv("CABINET_ACCESS_SHADOW_MODE", "true")

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        user_id, employee_id = _create_user_with_employee(conn, seed, suffix)

    cabinet_payload = {
        "resolved": True,
        "employee_id": employee_id,
        "org_unit_id": int(seed["unit_id"]),
        "catalog_position_id": 1,
        "org_unique_position": {"lifecycle_status": "active"},
        "position_cabinet": {"position_cabinet_id": 99},
        "permission_template": {"role_id": int(seed["executor_role_id"])},
        "effective_permissions": [{"permission_code": "ACCESS_NONE", "source": "permission_template_role"}],
        "reason": None,
    }

    try:
        with patch(
            "app.services.cabinet_access_shadow_service.resolve_effective_permissions",
            return_value=cabinet_payload,
        ) as cabinet_resolve:
            with patch(
                "app.services.cabinet_access_shadow_service.log_cabinet_access_shadow_result"
            ) as log_shadow:
                result = resolve_effective_access(user_id)

        cabinet_resolve.assert_called_once()
        log_shadow.assert_called_once()
        assert "access_level" in result
        assert result["user_id"] == user_id
        diagnostic = log_shadow.call_args.args[0]
        assert diagnostic["user_id"] == user_id
        assert diagnostic["legacy_permission_count"] >= 0
        assert diagnostic["cabinet_permission_count"] == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": user_id})
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_missing_cabinet_data_logs_diagnostic_without_breaking_request(seed, monkeypatch):
    _require_access_tables()
    monkeypatch.setenv("CABINET_ACCESS_SHADOW_MODE", "true")

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        user_id, employee_id = _create_user_with_employee(conn, seed, suffix)

    cabinet_payload = {
        "resolved": False,
        "employee_id": employee_id,
        "org_unit_id": int(seed["unit_id"]),
        "catalog_position_id": 123,
        "org_unique_position": None,
        "position_cabinet": None,
        "permission_template": None,
        "effective_permissions": [],
        "reason": "legacy_mapping_not_found",
    }

    try:
        with patch(
            "app.services.cabinet_access_shadow_service.resolve_effective_permissions",
            return_value=cabinet_payload,
        ):
            with patch(
                "app.services.cabinet_access_shadow_service.log_cabinet_access_shadow_result"
            ) as log_shadow:
                result = resolve_effective_access(user_id)

        assert "access_level" in result
        diagnostic = log_shadow.call_args.args[0]
        assert diagnostic["outcome"] == "cabinet_unresolved"
        assert diagnostic["mismatch_type"] == "legacy_mapping_not_found"
        assert diagnostic["cabinet_reason"] == "legacy_mapping_not_found"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": user_id})
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_matching_empty_permissions_logs_neutral_diagnostic(seed, monkeypatch):
    _require_access_tables()
    monkeypatch.setenv("CABINET_ACCESS_SHADOW_MODE", "true")

    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        user_id, employee_id = _create_user_with_employee(conn, seed, suffix)

    cabinet_payload = {
        "resolved": True,
        "employee_id": employee_id,
        "org_unit_id": int(seed["unit_id"]),
        "catalog_position_id": 1,
        "org_unique_position": {"lifecycle_status": "active"},
        "position_cabinet": {"position_cabinet_id": 1},
        "permission_template": None,
        "effective_permissions": [],
        "reason": None,
    }

    try:
        with patch(
            "app.services.cabinet_access_shadow_service.resolve_effective_permissions",
            return_value=cabinet_payload,
        ):
            with patch(
                "app.services.cabinet_access_shadow_service.log_cabinet_access_shadow_result"
            ) as log_shadow:
                legacy = resolve_effective_access(user_id)

        diagnostic = log_shadow.call_args.args[0]
        assert legacy["access_level"] == "NONE"
        assert diagnostic["outcome"] in {"match", "neutral", "mismatch"}
        assert "legacy_permission_count" in diagnostic
        assert "cabinet_permission_count" in diagnostic
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.users WHERE user_id = :id"), {"id": user_id})
            conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_compare_legacy_and_cabinet_access_match():
    legacy = {
        "effective_role_code": "ACCESS_OBSERVER",
        "matched_grants": [{"access_role_code": "ACCESS_OBSERVER"}],
    }
    cabinet = {
        "resolved": True,
        "effective_permissions": [{"permission_code": "ACCESS_OBSERVER"}],
        "reason": None,
    }

    diagnostic = compare_legacy_and_cabinet_access(
        legacy_result=legacy,
        cabinet_result=cabinet,
        user_id=1,
        employee_id=2,
        org_unit_id=3,
        catalog_position_id=4,
    )

    assert diagnostic["outcome"] == "match"
    assert diagnostic["mismatch_type"] is None
    assert diagnostic["legacy_permission_count"] == 1
    assert diagnostic["cabinet_permission_count"] == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_auth_me_contract_unchanged_with_shadow_on(seed, monkeypatch):
    from app.auth import _get_user_by_id

    user_id = int(seed["executor_user_id"])
    base_user = _get_user_by_id(user_id)
    assert base_user is not None

    monkeypatch.delenv("CABINET_ACCESS_SHADOW_MODE", raising=False)
    baseline = _enrich_user_context(dict(base_user))

    monkeypatch.setenv("CABINET_ACCESS_SHADOW_MODE", "true")
    with patch(
        "app.services.cabinet_access_shadow_service.resolve_effective_permissions",
        return_value={
            "resolved": False,
            "effective_permissions": [],
            "reason": "legacy_mapping_not_found",
            "org_unit_id": int(seed["unit_id"]),
            "catalog_position_id": None,
        },
    ):
        enriched = _enrich_user_context(dict(base_user))

    assert set(enriched.keys()) == set(baseline.keys())
    assert enriched["user_id"] == baseline["user_id"]
    assert "cabinet" not in enriched
    assert "accessible_cabinets" not in enriched


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_maybe_run_shadow_swallows_resolver_errors(seed, monkeypatch):
    monkeypatch.setenv("CABINET_ACCESS_SHADOW_MODE", "true")

    legacy = {
        "user_id": 1,
        "employee_id": 2,
        "effective_role_code": "IMPLICIT_NONE",
        "matched_grants": [],
    }

    with patch(
        "app.services.cabinet_access_shadow_service.resolve_effective_permissions",
        side_effect=RuntimeError("cabinet resolver exploded"),
    ):
        with patch(
            "app.services.cabinet_access_shadow_service.logger.exception"
        ) as log_exc:
            maybe_run_cabinet_access_shadow(user_id=1, legacy_result=legacy)

    log_exc.assert_called_once()

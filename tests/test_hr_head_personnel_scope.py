"""Personnel org-unit scope — HR head vs department head vs admin."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.directory.rbac import compute_scope
from app.security.directory_scope import is_privileged
from app.services.access_grant_service import grant_access
from app.services.org_units_service import OrgUnitsService
from app.services.personnel_visibility_resolver_service import resolve_effective_personnel_visibility
from tests.conftest import auth_headers, create_unit, insert_returning_id, table_exists
from tests.test_adr045_hr_head_auth_me import (
    _cleanup_ephemeral_user,
    _create_ephemeral_hr_head_user,
    _ensure_adr045_hr_head_role_grant,
)
from tests.test_adr042_role_targeted_grants import _db_available, _require_b2, _role_target_type_allowed

CLINICAL_GROUP_ID = 1


def _require_e1() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_visibility_assignments"):
            pytest.skip("ADR-042 E1 table missing")


def _group_id_for_unit(unit_id: int) -> int | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT group_id FROM public.org_units WHERE unit_id = :uid LIMIT 1"),
            {"uid": int(unit_id)},
        ).first()
        return int(row[0]) if row and row[0] is not None else None


def _clinical_unit_ids(limit: int = 5) -> list[int]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT unit_id
                FROM public.org_units
                WHERE group_id = :gid
                  AND COALESCE(is_active, TRUE) = TRUE
                ORDER BY unit_id
                LIMIT :limit
                """
            ),
            {"gid": CLINICAL_GROUP_ID, "limit": int(limit)},
        ).fetchall()
    return [int(r[0]) for r in rows]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_personnel_visibility_is_organization_wide(seed):
    _require_b2()
    _require_e1()
    if not _role_target_type_allowed():
        pytest.skip("ROLE target_type unavailable")

    _ensure_adr045_hr_head_role_grant()
    created = _create_ephemeral_hr_head_user(seed)
    if created is None:
        pytest.skip("HR_HEAD role missing")

    uid = int(created["user_id"])
    try:
        user_ctx = {
            "user_id": uid,
            "role_id": created["role_id"],
            "unit_id": seed["unit_id"],
        }
        vis = resolve_effective_personnel_visibility(uid, user_ctx=user_ctx)
        scope = compute_scope(uid, user_ctx)

        assert vis["has_visibility"] is True
        assert vis["organization_wide"] is True
        assert vis["scope_unit_ids"] is None
        assert vis["source"] == "access_level"
        assert scope["scope_unit_ids"] is None
        assert scope["has_personnel_visibility"] is True
        assert is_privileged(user_ctx) is False
    finally:
        _cleanup_ephemeral_user(created)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_org_units_api_includes_clinical_group(seed, client: TestClient):
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("ROLE target_type unavailable")

    _ensure_adr045_hr_head_role_grant()
    created = _create_ephemeral_hr_head_user(seed)
    if created is None:
        pytest.skip("HR_HEAD role missing")

    clinical_ids = _clinical_unit_ids(limit=3)
    if not clinical_ids:
        pytest.skip("No clinical org units in database")

    uid = int(created["user_id"])
    headers = auth_headers(uid)
    try:
        resp = client.get("/directory/org-units", params={"status": "active"}, headers=headers)
        assert resp.status_code == 200, resp.text
        all_ids = {int(row["unit_id"]) for row in resp.json().get("items") or []}
        assert clinical_ids[0] in all_ids

        resp_group = client.get(
            "/directory/org-units",
            params={"status": "active", "org_group_id": CLINICAL_GROUP_ID},
            headers=headers,
        )
        assert resp_group.status_code == 200, resp_group.text
        group_ids = {int(row["unit_id"]) for row in resp_group.json().get("items") or []}
        assert group_ids, "Clinical group must expose units for HR head"
        assert all(_group_id_for_unit(uid_) == CLINICAL_GROUP_ID for uid_ in group_ids)
        assert not any(uid_ in group_ids for uid_ in all_ids if _group_id_for_unit(uid_) != CLINICAL_GROUP_ID)
    finally:
        _cleanup_ephemeral_user(created)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_department_head_scope_stays_dept_limited(seed, client: TestClient, monkeypatch):
    _require_b2()
    _require_e1()

    with engine.begin() as conn:
        if not table_exists(conn, "access_roles"):
            pytest.skip("access registry missing")

        unit_id = create_unit(conn, "scope_mgr_unit")
        other_unit = create_unit(conn, "scope_mgr_other")
        user_id = insert_returning_id(
            conn,
            table="users",
            id_col="user_id",
            values={
                "full_name": "Scope Manager User",
                "google_login": f"scope_mgr_{unit_id}@corp.local",
                "role_id": seed["executor_role_id"],
                "unit_id": unit_id,
                "is_active": True,
            },
        )
        role_id = conn.execute(
            text("SELECT access_role_id FROM public.access_roles WHERE code = 'ACCESS_MANAGER' LIMIT 1")
        ).scalar_one()

    grant_access(
        access_role_id=int(role_id),
        target_type="USER",
        target_id=user_id,
        granted_by_user_id=seed["initiator_user_id"],
    )

    try:
        user_ctx = {"user_id": user_id, "role_id": seed["executor_role_id"], "unit_id": unit_id}
        vis = resolve_effective_personnel_visibility(user_id, user_ctx=user_ctx)
        scope = compute_scope(user_id, user_ctx)

        assert vis["organization_wide"] is False
        assert scope["scope_unit_ids"] == [unit_id]

        org = OrgUnitsService(engine)
        allowed = org.list_org_units(scope_unit_ids=scope["scope_unit_ids"], include_inactive=False)
        allowed_ids = {u.unit_id for u in allowed}
        assert unit_id in allowed_ids
        assert other_unit not in allowed_ids

        headers = auth_headers(user_id)
        resp = client.get("/directory/org-units", params={"status": "active"}, headers=headers)
        assert resp.status_code == 200, resp.text
        api_ids = {int(row["unit_id"]) for row in resp.json().get("items") or []}
        assert other_unit not in api_ids
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :uid"),
                {"uid": user_id},
            )
            conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": user_id})
            conn.execute(text("DELETE FROM public.org_units WHERE unit_id IN (:a, :b)"), {"a": unit_id, "b": other_unit})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_privileged_admin_org_units_unscoped(seed, client: TestClient, monkeypatch):
    _require_b2()
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))

    clinical_ids = _clinical_unit_ids(limit=1)
    if not clinical_ids:
        pytest.skip("No clinical org units in database")

    headers = auth_headers(seed["initiator_user_id"])
    resp = client.get(
        "/directory/org-units",
        params={"status": "active", "org_group_id": CLINICAL_GROUP_ID},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    group_ids = {int(row["unit_id"]) for row in resp.json().get("items") or []}
    assert clinical_ids[0] in group_ids

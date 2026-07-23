# tests/smoke/test_manual_bulk_delete_subtree_smoke.py
"""
Manual smoke: bulk-delete subtree preview + confirm via admin API.

Creates a disposable tree (parent → 2 children → 1 grandchild), previews deletion
for the parent only, confirms bulk delete, and verifies all four units are gone.

Requires DATABASE_URL and TEST_DATABASE_URL both pointing at corpsite_test.
Disable the default pytest DB guard plugin for this file because both URLs intentionally
target the same test database.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, create_user, get_columns, insert_returning_id, safe_delete, table_exists
from tests.smoke.conftest import REQUIRED_DATABASE, enforce_corpsite_test_smoke_guard

def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _ensure_system_admin_role(conn) -> None:
    cols = get_columns(conn, "roles")
    exists = conn.execute(
        text("SELECT 1 FROM public.roles WHERE role_id = :rid LIMIT 1"),
        {"rid": SYSTEM_ADMIN_ROLE_ID},
    ).first()
    if exists:
        return
    values: dict[str, Any] = {"role_id": SYSTEM_ADMIN_ROLE_ID, "name": "pytest_system_admin"}
    if "code" in cols:
        values["code"] = "SYSTEM_ADMIN"
    insert_returning_id(conn, table="roles", id_col="role_id", values=values)


def _ensure_org_group(conn) -> int:
    if not table_exists(conn, "org_unit_groups"):
        return 1
    row = conn.execute(
        text("SELECT group_id FROM public.org_unit_groups ORDER BY group_id LIMIT 1")
    ).scalar_one_or_none()
    if row is not None:
        return int(row)
    cols = get_columns(conn, "org_unit_groups")
    values: dict[str, Any] = {"name": f"smoke_group_{uuid4().hex[:6]}"}
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="org_unit_groups", id_col="group_id", values=values)


def _cleanup_units(*unit_ids: int | None) -> None:
    ids = [int(unit_id) for unit_id in unit_ids if unit_id is not None]
    if not ids:
        return
    with engine.begin() as conn:
        for unit_id in sorted(ids, reverse=True):
            safe_delete(conn, "org_units", "unit_id = :uid", {"uid": unit_id})


def _count_units(unit_ids: list[int]) -> int:
    if not unit_ids:
        return 0
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT COUNT(*)::int FROM public.org_units WHERE unit_id = ANY(:ids)"),
            {"ids": unit_ids},
        ).scalar_one()
    return int(row or 0)


def _create_org_unit_via_api(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    code: str,
    parent_unit_id: int,
    group_id: int,
) -> int:
    resp = client.post(
        "/admin/org-units",
        headers=headers,
        json={
            "name": name,
            "code": code,
            "parent_unit_id": int(parent_unit_id),
            "group_id": int(group_id),
        },
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["item"]["unit_id"])


@pytest.fixture
def smoke_sysadmin_headers(seed, monkeypatch):
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_USER_IDS", raising=False)
    monkeypatch.delenv("DIRECTORY_PRIVILEGED_ROLE_IDS", raising=False)
    suffix = uuid4().hex[:8]
    user_id: int | None = None
    with engine.begin() as conn:
        _ensure_system_admin_role(conn)
        user_id = create_user(
            conn,
            full_name=f"Smoke Bulk Delete Admin {suffix}",
            role_id=SYSTEM_ADMIN_ROLE_ID,
            unit_id=int(seed["unit_id"]),
        )
    headers = auth_headers(user_id)
    try:
        yield headers
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id = :uid"), {"uid": user_id})


@pytest.fixture
def smoke_org_group_id(seed):
    with engine.begin() as conn:
        return _ensure_org_group(conn)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_manual_bulk_delete_subtree_smoke(
    client: TestClient,
    seed,
    smoke_sysadmin_headers,
    smoke_org_group_id,
):
    enforce_corpsite_test_smoke_guard()

    suffix = uuid4().hex[:8]
    parent_id: int | None = None
    child_a_id: int | None = None
    child_b_id: int | None = None
    grandchild_id: int | None = None
    created_ids: list[int] = []

    try:
        anchor_parent_id = int(seed["unit_id"])
        group_id = int(smoke_org_group_id)

        parent_id = _create_org_unit_via_api(
            client,
            smoke_sysadmin_headers,
            name=f"smoke_bulk_parent_{suffix}",
            code=f"SMK_P_{suffix}",
            parent_unit_id=anchor_parent_id,
            group_id=group_id,
        )
        created_ids.append(parent_id)

        child_a_id = _create_org_unit_via_api(
            client,
            smoke_sysadmin_headers,
            name=f"smoke_bulk_child_a_{suffix}",
            code=f"SMK_CA_{suffix}",
            parent_unit_id=parent_id,
            group_id=group_id,
        )
        child_b_id = _create_org_unit_via_api(
            client,
            smoke_sysadmin_headers,
            name=f"smoke_bulk_child_b_{suffix}",
            code=f"SMK_CB_{suffix}",
            parent_unit_id=parent_id,
            group_id=group_id,
        )
        grandchild_id = _create_org_unit_via_api(
            client,
            smoke_sysadmin_headers,
            name=f"smoke_bulk_grandchild_{suffix}",
            code=f"SMK_GC_{suffix}",
            parent_unit_id=child_a_id,
            group_id=group_id,
        )
        created_ids.extend([child_a_id, child_b_id, grandchild_id])

        preview_resp = client.post(
            "/admin/org-units/bulk-delete/preview",
            headers=smoke_sysadmin_headers,
            json={"unit_ids": [parent_id]},
        )
        assert preview_resp.status_code == 200, preview_resp.text
        preview_body = preview_resp.json()
        assert len(preview_body["roots"]) == 1
        root = preview_body["roots"][0]
        assert int(root["id"]) == parent_id
        assert int(root["subtree_size"]) == 4
        descendant_ids = {int(row["id"]) for row in root["descendants"]}
        assert descendant_ids == {child_a_id, child_b_id, grandchild_id}

        delete_resp = client.post(
            "/admin/org-units/bulk-delete",
            headers=smoke_sysadmin_headers,
            json={"unit_ids": [parent_id]},
        )
        assert delete_resp.status_code == 200, delete_resp.text
        delete_body = delete_resp.json()
        assert delete_body["failed"] == []
        assert set(delete_body["deleted_ids"]) == set(created_ids)

        assert _count_units(created_ids) == 0, (
            f"Expected all smoke org units to be deleted from {REQUIRED_DATABASE}, "
            f"but {_count_units(created_ids)} remain: {created_ids}"
        )

        created_ids.clear()
    finally:
        if created_ids:
            _cleanup_units(*created_ids)

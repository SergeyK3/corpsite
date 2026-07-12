# tests/operational_orders/test_authorization_scope.py
"""Authorization and org-scope tests for Operational Orders intake API."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers, create_unit, create_user
from tests.operational_orders.conftest import _grant_user_permission, cleanup_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")

BASE = "/api/operational-orders/draft-workspaces"


def _payload(submitting_org_unit_id: int, *, author_ref: str = "author-scope-001"):
    return {
        "initiator": {"reference_type": "PERSON", "reference": "init-scope-001", "display_name": "Initiator"},
        "content_author": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Author"},
        "submitting_org_unit_id": submitting_org_unit_id,
        "blocks": [
            {
                "locale": "ru",
                "block_type": "TITLE",
                "submitted_text": "RU scope text",
                "source_type": "SUBMITTED",
                "sequence": 1,
            }
        ],
    }


@pytest.fixture
def scoped_users(seed):
    created_user_ids: list[int] = []
    created_unit_ids: list[int] = []
    with engine.begin() as conn:
        parent_row = conn.execute(
            text("SELECT parent_unit_id FROM public.org_units WHERE unit_id = :unit_id"),
            {"unit_id": int(seed["unit_id"])},
        ).mappings().first()
        parent_unit_id = parent_row["parent_unit_id"] if parent_row else None

        in_scope_child = create_unit(conn, f"pytest_oo_in_scope_{seed['unit_id']}")
        created_unit_ids.append(int(in_scope_child))
        if parent_unit_id is not None:
            conn.execute(
                text("UPDATE public.org_units SET parent_unit_id = :parent WHERE unit_id = :unit_id"),
                {"parent": int(parent_unit_id), "unit_id": int(in_scope_child)},
            )

        out_of_scope = create_unit(conn, f"pytest_oo_out_scope_{seed['unit_id']}")
        created_unit_ids.append(int(out_of_scope))
        roots = conn.execute(
            text(
                """
                SELECT unit_id
                FROM public.org_units
                WHERE parent_unit_id IS NULL
                ORDER BY unit_id
                LIMIT 1
                """
            )
        ).scalars().all()
        if roots:
            conn.execute(
                text("UPDATE public.org_units SET parent_unit_id = :parent WHERE unit_id = :unit_id"),
                {"parent": int(roots[0]), "unit_id": int(out_of_scope)},
            )

        role_id = int(seed["executor_role_id"])
        in_scope_user = create_user(
            conn,
            full_name="OO In Scope User",
            role_id=role_id,
            unit_id=int(in_scope_child),
        )
        out_scope_user = create_user(
            conn,
            full_name="OO Out Scope User",
            role_id=role_id,
            unit_id=int(out_of_scope),
        )
        created_user_ids.extend([int(in_scope_user), int(out_scope_user)])
        _grant_user_permission(conn, in_scope_user, "OPERATIONAL_ORDERS_INTAKE_CREATE")
        _grant_user_permission(conn, in_scope_user, "OPERATIONAL_ORDERS_INTAKE_READ")
        _grant_user_permission(conn, in_scope_user, "OPERATIONAL_ORDERS_INTAKE_OPERATE")

    data = {
        "in_scope_unit_id": int(in_scope_child),
        "out_of_scope_unit_id": int(out_of_scope),
        "in_scope_user_id": int(in_scope_user),
        "out_scope_user_id": int(out_scope_user),
    }
    try:
        yield data
    finally:
        with engine.begin() as conn:
            for user_id in created_user_ids:
                conn.execute(
                    text(
                        """
                        DELETE FROM public.access_grants
                        WHERE target_type = 'USER' AND target_id = :user_id
                        """
                    ),
                    {"user_id": int(user_id)},
                )
                conn.execute(
                    text("DELETE FROM public.users WHERE user_id = :user_id"),
                    {"user_id": int(user_id)},
                )
            for unit_id in created_unit_ids:
                conn.execute(
                    text("DELETE FROM public.org_units WHERE unit_id = :unit_id"),
                    {"unit_id": int(unit_id)},
                )


def test_create_forbidden_without_permission(client, seed, scoped_users):
    headers = auth_headers(scoped_users["out_scope_user_id"])
    resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "OO_FORBIDDEN"


def test_create_rejects_submitting_unit_outside_scope(client, scoped_users):
    headers = auth_headers(scoped_users["in_scope_user_id"])
    resp = client.post(
        BASE,
        json=_payload(scoped_users["out_of_scope_unit_id"]),
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "OO_FORBIDDEN"


def test_get_out_of_scope_workspace_forbidden(client, scoped_users, monkeypatch):
    creator_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=creator_headers,
    )
    assert create_resp.status_code == 200
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        other_headers = auth_headers(scoped_users["out_scope_user_id"])
        _grant = scoped_users["out_scope_user_id"]
        with engine.begin() as conn:
            _grant_user_permission(conn, _grant, "OPERATIONAL_ORDERS_INTAKE_READ")
        detail_resp = client.get(f"{BASE}/{workspace_id}", headers=other_headers)
        assert detail_resp.status_code == 403
        assert detail_resp.json()["detail"]["code"] == "OO_FORBIDDEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_list_returns_only_in_scope_workspaces(client, scoped_users):
    creator_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=creator_headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        list_resp = client.get(BASE, headers=creator_headers)
        assert list_resp.status_code == 200
        ids = {item["workspace_id"] for item in list_resp.json()["items"]}
        assert workspace_id in ids

        other_headers = auth_headers(scoped_users["out_scope_user_id"])
        with engine.begin() as conn:
            _grant_user_permission(conn, scoped_users["out_scope_user_id"], "OPERATIONAL_ORDERS_INTAKE_READ")
        other_list = client.get(BASE, headers=other_headers)
        assert other_list.status_code == 200
        other_ids = {item["workspace_id"] for item in other_list.json()["items"]}
        assert workspace_id not in other_ids
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_operate_out_of_scope_forbidden(client, scoped_users):
    creator_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=creator_headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        other_headers = auth_headers(scoped_users["out_scope_user_id"])
        with engine.begin() as conn:
            _grant_user_permission(conn, scoped_users["out_scope_user_id"], "OPERATIONAL_ORDERS_INTAKE_OPERATE")
        accept_resp = client.post(f"{BASE}/{workspace_id}/accept", json={}, headers=other_headers)
        assert accept_resp.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_cross_workspace_block_patch_returns_not_found(client, scoped_users, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(scoped_users["in_scope_user_id"]))
    headers = auth_headers(scoped_users["in_scope_user_id"])

    ws1 = client.post(BASE, json=_payload(scoped_users["in_scope_unit_id"]), headers=headers)
    ws2 = client.post(BASE, json=_payload(scoped_users["in_scope_unit_id"], author_ref="author-2"), headers=headers)
    ws1_id = ws1.json()["workspace"]["workspace_id"]
    ws2_block_id = ws2.json()["blocks"][0]["block_id"]
    try:
        patch_resp = client.patch(
            f"{BASE}/{ws1_id}/blocks/{ws2_block_id}",
            json={"workspace_effective_text": "cross workspace edit"},
            headers=headers,
        )
        assert patch_resp.status_code == 404
        assert patch_resp.json()["detail"]["code"] == "OO_BLOCK_NOT_FOUND"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, ws1_id)
            cleanup_workspace(conn, ws2.json()["workspace"]["workspace_id"])


def test_cross_workspace_clarification_resolve_not_found(client, scoped_users, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(scoped_users["in_scope_user_id"]))
    headers = auth_headers(scoped_users["in_scope_user_id"])

    ws1 = client.post(BASE, json=_payload(scoped_users["in_scope_unit_id"]), headers=headers)
    ws2 = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"], author_ref="author-clar"),
        headers=headers,
    )
    ws1_id = ws1.json()["workspace"]["workspace_id"]
    ws2_id = ws2.json()["workspace"]["workspace_id"]
    try:
        client.post(f"{BASE}/{ws2_id}/validate", json={}, headers=headers)
        clar_id = next(
            c["clarification_id"]
            for c in client.get(f"{BASE}/{ws2_id}", headers=headers).json()["clarifications"]
        )
        resolve_resp = client.post(
            f"{BASE}/{ws1_id}/clarifications/{clar_id}/resolve",
            json={"resolution_note": "wrong workspace"},
            headers=headers,
        )
        assert resolve_resp.status_code == 404
        assert resolve_resp.json()["detail"]["code"] == "OO_CLARIFICATION_NOT_FOUND"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, ws1_id)
            cleanup_workspace(conn, ws2_id)


def _count_workspace_side_effects(conn, workspace_id: int) -> tuple[int, int]:
    clar_count = conn.execute(
        text(
            """
            SELECT COUNT(1)
            FROM public.operational_order_clarifications
            WHERE workspace_id = :workspace_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).scalar()
    audit_count = conn.execute(
        text(
            """
            SELECT COUNT(1)
            FROM public.operational_order_draft_audit
            WHERE workspace_id = :workspace_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).scalar()
    return int(clar_count or 0), int(audit_count or 0)


def test_validate_forbidden_with_read_only_permission(client, scoped_users, seed):
    creator_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=creator_headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    read_only_user_id: int | None = None
    try:
        with engine.begin() as conn:
            read_only_user_id = create_user(
                conn,
                full_name="OO Read Only User",
                role_id=int(seed["executor_role_id"]),
                unit_id=scoped_users["in_scope_unit_id"],
            )
            _grant_user_permission(conn, read_only_user_id, "OPERATIONAL_ORDERS_INTAKE_READ")
        read_headers = auth_headers(read_only_user_id)
        validate_resp = client.post(f"{BASE}/{workspace_id}/validate", json={}, headers=read_headers)
        assert validate_resp.status_code == 403
        assert validate_resp.json()["detail"]["code"] == "OO_FORBIDDEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
            if read_only_user_id is not None:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :user_id"),
                    {"user_id": int(read_only_user_id)},
                )
                conn.execute(
                    text("DELETE FROM public.users WHERE user_id = :user_id"),
                    {"user_id": int(read_only_user_id)},
                )


def test_validate_allowed_with_operate_permission(client, scoped_users):
    headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    try:
        validate_resp = client.post(f"{BASE}/{workspace_id}/validate", json={}, headers=headers)
        assert validate_resp.status_code == 200
        assert "validation" in validate_resp.json()
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_validate_record_creator_out_of_scope_forbidden(client, scoped_users):
    creator_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=creator_headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    record_creator_id = create_resp.json()["workspace"]["record_creator_user_id"]
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET unit_id = :unit_id WHERE user_id = :user_id"),
                {
                    "unit_id": scoped_users["out_of_scope_unit_id"],
                    "user_id": record_creator_id,
                },
            )
            _grant_user_permission(conn, record_creator_id, "OPERATIONAL_ORDERS_INTAKE_OPERATE")
        creator_headers = auth_headers(record_creator_id)
        validate_resp = client.post(f"{BASE}/{workspace_id}/validate", json={}, headers=creator_headers)
        assert validate_resp.status_code == 403
        assert validate_resp.json()["detail"]["code"] == "OO_FORBIDDEN"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_validate_allowed_for_privileged_user(client, scoped_users, monkeypatch):
    creator_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=creator_headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    privileged_id = scoped_users["out_scope_user_id"]
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(privileged_id))
    try:
        privileged_headers = auth_headers(privileged_id)
        validate_resp = client.post(f"{BASE}/{workspace_id}/validate", json={}, headers=privileged_headers)
        assert validate_resp.status_code == 200
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_forbidden_validate_does_not_mutate_clarifications_or_audit(client, scoped_users, seed):
    creator_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=creator_headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    read_only_user_id: int | None = None
    try:
        with engine.begin() as conn:
            read_only_user_id = create_user(
                conn,
                full_name="OO Read Only Audit User",
                role_id=int(seed["executor_role_id"]),
                unit_id=scoped_users["in_scope_unit_id"],
            )
            _grant_user_permission(conn, read_only_user_id, "OPERATIONAL_ORDERS_INTAKE_READ")
            clar_before, audit_before = _count_workspace_side_effects(conn, workspace_id)
        read_headers = auth_headers(read_only_user_id)
        validate_resp = client.post(f"{BASE}/{workspace_id}/validate", json={}, headers=read_headers)
        assert validate_resp.status_code == 403
        with engine.connect() as conn:
            clar_after, audit_after = _count_workspace_side_effects(conn, workspace_id)
        assert clar_after == clar_before
        assert audit_after == audit_before
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
            if read_only_user_id is not None:
                conn.execute(
                    text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :user_id"),
                    {"user_id": int(read_only_user_id)},
                )
                conn.execute(
                    text("DELETE FROM public.users WHERE user_id = :user_id"),
                    {"user_id": int(read_only_user_id)},
                )


def test_record_creator_cannot_access_out_of_scope_workspace(client, seed, scoped_users):
    privileged_headers = auth_headers(scoped_users["in_scope_user_id"])
    create_resp = client.post(
        BASE,
        json=_payload(scoped_users["in_scope_unit_id"]),
        headers=privileged_headers,
    )
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    record_creator_id = create_resp.json()["workspace"]["record_creator_user_id"]
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET unit_id = :unit_id WHERE user_id = :user_id"),
                {
                    "unit_id": scoped_users["out_of_scope_unit_id"],
                    "user_id": record_creator_id,
                },
            )
            _grant_user_permission(conn, record_creator_id, "OPERATIONAL_ORDERS_INTAKE_READ")
        creator_headers = auth_headers(record_creator_id)
        detail_resp = client.get(f"{BASE}/{workspace_id}", headers=creator_headers)
        assert detail_resp.status_code == 403
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)

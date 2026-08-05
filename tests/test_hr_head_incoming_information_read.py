"""HR_HEAD receives only the Incoming Information read permission via ROLE grant."""
from __future__ import annotations

import runpy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.incoming_information.permissions import (
    can_control,
    can_execute,
    can_read,
    can_register,
    can_resolve,
    can_restricted_bypass,
)
from app.services.access_resolver_service import list_active_access_role_codes
from tests.conftest import auth_headers, create_unit, table_exists
from tests.incoming_information.conftest import (
    _require_ii_schema_fixture,
    assign_primary,
    cleanup_incoming_documents,
    grant_user_permission,
    ii_control_headers,
    lookup_dictionary_id,
    revoke_user_access_grants,
    utc_today,
)
from tests.test_adr042_role_targeted_grants import (
    _create_user,
    _db_available,
    _require_b2,
    _role_target_type_allowed,
)
from tests.test_adr045_hr_head_auth_me import (
    _assert_user_can_call_auth_me,
    _cleanup_ephemeral_user,
)

_ROLE_ID = 14
_ROLE_CODE = "HR_HEAD"
_ROLE_NAME = "Руководитель отдела кадров"
_PERMISSION_CODE = "INCOMING_INFO_READ"
_TEST_GRANT_REASON = "pytest: HR_HEAD read-only access to Incoming Information"
_MUTATION_OR_BYPASS_CODES = {
    "INCOMING_INFO_REGISTER",
    "INCOMING_INFO_RESOLVE",
    "INCOMING_INFO_EXECUTE",
    "INCOMING_INFO_CONTROL",
    "INCOMING_INFO_RESTRICTED_BYPASS",
}


def _load_migration() -> dict:
    return runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "g4b5c6d7e8f9_hr_head_incoming_info_read_grant.py"
        )
    )


def test_migration_grants_only_read_to_production_hr_head(monkeypatch) -> None:
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration["op"], "execute", statements.append)

    migration["upgrade"]()

    assert migration["down_revision"] == "f3a4b5c6d7e8"
    assert migration["_ROLE_ID"] == _ROLE_ID
    assert migration["_ROLE_CODE"] == _ROLE_CODE
    assert migration["_PERMISSION_CODE"] == _PERMISSION_CODE
    assert len(statements) == 1
    statement = statements[0]
    assert "ar.code = 'INCOMING_INFO_READ'" in statement
    assert "r.role_id = 14" in statement
    assert "r.code = 'HR_HEAD'" in statement
    assert all(code not in statement for code in _MUTATION_OR_BYPASS_CODES)


def _ensure_hr_head_role() -> bool:
    """Create the production role identity only when the isolated test DB lacks it."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT role_id, code, name FROM public.roles "
                "WHERE role_id = :role_id OR code = :role_code"
            ),
            {"role_id": _ROLE_ID, "role_code": _ROLE_CODE},
        ).mappings().first()
        if row is None:
            conn.execute(
                text(
                    "INSERT INTO public.roles (role_id, code, name) "
                    "VALUES (:role_id, :role_code, :role_name)"
                ),
                {
                    "role_id": _ROLE_ID,
                    "role_code": _ROLE_CODE,
                    "role_name": _ROLE_NAME,
                },
            )
            return True

    assert int(row["role_id"]) == _ROLE_ID
    assert row["code"] == _ROLE_CODE
    assert row["name"] == _ROLE_NAME
    return False


def _cleanup_test_role(created_for_test: bool) -> None:
    if not created_for_test:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.roles WHERE role_id = :role_id AND code = :role_code"),
            {"role_id": _ROLE_ID, "role_code": _ROLE_CODE},
        )


def _ensure_test_role_grant(role_id: int, granted_by_user_id: int) -> None:
    """Mirror the pending migration without touching an existing permanent grant."""
    with engine.begin() as conn:
        if not table_exists(conn, "access_grants") or not table_exists(conn, "access_roles"):
            return
        conn.execute(
            text(
                """
                INSERT INTO public.access_grants (
                    access_role_id,
                    target_type,
                    target_id,
                    granted_by_user_id,
                    reason
                )
                SELECT
                    ar.access_role_id,
                    'ROLE',
                    r.role_id,
                    :granted_by_user_id,
                    :reason
                FROM public.access_roles ar
                CROSS JOIN public.roles r
                WHERE ar.code = :permission_code
                  AND ar.is_active = TRUE
                  AND r.role_id = :role_id
                  AND r.code = :role_code
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.access_grants g
                      WHERE g.active_flag = TRUE
                        AND g.access_role_id = ar.access_role_id
                        AND g.target_type = 'ROLE'
                        AND g.target_id = r.role_id
                  )
                """
            ),
            {
                "reason": _TEST_GRANT_REASON,
                "permission_code": _PERMISSION_CODE,
                "role_id": role_id,
                "role_code": _ROLE_CODE,
                "granted_by_user_id": granted_by_user_id,
            },
        )


def _cleanup_test_role_grant(role_id: int) -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "access_grants") or not table_exists(conn, "access_roles"):
            return
        conn.execute(
            text(
                """
                DELETE FROM public.access_grants g
                USING public.access_roles ar
                WHERE g.access_role_id = ar.access_role_id
                  AND g.target_type = 'ROLE'
                  AND g.target_id = :role_id
                  AND ar.code = :permission_code
                  AND g.reason = :reason
                """
            ),
            {
                "role_id": role_id,
                "permission_code": _PERMISSION_CODE,
                "reason": _TEST_GRANT_REASON,
            },
        )


def _register_document_in_other_unit(
    client: TestClient,
    seed,
    headers: dict[str, str],
    *,
    responsible_org_unit_id: int,
    access_level: str,
    summary: str,
) -> dict:
    with engine.connect() as conn:
        document_type_id = lookup_dictionary_id(
            conn,
            table="incoming_document_types",
            code="REPORT",
        )
        receipt_channel_id = lookup_dictionary_id(
            conn,
            table="incoming_receipt_channels",
            code="IN_PERSON",
        )
    response = client.post(
        "/api/incoming-information/incoming-documents",
        headers=headers,
        json={
            "received_at": utc_today().isoformat(),
            "document_type_id": document_type_id,
            "receipt_channel_id": receipt_channel_id,
            "summary": summary,
            "access_level": access_level,
            "sender_kind": "EXTERNAL_TEXT",
            "sender_text": "HR scope test sender",
            "addressee_kind": "USER",
            "addressee_user_id": int(seed["executor_user_id"]),
            "registration_org_unit_id": int(seed["unit_id"]),
            "responsible_org_unit_id": int(responsible_org_unit_id),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_auth_me_has_only_incoming_information_read(client: TestClient, seed) -> None:
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("ROLE target_type is unavailable")

    migration = _load_migration()
    assert migration["_ROLE_ID"] == _ROLE_ID
    assert migration["_ROLE_CODE"] == _ROLE_CODE
    assert migration["_PERMISSION_CODE"] == _PERMISSION_CODE

    role_created_for_test = _ensure_hr_head_role()
    created = None
    try:
        _ensure_test_role_grant(_ROLE_ID, int(seed["initiator_user_id"]))

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            created = _create_user(conn, seed, role_id=_ROLE_ID, suffix=suffix)

        uid = int(created["user_id"])
        user_ctx = {
            "user_id": uid,
            "role_id": _ROLE_ID,
            "unit_id": int(seed["unit_id"]),
        }
        _assert_user_can_call_auth_me(uid)

        active_codes = set(list_active_access_role_codes(uid))
        assert _PERMISSION_CODE in active_codes
        assert active_codes.isdisjoint(_MUTATION_OR_BYPASS_CODES)

        response = client.get("/auth/me", headers=auth_headers(uid))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["role_id"] == _ROLE_ID
        assert body["role_name_ru"] == _ROLE_NAME
        assert body["incoming_information_permissions"] == {
            "register": False,
            "read": True,
            "resolve": False,
            "execute": False,
            "control": False,
            "restricted_bypass": False,
        }
        assert body["has_incoming_information_read"] is True

        assert can_read(user_ctx) is True
        assert can_register(user_ctx) is False
        assert can_resolve(user_ctx) is False
        assert can_execute(user_ctx) is False
        assert can_control(user_ctx) is False
        assert can_restricted_bypass(user_ctx) is False
    finally:
        if created is not None:
            _cleanup_ephemeral_user(created)
        _cleanup_test_role_grant(_ROLE_ID)
        _cleanup_test_role(role_created_for_test)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_hr_head_normal_org_wide_read_keeps_restricted_participant_policy(
    client: TestClient,
    seed,
    ii_control_headers,
) -> None:
    _require_b2()
    if not _role_target_type_allowed():
        pytest.skip("ROLE target_type is unavailable")

    role_created_for_test = _ensure_hr_head_role()
    created = None
    document_ids: list[int] = []
    ordinary_user_id = int(seed["initiator_user_id"])
    token = f"hr-head-org-wide-{uuid4().hex}"
    try:
        _ensure_test_role_grant(_ROLE_ID, ordinary_user_id)
        with engine.begin() as conn:
            other_unit_id = create_unit(conn, f"pytest_{token}")
            assert other_unit_id is not None
            created = _create_user(conn, seed, role_id=_ROLE_ID, suffix=uuid4().hex[:8])
            grant_user_permission(conn, ordinary_user_id, _PERMISSION_CODE)

        hr_head_user_id = int(created["user_id"])
        hr_headers = auth_headers(hr_head_user_id)

        normal = _register_document_in_other_unit(
            client,
            seed,
            ii_control_headers,
            responsible_org_unit_id=int(other_unit_id),
            access_level="NORMAL",
            summary=f"{token}-normal",
        )
        restricted_outsider = _register_document_in_other_unit(
            client,
            seed,
            ii_control_headers,
            responsible_org_unit_id=int(other_unit_id),
            access_level="RESTRICTED",
            summary=f"{token}-restricted-outsider",
        )
        restricted_participant = _register_document_in_other_unit(
            client,
            seed,
            ii_control_headers,
            responsible_org_unit_id=int(other_unit_id),
            access_level="RESTRICTED",
            summary=f"{token}-restricted-participant",
        )
        document_ids.extend(
            int(document["incoming_document_id"])
            for document in (normal, restricted_outsider, restricted_participant)
        )

        first_page = client.get(
            "/api/incoming-information/incoming-documents",
            headers=hr_headers,
            params={"q": token, "limit": 1, "offset": 0},
        )
        assert first_page.status_code == 200, first_page.text
        assert first_page.json()["total"] == 1
        assert [item["incoming_document_id"] for item in first_page.json()["items"]] == [
            normal["incoming_document_id"]
        ]

        beyond_page = client.get(
            "/api/incoming-information/incoming-documents",
            headers=hr_headers,
            params={"q": token, "limit": 1, "offset": 1},
        )
        assert beyond_page.status_code == 200, beyond_page.text
        assert beyond_page.json()["total"] == 1
        assert beyond_page.json()["items"] == []

        normal_detail = client.get(
            f"/api/incoming-information/incoming-documents/{normal['incoming_document_id']}",
            headers=hr_headers,
        )
        assert normal_detail.status_code == 200, normal_detail.text

        restricted_detail = client.get(
            f"/api/incoming-information/incoming-documents/{restricted_outsider['incoming_document_id']}",
            headers=hr_headers,
        )
        assert restricted_detail.status_code == 403

        ordinary_list = client.get(
            "/api/incoming-information/incoming-documents",
            headers=auth_headers(ordinary_user_id),
            params={"q": token, "limit": 100, "offset": 0},
        )
        assert ordinary_list.status_code == 200, ordinary_list.text
        assert ordinary_list.json()["total"] == 0
        ordinary_detail = client.get(
            f"/api/incoming-information/incoming-documents/{normal['incoming_document_id']}",
            headers=auth_headers(ordinary_user_id),
        )
        assert ordinary_detail.status_code == 403

        assigned = assign_primary(
            client,
            restricted_participant,
            ii_control_headers,
            primary_user_id=hr_head_user_id,
            controller_user_id=int(seed["executor_user_id"]),
        )
        participant_detail = client.get(
            f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}",
            headers=hr_headers,
        )
        assert participant_detail.status_code == 200, participant_detail.text

        visible_after_assignment = client.get(
            "/api/incoming-information/incoming-documents",
            headers=hr_headers,
            params={"q": token, "limit": 1, "offset": 0},
        )
        assert visible_after_assignment.status_code == 200, visible_after_assignment.text
        assert visible_after_assignment.json()["total"] == 2
        visible_ids = {
            item["incoming_document_id"]
            for offset in (0, 1)
            for item in client.get(
                "/api/incoming-information/incoming-documents",
                headers=hr_headers,
                params={"q": token, "limit": 1, "offset": offset},
            ).json()["items"]
        }
        assert visible_ids == {
            normal["incoming_document_id"],
            restricted_participant["incoming_document_id"],
        }
        assert restricted_outsider["incoming_document_id"] not in visible_ids
    finally:
        with engine.begin() as conn:
            if document_ids:
                cleanup_incoming_documents(conn, document_ids)
            revoke_user_access_grants(conn, ordinary_user_id)
        if created is not None:
            _cleanup_ephemeral_user(created)
        _cleanup_test_role_grant(_ROLE_ID)
        _cleanup_test_role(role_created_for_test)

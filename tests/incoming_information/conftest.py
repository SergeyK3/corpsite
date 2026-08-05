# tests/incoming_information/conftest.py
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.incoming_information.repository import DDL_REVISION, incoming_information_available
from tests.conftest import auth_headers, get_columns, table_exists


def utc_today() -> date:
    """Use UTC calendar date so received_at matches server registered_at near midnight."""
    return datetime.now(timezone.utc).date()


@pytest.fixture(autouse=True)
def _ii_isolate_env_privileged_allowlists(monkeypatch):
    """Ignore dev .env privileged allowlists unless a test sets them explicitly."""
    for name in (
        "DIRECTORY_PRIVILEGED_USER_IDS",
        "DIRECTORY_PRIVILEGED_IDS",
        "DIRECTORY_PRIVILEGED_ROLE_IDS",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session", autouse=True)
def _incoming_info_storage_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("incoming-info-attachments")
    previous = os.environ.get("INCOMING_INFO_STORAGE_ROOT")
    os.environ["INCOMING_INFO_STORAGE_ROOT"] = str(root)
    yield str(root)
    if previous is None:
        os.environ.pop("INCOMING_INFO_STORAGE_ROOT", None)
    else:
        os.environ["INCOMING_INFO_STORAGE_ROOT"] = previous


def _require_schema() -> None:
    if not incoming_information_available():
        pytest.skip(
            f"Incoming Information schema missing — run: alembic upgrade head (revision {DDL_REVISION})"
        )


@pytest.fixture(scope="session")
def _require_ii_schema_fixture():
    _require_schema()


def revoke_user_access_grants(conn, user_id: int) -> None:
    conn.execute(
        text(
            """
            DELETE FROM public.access_grants
            WHERE (target_type = 'USER' AND target_id = :user_id)
               OR granted_by_user_id = :user_id
            """
        ),
        {"user_id": int(user_id)},
    )


def ensure_system_admin_role_row(conn) -> None:
    from app.security.directory_scope import SYSTEM_ADMIN_ROLE_ID

    rid = int(SYSTEM_ADMIN_ROLE_ID)
    exists = conn.execute(
        text("SELECT 1 FROM public.roles WHERE role_id = :rid"),
        {"rid": rid},
    ).first()
    if exists:
        return
    cols = get_columns(conn, "roles")
    values: dict[str, object] = {"role_id": rid, "name": "pytest_system_admin_catalog"}
    if "code" in cols:
        values["code"] = "pytest_system_admin_catalog"
    if "created_at" in cols:
        values["created_at"] = datetime.now(timezone.utc)
    col_list = ", ".join(values.keys())
    bind_list = ", ".join(f":{k}" for k in values.keys())
    conn.execute(
        text(f"INSERT INTO public.roles ({col_list}) VALUES ({bind_list})"),
        values,
    )


def _assert_user_has_permissions(user_id: int, *permission_codes: str) -> None:
    from app.services.access_resolver_service import list_active_access_role_codes

    active = set(list_active_access_role_codes(int(user_id)))
    missing = [code for code in permission_codes if code not in active]
    assert not missing, (
        f"Seed user {user_id} missing active grants: {missing}; active={sorted(active)}"
    )


def grant_user_permission(conn, user_id: int, permission_code: str) -> None:
    """Grant permission active before test body (immediate activation only)."""
    role_row = conn.execute(
        text(
            """
            SELECT access_role_id
            FROM public.access_roles
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": permission_code},
    ).fetchone()
    if not role_row:
        raise RuntimeError(f"Missing access role seed: {permission_code}")
    conn.execute(
        text(
            """
            DELETE FROM public.access_grants g
            USING public.access_roles ar
            WHERE g.access_role_id = ar.access_role_id
              AND ar.code = :code
              AND g.target_type = 'USER'
              AND g.target_id = :user_id
            """
        ),
        {"code": permission_code, "user_id": int(user_id)},
    )
    conn.execute(
        text(
            """
            INSERT INTO public.access_grants (
                access_role_id, target_type, target_id, granted_by_user_id, reason, starts_at
            )
            VALUES (
                :access_role_id, 'USER', :user_id, :user_id, :reason,
                clock_timestamp() - interval '1 hour'
            )
            """
        ),
        {
            "access_role_id": int(role_row[0]),
            "user_id": int(user_id),
            "reason": "incoming_information tests",
        },
    )


def revoke_user_permission(conn, user_id: int, permission_code: str) -> None:
    conn.execute(
        text(
            """
            DELETE FROM public.access_grants g
            USING public.access_roles ar
            WHERE g.access_role_id = ar.access_role_id
              AND ar.code = :code
              AND g.target_type = 'USER'
              AND g.target_id = :user_id
            """
        ),
        {"code": permission_code, "user_id": int(user_id)},
    )


def cleanup_incoming_documents(conn, document_ids: list[int]) -> None:
    if not document_ids:
        return
    if not table_exists(conn, "incoming_documents"):
        return
    for table in (
        "incoming_document_transfers",
        "incoming_document_deadline_changes",
        "incoming_document_audit",
        "incoming_document_operational_order_links",
        "incoming_document_personnel_order_links",
        "incoming_document_attachments",
        "incoming_document_assignments",
    ):
        if table_exists(conn, table):
            conn.execute(
                text(f"DELETE FROM public.{table} WHERE incoming_document_id = ANY(:ids)"),
                {"ids": document_ids},
            )
    conn.execute(
        text("DELETE FROM public.incoming_documents WHERE incoming_document_id = ANY(:ids)"),
        {"ids": document_ids},
    )


def lookup_dictionary_id(conn, *, table: str, code: str) -> int:
    mapping = {
        "incoming_document_types": ("document_type_id", code),
        "incoming_receipt_channels": ("receipt_channel_id", code),
    }
    if table not in mapping:
        raise ValueError(table)
    id_col, value = mapping[table]
    row = conn.execute(
        text(
            f"""
            SELECT {id_col}
            FROM public.{table}
            WHERE code = :code
            LIMIT 1
            """
        ),
        {"code": value},
    ).first()
    if not row:
        raise RuntimeError(f"Missing dictionary seed {table}.{code}")
    return int(row[0])


@pytest.fixture
def ii_register_headers(seed, _require_ii_schema_fixture):
    user_id = int(seed["executor_user_id"])
    perms = ("INCOMING_INFO_REGISTER", "INCOMING_INFO_READ")
    with engine.begin() as conn:
        for perm in perms:
            grant_user_permission(conn, user_id, perm)
    _assert_user_has_permissions(user_id, *perms)
    yield auth_headers(user_id)


@pytest.fixture
def ii_outsider_headers(seed, _require_ii_schema_fixture):
    outsider_id = int(seed["initiator_user_id"])
    from tests.conftest import assert_non_privileged_role_id
    from app.security.directory_scope import is_privileged

    role_id = int(seed["initiator_role_id"])
    assert_non_privileged_role_id(role_id, label="initiator_role")
    assert not is_privileged({"user_id": outsider_id, "role_id": role_id})
    yield auth_headers(outsider_id)


@pytest.fixture
def ii_control_headers(seed, _require_ii_schema_fixture):
    user_id = int(seed["executor_user_id"])
    perms = (
        "INCOMING_INFO_REGISTER",
        "INCOMING_INFO_READ",
        "INCOMING_INFO_CONTROL",
        "INCOMING_INFO_EXECUTE",
        "INCOMING_INFO_RESOLVE",
    )
    with engine.begin() as conn:
        for perm in perms:
            grant_user_permission(conn, user_id, perm)
    _assert_user_has_permissions(user_id, *perms)
    yield auth_headers(user_id)


@pytest.fixture(autouse=True)
def _cleanup_seed_incoming_documents(seed, _require_ii_schema_fixture):
    yield
    user_ids = [int(seed["executor_user_id"]), int(seed["initiator_user_id"])]
    with engine.begin() as conn:
        if not table_exists(conn, "incoming_documents"):
            return
        rows = conn.execute(
            text(
                """
                SELECT incoming_document_id
                FROM public.incoming_documents
                WHERE created_by_user_id = ANY(:user_ids)
                """
            ),
            {"user_ids": user_ids},
        ).all()
        cleanup_incoming_documents(conn, [int(row[0]) for row in rows])


def register_test_document(client, seed, headers, *, access_level: str = "NORMAL") -> dict:
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="REPORT")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="IN_PERSON")
    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Workflow test document",
        "access_level": access_level,
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Sender",
        "addressee_kind": "ORG_UNIT",
        "addressee_org_unit_id": int(seed["unit_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
        "responsible_org_unit_id": int(seed["unit_id"]),
    }
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def grant_permissions(conn, user_id: int, *permission_codes: str) -> None:
    for code in permission_codes:
        grant_user_permission(conn, int(user_id), code)


def build_user_dict(user_id: int) -> dict:
    return {"user_id": int(user_id), "id": int(user_id)}


def register_restricted_document(client, seed, headers, *, addressee_user_id: int | None = None) -> dict:
    with engine.connect() as conn:
        doc_type_id = lookup_dictionary_id(conn, table="incoming_document_types", code="COMPLAINT")
        channel_id = lookup_dictionary_id(conn, table="incoming_receipt_channels", code="PAPER")
    payload = {
        "received_at": utc_today().isoformat(),
        "document_type_id": doc_type_id,
        "receipt_channel_id": channel_id,
        "summary": "Restricted workflow document",
        "access_level": "RESTRICTED",
        "sender_kind": "EXTERNAL_TEXT",
        "sender_text": "Sender",
        "addressee_kind": "USER",
        "addressee_user_id": int(addressee_user_id or seed["executor_user_id"]),
        "registration_org_unit_id": int(seed["unit_id"]),
        "responsible_org_unit_id": int(seed["unit_id"]),
    }
    response = client.post(
        "/api/incoming-information/incoming-documents",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def assign_primary(client, document: dict, headers, *, primary_user_id: int, controller_user_id: int | None = None) -> dict:
    payload = {
        "expected_version": document["row_version"],
        "primary_user_id": primary_user_id,
    }
    if controller_user_id is not None:
        payload["controller_user_id"] = controller_user_id
    response = client.post(
        f"/api/incoming-information/incoming-documents/{document['incoming_document_id']}/assign",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def advance_restricted_document_to_status(client, seed, headers, target_status: str) -> dict:
    document = register_restricted_document(client, seed, headers)
    if target_status == "REGISTERED":
        return document
    assigned = assign_primary(
        client,
        document,
        headers,
        primary_user_id=int(seed["executor_user_id"]),
        controller_user_id=int(seed["executor_user_id"]),
    )
    if target_status == "ASSIGNED":
        return assigned
    started = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
        json={"expected_version": assigned["row_version"]},
        headers=headers,
    )
    assert started.status_code == 200, started.text
    if target_status == "IN_PROGRESS":
        return started.json()
    waiting = client.post(
        f"/api/incoming-information/incoming-documents/{started.json()['incoming_document_id']}/request-information",
        json={"expected_version": started.json()["row_version"], "reason": "Need info"},
        headers=headers,
    )
    assert waiting.status_code == 200, waiting.text
    return waiting.json()


def advance_document_to_status(client, seed, headers, target_status: str) -> dict:
    document = register_test_document(client, seed, headers)
    if target_status == "REGISTERED":
        return document
    assigned = assign_primary(
        client,
        document,
        headers,
        primary_user_id=int(seed["executor_user_id"]),
        controller_user_id=int(seed["executor_user_id"]),
    )
    if target_status == "ASSIGNED":
        return assigned
    started = client.post(
        f"/api/incoming-information/incoming-documents/{assigned['incoming_document_id']}/start",
        json={"expected_version": assigned["row_version"]},
        headers=headers,
    )
    assert started.status_code == 200, started.text
    if target_status == "IN_PROGRESS":
        return started.json()
    waiting = client.post(
        f"/api/incoming-information/incoming-documents/{started.json()['incoming_document_id']}/request-information",
        json={"expected_version": started.json()["row_version"], "reason": "Need info"},
        headers=headers,
    )
    assert waiting.status_code == 200, waiting.text
    return waiting.json()

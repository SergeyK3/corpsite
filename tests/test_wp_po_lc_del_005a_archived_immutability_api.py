# tests/test_wp_po_lc_del_005a_archived_immutability_api.py
"""WP-PO-LC-DEL-005A — archived order immutability guard."""
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_lifecycle_audit_service import list_personnel_order_lifecycle_audit
from tests.conftest import auth_headers, create_role, create_user, get_columns, insert_returning_id
from tests.test_wp_po_003_personnel_orders_schema import _delete_personnel_order_audit_rows, _require_lc_del_003_schema

pytestmark = pytest.mark.usefixtures("_require_lc_del_005a_schema_fixture")


@pytest.fixture(scope="module", autouse=True)
def _require_lc_del_005a_schema_fixture():
    _require_lc_del_003_schema()


def _cleanup_order(order_id: int) -> None:
    with engine.begin() as conn:
        _delete_personnel_order_audit_rows(conn, order_id)
        conn.execute(
            text("DELETE FROM public.employee_events WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def _get_access_role_id(conn, code: str) -> int:
    return int(
        conn.execute(
            text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
            {"code": code},
        ).scalar_one()
    )


def _grant_user_permission(conn, *, user_id: int, permission_code: str) -> None:
    access_role_id = _get_access_role_id(conn, permission_code)
    insert_returning_id(
        conn,
        table="access_grants",
        id_col="grant_id",
        values={
            "access_role_id": access_role_id,
            "target_type": "USER",
            "target_id": int(user_id),
            "granted_by_user_id": int(user_id),
            "reason": f"pytest DEL005A {permission_code}",
        },
    )


def _cleanup_user(conn, user_id: int) -> None:
    conn.execute(
        text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :user_id"),
        {"user_id": int(user_id)},
    )
    conn.execute(text("DELETE FROM public.users WHERE user_id = :user_id"), {"user_id": int(user_id)})


def _create_draft_order(client, headers, *, suffix: str | None = None) -> int:
    token = suffix or uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"DEL005A-{token}",
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    return int(create_resp.json()["order"]["order_id"])


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_test_employee(conn, *, org_unit_id: int, position_id: int) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": f"DEL005A {uuid4().hex[:8]}",
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": 1.0,
            "is_active": True,
        },
    )


def _add_hire_item(client, headers, *, order_id: int, employee_id: int) -> None:
    item_resp = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json={
            "item_type_code": "HIRE",
            "employee_id": employee_id,
            "effective_date": "2026-07-12",
            "payload": {},
        },
        headers=headers,
    )
    assert item_resp.status_code == 200, item_resp.text


def _set_order_status(order_id: int, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET status = :status
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id), "status": status},
        )


def _set_archived(order_id: int, *, archived_by: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET archived_at = now(),
                    archived_by = :archived_by,
                    archive_reason_code = 'completed',
                    archive_reason_text = 'fixture archive'
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id), "archived_by": int(archived_by)},
        )


def _audit_count(order_id: int) -> int:
    return int(list_personnel_order_lifecycle_audit(order_id, limit=500, offset=0)["total"])


def _assert_order_archived_response(resp) -> None:
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "ORDER_ARCHIVED"


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def archive_user(seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del005a_archive_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL005A Archive {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_ARCHIVE")
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_RESTORE")
    try:
        yield {"user_id": user_id, "headers": auth_headers(user_id)}
    finally:
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def test_archived_registered_void_denied(client, privileged_headers, archive_user) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        _set_archived(order_id, archived_by=archive_user["user_id"])
        before = _audit_count(order_id)
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "test void archived"},
            headers=privileged_headers,
        )
        _assert_order_archived_response(resp)
        assert _audit_count(order_id) == before
    finally:
        _cleanup_order(order_id)


def test_archived_registered_apply_denied(client, privileged_headers, archive_user) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        _set_archived(order_id, archived_by=archive_user["user_id"])
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        _assert_order_archived_response(resp)
    finally:
        _cleanup_order(order_id)


def test_archived_registered_register_denied(client, privileged_headers, archive_user) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        _set_archived(order_id, archived_by=archive_user["user_id"])
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        _assert_order_archived_response(resp)
    finally:
        _cleanup_order(order_id)


def test_archived_draft_cancel_denied(client, privileged_headers, archive_user, seed) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del005a_cancel_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL005A Cancel {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_CANCEL_OWN")
    cancel_headers = auth_headers(user_id)
    order_id = _create_draft_order(client, privileged_headers, suffix=suffix)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET created_by = :created_by
                    WHERE order_id = :order_id
                    """
                ),
                {"created_by": int(user_id), "order_id": order_id},
            )
        _set_archived(order_id, archived_by=archive_user["user_id"])
        before = _audit_count(order_id)
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json={"reason_code": "created_by_mistake", "reason_text": "test"},
            headers=cancel_headers,
        )
        _assert_order_archived_response(resp)
        assert _audit_count(order_id) == before
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def test_archived_draft_update_header_denied(client, privileged_headers, archive_user) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_archived(order_id, archived_by=archive_user["user_id"])
        resp = client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={"comment": "should not apply"},
            headers=privileged_headers,
        )
        _assert_order_archived_response(resp)
    finally:
        _cleanup_order(order_id)


def test_archived_draft_create_item_denied(client, privileged_headers, archive_user) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_archived(order_id, archived_by=archive_user["user_id"])
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={"item_type_code": "HIRE", "employee_id": None},
            headers=privileged_headers,
        )
        _assert_order_archived_response(resp)
    finally:
        _cleanup_order(order_id)


def test_archived_draft_editorial_generate_denied(client, privileged_headers, archive_user) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_archived(order_id, archived_by=archive_user["user_id"])
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/editorial/generate",
            json={},
            headers=privileged_headers,
        )
        _assert_order_archived_response(resp)
    finally:
        _cleanup_order(order_id)


def test_restore_then_void_succeeds(client, privileged_headers, archive_user, seed) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    created_employee_ids: list[int] = []
    created_position_ids: list[int] = []
    try:
        with engine.begin() as conn:
            position_id = _create_position(conn, name=f"del005a-pos-{uuid4().hex[:8]}")
            created_position_ids.append(position_id)
            employee_id = _create_test_employee(
                conn,
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            created_employee_ids.append(employee_id)
        _add_hire_item(
            client,
            privileged_headers,
            order_id=order_id,
            employee_id=created_employee_ids[0],
        )
        _set_order_status(order_id, "REGISTERED")
        _set_archived(order_id, archived_by=archive_user["user_id"])

        restored = client.post(
            f"/directory/personnel-orders/{order_id}/restore",
            json={},
            headers=archive_user["headers"],
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["order"]["is_archived"] is False

        voided = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "post-restore void"},
            headers=privileged_headers,
        )
        assert voided.status_code == 200, voided.text
        assert voided.json()["order"]["status"] == "VOIDED"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            for employee_id in created_employee_ids:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            for position_id in created_position_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = :position_id"),
                    {"position_id": position_id},
                )


def test_archived_detail_and_audit_read_allowed(client, privileged_headers, archive_user) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        _set_archived(order_id, archived_by=archive_user["user_id"])

        detail = client.get(f"/directory/personnel-orders/{order_id}", headers=privileged_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["order"]["is_archived"] is True

        audit = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        assert audit.status_code == 200, audit.text
    finally:
        _cleanup_order(order_id)

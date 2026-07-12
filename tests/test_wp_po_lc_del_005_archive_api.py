# tests/test_wp_po_lc_del_005_archive_api.py
"""API tests for WP-PO-LC-DEL-005 personnel order archive / restore."""
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_lifecycle_audit_service import list_personnel_order_lifecycle_audit
from tests.conftest import auth_headers, create_role, create_user, insert_returning_id, table_exists
from tests.test_wp_po_003_personnel_orders_schema import _delete_personnel_order_audit_rows, _require_lc_del_003_schema

pytestmark = pytest.mark.usefixtures("_require_lc_del_005_schema_fixture")


@pytest.fixture(scope="module", autouse=True)
def _require_lc_del_005_schema_fixture():
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
    row = conn.execute(
        text("SELECT access_role_id FROM public.access_roles WHERE code = :code LIMIT 1"),
        {"code": code},
    ).scalar_one()
    return int(row)


def _grant_user_permission(conn, *, user_id: int, permission_code: str) -> int:
    access_role_id = _get_access_role_id(conn, permission_code)
    return insert_returning_id(
        conn,
        table="access_grants",
        id_col="grant_id",
        values={
            "access_role_id": access_role_id,
            "target_type": "USER",
            "target_id": int(user_id),
            "granted_by_user_id": int(user_id),
            "reason": f"pytest DEL005 {permission_code}",
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
            "order_number": f"DEL005-{token}",
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    return int(create_resp.json()["order"]["order_id"])


def _archive_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {"reason_code": "completed", "reason_text": "Перенесён в архив"}
    payload.update(overrides)
    return payload


def _set_order_status(order_id: int, status: str, *, void_reason: str | None = None) -> None:
    with engine.begin() as conn:
        if status == "VOIDED":
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET status = :status,
                        void_reason = COALESCE(:void_reason, void_reason, 'test void'),
                        void_kind = COALESCE(void_kind, 'CANCEL')
                    WHERE order_id = :order_id
                    """
                ),
                {
                    "order_id": int(order_id),
                    "status": status,
                    "void_reason": void_reason,
                },
            )
        else:
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


def _fetch_archive_state(order_id: int) -> Dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT status, void_kind, archived_at, archived_by, archive_reason_code
                FROM public.personnel_orders
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().one()
    return dict(row)


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def archive_user(seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del005_archive_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL005 Archive {suffix}",
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


def test_archive_registered_success(client, archive_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["order"]["status"] == "REGISTERED"
        assert body["order"]["is_archived"] is True
        assert body["order"]["archive_summary_at"]
        assert body["order"]["archive_summary_reason"]

        state = _fetch_archive_state(order_id)
        assert state["status"] == "REGISTERED"
        assert state["archived_at"] is not None
        assert state["archive_reason_code"] == "completed"

        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)["items"][0]
        assert audit["action"] == "ARCHIVE"
        assert audit["previous_status"] == "REGISTERED"
        assert audit["new_status"] == "REGISTERED"
        assert audit["reason_code"] == "completed"
    finally:
        _cleanup_order(order_id)


def test_archive_voided_success(client, archive_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "VOIDED")
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(reason_code="voided_record"),
            headers=archive_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        state = _fetch_archive_state(order_id)
        assert state["status"] == "VOIDED"
        assert state["void_kind"] in {"CANCEL", None}
        assert state["archived_at"] is not None
    finally:
        _cleanup_order(order_id)


@pytest.mark.parametrize("target_status", ["DRAFT", "READY_FOR_SIGNATURE", "SIGNED"])
def test_archive_non_archivable_status_denied(
    client,
    archive_user,
    privileged_headers,
    target_status: str,
) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, target_status)
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "ORDER_NOT_ARCHIVABLE"
    finally:
        _cleanup_order(order_id)


def test_archive_already_archived_denied(client, archive_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        first = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert first.status_code == 200, first.text
        repeat = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert repeat.status_code == 409, repeat.text
        assert repeat.json()["detail"]["code"] == "ORDER_ALREADY_ARCHIVED"
    finally:
        _cleanup_order(order_id)


def test_restore_archived_success(client, archive_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text

        restored = client.post(
            f"/directory/personnel-orders/{order_id}/restore",
            json={},
            headers=archive_user["headers"],
        )
        assert restored.status_code == 200, restored.text
        body = restored.json()
        assert body["order"]["is_archived"] is False
        assert body["order"]["status"] == "REGISTERED"

        state = _fetch_archive_state(order_id)
        assert state["archived_at"] is None
        assert state["archived_by"] is None
        assert state["archive_reason_code"] is None

        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)["items"][0]
        assert audit["action"] == "RESTORE"
        assert audit["previous_status"] == "REGISTERED"
        assert audit["new_status"] == "REGISTERED"
    finally:
        _cleanup_order(order_id)


def test_restore_non_archived_denied(client, archive_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/restore",
            json={},
            headers=archive_user["headers"],
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "ORDER_NOT_ARCHIVED"
    finally:
        _cleanup_order(order_id)


def test_archive_permission_denied(client, privileged_headers, seed) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        if not table_exists(conn, "access_grants") or not table_exists(conn, "access_roles"):
            pytest.skip("access_grants schema unavailable")
        role_id = create_role(conn, f"pytest_del005_noperm_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL005 NoPerm {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
    headers = auth_headers(user_id)
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "ARCHIVE_PERMISSION_DENIED"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def test_restore_permission_denied(client, archive_user, privileged_headers, seed) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del005_restore_denied_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL005 RestoreDenied {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_ARCHIVE")
    headers = auth_headers(user_id)
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/restore",
            json={},
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "RESTORE_PERMISSION_DENIED"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def test_archive_invalid_reason(client, archive_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json={"reason_code": "not_a_real_code"},
            headers=archive_user["headers"],
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "INVALID_ARCHIVE_REASON"
    finally:
        _cleanup_order(order_id)


def test_list_excludes_archived_by_default(client, archive_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        _set_order_status(order_id, "REGISTERED")
        archived = client.post(
            f"/directory/personnel-orders/{order_id}/archive",
            json=_archive_payload(),
            headers=archive_user["headers"],
        )
        assert archived.status_code == 200, archived.text

        hidden = client.get("/directory/personnel-orders", headers=privileged_headers)
        assert hidden.status_code == 200, hidden.text
        hidden_ids = {int(item["order_id"]) for item in hidden.json()["items"]}
        assert order_id not in hidden_ids

        visible = client.get(
            "/directory/personnel-orders?include_archived=true",
            headers=privileged_headers,
        )
        assert visible.status_code == 200, visible.text
        visible_ids = {int(item["order_id"]) for item in visible.json()["items"]}
        assert order_id in visible_ids
        visible_row = next(item for item in visible.json()["items"] if int(item["order_id"]) == order_id)
        assert visible_row["is_archived"] is True
    finally:
        _cleanup_order(order_id)


def test_cancel_regression_after_archive_filter(client, archive_user, privileged_headers, seed) -> None:
    """Archived orders remain hidden; cancel flow on active draft still works."""
    from tests.test_wp_po_lc_del_004_cancel_api import _cancel_payload, _create_draft_order as create_cancel_draft

    cancel_suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del005_cancel_{cancel_suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL005 Cancel {cancel_suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_CANCEL_OWN")
    cancel_headers = auth_headers(user_id)
    cancel_order_id = create_cancel_draft(
        client,
        privileged_headers,
        suffix=cancel_suffix,
        created_by=user_id,
    )
    try:
        resp = client.post(
            f"/directory/personnel-orders/{cancel_order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["order"]["status"] == "VOIDED"
    finally:
        _cleanup_order(cancel_order_id)
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)

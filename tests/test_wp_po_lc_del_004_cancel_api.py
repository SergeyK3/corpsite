# tests/test_wp_po_lc_del_004_cancel_api.py
"""API tests for WP-PO-LC-DEL-004 personnel order cancel command."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_lifecycle_audit_service import list_personnel_order_lifecycle_audit
from tests.conftest import auth_headers, create_role, create_user, get_columns, insert_returning_id, table_exists
from tests.test_wp_po_003_personnel_orders_schema import _delete_personnel_order_audit_rows, _require_lc_del_003_schema

pytestmark = pytest.mark.usefixtures("_require_lc_del_004_schema_fixture")


@pytest.fixture(scope="module", autouse=True)
def _require_lc_del_004_schema_fixture():
    _require_lc_del_003_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


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
            "reason": f"pytest DEL004 {permission_code}",
        },
    )


def _cleanup_user(conn, user_id: int) -> None:
    conn.execute(
        text("DELETE FROM public.access_grants WHERE target_type = 'USER' AND target_id = :user_id"),
        {"user_id": int(user_id)},
    )
    conn.execute(text("DELETE FROM public.users WHERE user_id = :user_id"), {"user_id": int(user_id)})


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
            "full_name": f"DEL004 {uuid4().hex[:8]}",
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": 1.0,
            "is_active": True,
        },
    )


def _create_unit(conn, *, name: str, parent_unit_id: Optional[int] = None) -> int:
    cols = get_columns(conn, "org_units")
    values: Dict[str, Any] = {"name": name}
    if "code" in cols:
        values["code"] = name
    if parent_unit_id is not None and "parent_unit_id" in cols:
        values["parent_unit_id"] = int(parent_unit_id)
    if "is_active" in cols:
        values["is_active"] = True
    return insert_returning_id(conn, table="org_units", id_col="unit_id", values=values)


def _create_draft_order(client, headers, *, suffix: str | None = None, created_by: int | None = None) -> int:
    token = suffix or uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"DEL004-{token}",
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = int(create_resp.json()["order"]["order_id"])
    if created_by is not None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET created_by = :created_by
                    WHERE order_id = :order_id
                    """
                ),
                {"created_by": int(created_by), "order_id": order_id},
            )
    return order_id


def _cancel_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {"reason_code": "created_by_mistake", "reason_text": "Test cancel"}
    payload.update(overrides)
    return payload


def _fetch_order_state(order_id: int) -> Dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT status, void_kind, void_reason
                FROM public.personnel_orders
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().one()
    return dict(row)


@pytest.fixture
def cancel_own_user(seed):
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del004_own_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL004 Own {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_CANCEL_OWN")
    try:
        yield {"user_id": user_id, "headers": auth_headers(user_id)}
    finally:
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


@pytest.fixture
def cancel_scope_user(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_RBAC_MODE", "dept")
    suffix = uuid4().hex[:8]
    created_units: List[int] = []
    created_users: List[int] = []
    with engine.begin() as conn:
        parent_unit = _create_unit(conn, name=f"del004_parent_{suffix}")
        child_unit = _create_unit(conn, name=f"del004_child_{suffix}", parent_unit_id=parent_unit)
        outsider_unit = _create_unit(conn, name=f"del004_outsider_{suffix}")
        created_units.extend([parent_unit, child_unit, outsider_unit])

        manager_role_id = create_role(conn, f"pytest_del004_mgr_{suffix}")
        author_role_id = create_role(conn, f"pytest_del004_author_{suffix}")

        manager_user_id = create_user(
            conn,
            full_name=f"DEL004 Manager {suffix}",
            role_id=manager_role_id,
            unit_id=parent_unit,
        )
        author_user_id = create_user(
            conn,
            full_name=f"DEL004 Author {suffix}",
            role_id=author_role_id,
            unit_id=child_unit,
        )
        outsider_user_id = create_user(
            conn,
            full_name=f"DEL004 Outsider {suffix}",
            role_id=author_role_id,
            unit_id=outsider_unit,
        )
        created_users.extend([manager_user_id, author_user_id, outsider_user_id])
        _grant_user_permission(
            conn,
            user_id=manager_user_id,
            permission_code="PERSONNEL_ORDERS_CANCEL_SCOPE",
        )

    try:
        yield {
            "manager_user_id": manager_user_id,
            "manager_headers": auth_headers(manager_user_id),
            "author_user_id": author_user_id,
            "author_headers": auth_headers(author_user_id),
            "outsider_user_id": outsider_user_id,
            "outsider_headers": auth_headers(outsider_user_id),
            "parent_unit": parent_unit,
            "child_unit": child_unit,
            "outsider_unit": outsider_unit,
        }
    finally:
        with engine.begin() as conn:
            for user_id in created_users:
                _cleanup_user(conn, user_id)
            for unit_id in reversed(created_units):
                conn.execute(
                    text("DELETE FROM public.org_units WHERE unit_id = :unit_id"),
                    {"unit_id": int(unit_id)},
                )


def test_cancel_own_draft_success(client, cancel_own_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_own_user["user_id"],
    )
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        state = _fetch_order_state(order_id)
        assert state["status"] == "VOIDED"
        assert state["void_kind"] == "CANCEL"

        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)
        assert audit["total"] == 1
        entry = audit["items"][0]
        assert entry["action"] == "CANCEL"
        assert entry["new_void_kind"] == "CANCEL"
        assert entry["reason_code"] == "created_by_mistake"
        assert entry["metadata_json"]["permission_used"] == "PERSONNEL_ORDERS_CANCEL_OWN"
        assert entry["metadata_json"]["ownership_match"] is True
    finally:
        _cleanup_order(order_id)


def test_cancel_own_foreign_draft_forbidden(client, cancel_own_user, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "CANCEL_PERMISSION_DENIED"
        assert _fetch_order_state(order_id)["status"] == "DRAFT"
        assert list_personnel_order_lifecycle_audit(order_id)["total"] == 0
    finally:
        _cleanup_order(order_id)


def test_cancel_scope_in_scope_draft_success(client, cancel_scope_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_scope_user["author_user_id"],
    )
    employee_id = 0
    pos_ids: List[int] = []
    try:
        with engine.begin() as conn:
            position_id = _create_position(conn, name=f"del004-scope-{uuid4().hex[:8]}")
            pos_ids.append(position_id)
            employee_id = _create_test_employee(
                conn,
                org_unit_id=int(cancel_scope_user["child_unit"]),
                position_id=position_id,
            )
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-12",
                "payload": {
                    "org_unit_id": int(cancel_scope_user["child_unit"]),
                    "position_id": position_id,
                    "employment_rate": 1.0,
                },
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text

        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(reason_code="no_longer_required"),
            headers=cancel_scope_user["manager_headers"],
        )
        assert resp.status_code == 200, resp.text
        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)["items"][0]
        assert audit["metadata_json"]["permission_used"] == "PERSONNEL_ORDERS_CANCEL_SCOPE"
        assert audit["metadata_json"]["scope_rule"] == "all_items_in_scope"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )


def test_cancel_scope_out_of_scope_forbidden(client, cancel_scope_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_scope_user["outsider_user_id"],
    )
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_scope_user["manager_headers"],
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "CANCEL_SCOPE_DENIED"
        assert list_personnel_order_lifecycle_audit(order_id)["total"] == 0
    finally:
        _cleanup_order(order_id)


def test_cancel_without_permissions_forbidden(client, seed, privileged_headers) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del004_noperm_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL004 NoPerm {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
    headers = auth_headers(user_id)
    order_id = _create_draft_order(client, privileged_headers)
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "CANCEL_PERMISSION_DENIED"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def test_cancel_sysadmin_without_hr_grant_forbidden(client, seed, privileged_headers) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        if not table_exists(conn, "access_grants") or not table_exists(conn, "access_roles"):
            pytest.skip("access_grants schema unavailable")
        role_id = create_role(conn, f"pytest_del004_sys_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL004 Sys {suffix}",
            role_id=role_id,
            unit_id=int(seed["unit_id"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="SYSADMIN_CABINET")
    headers = auth_headers(user_id)
    order_id = _create_draft_order(client, privileged_headers, created_by=user_id)
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=headers,
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "CANCEL_PERMISSION_DENIED"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            _cleanup_user(conn, user_id)


def test_cancel_ready_for_signature_success(client, cancel_own_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_own_user["user_id"],
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET status = 'READY_FOR_SIGNATURE'
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            )
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 200, resp.text
        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)["items"][0]
        assert audit["previous_status"] == "READY_FOR_SIGNATURE"
    finally:
        _cleanup_order(order_id)


@pytest.mark.parametrize("target_status", ["SIGNED", "REGISTERED"])
def test_cancel_signed_or_registered_rejected(client, cancel_own_user, privileged_headers, target_status) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_own_user["user_id"],
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET status = :status
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id, "status": target_status},
            )
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "ORDER_NOT_CANCELLABLE"
    finally:
        _cleanup_order(order_id)


def test_cancel_already_voided_rejected(client, cancel_own_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_own_user["user_id"],
    )
    try:
        first = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert first.status_code == 200, first.text
        repeat = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert repeat.status_code == 409, repeat.text
        assert repeat.json()["detail"]["code"] == "ORDER_ALREADY_VOIDED"
        assert list_personnel_order_lifecycle_audit(order_id)["total"] == 1
    finally:
        _cleanup_order(order_id)


def test_cancel_draft_with_approved_events_rejected(client, cancel_own_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_own_user["user_id"],
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.employee_events (
                        employee_id,
                        event_type,
                        event_class,
                        effective_date,
                        order_id,
                        lifecycle_status,
                        created_by
                    )
                    VALUES (
                        (SELECT employee_id FROM public.employees ORDER BY employee_id LIMIT 1),
                        'HIRE',
                        'FACT',
                        '2026-07-12',
                        :order_id,
                        'APPROVED',
                        :created_by
                    )
                    """
                ),
                {"order_id": order_id, "created_by": cancel_own_user["user_id"]},
            )
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "ORDER_ALREADY_APPLIED"
        assert _fetch_order_state(order_id)["status"] == "DRAFT"
    finally:
        _cleanup_order(order_id)


def test_cancel_invalid_other_reason_requires_text(client, cancel_own_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_own_user["user_id"],
    )
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json={"reason_code": "other"},
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "INVALID_CANCEL_REASON"
    finally:
        _cleanup_order(order_id)


def test_cancel_rolls_back_when_audit_insert_fails(client, cancel_own_user, privileged_headers, monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("audit insert blocked for test")

    monkeypatch.setattr(
        "app.services.personnel_orders_cancel_service.append_cancel_order_audit",
        _boom,
    )
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_own_user["user_id"],
    )
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_own_user["headers"],
        )
        assert resp.status_code == 500, resp.text
        assert _fetch_order_state(order_id)["status"] == "DRAFT"
        assert list_personnel_order_lifecycle_audit(order_id)["total"] == 0
    finally:
        _cleanup_order(order_id)


def test_legacy_void_still_works_for_draft(client, privileged_headers) -> None:
    order_id = _create_draft_order(client, privileged_headers)
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "legacy void path"},
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["order"]["status"] == "VOIDED"
    finally:
        _cleanup_order(order_id)


def test_cancel_scope_composite_multi_scope_denied(client, cancel_scope_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_scope_user["author_user_id"],
    )
    employee_ids: List[int] = []
    pos_ids: List[int] = []
    try:
        with engine.begin() as conn:
            for unit_id in (cancel_scope_user["child_unit"], cancel_scope_user["outsider_unit"]):
                position_id = _create_position(conn, name=f"del004-composite-{uuid4().hex[:8]}")
                pos_ids.append(position_id)
                employee_ids.append(
                    _create_test_employee(conn, org_unit_id=int(unit_id), position_id=position_id)
                )

        for idx, employee_id in enumerate(employee_ids, start=1):
            item_resp = client.post(
                f"/directory/personnel-orders/{order_id}/items",
                json={
                    "item_type_code": "HIRE",
                    "employee_id": employee_id,
                    "effective_date": "2026-07-12",
                    "payload": {"employment_rate": 1.0},
                    "item_number": idx,
                },
                headers=privileged_headers,
            )
            assert item_resp.status_code == 200, item_resp.text

        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_scope_user["manager_headers"],
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "CANCEL_SCOPE_DENIED"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            for employee_id in employee_ids:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )


def test_cancel_scope_empty_order_author_fallback(client, cancel_scope_user, privileged_headers) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_scope_user["author_user_id"],
    )
    try:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_scope_user["manager_headers"],
        )
        assert resp.status_code == 200, resp.text
        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)["items"][0]
        assert audit["metadata_json"]["scope_rule"] == "author_unit_fallback"
    finally:
        _cleanup_order(order_id)


def test_cancel_scope_and_own_precedence_allows_own_out_of_scope(client, cancel_scope_user, privileged_headers) -> None:
    suffix = uuid4().hex[:8]
    user_id = 0
    with engine.begin() as conn:
        role_id = create_role(conn, f"pytest_del004_both_{suffix}")
        user_id = create_user(
            conn,
            full_name=f"DEL004 Both {suffix}",
            role_id=role_id,
            unit_id=int(cancel_scope_user["parent_unit"]),
        )
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_CANCEL_OWN")
        _grant_user_permission(conn, user_id=user_id, permission_code="PERSONNEL_ORDERS_CANCEL_SCOPE")

    headers = auth_headers(user_id)
    order_id = _create_draft_order(client, privileged_headers, created_by=user_id)
    employee_id = 0
    pos_id = 0
    try:
        with engine.begin() as conn:
            pos_id = _create_position(conn, name=f"del004-both-{suffix}")
            employee_id = _create_test_employee(
                conn,
                org_unit_id=int(cancel_scope_user["outsider_unit"]),
                position_id=pos_id,
            )
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-12",
                "payload": {"employment_rate": 1.0},
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text

        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)["items"][0]
        assert audit["metadata_json"]["permission_used"] == "PERSONNEL_ORDERS_CANCEL_OWN"
        assert audit["metadata_json"]["ownership_match"] is True
        assert audit["metadata_json"]["scope_rule"] == "created_by_match"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            if pos_id:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = :position_id"),
                    {"position_id": pos_id},
                )
            _cleanup_user(conn, user_id)


def test_cancel_scope_rejects_payload_spoof_when_employee_outside_scope(
    client,
    cancel_scope_user,
    privileged_headers,
) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_scope_user["author_user_id"],
    )
    employee_id = 0
    pos_id = 0
    try:
        with engine.begin() as conn:
            pos_id = _create_position(conn, name=f"del004-spoof-{uuid4().hex[:8]}")
            employee_id = _create_test_employee(
                conn,
                org_unit_id=int(cancel_scope_user["outsider_unit"]),
                position_id=pos_id,
            )
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-12",
                "payload": {
                    "org_unit_id": int(cancel_scope_user["child_unit"]),
                    "employment_rate": 1.0,
                },
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text

        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_scope_user["manager_headers"],
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "CANCEL_SCOPE_DENIED"
        assert list_personnel_order_lifecycle_audit(order_id)["total"] == 0
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            if pos_id:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = :position_id"),
                    {"position_id": pos_id},
                )


def test_cancel_scope_uses_employee_unit_over_payload_conflict(
    client,
    cancel_scope_user,
    privileged_headers,
) -> None:
    order_id = _create_draft_order(
        client,
        privileged_headers,
        created_by=cancel_scope_user["author_user_id"],
    )
    employee_id = 0
    pos_id = 0
    try:
        with engine.begin() as conn:
            pos_id = _create_position(conn, name=f"del004-empwin-{uuid4().hex[:8]}")
            employee_id = _create_test_employee(
                conn,
                org_unit_id=int(cancel_scope_user["child_unit"]),
                position_id=pos_id,
            )
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-12",
                "payload": {
                    "org_unit_id": int(cancel_scope_user["outsider_unit"]),
                    "employment_rate": 1.0,
                },
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text

        resp = client.post(
            f"/directory/personnel-orders/{order_id}/cancel",
            json=_cancel_payload(),
            headers=cancel_scope_user["manager_headers"],
        )
        assert resp.status_code == 200, resp.text
        audit = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)["items"][0]
        assert audit["metadata_json"]["permission_used"] == "PERSONNEL_ORDERS_CANCEL_SCOPE"
        assert audit["metadata_json"]["scope_rule"] == "all_items_in_scope"
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            if employee_id:
                conn.execute(
                    text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                    {"employee_id": employee_id},
                )
            if pos_id:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = :position_id"),
                    {"position_id": pos_id},
                )

# tests/test_personnel_order_requisites_pipeline.py
"""API pipeline tests: signatory requisites from card through GET/PATCH persistence."""
from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import auth_headers
from tests.test_employee_documents_routes import _create_employee, _create_position
from tests.test_personnel_order_signatory_resolver import (
    _cleanup_director_fixtures,
    _cleanup_order,
    _create_director_user,
    _deactivate_active_director_contours,
    _ensure_director_role_id,
    _restore_active_director_contours,
)
from tests.test_wp_po_003_personnel_orders_schema import _require_schema

pytestmark = pytest.mark.usefixtures("_require_wp_po_003_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _setup_director(seed) -> tuple[int, int, List[int], List[int], List[int], List[int], List[int]]:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []

    with engine.begin() as conn:
        deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
        position_id = _create_position(conn, name=f"Директор pytest {suffix}")
        position_ids.append(position_id)
        employee_id = _create_employee(
            conn,
            full_name="Тулеутаев Мухтар Есенжанович",
            org_unit_id=int(seed["unit_id"]),
            position_id=position_id,
        )
        employee_ids.append(employee_id)
        role_id = _ensure_director_role_id(conn)
        user_id = _create_director_user(
            conn,
            employee_id=employee_id,
            role_id=role_id,
            full_name="Тулеутаев Мухтар Есенжанович",
        )
        user_ids.append(user_id)

    return (
        employee_id,
        position_id,
        user_ids,
        employee_ids,
        position_ids,
        deactivated_user_ids,
        deactivated_employee_ids,
    )


def test_card_auto_fill_and_get_persist_requisites(client, privileged_headers, seed) -> None:
    (
        employee_id,
        position_id,
        user_ids,
        employee_ids,
        position_ids,
        deactivated_user_ids,
        deactivated_employee_ids,
    ) = _setup_director(seed)
    order_id: Optional[int] = None

    try:
        create_resp = client.post(
            "/directory/personnel-orders",
            json={"order_type_code": "HIRE", "source_mode": "PAPER"},
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created = create_resp.json()
        order_id = created["order"]["order_id"]
        assert created["order"]["signed_by_employee_id"] == employee_id
        assert created["order"]["signed_by_name"] == "М. Тулеутаев"
        assert "Директор pytest" in (created["order"]["signed_by_position"] or "")

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={"order_date": "2026-07-18"},
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text

        get_resp = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert get_resp.status_code == 200, get_resp.text
        order = get_resp.json()["order"]
        assert order["order_date"] == "2026-07-18"
        assert order["signed_by_employee_id"] == employee_id
        assert order["signed_by_name"] == "М. Тулеутаев"
        assert "Директор pytest" in (order["signed_by_position"] or "")

        reopen_resp = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert reopen_resp.status_code == 200
        reopened = reopen_resp.json()["order"]
        assert reopened["order_date"] == "2026-07-18"
        assert reopened["signed_by_name"] == "М. Тулеутаев"
    finally:
        if order_id is not None:
            _cleanup_order(order_id)
        _cleanup_director_fixtures(
            user_ids=user_ids,
            employee_ids=employee_ids,
            position_ids=position_ids,
        )
        with engine.begin() as conn:
            _restore_active_director_contours(
                conn,
                deactivated_user_ids=deactivated_user_ids,
                deactivated_employee_ids=deactivated_employee_ids,
            )


def test_manual_signatory_replacement_persists_and_is_not_overwritten(
    client, privileged_headers, seed
) -> None:
    (
        employee_id,
        _position_id,
        user_ids,
        employee_ids,
        position_ids,
        deactivated_user_ids,
        deactivated_employee_ids,
    ) = _setup_director(seed)
    order_id: Optional[int] = None

    try:
        create_resp = client.post(
            "/directory/personnel-orders",
            json={"order_type_code": "HIRE", "source_mode": "PAPER", "order_date": "2026-07-18"},
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        order_id = create_resp.json()["order"]["order_id"]
        assert create_resp.json()["order"]["signed_by_name"] == "М. Тулеутаев"

        patch_resp = client.patch(
            f"/directory/personnel-orders/{order_id}",
            json={
                "signed_by_position": "И. о. директора",
                "signed_by_name": "К. Замещающий",
            },
            headers=privileged_headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        patched = patch_resp.json()["order"]
        assert patched["signed_by_position"] == "И. о. директора"
        assert patched["signed_by_name"] == "К. Замещающий"

        get_resp = client.get(
            f"/directory/personnel-orders/{order_id}",
            headers=privileged_headers,
        )
        assert get_resp.status_code == 200
        order = get_resp.json()["order"]
        assert order["signed_by_position"] == "И. о. директора"
        assert order["signed_by_name"] == "К. Замещающий"
        assert order["signed_by_name"] != "М. Тулеутаев"
        assert order["signed_by_employee_id"] == employee_id
    finally:
        if order_id is not None:
            _cleanup_order(order_id)
        _cleanup_director_fixtures(
            user_ids=user_ids,
            employee_ids=employee_ids,
            position_ids=position_ids,
        )
        with engine.begin() as conn:
            _restore_active_director_contours(
                conn,
                deactivated_user_ids=deactivated_user_ids,
                deactivated_employee_ids=deactivated_employee_ids,
            )


def test_create_without_director_does_not_fail(client, privileged_headers, seed) -> None:
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    order_id: Optional[int] = None
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids = [
                int(row[0])
                for row in conn.execute(
                    text(
                        """
                        SELECT u.user_id
                        FROM public.users u
                        JOIN public.roles r ON r.role_id = u.role_id
                        WHERE UPPER(BTRIM(r.code)) = 'DIRECTOR'
                          AND COALESCE(u.is_active, TRUE) = TRUE
                        """
                    )
                ).all()
            ]
            if deactivated_user_ids:
                conn.execute(
                    text(
                        "UPDATE public.users SET is_active = FALSE WHERE user_id = ANY(:ids)"
                    ),
                    {"ids": deactivated_user_ids},
                )
            deactivated_employee_ids = [
                int(row[0])
                for row in conn.execute(
                    text(
                        """
                        SELECT e.employee_id
                        FROM public.employees e
                        JOIN public.positions p ON p.position_id = e.position_id
                        WHERE LOWER(BTRIM(p.name)) = 'директор'
                          AND COALESCE(e.is_active, TRUE) = TRUE
                        """
                    )
                ).all()
            ]
            if deactivated_employee_ids:
                conn.execute(
                    text(
                        "UPDATE public.employees SET is_active = FALSE WHERE employee_id = ANY(:ids)"
                    ),
                    {"ids": deactivated_employee_ids},
                )

        create_resp = client.post(
            "/directory/personnel-orders",
            json={"order_type_code": "HIRE", "source_mode": "PAPER"},
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        order_id = create_resp.json()["order"]["order_id"]
        order = create_resp.json()["order"]
        assert not (order.get("signed_by_name") or "").strip()
        assert not (order.get("signed_by_position") or "").strip()
        assert order.get("signed_by_employee_id") is None
    finally:
        if order_id is not None:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            if deactivated_user_ids:
                conn.execute(
                    text(
                        "UPDATE public.users SET is_active = TRUE WHERE user_id = ANY(:ids)"
                    ),
                    {"ids": deactivated_user_ids},
                )
            if deactivated_employee_ids:
                conn.execute(
                    text(
                        "UPDATE public.employees SET is_active = TRUE WHERE employee_id = ANY(:ids)"
                    ),
                    {"ids": deactivated_employee_ids},
                )
        _cleanup_director_fixtures(
            user_ids=user_ids,
            employee_ids=employee_ids,
            position_ids=position_ids,
        )

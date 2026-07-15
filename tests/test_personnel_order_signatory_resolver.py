# tests/test_personnel_order_signatory_resolver.py
"""Tests for personnel order default signatory resolution."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_signatory_resolver import (
    SOURCE_HR_DIRECTOR_ASSIGNMENT,
    SOURCE_PLATFORM_ROLE,
    SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE,
    WARNING_AMBIGUOUS_DIRECTORS,
    WARNING_AMBIGUOUS_EMPLOYEES,
    WARNING_NAME_BRIDGE_BLOCKED,
    WARNING_NOT_FOUND,
    apply_default_signatory_if_needed,
    format_signatory_fio_short,
    resolve_default_personnel_order_signatory,
    signatory_fields_all_empty,
    signatory_fields_provided,
)
from tests.conftest import auth_headers, create_role, get_columns, insert_returning_id
from tests.test_employee_documents_routes import _create_employee, _create_position
from tests.test_wp_po_003_personnel_orders_schema import (
    _delete_personnel_order_audit_rows,
    _require_schema,
)

pytestmark = pytest.mark.usefixtures("_require_wp_po_003_schema")


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()


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
            text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def _ensure_director_role_id(conn) -> int:
    cols = get_columns(conn, "roles")
    if "code" in cols:
        existing = conn.execute(
            text(
                """
                SELECT role_id
                FROM public.roles
                WHERE UPPER(BTRIM(code)) = 'DIRECTOR'
                ORDER BY role_id
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
        if existing is not None:
            return int(existing)
    return create_role(conn, "DIRECTOR")


def _create_director_user(
    conn,
    *,
    employee_id: Optional[int],
    role_id: int,
    full_name: str,
) -> int:
    cols = get_columns(conn, "users")
    values: Dict[str, Any] = {
        "full_name": full_name,
        "google_login": f"pytest_director_{uuid4().hex[:10]}@corp.local",
        "role_id": role_id,
        "is_active": True,
    }
    if "employee_id" in cols and employee_id is not None:
        values["employee_id"] = int(employee_id)
    if "login" in cols:
        values["login"] = f"pytest_director_{uuid4().hex[:8]}"
    return insert_returning_id(conn, table="users", id_col="user_id", values=values)


def _ensure_director_position_id(conn) -> int:
    existing = conn.execute(
        text(
            """
            SELECT position_id
            FROM public.positions
            WHERE LOWER(BTRIM(name)) = 'директор'
            ORDER BY position_id
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if existing is not None:
        return int(existing)
    return _create_position(conn, name="Директор")


def _deactivate_active_director_contours(conn) -> Tuple[List[int], List[int]]:
    """Temporarily hide seed/production director rows for isolated resolver tests."""
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
            text("UPDATE public.users SET is_active = FALSE WHERE user_id = ANY(:ids)"),
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
    return deactivated_user_ids, deactivated_employee_ids


def _restore_active_director_contours(
    conn,
    *,
    deactivated_user_ids: List[int],
    deactivated_employee_ids: List[int],
) -> None:
    if deactivated_user_ids:
        conn.execute(
            text("UPDATE public.users SET is_active = TRUE WHERE user_id = ANY(:ids)"),
            {"ids": deactivated_user_ids},
        )
    if deactivated_employee_ids:
        conn.execute(
            text(
                "UPDATE public.employees SET is_active = TRUE WHERE employee_id = ANY(:ids)"
            ),
            {"ids": deactivated_employee_ids},
        )


def _cleanup_director_fixtures(
    *,
    user_ids: List[int],
    employee_ids: List[int],
    position_ids: List[int],
) -> None:
    with engine.begin() as conn:
        if user_ids and get_columns(conn, "users"):
            conn.execute(
                text("DELETE FROM public.users WHERE user_id = ANY(:ids)"),
                {"ids": [int(x) for x in user_ids]},
            )
        if employee_ids:
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
                {"ids": [int(x) for x in employee_ids]},
            )
        if position_ids:
            conn.execute(
                text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                {"ids": [int(x) for x in position_ids]},
            )


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("Тулеутаев Мухтар Есенжанович", "М. Тулеутаев"),
        ("Алия Садыкова", "А. Садыкова"),
        ("Иванова-Петрова Мария Сергеевна", "М. Иванова-Петрова"),
        ("  Тулеутаев   Мухтар  ", "М. Тулеутаев"),
        ("Тулеутаев", "Тулеутаев"),
        ("", ""),
    ],
)
def test_format_signatory_fio_short(full_name: str, expected: str) -> None:
    assert format_signatory_fio_short(full_name) == expected


def test_signatory_field_helpers() -> None:
    assert signatory_fields_provided(signed_by_name=" М. Тулеутаев ")
    assert signatory_fields_provided(signed_by_position="Директор")
    assert signatory_fields_provided(signed_by_employee_id=42)
    assert not signatory_fields_provided()
    assert signatory_fields_all_empty()
    assert not signatory_fields_all_empty(signed_by_name="x")


def test_resolve_single_director_via_platform_role(seed) -> None:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
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

            resolution = resolve_default_personnel_order_signatory(conn)

        assert resolution.employee_id == employee_id
        assert resolution.signed_by_name == "М. Тулеутаев"
        assert resolution.signed_by_position == "Директор"
        assert resolution.source == SOURCE_PLATFORM_ROLE
        assert resolution.warning is None
    finally:
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


def test_resolve_director_via_platform_role_without_user_employee_link(seed) -> None:
    """ADR-044 gap: DIRECTOR user without users.employee_id matches employee by full_name."""
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
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
                employee_id=None,
                role_id=role_id,
                full_name="Тулеутаев Мухтар Есенжанович",
            )
            user_ids.append(user_id)

            resolution = resolve_default_personnel_order_signatory(conn)

        assert resolution.employee_id == employee_id
        assert resolution.signed_by_name == "М. Тулеутаев"
        assert resolution.signed_by_position == "Директор"
        assert resolution.source == SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE
        assert resolution.warning is None
    finally:
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


def test_resolve_multiple_directors_is_ambiguous(seed) -> None:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
            role_id = _ensure_director_role_id(conn)

            for index in range(2):
                employee_id = _create_employee(
                    conn,
                    full_name=f"Директор{index} Тестов Тестович",
                    org_unit_id=int(seed["unit_id"]),
                    position_id=position_id,
                )
                employee_ids.append(employee_id)
                user_id = _create_director_user(
                    conn,
                    employee_id=employee_id,
                    role_id=role_id,
                    full_name=f"Директор{index} Тестов Тестович",
                )
                user_ids.append(user_id)

            resolution = resolve_default_personnel_order_signatory(conn)

        assert resolution.employee_id is None
        assert resolution.signed_by_name is None
        assert resolution.signed_by_position is None
        assert resolution.warning is not None
        assert "несколько" in resolution.warning.lower()
    finally:
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


def test_resolve_director_missing_returns_warning(seed) -> None:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
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
                        """
                        UPDATE public.users
                        SET is_active = FALSE
                        WHERE user_id = ANY(:ids)
                        """
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
                        WHERE LOWER(BTRIM(p.name)) = :position_name
                          AND COALESCE(e.is_active, TRUE) = TRUE
                        """
                    ),
                    {"position_name": "директор"},
                ).all()
            ]
            if deactivated_employee_ids:
                conn.execute(
                    text(
                        """
                        UPDATE public.employees
                        SET is_active = FALSE
                        WHERE employee_id = ANY(:ids)
                        """
                    ),
                    {"ids": deactivated_employee_ids},
                )

            position_id = _create_position(conn, name=f"Экономист pytest {suffix}")
            position_ids.append(position_id)
            employee_id = _create_employee(
                conn,
                full_name="Сотрудник Без Роли",
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            employee_ids.append(employee_id)

            resolution = resolve_default_personnel_order_signatory(conn)

        assert resolution.employee_id is None
        assert resolution.warning is not None
        assert "вручную" in resolution.warning.lower()
    finally:
        with engine.begin() as conn:
            if deactivated_user_ids:
                conn.execute(
                    text(
                        """
                        UPDATE public.users
                        SET is_active = TRUE
                        WHERE user_id = ANY(:ids)
                        """
                    ),
                    {"ids": deactivated_user_ids},
                )
            if deactivated_employee_ids:
                conn.execute(
                    text(
                        """
                        UPDATE public.employees
                        SET is_active = TRUE
                        WHERE employee_id = ANY(:ids)
                        """
                    ),
                    {"ids": deactivated_employee_ids},
                )
        _cleanup_director_fixtures(
            user_ids=user_ids,
            employee_ids=employee_ids,
            position_ids=position_ids,
        )


def test_apply_default_signatory_does_not_override_user_values(seed) -> None:
    with engine.begin() as conn:
        employee_id, signed_by_name, signed_by_position, warning = apply_default_signatory_if_needed(
            signed_by_employee_id=99,
            signed_by_name="И. о. директора",
            signed_by_position="И. о. директора",
            conn=conn,
        )

    assert employee_id == 99
    assert signed_by_name == "И. о. директора"
    assert signed_by_position == "И. о. директора"
    assert warning is None


def test_create_draft_auto_fills_signatory_from_director(client, privileged_headers, seed) -> None:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    order_id: Optional[int] = None
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
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
        assert created["order"]["signed_by_position"] == "Директор"
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


def test_create_draft_respects_explicit_signatory(client, privileged_headers, seed) -> None:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    order_id: Optional[int] = None
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
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

        create_resp = client.post(
            "/directory/personnel-orders",
            json={
                "order_type_code": "HIRE",
                "source_mode": "PAPER",
                "signed_by_name": "И. о. директора",
                "signed_by_position": "И. о. директора",
            },
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created = create_resp.json()
        order_id = created["order"]["order_id"]
        assert created["order"]["signed_by_employee_id"] is None
        assert created["order"]["signed_by_name"] == "И. о. директора"
        assert created["order"]["signed_by_position"] == "И. о. директора"
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


def test_existing_order_snapshot_not_changed_after_director_swap(client, privileged_headers, seed) -> None:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    order_id: Optional[int] = None
    new_order_id: Optional[int] = None
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
            first_employee_id = _create_employee(
                conn,
                full_name="Тулеутаев Мухтар Есенжанович",
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            employee_ids.append(first_employee_id)
            role_id = _ensure_director_role_id(conn)
            first_user_id = _create_director_user(
                conn,
                employee_id=first_employee_id,
                role_id=role_id,
                full_name="Тулеутаев Мухтар Есенжанович",
            )
            user_ids.append(first_user_id)

        create_resp = client.post(
            "/directory/personnel-orders",
            json={"order_type_code": "HIRE", "source_mode": "PAPER"},
            headers=privileged_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        created = create_resp.json()
        order_id = created["order"]["order_id"]
        assert created["order"]["signed_by_employee_id"] == first_employee_id
        assert created["order"]["signed_by_name"] == "М. Тулеутаев"

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE public.users SET is_active = FALSE WHERE user_id = :user_id"),
                {"user_id": first_user_id},
            )
            second_employee_id = _create_employee(
                conn,
                full_name="Садыкова Алия Болатовна",
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            employee_ids.append(second_employee_id)
            second_user_id = _create_director_user(
                conn,
                employee_id=second_employee_id,
                role_id=role_id,
                full_name="Садыкова Алия Болатовна",
            )
            user_ids.append(second_user_id)

        detail_resp = client.get(f"/directory/personnel-orders/{order_id}", headers=privileged_headers)
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()
        assert detail["order"]["signed_by_employee_id"] == first_employee_id
        assert detail["order"]["signed_by_name"] == "М. Тулеутаев"

        new_resp = client.post(
            "/directory/personnel-orders",
            json={"order_type_code": "HIRE", "source_mode": "PAPER"},
            headers=privileged_headers,
        )
        assert new_resp.status_code == 201, new_resp.text
        new_order = new_resp.json()["order"]
        new_order_id = int(new_order["order_id"])
        assert new_order["signed_by_employee_id"] == second_employee_id
        assert new_order["signed_by_name"] == "А. Садыкова"
    finally:
        if new_order_id is not None:
            _cleanup_order(new_order_id)
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


def test_signatory_default_endpoint(client, privileged_headers, seed) -> None:
    suffix = uuid4().hex[:8]
    user_ids: List[int] = []
    employee_ids: List[int] = []
    position_ids: List[int] = []
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
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

        resp = client.get(
            "/directory/personnel-orders/signatory-default",
            headers=privileged_headers,
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["signed_by_employee_id"] == employee_id
        assert payload["signed_by_name"] == "М. Тулеутаев"
        assert payload["signed_by_position"] == "Директор"
        assert payload["source"] == SOURCE_PLATFORM_ROLE
    finally:
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


def test_name_bridge_rejects_inactive_employee_with_matching_fio(seed) -> None:
    user_ids: List[int] = []
    employee_ids: List[int] = []
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
            employee_id = _create_employee(
                conn,
                full_name="Тулеутаев Мухтар Есенжанович",
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            employee_ids.append(employee_id)
            conn.execute(
                text("UPDATE public.employees SET is_active = FALSE WHERE employee_id = :id"),
                {"id": employee_id},
            )
            role_id = _ensure_director_role_id(conn)
            user_ids.append(
                _create_director_user(
                    conn,
                    employee_id=None,
                    role_id=role_id,
                    full_name="Тулеутаев Мухтар Есенжанович",
                )
            )
            resolution = resolve_default_personnel_order_signatory(conn)

        assert not resolution.resolved
        assert resolution.warning is not None
    finally:
        _cleanup_director_fixtures(user_ids=user_ids, employee_ids=employee_ids, position_ids=[])
        with engine.begin() as conn:
            _restore_active_director_contours(
                conn,
                deactivated_user_ids=deactivated_user_ids,
                deactivated_employee_ids=deactivated_employee_ids,
            )


def test_name_bridge_rejects_duplicate_employee_names(seed) -> None:
    user_ids: List[int] = []
    employee_ids: List[int] = []
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
            for _ in range(2):
                employee_ids.append(
                    _create_employee(
                        conn,
                        full_name="Тулеутаев  Мухтар   Есенжанович",
                        org_unit_id=int(seed["unit_id"]),
                        position_id=position_id,
                    )
                )
            role_id = _ensure_director_role_id(conn)
            user_ids.append(
                _create_director_user(
                    conn,
                    employee_id=None,
                    role_id=role_id,
                    full_name="тулеутаев мухтар есенжанович",
                )
            )
            resolution = resolve_default_personnel_order_signatory(conn)

        assert not resolution.resolved
        assert resolution.warning == WARNING_AMBIGUOUS_EMPLOYEES
        assert resolution.source == SOURCE_PLATFORM_ROLE_VERIFIED_NAME_BRIDGE
    finally:
        _cleanup_director_fixtures(user_ids=user_ids, employee_ids=employee_ids, position_ids=[])
        with engine.begin() as conn:
            _restore_active_director_contours(
                conn,
                deactivated_user_ids=deactivated_user_ids,
                deactivated_employee_ids=deactivated_employee_ids,
            )


def test_hr_fallback_resolves_without_platform_user_linkage(seed) -> None:
    employee_ids: List[int] = []
    deactivated_user_ids: List[int] = []
    deactivated_employee_ids: List[int] = []

    try:
        with engine.begin() as conn:
            deactivated_user_ids, deactivated_employee_ids = _deactivate_active_director_contours(conn)
            position_id = _ensure_director_position_id(conn)
            employee_id = _create_employee(
                conn,
                full_name="Садыкова Алия Болатовна",
                org_unit_id=int(seed["unit_id"]),
                position_id=position_id,
            )
            employee_ids.append(employee_id)
            resolution = resolve_default_personnel_order_signatory(conn)

        assert resolution.resolved
        assert resolution.employee_id == employee_id
        assert resolution.source == SOURCE_HR_DIRECTOR_ASSIGNMENT
    finally:
        _cleanup_director_fixtures(user_ids=[], employee_ids=employee_ids, position_ids=[])
        with engine.begin() as conn:
            _restore_active_director_contours(
                conn,
                deactivated_user_ids=deactivated_user_ids,
                deactivated_employee_ids=deactivated_employee_ids,
            )

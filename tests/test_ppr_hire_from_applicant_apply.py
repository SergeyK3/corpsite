"""Integration tests: applicant HIRE apply without pre-existing Employee."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE, HR_RELATIONSHIP_EMPLOYED
from app.services.ppr_candidate_service import list_ppr_applicants, save_intended_employment
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema
from tests.test_wp_po_003_personnel_orders_schema import (
    _delete_personnel_order_audit_rows,
    _require_schema,
)

pytestmark = [
    pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL unavailable"),
    pytest.mark.usefixtures("_require_wp_po_003_schema"),
]


@pytest.fixture(scope="module", autouse=True)
def _require_wp_po_003_schema():
    _require_schema()
    require_ppr_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _ensure_candidate_envelope(conn, person_id: int) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.personnel_record_metadata (
                person_id, ppr_lifecycle_state, hr_relationship_context, version
            )
            VALUES (:person_id, 'CREATED', :ctx, 1)
            ON CONFLICT (person_id) DO UPDATE
            SET hr_relationship_context = EXCLUDED.hr_relationship_context,
                updated_at = now()
            """
        ),
        {"person_id": person_id, "ctx": HR_RELATIONSHIP_CANDIDATE},
    )


def _create_applicant(
    conn,
    *,
    suffix: str,
    org_unit_id: int,
    position_id: int,
    intended_rate: float,
) -> int:
    person_id = insert_person(conn, full_name=f"Applicant Hire {suffix}")
    cols = get_columns(conn, "persons")
    if "iin" in cols:
        digits = "".join(ch for ch in suffix if ch.isdigit())
        iin = (f"8{digits}").ljust(12, "0")[:12]
        conn.execute(
            text("UPDATE public.persons SET iin = :iin WHERE person_id = :person_id"),
            {"person_id": person_id, "iin": iin},
        )
    _ensure_candidate_envelope(conn, person_id)
    save_intended_employment(
        conn,
        person_id=person_id,
        org_group_id=None,
        org_unit_id=org_unit_id,
        position_id=position_id,
        employment_rate=intended_rate,
    )
    return person_id


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


def _create_registered_hire_order_for_person(
    client,
    privileged_headers,
    *,
    person_id: int,
    org_unit_id: int,
    position_id: int,
    employment_rate: float,
    effective_date: str = "2026-07-16",
) -> tuple[int, int]:
    suffix = uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"HIRE-PERSON-{suffix}",
            "order_date": effective_date,
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    item_resp = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json={
            "item_type_code": "HIRE",
            "employee_id": None,
            "effective_date": effective_date,
            "payload": {
                "person_id": person_id,
                "org_unit_id": org_unit_id,
                "position_id": position_id,
                "employment_rate": employment_rate,
            },
        },
        headers=privileged_headers,
    )
    assert item_resp.status_code == 200, item_resp.text
    item_id = item_resp.json()["items"][0]["item_id"]

    register_resp = client.post(
        f"/directory/personnel-orders/{order_id}/register",
        json={"target_status": "REGISTERED"},
        headers=privileged_headers,
    )
    assert register_resp.status_code == 200, register_resp.text
    return order_id, item_id


def test_hire_apply_creates_employee_from_person(client, privileged_headers, seed):
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0

    try:
        with engine.begin() as conn:
            org_unit_id = int(seed["unit_id"])
            position_id = conn.execute(
                text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
            ).scalar_one()
            person_id = _create_applicant(
                conn,
                suffix=suffix,
                org_unit_id=org_unit_id,
                position_id=int(position_id),
                intended_rate=1.0,
            )
            person_ids.append(person_id)

        order_id, item_id = _create_registered_hire_order_for_person(
            client,
            privileged_headers,
            person_id=person_id,
            org_unit_id=org_unit_id,
            position_id=int(position_id),
            employment_rate=1.0,
        )

        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        body = apply_resp.json()
        assert len(body["events"]) == 1
        event = body["events"][0]
        assert event["event_type"] == "HIRE"
        assert event["order_id"] == order_id
        assert event["order_item_id"] == item_id

        employee_id = int(event["employee_id"])
        employee_ids.append(employee_id)

        with engine.begin() as conn:
            emp = conn.execute(
                text(
                    """
                    SELECT employee_id, person_id, org_unit_id, position_id, employment_rate, is_active
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().one()
            assert int(emp["person_id"]) == person_id
            assert int(emp["org_unit_id"]) == org_unit_id
            assert int(emp["position_id"]) == int(position_id)
            assert float(emp["employment_rate"]) == 1.0
            assert emp["is_active"] is True

            ctx = conn.execute(
                text(
                    """
                    SELECT hr_relationship_context
                    FROM public.personnel_record_metadata
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id},
            ).scalar_one()
            assert ctx == HR_RELATIONSHIP_EMPLOYED

            item_row = conn.execute(
                text(
                    """
                    SELECT employee_id
                    FROM public.personnel_order_items
                    WHERE item_id = :item_id
                    """
                ),
                {"item_id": item_id},
            ).mappings().one()
            assert int(item_row["employee_id"]) == employee_id

            if table_exists(conn, "person_assignments"):
                assignment = conn.execute(
                    text(
                        """
                        SELECT org_unit_id, position_id, rate
                        FROM public.person_assignments
                        WHERE person_id = :person_id
                        ORDER BY assignment_id DESC
                        LIMIT 1
                        """
                    ),
                    {"person_id": person_id},
                ).mappings().first()
                assert assignment is not None
                assert int(assignment["org_unit_id"]) == org_unit_id
                assert int(assignment["position_id"]) == int(position_id)
                assert float(assignment["rate"]) == 1.0

            ppr_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.personnel_record_metadata
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id},
            ).scalar_one()
            assert int(ppr_count) == 1

            employee_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employees
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id},
            ).scalar_one()
            assert int(employee_count) == 1

            cols = get_columns(conn, "employees")
            if "operational_status" in cols:
                op_status = conn.execute(
                    text(
                        """
                        SELECT operational_status
                        FROM public.employees
                        WHERE employee_id = :employee_id
                        """
                    ),
                    {"employee_id": employee_id},
                ).scalar_one()
                assert op_status == "active"
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_hire_apply_uses_order_values_not_intended_defaults(client, privileged_headers, seed):
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0

    try:
        with engine.begin() as conn:
            org_unit_id = int(seed["unit_id"])
            alt_unit = conn.execute(
                text(
                    """
                    SELECT unit_id
                    FROM public.org_units
                    WHERE unit_id <> :unit_id
                    ORDER BY unit_id ASC
                    LIMIT 1
                    """
                ),
                {"unit_id": org_unit_id},
            ).scalar_one_or_none()
            if alt_unit is None:
                pytest.skip("second org_unit required")
            alt_unit_id = int(alt_unit)

            positions = conn.execute(
                text(
                    """
                    SELECT position_id
                    FROM public.positions
                    ORDER BY position_id ASC
                    LIMIT 2
                    """
                )
            ).scalars().all()
            if len(positions) < 2:
                pytest.skip("two positions required")
            intended_position_id = int(positions[0])
            order_position_id = int(positions[1])

            person_id = _create_applicant(
                conn,
                suffix=suffix,
                org_unit_id=org_unit_id,
                position_id=intended_position_id,
                intended_rate=1.0,
            )
            person_ids.append(person_id)

        order_id, _ = _create_registered_hire_order_for_person(
            client,
            privileged_headers,
            person_id=person_id,
            org_unit_id=alt_unit_id,
            position_id=order_position_id,
            employment_rate=0.5,
        )

        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        employee_id = int(apply_resp.json()["events"][0]["employee_id"])
        employee_ids.append(employee_id)

        with engine.begin() as conn:
            emp = conn.execute(
                text(
                    """
                    SELECT org_unit_id, position_id, employment_rate
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().one()
            assert int(emp["org_unit_id"]) == alt_unit_id
            assert int(emp["position_id"]) == order_position_id
            assert float(emp["employment_rate"]) == 0.5
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_hire_apply_intended_employment_not_exposed_after_apply(client, privileged_headers, seed):
    """After Apply, intended_* is not part of the PPR read model (source of truth = Employee)."""
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0

    try:
        with engine.begin() as conn:
            org_unit_id = int(seed["unit_id"])
            position_id = int(
                conn.execute(
                    text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
                ).scalar_one()
            )
            person_id = _create_applicant(
                conn,
                suffix=suffix,
                org_unit_id=org_unit_id,
                position_id=position_id,
                intended_rate=1.0,
            )
            person_ids.append(person_id)

        order_id, _ = _create_registered_hire_order_for_person(
            client,
            privileged_headers,
            person_id=person_id,
            org_unit_id=org_unit_id,
            position_id=position_id,
            employment_rate=1.0,
        )

        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        employee_ids.append(int(apply_resp.json()["events"][0]["employee_id"]))

        card_resp = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
        assert card_resp.status_code == 200, card_resp.text
        body = card_resp.json()
        assert body["materialization"]["hr_relationship_context"] == HR_RELATIONSHIP_EMPLOYED
        assert body.get("intended_employment") is None

        defaults_resp = client.get(
            f"/api/ppr/persons/{person_id}/hire-defaults",
            headers=privileged_headers,
        )
        assert defaults_resp.status_code == 404, defaults_resp.text
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_hire_apply_repeat_is_idempotent_conflict(client, privileged_headers, seed):
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0

    try:
        with engine.begin() as conn:
            org_unit_id = int(seed["unit_id"])
            position_id = int(
                conn.execute(
                    text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
                ).scalar_one()
            )
            person_id = _create_applicant(
                conn,
                suffix=suffix,
                org_unit_id=org_unit_id,
                position_id=position_id,
                intended_rate=1.0,
            )
            person_ids.append(person_id)

        order_id, _ = _create_registered_hire_order_for_person(
            client,
            privileged_headers,
            person_id=person_id,
            org_unit_id=org_unit_id,
            position_id=position_id,
            employment_rate=1.0,
        )

        first = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert first.status_code == 200, first.text
        employee_id = int(first.json()["events"][0]["employee_id"])
        employee_ids.append(employee_id)

        with engine.begin() as conn:
            person_before = conn.execute(
                text(
                    """
                    SELECT full_name, person_status
                    FROM public.persons
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id},
            ).mappings().one()
            employee_before = conn.execute(
                text(
                    """
                    SELECT org_unit_id, position_id, employment_rate, is_active
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().one()
            hr_context_before = conn.execute(
                text(
                    """
                    SELECT hr_relationship_context
                    FROM public.personnel_record_metadata
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id},
            ).scalar_one()
            event_count_before = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_events
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
            assignment_count_before = 0
            if table_exists(conn, "person_assignments"):
                assignment_count_before = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.person_assignments
                        WHERE person_id = :person_id
                        """
                    ),
                    {"person_id": person_id},
                ).scalar_one()

        second = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert second.status_code == 409, second.text

        with engine.begin() as conn:
            person_after = conn.execute(
                text(
                    """
                    SELECT full_name, person_status
                    FROM public.persons
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id},
            ).mappings().one()
            employee_after = conn.execute(
                text(
                    """
                    SELECT org_unit_id, position_id, employment_rate, is_active
                    FROM public.employees
                    WHERE employee_id = :employee_id
                    """
                ),
                {"employee_id": employee_id},
            ).mappings().one()
            hr_context_after = conn.execute(
                text(
                    """
                    SELECT hr_relationship_context
                    FROM public.personnel_record_metadata
                    WHERE person_id = :person_id
                    """
                ),
                {"person_id": person_id},
            ).scalar_one()
            event_count_after = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_events
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
            assert dict(person_after) == dict(person_before)
            assert dict(employee_after) == dict(employee_before)
            assert hr_context_after == hr_context_before == HR_RELATIONSHIP_EMPLOYED
            assert int(event_count_after) == int(event_count_before) == 1
            if table_exists(conn, "person_assignments"):
                assignment_count_after = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.person_assignments
                        WHERE person_id = :person_id
                        """
                    ),
                    {"person_id": person_id},
                ).scalar_one()
                assert int(assignment_count_after) == int(assignment_count_before) == 1
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_hire_apply_excludes_person_from_applicant_roster(client, privileged_headers, seed):
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0

    try:
        with engine.begin() as conn:
            org_unit_id = int(seed["unit_id"])
            position_id = int(
                conn.execute(
                    text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
                ).scalar_one()
            )
            person_id = _create_applicant(
                conn,
                suffix=suffix,
                org_unit_id=org_unit_id,
                position_id=position_id,
                intended_rate=1.0,
            )
            person_ids.append(person_id)
            before_items, _ = list_ppr_applicants(conn, q=suffix)
            assert any(int(row["person_id"]) == person_id for row in before_items)

        order_id, _ = _create_registered_hire_order_for_person(
            client,
            privileged_headers,
            person_id=person_id,
            org_unit_id=org_unit_id,
            position_id=position_id,
            employment_rate=1.0,
        )
        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text
        employee_ids.append(int(apply_resp.json()["events"][0]["employee_id"]))

        with engine.begin() as conn:
            after_items, _ = list_ppr_applicants(conn, q=suffix)
            assert not any(int(row["person_id"]) == person_id for row in after_items)

        by_employee = client.get(
            f"/api/ppr/employees/{employee_ids[0]}",
            headers=privileged_headers,
        )
        assert by_employee.status_code == 200, by_employee.text
        assert (
            by_employee.json()["materialization"]["hr_relationship_context"]
            == HR_RELATIONSHIP_EMPLOYED
        )
        assert by_employee.json().get("intended_employment") is None
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_hire_apply_rollback_when_person_already_employed(client, privileged_headers, seed):
    suffix = uuid4().hex[:8]
    person_ids: list[int] = []
    employee_ids: list[int] = []
    order_id = 0

    try:
        with engine.begin() as conn:
            org_unit_id = int(seed["unit_id"])
            position_id = int(
                conn.execute(
                    text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")
                ).scalar_one()
            )
            person_id = _create_applicant(
                conn,
                suffix=suffix,
                org_unit_id=org_unit_id,
                position_id=position_id,
                intended_rate=1.0,
            )
            person_ids.append(person_id)

        order_id, _ = _create_registered_hire_order_for_person(
            client,
            privileged_headers,
            person_id=person_id,
            org_unit_id=org_unit_id,
            position_id=position_id,
            employment_rate=1.0,
        )

        with engine.begin() as conn:
            existing_employee_id = insert_returning_id(
                conn,
                table="employees",
                id_col="employee_id",
                values={
                    "full_name": f"Already employed {suffix}",
                    "person_id": person_id,
                    "org_unit_id": org_unit_id,
                    "position_id": position_id,
                    "employment_rate": 1.0,
                    "is_active": True,
                },
            )
            employee_ids.append(existing_employee_id)

        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 422, apply_resp.text

        with engine.begin() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employee_events
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).scalar_one()
            assert int(count) == 0
    finally:
        if order_id:
            _cleanup_order(order_id)
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)

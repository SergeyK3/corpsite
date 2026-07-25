# tests/personnel_lk/test_registry_query_service.py
"""Service-level tests for person-centric LK registry query."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.domain.status import APPLICATION_STATUS_COMPLETED
from app.personnel_lk.application.registry_query_service import list_personnel_lk_registry
from tests.personnel_lk.conftest import (
    insert_application,
    load_org_fixture,
    seed_user_id,
    set_employee_assignment,
    unique_iin,
)
from tests.personnel_applications.conftest import insert_person_with_iin, materialize_envelope
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person


def _suffix() -> str:
    return uuid4().hex[:8]


def test_hired_person_appears_once_as_employee_not_applicant(lk_env) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            org = load_org_fixture(conn)
            person_id = insert_person_with_iin(
                conn,
                full_name=f"Hired Once {suffix}",
                iin=unique_iin("1"),
            )
            person_ids.append(person_id)
            materialize_envelope(conn, person_id)
            completed_app = insert_application(
                conn,
                person_id=person_id,
                registered_by_user_id=user_id,
                status=APPLICATION_STATUS_COMPLETED,
                application_received_at=date(2026, 1, 10),
                intended_org_unit_id=org["org_unit_id"],
            )
            active_app = insert_application(
                conn,
                person_id=person_id,
                registered_by_user_id=user_id,
                status="registered",
                application_received_at=date(2026, 2, 10),
                intended_org_unit_id=org["org_unit_id"],
            )
            employee_id = insert_employee(conn, full_name=f"Hired Once {suffix}", person_id=person_id)
            employee_ids.append(employee_id)
            set_employee_assignment(
                conn,
                employee_id=employee_id,
                org_unit_id=org["org_unit_id"],
                position_id=org["position_id"],
            )

            items, total = list_personnel_lk_registry(conn, status="all")
            matches = [row for row in items if row.person_id == person_id]
            assert total >= 1
            assert len(matches) == 1
            row = matches[0]
            assert row.record_kind == "employee"
            assert row.employee_id == employee_id
            assert row.active_application_id is None
            assert row.application_status is None
            assert row.status == "active"

            apps = conn.execute(
                text(
                    """
                    SELECT application_id
                    FROM public.personnel_applications
                    WHERE person_id = :person_id
                    ORDER BY application_id
                    """
                ),
                {"person_id": person_id},
            ).scalars().all()
            assert completed_app in apps
            assert active_app in apps
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_chooses_latest_active_application_for_applicant(lk_env) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            org = load_org_fixture(conn)
            person_id = insert_person_with_iin(
                conn,
                full_name=f"Latest App {suffix}",
                iin=unique_iin("2"),
            )
            person_ids.append(person_id)
            materialize_envelope(conn, person_id)
            insert_application(
                conn,
                person_id=person_id,
                registered_by_user_id=user_id,
                status=APPLICATION_STATUS_COMPLETED,
                application_received_at=date(2026, 1, 5),
            )
            latest_app = insert_application(
                conn,
                person_id=person_id,
                registered_by_user_id=user_id,
                status="intake_pending",
                application_received_at=date(2026, 3, 5),
                intended_org_unit_id=org["org_unit_id"],
                intended_employment_rate=0.5,
            )

            items, _ = list_personnel_lk_registry(
                conn,
                q=suffix,
                record_kind="applicant",
                status="all",
            )
            row = next(item for item in items if item.person_id == person_id)
            assert row.record_kind == "applicant"
            assert row.active_application_id == latest_app
            assert row.application_status == "intake_pending"
            assert row.status == "applicant"
            assert float(row.rate or 0) == 0.5
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_record_kind_filters(lk_env) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            employee_person = insert_person(conn, full_name=f"Emp Only {suffix}")
            applicant_person = insert_person_with_iin(
                conn,
                full_name=f"App Only {suffix}",
                iin=unique_iin("3"),
            )
            person_ids.extend([employee_person, applicant_person])
            materialize_envelope(conn, applicant_person)
            employee_id = insert_employee(
                conn,
                full_name=f"Emp Only {suffix}",
                person_id=employee_person,
            )
            employee_ids.append(employee_id)
            insert_application(
                conn,
                person_id=applicant_person,
                registered_by_user_id=user_id,
                status="registered",
            )

            emp_items, emp_total = list_personnel_lk_registry(
                conn,
                q=suffix,
                record_kind="employee",
                status="all",
            )
            app_items, app_total = list_personnel_lk_registry(
                conn,
                q=suffix,
                record_kind="applicant",
                status="all",
            )
            assert emp_total == 1
            assert app_total == 1
            assert emp_items[0].record_kind == "employee"
            assert app_items[0].record_kind == "applicant"
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_org_filters_use_employee_and_applicant_sources(lk_env) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    employee_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            org = load_org_fixture(conn)
            if org["org_unit_id"] is None or org["position_id"] is None:
                return

            employee_person = insert_person(conn, full_name=f"Org Emp {suffix}")
            applicant_person = insert_person_with_iin(
                conn,
                full_name=f"Org App {suffix}",
                iin=unique_iin("4"),
            )
            person_ids.extend([employee_person, applicant_person])
            materialize_envelope(conn, applicant_person)
            employee_id = insert_employee(
                conn,
                full_name=f"Org Emp {suffix}",
                person_id=employee_person,
            )
            employee_ids.append(employee_id)
            set_employee_assignment(
                conn,
                employee_id=employee_id,
                org_unit_id=org["org_unit_id"],
                position_id=org["position_id"],
            )
            insert_application(
                conn,
                person_id=applicant_person,
                registered_by_user_id=user_id,
                status="registered",
                intended_org_unit_id=org["org_unit_id"],
                intended_position_id=org["position_id"],
                intended_org_group_id=org["org_group_id"],
            )

            by_unit, _ = list_personnel_lk_registry(
                conn,
                q=suffix,
                org_unit_id=org["org_unit_id"],
                status="all",
            )
            by_position, _ = list_personnel_lk_registry(
                conn,
                q=suffix,
                position_id=org["position_id"],
                status="all",
            )
            assert {row.person_id for row in by_unit} == {employee_person, applicant_person}
            assert {row.person_id for row in by_position} == {employee_person, applicant_person}

            if org["org_group_id"] is not None:
                by_group, _ = list_personnel_lk_registry(
                    conn,
                    q=suffix,
                    org_group_id=org["org_group_id"],
                    status="all",
                )
                assert applicant_person in {row.person_id for row in by_group}
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)


def test_search_by_name_iin_and_application_id(lk_env) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            iin = unique_iin("5")
            person_id = insert_person_with_iin(
                conn,
                full_name=f"Search Target {suffix}",
                iin=iin,
            )
            person_ids.append(person_id)
            materialize_envelope(conn, person_id)
            application_id = insert_application(
                conn,
                person_id=person_id,
                registered_by_user_id=user_id,
                status="registered",
            )

            by_name, _ = list_personnel_lk_registry(conn, q=suffix, record_kind="applicant", status="all")
            by_iin, _ = list_personnel_lk_registry(conn, q=iin[-6:], record_kind="applicant", status="all")
            by_app, _ = list_personnel_lk_registry(
                conn,
                q=str(application_id),
                record_kind="applicant",
                status="all",
            )
            assert any(row.person_id == person_id for row in by_name)
            assert any(row.person_id == person_id for row in by_iin)
            assert any(row.active_application_id == application_id for row in by_app)
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_application_status_filter(lk_env) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            pending_person = insert_person_with_iin(
                conn,
                full_name=f"Pending {suffix}",
                iin=unique_iin("6"),
            )
            other_person = insert_person_with_iin(
                conn,
                full_name=f"Registered {suffix}",
                iin=unique_iin("7"),
            )
            person_ids.extend([pending_person, other_person])
            materialize_envelope(conn, pending_person)
            materialize_envelope(conn, other_person)
            insert_application(
                conn,
                person_id=pending_person,
                registered_by_user_id=user_id,
                status="intake_pending",
            )
            insert_application(
                conn,
                person_id=other_person,
                registered_by_user_id=user_id,
                status="registered",
            )

            items, total = list_personnel_lk_registry(
                conn,
                q=suffix,
                record_kind="applicant",
                application_status="intake_pending",
                status="all",
            )
            assert total == 1
            assert items[0].person_id == pending_person
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])


def test_stable_sort_total_and_second_page(lk_env) -> None:
    suffix = _suffix()
    person_ids: list[int] = []
    try:
        with engine.begin() as conn:
            user_id = seed_user_id(conn)
            created: list[tuple[int, str]] = []
            for label in ("Charlie", "Alpha", "Bravo"):
                person_id = insert_person_with_iin(
                    conn,
                    full_name=f"{label} {suffix}",
                    iin=unique_iin(str(ord(label[0]))),
                )
                person_ids.append(person_id)
                materialize_envelope(conn, person_id)
                insert_application(
                    conn,
                    person_id=person_id,
                    registered_by_user_id=user_id,
                    status="registered",
                )
                created.append((person_id, label))

            page1, total = list_personnel_lk_registry(
                conn,
                q=suffix,
                record_kind="applicant",
                status="all",
                limit=2,
                offset=0,
            )
            page2, total2 = list_personnel_lk_registry(
                conn,
                q=suffix,
                record_kind="applicant",
                status="all",
                limit=2,
                offset=2,
            )
            assert total == 3
            assert total2 == 3
            assert len(page1) == 2
            assert len(page2) == 1
            ordered_labels = [row.fio.split()[0] for row in page1 + page2]
            assert ordered_labels == ["Alpha", "Bravo", "Charlie"]
            assert len({row.person_id for row in page1 + page2}) == 3
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=[])

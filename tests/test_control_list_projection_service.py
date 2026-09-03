from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from threading import Event, Thread
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, event, text

from app.db.engine import engine as project_test_engine

from app.control_list_projection.service import (
    ControlListAssignmentConflict,
    ControlListAuthorizationError,
    ControlListConfigurationError,
    _build_control_list_projection,
    build_control_list_projection,
    organization_timezone,
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Connection:
    def __init__(self, rows_by_marker, calls):
        self._rows_by_marker = rows_by_marker
        self._calls = calls
        self.transaction_sql = []

    @contextmanager
    def begin(self):
        yield

    def exec_driver_sql(self, statement):
        self.transaction_sql.append(statement)

    def execute(self, statement, params):
        sql = str(statement)
        marker = next(
            name
            for name in ("base", "education", "training", "contacts", "additional")
            if f"control_list:{name}" in sql
        )
        self._calls.append((marker, sql, dict(params)))
        return _Result(self._rows_by_marker.get(marker, []))


class _Engine:
    def __init__(self, **rows_by_marker):
        self.rows_by_marker = rows_by_marker
        self.calls = []
        self.connection = _Connection(self.rows_by_marker, self.calls)

    @contextmanager
    def connect(self):
        yield self.connection


def _base_row(employee_id: int, **overrides):
    row = {
        "employee_id": employee_id,
        "person_id": 1000 + employee_id,
        "full_name": f"Person {employee_id}",
        "birth_date": date(1990, 1, 2),
        "iin": f"900102300{employee_id:03d}",
        "assignment_id": 2000 + employee_id,
        "org_unit_id": 10,
        "org_unit_name": "Unit",
        "group_id": 1,
        "group_name": "Group",
        "position_id": 20,
        "position_name": "Doctor",
        "position_category": "specialist",
        "rate": Decimal("1.00"),
        "assignment_start_date": date(2025, 1, 1),
    }
    row.update(overrides)
    return row


def _fixed_clock(calls=None):
    def clock(timezone: ZoneInfo):
        if calls is not None:
            calls.append(timezone.key)
        return datetime(2026, 9, 3, 14, 15, tzinfo=timezone)

    return clock


def _postgres_available() -> bool:
    try:
        with project_test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@contextmanager
def _projection_database():
    database_name = f"corpsite_wpcl002_projection_{uuid4().hex[:10]}_test"
    admin_url = (
        str(project_test_engine.url.render_as_string(hide_password=False)).rsplit("/", 1)[0]
        + "/postgres"
    )
    database_url = admin_url.rsplit("/", 1)[0] + f"/{database_name}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    projection_engine = create_engine(database_url, hide_parameters=True)

    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{database_name}"'))

    try:
        with projection_engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE public.persons (
                    person_id BIGINT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    birth_date DATE NULL,
                    iin TEXT NULL,
                    person_status TEXT NOT NULL
                );
                CREATE TABLE public.employees (
                    employee_id BIGINT PRIMARY KEY,
                    person_id BIGINT NOT NULL,
                    org_unit_id BIGINT NULL,
                    is_active BOOLEAN NULL,
                    operational_status TEXT NOT NULL,
                    date_from DATE NULL,
                    date_to DATE NULL
                );
                CREATE TABLE public.deps_group (
                    group_id BIGINT PRIMARY KEY,
                    group_name TEXT NOT NULL
                );
                CREATE TABLE public.org_units (
                    unit_id BIGINT PRIMARY KEY,
                    name TEXT NOT NULL,
                    group_id BIGINT NULL
                );
                CREATE TABLE public.positions (
                    position_id BIGINT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NULL
                );
                CREATE TABLE public.person_assignments (
                    assignment_id BIGINT PRIMARY KEY,
                    person_id BIGINT NOT NULL,
                    org_unit_id BIGINT NOT NULL,
                    position_id BIGINT NULL,
                    rate NUMERIC NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NULL,
                    active_flag BOOLEAN NOT NULL,
                    is_primary BOOLEAN NOT NULL,
                    lifecycle_status TEXT NOT NULL
                );
                CREATE TABLE public.person_education (
                    education_id BIGINT PRIMARY KEY,
                    person_id BIGINT NOT NULL,
                    institution_name TEXT NULL,
                    specialty TEXT NULL,
                    started_at DATE NULL,
                    completed_at DATE NULL,
                    lifecycle_status TEXT NOT NULL,
                    verification_status TEXT NOT NULL
                );
                CREATE TABLE public.person_training (
                    training_id BIGINT PRIMARY KEY,
                    person_id BIGINT NOT NULL,
                    title TEXT NULL,
                    organization_name TEXT NULL,
                    hours NUMERIC NULL,
                    started_at DATE NULL,
                    completed_at DATE NULL,
                    certificate_number TEXT NULL,
                    lifecycle_status TEXT NOT NULL,
                    verification_status TEXT NOT NULL
                );
                CREATE TABLE public.contacts (
                    contact_id BIGINT PRIMARY KEY,
                    person_id BIGINT NOT NULL,
                    phone TEXT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
                );
                CREATE TABLE public.personnel_record_metadata (
                    person_id BIGINT PRIMARY KEY,
                    additional_profile JSONB NULL
                );
            """))
        yield projection_engine
    finally:
        projection_engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname=:database_name AND pid <> pg_backend_pid()
            """), {"database_name": database_name})
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()


def _insert_employee(
    conn,
    employee_id: int,
    *,
    status: str = "active",
    person_status: str = "active",
    date_from: date | None = None,
    date_to: date | None = None,
) -> None:
    conn.execute(text("""
        INSERT INTO public.persons
            (person_id, full_name, birth_date, iin, person_status)
        VALUES (:id, :name, DATE '1990-01-02', :iin, :person_status)
    """), {
        "id": employee_id,
        "name": f"Person {employee_id:02d}",
        "iin": f"90010230{employee_id:04d}",
        "person_status": person_status,
    })
    conn.execute(text("""
        INSERT INTO public.employees
            (employee_id, person_id, org_unit_id, is_active, operational_status, date_from, date_to)
        VALUES (:id, :id, 999, TRUE, :status, :date_from, :date_to)
    """), {
        "id": employee_id,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
    })


def _insert_assignment(
    conn,
    assignment_id: int,
    person_id: int,
    unit_id: int,
    *,
    primary: bool = True,
    start_date: date = date(2020, 1, 1),
    end_date: date | None = None,
    active: bool = True,
) -> None:
    conn.execute(text("""
        INSERT INTO public.person_assignments
            (assignment_id, person_id, org_unit_id, position_id, rate, start_date,
             end_date, active_flag, is_primary, lifecycle_status)
        VALUES (:assignment_id, :person_id, :unit_id, 1, 1.0, :start_date,
                :end_date, :active, :primary, 'active')
    """), {
        "assignment_id": assignment_id,
        "person_id": person_id,
        "unit_id": unit_id,
        "primary": primary,
        "start_date": start_date,
        "end_date": end_date,
        "active": active,
    })


def _seed_projection_reference_data(conn) -> None:
    conn.execute(text("""
        INSERT INTO public.deps_group VALUES (1, 'Group A'), (2, 'Group B');
        INSERT INTO public.org_units VALUES
            (10, 'Unit A', 1), (20, 'Unit B', 2), (999, 'Legacy Unit', NULL);
        INSERT INTO public.positions VALUES (1, 'Doctor', 'specialist');
    """))


def test_projection_uses_one_snapshot_date_scope_and_fixed_query_count(monkeypatch):
    monkeypatch.setenv("ORGANIZATION_TIMEZONE", "Asia/Almaty")
    clock_calls = []
    engine = _Engine(base=[_base_row(1), _base_row(2)])

    result = _build_control_list_projection(
        engine,
        initiator_user_id=77,
        scope_unit_ids=[12, 10, 12],
        clock=_fixed_clock(clock_calls),
    )

    assert clock_calls == ["Asia/Almaty"]
    assert result.metadata.as_of_date == date(2026, 9, 3)
    assert result.metadata.timezone == "Asia/Almaty"
    assert result.metadata.initiator_user_id == 77
    assert result.metadata.scope.org_unit_ids == [10, 12]
    assert result.total == 2
    assert engine.connection.transaction_sql == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    ]
    assert [name for name, _, _ in engine.calls] == [
        "base",
        "education",
        "training",
        "contacts",
        "additional",
    ]
    assert engine.calls[0][2] == {
        "as_of_date": date(2026, 9, 3),
        "organization_wide": False,
        "scope_unit_ids": [10, 12],
    }
    assert all(call[2] == {"person_ids": [1001, 1002]} for call in engine.calls[1:])


def test_base_query_defines_active_employee_and_primary_assignment_without_legacy_sources():
    engine = _Engine(base=[_base_row(1)])

    _build_control_list_projection(
        engine, initiator_user_id=77, scope_unit_ids=None, clock=_fixed_clock()
    )

    sql = engine.calls[0][1].lower()
    assert "e.operational_status = 'active'" in sql
    assert "p.person_status = 'active'" in sql
    assert "pa.is_primary is true" in sql
    assert "pa.active_flag is true" in sql
    assert "pa.lifecycle_status = 'active'" in sql
    assert "pa.start_date <= :as_of_date" in sql
    assert "pending" not in sql
    assert "intake" not in sql
    assert "hr_import" not in sql
    assert "source_text" not in sql


def test_missing_and_multiple_primary_assignments_are_aggregated_and_fail_closed():
    missing = _base_row(
        7,
        assignment_id=None,
        org_unit_id=None,
        org_unit_name=None,
        assignment_start_date=None,
    )
    duplicate_a = _base_row(8, assignment_id=81)
    duplicate_b = _base_row(8, assignment_id=82)
    engine = _Engine(base=[duplicate_b, missing, duplicate_a])

    with pytest.raises(ControlListAssignmentConflict) as raised:
        _build_control_list_projection(
            engine, initiator_user_id=77, scope_unit_ids=None, clock=_fixed_clock()
        )

    assert raised.value.detail.model_dump(mode="json")["conflicts"] == [
        {
            "employee_id": 7,
            "violation": "MISSING_PRIMARY_ASSIGNMENT",
        },
        {
            "employee_id": 8,
            "violation": "MULTIPLE_PRIMARY_ASSIGNMENTS",
        },
    ]
    assert [name for name, _, _ in engine.calls] == ["base"]


def test_rows_and_structured_collections_have_stable_order(monkeypatch):
    monkeypatch.setenv("ORGANIZATION_TIMEZONE", "Asia/Almaty")
    engine = _Engine(
        base=[
            _base_row(3, group_name=None, org_unit_name="A", full_name="A"),
            _base_row(2, group_name="A", org_unit_name="B", full_name="B"),
            _base_row(1, group_name="A", org_unit_name="A", full_name="Z"),
        ],
        education=[
            {
                "education_id": 2,
                "person_id": 1001,
                "institution_name": "Later",
                "specialty": "S2",
                "started_at": date(2015, 1, 1),
                "completed_at": date(2019, 1, 1),
            },
            {
                "education_id": 1,
                "person_id": 1001,
                "institution_name": "Earlier",
                "specialty": "S1",
                "started_at": date(2005, 1, 1),
                "completed_at": date(2009, 1, 1),
            },
        ],
        training=[
            {
                "training_id": 1,
                "person_id": 1001,
                "title": "Old",
                "organization_name": None,
                "hours": None,
                "started_at": date(2020, 1, 1),
                "completed_at": date(2020, 2, 1),
                "certificate_number": None,
            },
            {
                "training_id": 2,
                "person_id": 1001,
                "title": "New",
                "organization_name": None,
                "hours": None,
                "started_at": date(2024, 1, 1),
                "completed_at": date(2024, 2, 1),
                "certificate_number": None,
            },
        ],
        contacts=[
            {"contact_id": 3, "person_id": 1001, "phone": "+7 (701) 200-00-00"},
            {"contact_id": 1, "person_id": 1001, "phone": "+7 700 100 00 00"},
            {"contact_id": 4, "person_id": 1001, "phone": "+77012000000"},
        ],
        additional=[
            {
                "person_id": 1001,
                "additional_profile": {
                    "academic_degrees": [{"degree": "PhD"}, {"degree": "MD"}],
                    "awards": [{"name": "First"}, {"name": "Second"}],
                },
            }
        ],
    )

    result = _build_control_list_projection(
        engine, initiator_user_id=77, scope_unit_ids=None, clock=_fixed_clock()
    )

    assert [(item.number, item.employee_id) for item in result.items] == [(1, 1), (2, 2), (3, 3)]
    first = result.items[0]
    assert [item.record_id for item in first.education] == [1, 2]
    assert [item.graduation_year for item in first.education] == [2009, 2019]
    assert [item.record_id for item in first.training] == [2, 1]
    assert [item.contact_id for item in first.phones] == [1, 3]
    assert [item.ordinal for item in first.academic_degrees] == [0, 1]
    assert [item.ordinal for item in first.awards] == [0, 1]


def test_partial_fields_are_null_or_empty_and_reported():
    engine = _Engine(
        base=[
            _base_row(
                1,
                group_name=None,
                birth_date=None,
                iin=None,
                position_name=None,
                position_category=None,
                rate=None,
            )
        ]
    )

    item = _build_control_list_projection(
        engine, initiator_user_id=77, scope_unit_ids=None, clock=_fixed_clock()
    ).items[0]

    assert item.org_group is None
    assert item.birth_date is None
    assert item.iin is None
    assert item.education == []
    assert item.training == []
    assert item.academic_degrees == []
    assert item.awards == []
    assert item.phones == []
    assert set(item.missing_fields) == {
        "org_group",
        "birth_date",
        "iin",
        "position",
        "position_category",
        "employment_rate",
        "education",
        "education_graduation_year",
        "diploma_specialty",
        "training",
        "academic_degrees",
        "awards",
        "phones",
    }


def test_empty_scope_executes_no_database_queries():
    engine = _Engine()

    result = _build_control_list_projection(
        engine, initiator_user_id=77, scope_unit_ids=[], clock=_fixed_clock()
    )

    assert result.total == 0
    assert result.items == []
    assert engine.calls == []


def test_projection_executes_selects_only_and_verified_canonical_collections():
    engine = _Engine(base=[_base_row(1)])

    _build_control_list_projection(
        engine, initiator_user_id=77, scope_unit_ids=None, clock=_fixed_clock()
    )

    for _, sql, _ in engine.calls:
        lowered = sql.lower()
        assert "insert " not in lowered
        assert "update " not in lowered
        assert "delete " not in lowered
    education_sql = engine.calls[1][1].lower()
    training_sql = engine.calls[2][1].lower()
    additional_sql = engine.calls[4][1].lower()
    assert "verification_status = 'verified'" in education_sql
    assert "verification_status = 'verified'" in training_sql
    assert "personnel_record_metadata" in additional_sql
    assert "intake" not in additional_sql
    assert "hr_import" not in additional_sql


@pytest.mark.parametrize(
    "configured",
    ["", "Not/A_Real_Zone", "../Asia/Almaty"],
)
def test_invalid_timezone_is_a_safe_configuration_error(monkeypatch, configured):
    monkeypatch.setenv("ORGANIZATION_TIMEZONE", configured)

    with pytest.raises(ControlListConfigurationError) as raised:
        organization_timezone()

    assert str(raised.value) == "Organization timezone configuration is invalid."
    if configured:
        assert configured not in str(raised.value)


def test_explicit_absence_is_typed_and_not_reported_missing():
    engine = _Engine(
        base=[_base_row(1)],
        additional=[
            {
                "person_id": 1001,
                "additional_profile": {
                    "academic_degrees": [],
                    "academic_degrees_none": True,
                    "awards": [],
                    "awards_none": True,
                },
            }
        ],
    )

    item = _build_control_list_projection(
        engine, initiator_user_id=77, scope_unit_ids=None, clock=_fixed_clock()
    ).items[0]

    assert item.academic_degrees_none is True
    assert item.awards_none is True
    assert "academic_degrees" not in item.missing_fields
    assert "awards" not in item.missing_fields


def test_public_service_facade_denies_before_read_without_permission(monkeypatch):
    import app.control_list_projection.service as service

    engine = _Engine(base=[_base_row(1)])
    monkeypatch.setattr(service, "has_admin_permission", lambda *_args: False)

    with pytest.raises(ControlListAuthorizationError) as raised:
        build_control_list_projection(
            engine,
            user_context={"user_id": 77, "role_code": "ADMIN"},
            clock=_fixed_clock(),
        )

    assert raised.value.code == "CONTROL_LIST_EXPORT_FORBIDDEN"
    assert str(raised.value) == "Control-list export permission is required."
    assert engine.calls == []


def test_public_service_facade_uses_resolved_scope(monkeypatch):
    import app.control_list_projection.service as service

    engine = _Engine(base=[_base_row(1)])
    monkeypatch.setattr(service, "has_admin_permission", lambda *_args: True)
    monkeypatch.setattr(
        service,
        "compute_scope",
        lambda *_args, **_kwargs: {
            "privileged": False,
            "has_personnel_visibility": True,
            "scope_unit_ids": [10],
        },
    )

    result = build_control_list_projection(
        engine,
        user_context={"user_id": 77, "role_code": "HR_HEAD"},
        clock=_fixed_clock(),
    )

    assert result.total == 1
    assert engine.calls[0][2]["scope_unit_ids"] == [10]


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_postgresql_scope_activity_collections_and_fail_closed() -> None:
    with _projection_database() as pg_engine:
        snapshot_date = date(2026, 9, 3)
        with pg_engine.begin() as conn:
            _seed_projection_reference_data(conn)
            for employee_id in range(1, 9):
                _insert_employee(
                    conn,
                    employee_id,
                    status="inactive" if employee_id == 6 else "active",
                    person_status="inactive" if employee_id == 7 else "active",
                    date_from=snapshot_date if employee_id == 5 else None,
                    date_to=snapshot_date if employee_id == 5 else (
                        date(2026, 9, 2) if employee_id == 8 else None
                    ),
                )

            _insert_assignment(conn, 11, 1, 10)
            _insert_assignment(conn, 12, 1, 20, primary=False)
            _insert_assignment(conn, 21, 2, 20)
            _insert_assignment(conn, 22, 2, 20)
            _insert_assignment(conn, 31, 3, 10)
            _insert_assignment(conn, 32, 3, 20)
            # Employee 4 deliberately has no assignment.
            _insert_assignment(
                conn, 51, 5, 10, start_date=snapshot_date, end_date=snapshot_date
            )
            _insert_assignment(conn, 61, 6, 10)
            _insert_assignment(conn, 71, 7, 10)
            _insert_assignment(conn, 81, 8, 10)

        with pytest.raises(ControlListAssignmentConflict) as scoped_error:
            _build_control_list_projection(
                pg_engine,
                initiator_user_id=99,
                scope_unit_ids=[10],
                clock=_fixed_clock(),
            )
        assert scoped_error.value.detail.model_dump(mode="json")["conflicts"] == [
            {"employee_id": 3, "violation": "MULTIPLE_PRIMARY_ASSIGNMENTS"}
        ]

        with pytest.raises(ControlListAssignmentConflict) as wide_error:
            _build_control_list_projection(
                pg_engine,
                initiator_user_id=99,
                scope_unit_ids=None,
                clock=_fixed_clock(),
            )
        assert wide_error.value.detail.model_dump(mode="json")["conflicts"] == [
            {"employee_id": 2, "violation": "MULTIPLE_PRIMARY_ASSIGNMENTS"},
            {"employee_id": 3, "violation": "MULTIPLE_PRIMARY_ASSIGNMENTS"},
            {"employee_id": 4, "violation": "MISSING_PRIMARY_ASSIGNMENT"},
        ]
        serialized = str(wide_error.value.detail.model_dump(mode="json")).lower()
        assert "iin" not in serialized
        assert "phone" not in serialized
        assert "full_name" not in serialized

        with pg_engine.begin() as conn:
            conn.execute(text(
                "UPDATE public.person_assignments SET active_flag=FALSE "
                "WHERE assignment_id IN (22, 32)"
            ))
            conn.execute(text("""
                INSERT INTO public.person_education VALUES
                    (101, 1, 'Later University', 'Later Specialty', DATE '2010-01-01',
                     DATE '2014-01-01', 'active', 'verified'),
                    (100, 1, 'Earlier University', 'Earlier Specialty', DATE '2000-01-01',
                     DATE '2004-01-01', 'active', 'verified'),
                    (199, 2, 'Outside University', 'Outside', NULL, NULL, 'active', 'verified');
                INSERT INTO public.person_training VALUES
                    (201, 1, 'Old Course', NULL, NULL, NULL, DATE '2020-01-01', NULL,
                     'active', 'verified'),
                    (202, 1, 'New Course', NULL, NULL, NULL, DATE '2025-01-01', NULL,
                     'active', 'verified');
                INSERT INTO public.contacts VALUES
                    (301, 1, '+7 (701) 111-22-33', FALSE),
                    (302, 1, '7 701 111 22 33', FALSE),
                    (303, 1, '+7 702 000 00 00', FALSE);
                INSERT INTO public.personnel_record_metadata VALUES
                    (1, '{"academic_degrees": [], "academic_degrees_none": true,
                          "awards": [], "awards_none": true}'::jsonb);
            """))
            counts_before = tuple(conn.execute(text("""
                SELECT
                    (SELECT count(*) FROM public.persons),
                    (SELECT count(*) FROM public.person_assignments),
                    (SELECT count(*) FROM public.person_education),
                    (SELECT count(*) FROM public.contacts)
            """)).one())

        transaction_state: dict[str, str] = {}
        statements: list[str] = []

        def inspect_transaction(conn, _cursor, statement, _params, _context, _many):
            statements.append(statement)
            if "control_list:education" in statement:
                transaction_state["isolation"] = conn.exec_driver_sql(
                    "SHOW transaction_isolation"
                ).scalar_one()
                transaction_state["read_only"] = conn.exec_driver_sql(
                    "SHOW transaction_read_only"
                ).scalar_one()

        event.listen(pg_engine, "before_cursor_execute", inspect_transaction)
        try:
            result = _build_control_list_projection(
                pg_engine,
                initiator_user_id=99,
                scope_unit_ids=[10],
                clock=_fixed_clock(),
            )
        finally:
            event.remove(pg_engine, "before_cursor_execute", inspect_transaction)

        assert transaction_state == {"isolation": "repeatable read", "read_only": "on"}
        assert [item.employee_id for item in result.items] == [1, 3, 5]
        assert result.items[0].org_unit == "Unit A"
        assert result.items[0].position == "Doctor"
        assert [item.record_id for item in result.items[0].education] == [100, 101]
        assert [item.record_id for item in result.items[0].training] == [202, 201]
        assert [item.contact_id for item in result.items[0].phones] == [301, 303]
        assert result.items[0].academic_degrees_none is True
        assert result.items[0].awards_none is True
        assert "academic_degrees" not in result.items[0].missing_fields
        assert "awards" not in result.items[0].missing_fields
        assert sum("control_list:education" in statement for statement in statements) == 1
        assert sum("control_list:training" in statement for statement in statements) == 1
        assert sum("control_list:contacts" in statement for statement in statements) == 1
        assert all("pending" not in statement.lower() for statement in statements)
        assert all("intake" not in statement.lower() for statement in statements)

        with pg_engine.connect() as conn:
            counts_after = tuple(conn.execute(text("""
                SELECT
                    (SELECT count(*) FROM public.persons),
                    (SELECT count(*) FROM public.person_assignments),
                    (SELECT count(*) FROM public.person_education),
                    (SELECT count(*) FROM public.contacts)
            """)).one())
        assert counts_after == counts_before


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_postgresql_projection_uses_one_repeatable_read_snapshot() -> None:
    with _projection_database() as pg_engine:
        with pg_engine.begin() as conn:
            _seed_projection_reference_data(conn)
            _insert_employee(conn, 1)
            _insert_assignment(conn, 11, 1, 10)
            conn.execute(text("""
                INSERT INTO public.person_education VALUES
                    (100, 1, 'Before concurrent commit', 'Specialty', NULL,
                     DATE '2020-01-01', 'active', 'verified')
            """))

        base_selected = Event()
        writer_finished = Event()
        writer_errors: list[BaseException] = []

        def pause_after_base(_conn, _cursor, statement, _params, _context, _many):
            if "control_list:base" not in statement:
                return
            base_selected.set()
            assert writer_finished.wait(timeout=10)

        def concurrent_writer() -> None:
            try:
                assert base_selected.wait(timeout=10)
                with pg_engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE public.person_education
                        SET institution_name='After concurrent commit'
                        WHERE education_id=100
                    """))
            except BaseException as exc:  # pragma: no cover - surfaced below
                writer_errors.append(exc)
            finally:
                writer_finished.set()

        event.listen(pg_engine, "after_cursor_execute", pause_after_base)
        writer = Thread(target=concurrent_writer, daemon=True)
        writer.start()
        try:
            result = _build_control_list_projection(
                pg_engine,
                initiator_user_id=99,
                scope_unit_ids=[10],
                clock=_fixed_clock(),
            )
        finally:
            event.remove(pg_engine, "after_cursor_execute", pause_after_base)
            writer.join(timeout=10)

        assert not writer.is_alive()
        assert writer_errors == []
        assert result.items[0].education[0].institution_name == "Before concurrent commit"
        with pg_engine.connect() as conn:
            assert conn.execute(text(
                "SELECT institution_name FROM public.person_education WHERE education_id=100"
            )).scalar_one() == "After concurrent commit"

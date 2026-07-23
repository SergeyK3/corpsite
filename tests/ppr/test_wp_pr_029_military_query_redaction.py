# tests/ppr/test_wp_pr_029_military_query_redaction.py
"""Query API, redaction, and architecture guards for PPR-MILITARY (WP-PR-029)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.ppr_errors import map_ppr_mutation_error
from app.api.ppr_mappers import composite_to_response
from app.api.ppr_schemas import PprMilitaryRecordDetailsResponse, PprMilitaryRecordResponse
from app.db.engine import engine
from app.db.models.personnel_migration import (
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    MILITARY_RECORD_KIND_REGISTRATION,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.main import app
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_CREATE_MILITARY_SERVICE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
    COMMAND_TYPE_VOID_MILITARY_SERVICE,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.section_commands import CreateMilitaryServiceRecord
from app.ppr.domain.section_models import (
    SECTION_CODE_PPR_MILITARY,
    MilitaryServiceRecord,
    SUPPORTED_SECTION_CODES,
)
from app.ppr.read.models import PprSectionAggregation
from app.ppr.read.query_service import PprQueryApplicationService
from app.ppr.read.section_aggregation import PprSectionAggregationReader
from app.ppr.read.uow import PprReadUnitOfWork
from app.services.ppr_query_access_service import include_military_restricted_fields
from app.security.directory_scope import _parse_int_set_env
from sqlalchemy.exc import IntegrityError
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run: alembic upgrade head")
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def military_details_headers(seed, monkeypatch):
    monkeypatch.setenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def person_id():
    require_ppr_schema()
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        pid = insert_person(conn, full_name=f"WP29 Military {suffix}")
    yield pid
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[pid], employee_ids=[])


@pytest.fixture
def linked_person_employee():
    require_ppr_schema()
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"WP29 Linked {suffix}")
        employee_id = insert_employee(conn, full_name=f"WP29 Emp {suffix}", person_id=person_id)
    yield {"person_id": person_id, "employee_id": employee_id}
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


def _materialize(person_id: int) -> None:
    svc = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    svc.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )
    svc.activate_ppr(
        PprCommandEnvelope(
            command_id=f"act-{uuid4().hex}",
            command_type=COMMAND_TYPE_ACTIVATE_PPR,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )


def _full_registration_payload(**overrides) -> dict:
    base = {
        "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
        "obligation_status": "liable",
        "registration_category": "II",
        "military_rank": "рядовой",
        "registration_status": "registered",
        "military_specialty_code": "123456",
        "commissariat_name": "Военкомат №1",
        "registered_at": date(2015, 3, 1),
        "military_id_book_series": "АА",
        "military_id_book_number": "1234567",
        "registration_certificate_series": "ББ",
        "registration_certificate_number": "987654",
        "notes": "Round-trip notes",
        "source_type": SECTION_SOURCE_TYPE_ENTERED,
        "provenance": {"import_batch": "test-batch"},
        "employee_context_id": 42,
        "metadata": {"restricted_flag": True},
    }
    base.update(overrides)
    return base


def _seed_full_record(person_id: int) -> int:
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    result = section_service.create_military_service(
        PprCommandEnvelope(
            command_id=f"seed-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload=_full_registration_payload(),
            person_id=person_id,
        )
    )
    assert result.section_record_id is not None
    return int(result.section_record_id)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_query_active_zero_or_one(person_id: int) -> None:
    _materialize(person_id)
    query = PprQueryApplicationService()
    sections = query.load_sections(person_id)
    assert len(sections[SECTION_CODE_PPR_MILITARY].active) == 0

    _seed_full_record(person_id)
    sections = query.load_sections(person_id)
    assert len(sections[SECTION_CODE_PPR_MILITARY].active) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_query_history_buckets(person_id: int) -> None:
    _materialize(person_id)
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    created = section_service.create_military_service(
        PprCommandEnvelope(
            command_id=f"hist-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload=_full_registration_payload(military_rank="первый"),
            person_id=person_id,
        )
    )
    assert created.section_record_id is not None
    with engine.begin() as conn:
        updated_at = conn.execute(
            text("SELECT updated_at FROM public.person_military_service WHERE military_id = :rid"),
            {"rid": created.section_record_id},
        ).scalar_one()

    section_service.supersede_military_service(
        PprCommandEnvelope(
            command_id=f"sup-{uuid4().hex}",
            command_type=COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": created.section_record_id,
                "expected_updated_at": updated_at,
                "replacement": _full_registration_payload(military_rank="второй"),
            },
            person_id=person_id,
        )
    )

    with engine.begin() as conn:
        replacement_updated_at = conn.execute(
            text(
                """
                SELECT updated_at FROM public.person_military_service
                WHERE person_id = :pid AND lifecycle_status = 'active'
                """
            ),
            {"pid": person_id},
        ).scalar_one()
        replacement_id = conn.execute(
            text(
                """
                SELECT military_id FROM public.person_military_service
                WHERE person_id = :pid AND lifecycle_status = 'active'
                """
            ),
            {"pid": person_id},
        ).scalar_one()

    section_service.void_military_service(
        PprCommandEnvelope(
            command_id=f"void-{uuid4().hex}",
            command_type=COMMAND_TYPE_VOID_MILITARY_SERVICE,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": replacement_id,
                "reason": "void history",
                "expected_updated_at": replacement_updated_at,
            },
            person_id=person_id,
        )
    )

    section_service.create_military_service(
        PprCommandEnvelope(
            command_id=f"new-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp29-test",
            requested_at=datetime.now(UTC),
            payload=_full_registration_payload(military_rank="третий"),
            person_id=person_id,
        )
    )

    sections = PprQueryApplicationService().load_sections(person_id)
    military = sections[SECTION_CODE_PPR_MILITARY]
    assert len(military.active) == 1
    assert military.active[0].lifecycle_status == "active"
    assert len(military.superseded) == 1
    assert military.superseded[0].lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert len(military.voided) == 1
    assert military.voided[0].lifecycle_status == LIFECYCLE_STATUS_VOIDED


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_route_includes_military_section(
    client: TestClient,
    person_id: int,
    privileged_headers,
) -> None:
    _materialize(person_id)
    _seed_full_record(person_id)
    resp = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    assert resp.status_code == 200
    section = resp.json()["sections"][SECTION_CODE_PPR_MILITARY]
    assert len(section["active"]) == 1
    assert section["active"][0]["military_rank"] == "рядовой"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_route_includes_military_section(
    client: TestClient,
    linked_person_employee: dict,
    privileged_headers,
) -> None:
    person_id = linked_person_employee["person_id"]
    employee_id = linked_person_employee["employee_id"]
    _materialize(person_id)
    _seed_full_record(person_id)
    resp = client.get(f"/api/ppr/employees/{employee_id}", headers=privileged_headers)
    assert resp.status_code == 200
    section = resp.json()["sections"][SECTION_CODE_PPR_MILITARY]
    assert len(section["active"]) == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_empty_military_section(person_id: int, client: TestClient, privileged_headers) -> None:
    _materialize(person_id)
    resp = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    assert resp.status_code == 200
    section = resp.json()["sections"][SECTION_CODE_PPR_MILITARY]
    assert section["active"] == []
    assert section["superseded"] == []
    assert section["voided"] == []


def test_redaction_default_hides_restricted_fields() -> None:
    record = MilitaryServiceRecord(
        person_id=1,
        record_kind=MILITARY_RECORD_KIND_REGISTRATION,
        military_rank="рядовой",
        obligation_status="liable",
        registration_status="registered",
        military_id_book_series="АА",
        military_id_book_number="1234567",
        registration_certificate_series="ББ",
        registration_certificate_number="987654",
        source_type=SECTION_SOURCE_TYPE_ENTERED,
    )
    section = PprSectionAggregation(section_code=SECTION_CODE_PPR_MILITARY, active=(record,))
    composite = _minimal_composite(section)
    response = composite_to_response(
        composite,
        read_mode="ppr",
        source="unit-test",
        include_sensitive_identity=False,
        include_military_restricted=False,
    )
    item = response.sections[SECTION_CODE_PPR_MILITARY].active[0]
    assert isinstance(item, PprMilitaryRecordResponse)
    assert not isinstance(item, PprMilitaryRecordDetailsResponse)
    assert "military_id_book_series" not in item.model_fields_set
    assert "military_id_book_number" not in item.model_fields_set


def test_redaction_privileged_exposes_restricted_fields() -> None:
    record = MilitaryServiceRecord(
        person_id=1,
        record_kind=MILITARY_RECORD_KIND_REGISTRATION,
        military_rank="рядовой",
        obligation_status="liable",
        registration_status="registered",
        military_id_book_series="АА",
        military_id_book_number="1234567",
        registration_certificate_series="ББ",
        registration_certificate_number="987654",
        source_type=SECTION_SOURCE_TYPE_ENTERED,
    )
    section = PprSectionAggregation(section_code=SECTION_CODE_PPR_MILITARY, active=(record,))
    composite = _minimal_composite(section)
    response = composite_to_response(
        composite,
        read_mode="ppr",
        source="unit-test",
        include_sensitive_identity=False,
        include_military_restricted=True,
    )
    item = response.sections[SECTION_CODE_PPR_MILITARY].active[0]
    assert isinstance(item, PprMilitaryRecordDetailsResponse)
    assert item.military_id_book_series == "АА"
    assert item.military_id_book_number == "1234567"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_redaction_storage_unchanged_after_query(
    person_id: int,
    client: TestClient,
    privileged_headers,
) -> None:
    _materialize(person_id)
    _seed_full_record(person_id)
    resp = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    assert resp.status_code == 200
    item = resp.json()["sections"][SECTION_CODE_PPR_MILITARY]["active"][0]
    assert "military_id_book_number" not in item

    with engine.begin() as conn:
        stored = conn.execute(
            text(
                """
                SELECT military_id_book_number, registration_certificate_number
                FROM public.person_military_service
                WHERE person_id = :pid AND lifecycle_status = 'active'
                """
            ),
            {"pid": person_id},
        ).one()
    assert stored[0] == "1234567"
    assert stored[1] == "987654"


def test_employee_context_id_does_not_grant_restricted_access(monkeypatch) -> None:
    monkeypatch.setenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", "")
    user_ctx = {"user_id": 999, "employee_context_id": 42}
    assert include_military_restricted_fields(user_ctx) is False


def test_allowlist_env_absent_is_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", raising=False)
    assert _parse_int_set_env("PPR_VIEW_MILITARY_DETAILS_USER_IDS") == set()
    assert include_military_restricted_fields({"user_id": 1}) is False


def test_allowlist_env_empty_is_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", "")
    assert include_military_restricted_fields({"user_id": 1}) is False


def test_allowlist_malformed_entries_do_not_open_access(monkeypatch) -> None:
    monkeypatch.setenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", "abc, ,not-an-int")
    assert _parse_int_set_env("PPR_VIEW_MILITARY_DETAILS_USER_IDS") == set()
    assert include_military_restricted_fields({"user_id": 999}) is False


def test_allowlist_only_explicit_user_ids_grant_access(monkeypatch) -> None:
    monkeypatch.setenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", "7, 42")
    assert include_military_restricted_fields({"user_id": 7}) is True
    assert include_military_restricted_fields({"user_id": 42}) is True
    assert include_military_restricted_fields({"user_id": 8}) is False


def test_hr_admin_without_military_grant_is_fail_closed(monkeypatch, seed) -> None:
    uid = int(seed["initiator_user_id"])
    monkeypatch.delenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", raising=False)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(uid))
    user_ctx = {"user_id": uid}
    assert include_military_restricted_fields(user_ctx) is False


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_and_employee_routes_apply_same_redaction(
    client: TestClient,
    linked_person_employee: dict,
    seed,
    monkeypatch,
) -> None:
    person_id = linked_person_employee["person_id"]
    employee_id = linked_person_employee["employee_id"]
    uid = int(seed["initiator_user_id"])
    headers = auth_headers(uid)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(uid))
    monkeypatch.delenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", raising=False)

    _materialize(person_id)
    _seed_full_record(person_id)

    person_resp = client.get(f"/api/ppr/persons/{person_id}", headers=headers)
    employee_resp = client.get(f"/api/ppr/employees/{employee_id}", headers=headers)
    assert person_resp.status_code == 200
    assert employee_resp.status_code == 200

    person_item = person_resp.json()["sections"][SECTION_CODE_PPR_MILITARY]["active"][0]
    employee_item = employee_resp.json()["sections"][SECTION_CODE_PPR_MILITARY]["active"][0]
    assert "military_id_book_number" not in person_item
    assert "military_id_book_number" not in employee_item
    assert person_item["military_rank"] == employee_item["military_rank"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_granted_user_sees_restricted_fields_on_person_and_employee_routes(
    client: TestClient,
    linked_person_employee: dict,
    seed,
    monkeypatch,
) -> None:
    person_id = linked_person_employee["person_id"]
    employee_id = linked_person_employee["employee_id"]
    uid = int(seed["initiator_user_id"])
    headers = auth_headers(uid)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(uid))
    monkeypatch.setenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", str(uid))

    _materialize(person_id)
    _seed_full_record(person_id)

    person_item = client.get(
        f"/api/ppr/persons/{person_id}",
        headers=headers,
    ).json()["sections"][SECTION_CODE_PPR_MILITARY]["active"][0]
    employee_item = client.get(
        f"/api/ppr/employees/{employee_id}",
        headers=headers,
    ).json()["sections"][SECTION_CODE_PPR_MILITARY]["active"][0]

    assert person_item["military_id_book_number"] == "1234567"
    assert employee_item["military_id_book_number"] == "1234567"
    assert person_item["registration_certificate_number"] == "987654"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_request_query_params_cannot_enable_restricted_fields(
    client: TestClient,
    person_id: int,
    seed,
    monkeypatch,
) -> None:
    uid = int(seed["initiator_user_id"])
    headers = auth_headers(uid)
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(uid))
    monkeypatch.delenv("PPR_VIEW_MILITARY_DETAILS_USER_IDS", raising=False)

    _materialize(person_id)
    _seed_full_record(person_id)

    resp = client.get(
        f"/api/ppr/persons/{person_id}",
        headers=headers,
        params={
            "include_military_restricted": "true",
            "include_restricted": "1",
            "view_military_details": "yes",
        },
    )
    assert resp.status_code == 200
    item = resp.json()["sections"][SECTION_CODE_PPR_MILITARY]["active"][0]
    assert "military_id_book_number" not in item
    assert "registration_certificate_number" not in item


class _FakeDiag:
    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class _FakeOrig:
    def __init__(self, *, pgcode: str | None, constraint_name: str | None) -> None:
        self.pgcode = pgcode
        self.diag = _FakeDiag(constraint_name) if constraint_name is not None else None


def _fake_integrity_error(*, pgcode: str | None, constraint_name: str | None) -> IntegrityError:
    return IntegrityError("statement", {}, _FakeOrig(pgcode=pgcode, constraint_name=constraint_name))


def test_integrity_error_maps_409_only_for_military_second_active() -> None:
    mapped = map_ppr_mutation_error(
        _fake_integrity_error(
            pgcode="23505",
            constraint_name="uq_person_military_service_one_active_per_person",
        )
    )
    assert mapped is not None
    assert mapped.status_code == 409


def test_integrity_error_other_unique_violation_is_not_mapped() -> None:
    mapped = map_ppr_mutation_error(
        _fake_integrity_error(
            pgcode="23505",
            constraint_name="some_other_unique_constraint",
        )
    )
    assert mapped is None


def test_integrity_error_other_pgcode_is_not_mapped() -> None:
    mapped = map_ppr_mutation_error(
        _fake_integrity_error(
            pgcode="23503",
            constraint_name="uq_person_military_service_one_active_per_person",
        )
    )
    assert mapped is None


def test_integrity_error_without_diag_is_not_mapped() -> None:
    mapped = map_ppr_mutation_error(_fake_integrity_error(pgcode="23505", constraint_name=None))
    assert mapped is None


def test_architecture_no_update_command() -> None:
    from app.ppr.domain import section_commands

    assert not hasattr(section_commands, "UpdateMilitaryServiceRecord")
    assert "UpdateMilitaryServiceRecord" not in section_commands.__dict__


def test_architecture_supported_section_codes() -> None:
    assert SECTION_CODE_PPR_MILITARY in SUPPORTED_SECTION_CODES


def test_architecture_aggregation_reader_has_load_military() -> None:
    assert hasattr(PprSectionAggregationReader, "load_military")


def test_architecture_no_update_handler() -> None:
    from app.ppr.domain import section_handlers

    assert not hasattr(section_handlers, "handle_update_military_service_record")


def _minimal_composite(military_section: PprSectionAggregation):
    from app.ppr.domain.identity_models import (
        INPUT_KIND_PERSON_ID,
        IdentityResolution,
        PersonIdentitySnapshot,
        RESULT_DIRECT,
    )
    from app.ppr.domain.models import PPR_LIFECYCLE_CREATED
    from app.ppr.domain.person_models import PersonGeneralReadSnapshot
    from app.ppr.domain.section_models import SECTION_CODE_PPR_EDUCATION, SECTION_CODE_PPR_FAMILY, SECTION_CODE_PPR_TRAINING
    from app.ppr.read.models import PprAdditionalReadSlice, PprCompositeReadMetadata, PprCompositeReadModel

    now = datetime.now(UTC)
    identity = PersonIdentitySnapshot(
        person_id=1,
        person_status="active",
        merged_into_person_id=None,
        match_key="k",
        iin=None,
    )
    resolution = IdentityResolution(
        input_kind=INPUT_KIND_PERSON_ID,
        input_id=1,
        employee_id=None,
        source_person_id=1,
        resolved_person_id=1,
        merge_redirected=False,
        merge_chain=(1,),
        result_code=RESULT_DIRECT,
    )
    empty = PprSectionAggregation(section_code=SECTION_CODE_PPR_EDUCATION, active=())
    return PprCompositeReadModel(
        person_id=1,
        employee_id=None,
        materialized=True,
        lifecycle_state=PPR_LIFECYCLE_CREATED,
        hr_relationship_context=None,
        envelope_version=1,
        envelope_created_at=now,
        envelope_updated_at=now,
        identity=identity,
        identity_resolution=resolution,
        general=PersonGeneralReadSnapshot(
            person_id=1,
            full_name="Test",
            last_name=None,
            first_name=None,
            middle_name=None,
            birth_date=None,
            iin=None,
            created_at=now,
            updated_at=now,
        ),
        education=empty,
        training=PprSectionAggregation(section_code=SECTION_CODE_PPR_TRAINING, active=()),
        family=PprSectionAggregation(section_code=SECTION_CODE_PPR_FAMILY, active=()),
        external_employment=PprSectionAggregation(section_code="PPR-EMPLOYMENT-BIOGRAPHY", active=()),
        military=military_section,
        events=None,
        intended_employment=None,
        additional=PprAdditionalReadSlice.empty(),
        metadata=PprCompositeReadMetadata(
            evaluated_at=now,
            source_person_id=1,
            merge_redirected=False,
        ),
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_round_trip_ordinary_fields_via_query(person_id: int) -> None:
    _materialize(person_id)
    _seed_full_record(person_id)
    with PprReadUnitOfWork() as uow:
        reader = PprSectionAggregationReader(uow.sections, uow.connection)
        military = reader.load_military(person_id)
    assert len(military.active) == 1
    record = military.active[0]
    assert isinstance(record, MilitaryServiceRecord)
    assert record.military_rank == "рядовой"
    assert record.commissariat_name == "Военкомат №1"
    assert record.military_id_book_number == "1234567"
    assert record.provenance == {"import_batch": "test-batch"}
    assert record.metadata == {"restricted_flag": True}


def test_create_command_exists_not_update() -> None:
    assert CreateMilitaryServiceRecord is not None

# tests/ppr/test_r7_ppr_api.py
"""API integration tests for PPR R7 query endpoints."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
    RELATIONSHIP_TYPE_MOTHER,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_ADD_RELATIVE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.models import PPR_LIFECYCLE_CREATED, PPR_LIFECYCLE_NOT_MATERIALIZED
from app.ppr.domain.section_models import EducationRecord
from app.ppr.infrastructure.section_repository import SqlAlchemySectionMutationRepository
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


def _require_metadata_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run: alembic upgrade head")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def bare_person():
    require_ppr_schema()
    _require_metadata_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"R7 API Bare {suffix}")
    yield person_id
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.fixture
def linked_person_employee():
    require_ppr_schema()
    _require_metadata_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = insert_person(conn, full_name=f"R7 API Linked {suffix}")
        employee_id = insert_employee(conn, full_name=f"R7 API Emp {suffix}", person_id=person_id)
    yield {"person_id": person_id, "employee_id": employee_id}
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])


def _materialize(person_id: int) -> None:
    svc = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    svc.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"r7-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="r7-test",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        )
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_openapi_has_ppr_routes(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema.get("paths", {})
    assert "/api/ppr/persons/{person_id}" in paths
    assert "/api/ppr/employees/{employee_id}" in paths
    assert "/api/ppr/persons/{person_id}/summary" in paths


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_get_by_person_not_materialized(client: TestClient, bare_person: int, privileged_headers) -> None:
    resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"]["resolved_person_id"] == bare_person
    assert body["materialization"]["materialized"] is False
    assert body["materialization"]["lifecycle_state"] == PPR_LIFECYCLE_NOT_MATERIALIZED
    assert body["metadata"]["read_mode"] == "ppr"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_get_by_person_materialized(client: TestClient, bare_person: int, privileged_headers) -> None:
    _materialize(bare_person)
    resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["materialization"]["materialized"] is True
    assert body["materialization"]["lifecycle_state"] == PPR_LIFECYCLE_CREATED
    assert body["materialization"]["envelope_version"] == 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_get_by_employee(client: TestClient, linked_person_employee: dict, privileged_headers) -> None:
    resp = client.get(
        f"/api/ppr/employees/{linked_person_employee['employee_id']}",
        headers=privileged_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"]["resolved_person_id"] == linked_person_employee["person_id"]
    assert body["identity"]["employee_context_id"] == linked_person_employee["employee_id"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_missing_person_404(client: TestClient, privileged_headers) -> None:
    resp = client.get("/api/ppr/persons/999999999", headers=privileged_headers)
    assert resp.status_code == 404


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_missing_employee_404(client: TestClient, privileged_headers) -> None:
    resp = client.get("/api/ppr/employees/999999999", headers=privileged_headers)
    assert resp.status_code == 404


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_employee_without_person_link_409(client: TestClient, seed, privileged_headers) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_id = insert_employee(conn, full_name=f"R7 Orphan {suffix}")
    try:
        resp = client.get(f"/api/ppr/employees/{employee_id}", headers=privileged_headers)
        assert resp.status_code == 409
    finally:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_education_aggregation_in_api(client: TestClient, bare_person: int, privileged_headers) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemySectionMutationRepository(conn)
        from app.db.models.personnel_migration import EDUCATION_KIND_BASIC

        repo.insert_record(
            EducationRecord(
                person_id=bare_person,
                education_kind=EDUCATION_KIND_BASIC,
                institution_name="R7 University",
            )
        )
    resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    assert resp.status_code == 200
    education = resp.json()["sections"]["PPR-EDUCATION"]["active"]
    assert len(education) == 1
    assert education[0]["institution_name"] == "R7 University"
    assert "PPR-FAMILY" in resp.json()["sections"]
    assert "PPR-EMPLOYMENT-BIOGRAPHY" in resp.json()["sections"]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_family_aggregation_in_api(client: TestClient, bare_person: int, privileged_headers) -> None:
    _materialize(bare_person)
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    section_service.add_relative(
        PprCommandEnvelope(
            command_id=f"r7-family-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_RELATIVE,
            actor_id="r7-test",
            requested_at=datetime.now(UTC),
            payload={
                "relationship_type": RELATIONSHIP_TYPE_MOTHER,
                "full_name": "R7 Mother Relative",
            },
            person_id=bare_person,
        )
    )
    resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    assert resp.status_code == 200
    family = resp.json()["sections"]["PPR-FAMILY"]["active"]
    assert len(family) == 1
    assert family[0]["full_name"] == "R7 Mother Relative"
    assert family[0]["relationship_type"] == RELATIONSHIP_TYPE_MOTHER
    assert family[0]["relationship_label"] == "Мать"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_aggregation_in_api(
    client: TestClient,
    bare_person: int,
    privileged_headers,
) -> None:
    _materialize(bare_person)
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    section_service.add_external_employment(
        PprCommandEnvelope(
            command_id=f"r7-emp-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="r7-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
                "notes": "Сводный стаж 15 лет",
            },
            person_id=bare_person,
        )
    )
    resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    assert resp.status_code == 200
    section = resp.json()["sections"]["PPR-EMPLOYMENT-BIOGRAPHY"]
    assert section["section_code"] == "PPR-EMPLOYMENT-BIOGRAPHY"
    assert len(section["active"]) == 1
    assert section["active"][0]["record_kind"] == EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY
    assert section["active"][0]["notes"] == "Сводный стаж 15 лет"
    assert section["superseded"] == []
    assert section["voided"] == []


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_external_employment_aggregation_in_employee_api(
    client: TestClient,
    linked_person_employee: dict,
    privileged_headers,
) -> None:
    _materialize(linked_person_employee["person_id"])
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    section_service.add_external_employment(
        PprCommandEnvelope(
            command_id=f"r7-emp-emp-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="r7-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
                "notes": "Employee path biography",
            },
            person_id=linked_person_employee["person_id"],
        )
    )
    resp = client.get(
        f"/api/ppr/employees/{linked_person_employee['employee_id']}",
        headers=privileged_headers,
    )
    assert resp.status_code == 200
    section = resp.json()["sections"]["PPR-EMPLOYMENT-BIOGRAPHY"]
    assert len(section["active"]) == 1
    assert section["active"][0]["notes"] == "Employee path biography"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_event_summary_in_materialized_api(client: TestClient, bare_person: int, privileged_headers) -> None:
    _materialize(bare_person)
    resp = client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert events is not None
    assert events["returned_count"] >= 1


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_summary_endpoint(client: TestClient, linked_person_employee: dict, privileged_headers) -> None:
    resp = client.get(
        f"/api/ppr/persons/{linked_person_employee['person_id']}/summary",
        headers=privileged_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"].startswith("R7 API Linked")
    assert "education_active_count" in body
    assert "family_active_count" in body
    assert "external_employment_active_count" in body


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_no_write_side_effects(client: TestClient, bare_person: int, privileged_headers) -> None:
    client.get(f"/api/ppr/persons/{bare_person}", headers=privileged_headers)
    with engine.begin() as conn:
        meta = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.personnel_record_metadata WHERE person_id = :person_id"
            ),
            {"person_id": bare_person},
        ).scalar_one()
        events = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.personnel_record_events WHERE person_id = :person_id"
            ),
            {"person_id": bare_person},
        ).scalar_one()
    assert int(meta) == 0
    assert int(events) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unauthorized_403(client: TestClient, bare_person: int, seed) -> None:
    headers = auth_headers(seed["executor_user_id"])
    resp = client.get(f"/api/ppr/persons/{bare_person}", headers=headers)
    assert resp.status_code == 403

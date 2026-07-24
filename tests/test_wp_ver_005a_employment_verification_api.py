"""WP-VER-005A: employment revision producer wiring + verification HTTP API."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
)
from app.db.models.personnel_verification import (
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    TASK_STATUS_REJECTED,
)
from app.main import app
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import RESULT_STATUS_COMMITTED
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.section_models import SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run alembic upgrade head")
        if not table_exists(conn, "verification_tasks"):
            pytest.skip("verification tables missing — run alembic upgrade head")
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip("personnel_record_metadata missing — run alembic upgrade head")


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def person_id(seed):
    # Depend on seed so person/attestation cleanup runs before seed user teardown.
    _ = seed
    require_ppr_schema()
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        pid = insert_person(conn, full_name=f"VER005A {suffix}")
    yield pid
    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[pid], employee_ids=[])


def _ensure_policy(*, user_id: int) -> int:
    with engine.begin() as conn:
        repo = PersonnelVerificationRepository(conn)
        active = repo.get_active_policy(CONTROL_POINT_EMPLOYMENT_EPISODE)
        if active is not None:
            return active.policy_id
        draft = repo.create_policy_draft(
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            effective_from=date(2026, 1, 1),
            decision_basis=f"WP-VER-005A policy {uuid4().hex[:8]}",
            created_by_user_id=user_id,
        )
        published = repo.publish_policy(policy_id=draft.policy_id, published_by_user_id=user_id)
        return published.policy_id


def _materialize(person_id: int) -> None:
    PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort()).materialize_ppr(
        PprCommandEnvelope(
            command_id=f"ver005a-mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="ver005a-test",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        )
    )


def _add_employment(person_id: int, *, employer_name: str = "Prior Clinic") -> tuple[int, datetime]:
    result = PprSectionApplicationService(authorization=AllowAllAuthorizationPort()).add_external_employment(
        PprCommandEnvelope(
            command_id=f"ver005a-add-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="ver005a-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": employer_name,
                "position_title": "Physician",
                "started_at": date(2018, 1, 1),
            },
            person_id=person_id,
        )
    )
    assert result.section_record_id is not None
    with engine.begin() as conn:
        updated_at = conn.execute(
            text(
                "SELECT updated_at FROM public.person_external_employment WHERE employment_id = :rid"
            ),
            {"rid": result.section_record_id},
        ).scalar_one()
    return int(result.section_record_id), updated_at


def _lifecycle(employment_id: int) -> str:
    with engine.begin() as conn:
        return str(
            conn.execute(
                text(
                    "SELECT lifecycle_status FROM public.person_external_employment "
                    "WHERE employment_id = :rid"
                ),
                {"rid": employment_id},
            ).scalar_one()
        )


def _prior_updated_at(employment_id: int) -> datetime:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "SELECT updated_at FROM public.person_external_employment WHERE employment_id = :rid"
            ),
            {"rid": employment_id},
        ).scalar_one()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_openapi_has_employment_verification_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json().get("paths", {})
    assert "/api/personnel-verification/employment/pending-tasks" in paths
    assert "/api/personnel-verification/employment/revisions/{revision_id}/state" in paths
    assert "/api/personnel-verification/employment/tasks/{task_id}/confirm" in paths
    assert "/api/personnel-verification/employment/tasks/{task_id}/reject" in paths


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_supersede_creates_pending_revision_and_task_without_superseding_prior(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    prior_id, updated_at = _add_employment(person_id)

    resp = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records/{prior_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"ver005a-sup-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Pending Clinic",
                "position_title": "Surgeon",
                "started_at": "2021-01-01",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    revision_id = resp.json()["section_record_id"]
    assert revision_id != prior_id
    assert _lifecycle(prior_id) == LIFECYCLE_STATUS_ACTIVE
    assert _lifecycle(revision_id) == LIFECYCLE_STATUS_ACTIVE

    tasks = client.get(
        f"/api/personnel-verification/employment/pending-tasks?person_id={person_id}",
        headers=privileged_headers,
    )
    assert tasks.status_code == 200, tasks.text
    items = tasks.json()["items"]
    assert len(items) == 1
    assert items[0]["object_id"] == prior_id
    assert items[0]["object_version_id"] == revision_id
    assert items[0]["status"] == TASK_STATUS_PENDING

    read_resp = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    assert read_resp.status_code == 200
    active = read_resp.json()["sections"][SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY]["active"]
    active_ids = {row["record_id"] for row in active}
    assert active_ids == {prior_id}
    assert not any(row["employer_name"] == "Pending Clinic" for row in active)

    state = client.get(
        f"/api/personnel-verification/employment/revisions/{revision_id}/state",
        headers=privileged_headers,
    )
    assert state.status_code == 200, state.text
    assert state.json()["state"] == "pending"
    assert state.json()["object_version_id"] == revision_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_confirm_shows_revision_and_supersedes_prior(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    prior_id, updated_at = _add_employment(person_id)
    supersede = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records/{prior_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"ver005a-sup-c-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Confirmed Clinic",
                "position_title": "Lead",
                "started_at": "2022-01-01",
            },
        },
    )
    assert supersede.status_code == 200, supersede.text
    revision_id = supersede.json()["section_record_id"]
    task_id = client.get(
        f"/api/personnel-verification/employment/pending-tasks?person_id={person_id}",
        headers=privileged_headers,
    ).json()["items"][0]["task_id"]

    confirm = client.post(
        f"/api/personnel-verification/employment/tasks/{task_id}/confirm",
        headers=privileged_headers,
        json={"expected_prior_updated_at": _prior_updated_at(prior_id).isoformat()},
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["task"]["status"] == TASK_STATUS_COMPLETED
    assert body["prior_lifecycle_status"] == LIFECYCLE_STATUS_SUPERSEDED
    assert body["revision_lifecycle_status"] == LIFECYCLE_STATUS_ACTIVE
    assert _lifecycle(prior_id) == LIFECYCLE_STATUS_SUPERSEDED
    assert _lifecycle(revision_id) == LIFECYCLE_STATUS_ACTIVE

    read_resp = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    section = read_resp.json()["sections"][SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY]
    assert any(row["record_id"] == revision_id for row in section["active"])
    assert any(row["record_id"] == prior_id for row in section["superseded"])
    assert not any(row["record_id"] == prior_id for row in section["active"])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_reject_keeps_prior_and_voids_revision(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    prior_id, updated_at = _add_employment(person_id)
    supersede = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records/{prior_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"ver005a-sup-r-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Rejected Clinic",
                "position_title": "Nurse",
                "started_at": "2020-01-01",
            },
        },
    )
    revision_id = supersede.json()["section_record_id"]
    task_id = client.get(
        f"/api/personnel-verification/employment/pending-tasks?person_id={person_id}",
        headers=privileged_headers,
    ).json()["items"][0]["task_id"]

    reject = client.post(
        f"/api/personnel-verification/employment/tasks/{task_id}/reject",
        headers=privileged_headers,
        json={
            "expected_prior_updated_at": _prior_updated_at(prior_id).isoformat(),
            "comment": "incorrect dates",
        },
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["task"]["status"] == TASK_STATUS_REJECTED
    assert _lifecycle(prior_id) == LIFECYCLE_STATUS_ACTIVE
    assert _lifecycle(revision_id) == LIFECYCLE_STATUS_VOIDED

    read_resp = client.get(f"/api/ppr/persons/{person_id}", headers=privileged_headers)
    section = read_resp.json()["sections"][SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY]
    assert any(row["record_id"] == prior_id for row in section["active"])
    assert any(row["record_id"] == revision_id for row in section["voided"])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unauthorized_and_non_admin_are_denied(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    _add_employment(person_id)

    bare = client.get("/api/personnel-verification/employment/pending-tasks")
    assert bare.status_code in (401, 403)

    plain_headers = auth_headers(seed["executor_user_id"])
    denied = client.get(
        f"/api/personnel-verification/employment/pending-tasks?person_id={person_id}",
        headers=plain_headers,
    )
    assert denied.status_code == 403

    missing = client.get(
        "/api/personnel-verification/employment/revisions/999999999/state",
        headers=privileged_headers,
    )
    assert missing.status_code == 404


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repeat_confirm_and_cas_conflict_leave_no_partial_state(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    prior_id, updated_at = _add_employment(person_id)
    supersede = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records/{prior_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"ver005a-sup-cas-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "CAS Clinic",
                "position_title": "Doc",
                "started_at": "2023-01-01",
            },
        },
    )
    revision_id = supersede.json()["section_record_id"]
    task_id = client.get(
        f"/api/personnel-verification/employment/pending-tasks?person_id={person_id}",
        headers=privileged_headers,
    ).json()["items"][0]["task_id"]
    token = _prior_updated_at(prior_id)

    first = client.post(
        f"/api/personnel-verification/employment/tasks/{task_id}/confirm",
        headers=privileged_headers,
        json={"expected_prior_updated_at": token.isoformat()},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/personnel-verification/employment/tasks/{task_id}/confirm",
        headers=privileged_headers,
        json={"expected_prior_updated_at": token.isoformat()},
    )
    assert second.status_code == 409, second.text
    with engine.begin() as conn:
        attest_count = conn.execute(
            text("SELECT COUNT(*) FROM public.verification_attestations WHERE task_id = :tid"),
            {"tid": task_id},
        ).scalar_one()
    assert int(attest_count) == 1
    assert _lifecycle(prior_id) == LIFECYCLE_STATUS_SUPERSEDED
    assert _lifecycle(revision_id) == LIFECYCLE_STATUS_ACTIVE

    # Fresh pending + stale CAS on confirm
    prior2, updated2 = _add_employment(person_id, employer_name="CAS Prior 2")
    supersede2 = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records/{prior2}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"ver005a-sup-cas2-{uuid4().hex}",
            "expected_updated_at": updated2.isoformat(),
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "CAS Pending 2",
                "position_title": "Doc",
                "started_at": "2024-01-01",
            },
        },
    )
    revision2 = supersede2.json()["section_record_id"]
    task2 = client.get(
        f"/api/personnel-verification/employment/pending-tasks?person_id={person_id}",
        headers=privileged_headers,
    ).json()["items"][0]["task_id"]
    stale = _prior_updated_at(prior2)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.person_external_employment
                SET updated_at = NOW() + INTERVAL '1 second'
                WHERE employment_id = :rid
                """
            ),
            {"rid": prior2},
        )
    conflict = client.post(
        f"/api/personnel-verification/employment/tasks/{task2}/confirm",
        headers=privileged_headers,
        json={"expected_prior_updated_at": stale.isoformat()},
    )
    assert conflict.status_code == 409, conflict.text
    assert _lifecycle(prior2) == LIFECYCLE_STATUS_ACTIVE
    assert _lifecycle(revision2) == LIFECYCLE_STATUS_ACTIVE
    with engine.begin() as conn:
        attest2 = conn.execute(
            text("SELECT COUNT(*) FROM public.verification_attestations WHERE task_id = :tid"),
            {"tid": task2},
        ).scalar_one()
    assert int(attest2) == 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_add_and_void_remain_unchanged(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    create = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records",
        headers=privileged_headers,
        json={
            "command_id": f"ver005a-create-{uuid4().hex}",
            "record": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "Add Clinic",
                "position_title": "GP",
                "started_at": "2017-01-01",
            },
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["status"] == RESULT_STATUS_COMMITTED
    record_id = create.json()["section_record_id"]
    updated_at = _prior_updated_at(record_id)

    void = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records/{record_id}/void",
        headers=privileged_headers,
        json={
            "command_id": f"ver005a-void-{uuid4().hex}",
            "reason": "duplicate",
            "expected_updated_at": updated_at.isoformat(),
        },
    )
    assert void.status_code == 200, void.text
    assert _lifecycle(record_id) == LIFECYCLE_STATUS_VOIDED

    # Application-level void path also intact
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    added = section_service.add_external_employment(
        PprCommandEnvelope(
            command_id=f"ver005a-app-add-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="ver005a-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": "App Add",
                "position_title": "Role",
                "started_at": date(2016, 1, 1),
            },
            person_id=person_id,
        )
    )
    assert added.section_record_id is not None
    void_app = section_service.void_external_employment(
        PprCommandEnvelope(
            command_id=f"ver005a-app-void-{uuid4().hex}",
            command_type=COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT,
            actor_id="ver005a-test",
            requested_at=datetime.now(UTC),
            payload={
                "record_id": added.section_record_id,
                "reason": "cleanup",
                "expected_updated_at": _prior_updated_at(int(added.section_record_id)),
            },
            person_id=person_id,
        )
    )
    assert void_app.status == RESULT_STATUS_COMMITTED

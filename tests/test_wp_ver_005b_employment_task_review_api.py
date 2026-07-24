"""WP-VER-005B: GET /employment/tasks/{task_id}/review API contract."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
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
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from tests.conftest import auth_headers, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run: alembic upgrade head")
        if not table_exists(conn, "verification_tasks"):
            pytest.skip("verification tables missing — run: alembic upgrade head")
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
def person_id(seed):
    _ = seed
    require_ppr_schema()
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        pid = insert_person(conn, full_name=f"VER005B {suffix}")
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
            decision_basis=f"WP-VER-005B policy {uuid4().hex[:8]}",
            created_by_user_id=user_id,
        )
        published = repo.publish_policy(policy_id=draft.policy_id, published_by_user_id=user_id)
        return published.policy_id


def _materialize(person_id: int) -> None:
    PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort()).materialize_ppr(
        PprCommandEnvelope(
            command_id=f"ver005b-mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="ver005b-test",
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=person_id,
        )
    )


def _add_employment(person_id: int, *, employer_name: str = "Prior Clinic") -> tuple[int, datetime]:
    result = PprSectionApplicationService(authorization=AllowAllAuthorizationPort()).add_external_employment(
        PprCommandEnvelope(
            command_id=f"ver005b-add-{uuid4().hex}",
            command_type=COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT,
            actor_id="ver005b-test",
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


def _prior_updated_at(employment_id: int) -> datetime:
    with engine.begin() as conn:
        return conn.execute(
            text(
                "SELECT updated_at FROM public.person_external_employment WHERE employment_id = :rid"
            ),
            {"rid": employment_id},
        ).scalar_one()


def _create_pending_revision(
    client: TestClient,
    *,
    person_id: int,
    privileged_headers,
    employer_name: str = "Pending Clinic",
) -> tuple[int, int, int]:
    prior_id, updated_at = _add_employment(person_id)
    supersede = client.post(
        f"/api/ppr/persons/{person_id}/employment-biography/records/{prior_id}/supersede",
        headers=privileged_headers,
        json={
            "command_id": f"ver005b-sup-{uuid4().hex}",
            "expected_updated_at": updated_at.isoformat(),
            "replacement": {
                "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
                "employer_name": employer_name,
                "position_title": "Surgeon",
                "started_at": "2021-01-01",
            },
        },
    )
    assert supersede.status_code == 200, supersede.text
    revision_id = int(supersede.json()["section_record_id"])
    tasks = client.get(
        f"/api/personnel-verification/employment/pending-tasks?person_id={person_id}",
        headers=privileged_headers,
    )
    assert tasks.status_code == 200, tasks.text
    items = [
        item
        for item in tasks.json()["items"]
        if item["object_id"] == prior_id and item["object_version_id"] == revision_id
    ]
    assert len(items) == 1
    return prior_id, revision_id, int(items[0]["task_id"])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_review_pending_task_happy_path_identity(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    prior_id, revision_id, task_id = _create_pending_revision(
        client,
        person_id=person_id,
        privileged_headers=privileged_headers,
        employer_name="Review Clinic",
    )

    resp = client.get(
        f"/api/personnel-verification/employment/tasks/{task_id}/review",
        headers=privileged_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task"]["task_id"] == task_id
    assert body["task"]["status"] == TASK_STATUS_PENDING
    assert body["person_id"] == person_id
    assert body["person_full_name"]
    assert body["verification_state"] == "pending"
    assert body["prior"]["employment_id"] == prior_id
    assert body["revision"]["employment_id"] == revision_id
    assert body["task"]["object_id"] == prior_id
    assert body["task"]["object_version_id"] == revision_id
    assert body["revision"]["employer_name"] == "Review Clinic"

    with engine.begin() as conn:
        supersedes = conn.execute(
            text(
                """
                SELECT supersedes_employment_id
                FROM public.person_external_employment
                WHERE employment_id = :rid
                """
            ),
            {"rid": revision_id},
        ).scalar_one()
    assert int(supersedes) == prior_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_review_denied_without_hr_admin(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    _, _, task_id = _create_pending_revision(
        client, person_id=person_id, privileged_headers=privileged_headers
    )

    bare = client.get(f"/api/personnel-verification/employment/tasks/{task_id}/review")
    assert bare.status_code in (401, 403)

    denied = client.get(
        f"/api/personnel-verification/employment/tasks/{task_id}/review",
        headers=auth_headers(seed["executor_user_id"]),
    )
    assert denied.status_code == 403


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_review_rejected_and_completed_tasks_return_409(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)

    prior_r, _, task_reject = _create_pending_revision(
        client,
        person_id=person_id,
        privileged_headers=privileged_headers,
        employer_name="To Reject",
    )
    reject = client.post(
        f"/api/personnel-verification/employment/tasks/{task_reject}/reject",
        headers=privileged_headers,
        json={"expected_prior_updated_at": _prior_updated_at(prior_r).isoformat()},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["task"]["status"] == TASK_STATUS_REJECTED

    rejected_review = client.get(
        f"/api/personnel-verification/employment/tasks/{task_reject}/review",
        headers=privileged_headers,
    )
    assert rejected_review.status_code == 409, rejected_review.text
    assert "prior" not in rejected_review.json()
    assert "revision" not in rejected_review.json()

    prior_c, _, task_confirm = _create_pending_revision(
        client,
        person_id=person_id,
        privileged_headers=privileged_headers,
        employer_name="To Confirm",
    )
    confirm = client.post(
        f"/api/personnel-verification/employment/tasks/{task_confirm}/confirm",
        headers=privileged_headers,
        json={"expected_prior_updated_at": _prior_updated_at(prior_c).isoformat()},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["task"]["status"] == TASK_STATUS_COMPLETED

    completed_review = client.get(
        f"/api/personnel-verification/employment/tasks/{task_confirm}/review",
        headers=privileged_headers,
    )
    assert completed_review.status_code == 409, completed_review.text


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_review_missing_task_returns_404(
    client: TestClient,
    privileged_headers,
    seed,
) -> None:
    _ = seed
    _require_schema()
    resp = client.get(
        "/api/personnel-verification/employment/tasks/999999999/review",
        headers=privileged_headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_review_broken_prior_revision_link_returns_controlled_4xx(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    _, revision_id, task_id = _create_pending_revision(
        client, person_id=person_id, privileged_headers=privileged_headers
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE public.person_external_employment
                SET supersedes_employment_id = NULL
                WHERE employment_id = :rid
                """
            ),
            {"rid": revision_id},
        )

    resp = client.get(
        f"/api/personnel-verification/employment/tasks/{task_id}/review",
        headers=privileged_headers,
    )
    assert resp.status_code in (400, 409, 422), resp.text
    assert resp.status_code != 500


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_review_enforces_personnel_visibility(
    client: TestClient,
    person_id: int,
    privileged_headers,
    seed,
    monkeypatch,
) -> None:
    _ensure_policy(user_id=int(seed["initiator_user_id"]))
    _materialize(person_id)
    _, _, task_id = _create_pending_revision(
        client, person_id=person_id, privileged_headers=privileged_headers
    )

    def _deny(_user, _person_id, **_kwargs):
        raise HTTPException(status_code=404, detail="Person not found.")

    monkeypatch.setattr(
        "app.api.personnel_verification_router.assert_ppr_read_allowed_for_person",
        _deny,
    )
    resp = client.get(
        f"/api/personnel-verification/employment/tasks/{task_id}/review",
        headers=privileged_headers,
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Person not found."

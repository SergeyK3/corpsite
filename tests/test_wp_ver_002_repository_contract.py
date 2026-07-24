"""Repository contract tests for WP-VER-002 personnel verification foundation."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    LIFECYCLE_STATUS_ACTIVE,
    VERIFICATION_STATUS_PENDING,
)
from app.personnel_verification.application.verification_state_service import (
    VerificationStateService,
)
from app.personnel_verification.domain.errors import (
    AttestationImmutableError,
    AttestationValidationError,
    CanonicalRecordUnavailableError,
    ControlledRecordNotFoundError,
    TaskValidationError,
)
from app.personnel_verification.domain.types import (
    ATTESTATION_DECISION_REJECTED,
    ATTESTATION_DECISION_VERIFIED,
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    CONTROL_POINT_MEDICAL_CATEGORY,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
    TASK_STATUS_CANCELLED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    TASK_STATUS_REJECTED,
    VERIFICATION_STATE_PENDING,
    VERIFICATION_STATE_VERIFIED,
)
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository
from tests.conftest import table_exists
from tests.ppr.conftest import insert_employee, insert_person, ppr_db_available


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "verification_policies"):
            pytest.skip("WP-VER-002 schema missing — run alembic upgrade head")
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run alembic upgrade head")


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


def _insert_employment(conn, *, person_id: int, employer_name: str) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.person_external_employment (
                person_id, record_kind, employer_name, position_title,
                started_at, verification_status, lifecycle_status, metadata
            ) VALUES (
                :person_id, :record_kind, :employer_name, :position_title,
                DATE '2020-01-01', :verification_status, :lifecycle_status, '{}'::jsonb
            )
            RETURNING employment_id
            """
        ),
        {
            "person_id": person_id,
            "record_kind": EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
            "employer_name": employer_name,
            "position_title": "Physician",
            "verification_status": VERIFICATION_STATUS_PENDING,
            "lifecycle_status": LIFECYCLE_STATUS_ACTIVE,
        },
    ).mappings().one()
    return int(row["employment_id"])


def _publish_policy(repo: PersonnelVerificationRepository, *, user_id: int, control_point: str):
    draft = repo.create_policy_draft(
        control_point=control_point,
        effective_from=date(2026, 1, 1),
        decision_basis=f"HR decision {uuid4().hex[:8]}",
        created_by_user_id=user_id,
    )
    return repo.publish_policy(policy_id=draft.policy_id, published_by_user_id=user_id)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_policy_publish_and_medical_policy_without_task(seed, db_tx) -> None:
    _require_schema()
    repo = PersonnelVerificationRepository(db_tx)
    user_id = int(seed["initiator_user_id"])

    medical_policy = _publish_policy(
        repo, user_id=user_id, control_point=CONTROL_POINT_MEDICAL_CATEGORY
    )
    assert medical_policy.status == "active"
    assert medical_policy.control_point == CONTROL_POINT_MEDICAL_CATEGORY

    person_id = insert_person(db_tx, full_name=f"Medical Block {uuid4().hex[:6]}")
    with pytest.raises(CanonicalRecordUnavailableError):
        repo.create_pending_task(
            person_id=person_id,
            control_point=CONTROL_POINT_MEDICAL_CATEGORY,
            object_id=1,
            object_version_id=1,
            policy_id=medical_policy.policy_id,
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_independent_employment_tasks_use_object_id_equals_version_and_do_not_supersede(
    seed, db_tx
) -> None:
    """Two independent active employment rows each use object_id = object_version_id.

    Shared physical lineage / related verified+pending revisions are WP-VER-003.
    Creating a task for one row must not supersede another active row.
    """
    _require_schema()
    repo = PersonnelVerificationRepository(db_tx)
    user_id = int(seed["initiator_user_id"])
    employee_id = insert_employee(db_tx, full_name=f"Verifier {uuid4().hex[:6]}")
    person_id = insert_person(db_tx, full_name=f"Indep Emp {uuid4().hex[:6]}")

    policy = _publish_policy(
        repo, user_id=user_id, control_point=CONTROL_POINT_EMPLOYMENT_EPISODE
    )

    employment_a = _insert_employment(
        db_tx, person_id=person_id, employer_name="Clinic A"
    )
    employment_b = _insert_employment(
        db_tx, person_id=person_id, employer_name="Clinic B"
    )

    task_a = repo.create_pending_task(
        person_id=person_id,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_id=employment_a,
        object_version_id=employment_a,
        policy_id=policy.policy_id,
    )
    attestation = repo.create_attestation(
        task_id=task_a.task_id,
        decision=ATTESTATION_DECISION_VERIFIED,
        verifier_user_id=user_id,
        verifier_employee_id=employee_id,
        evidence_ref="scan://employment-a",
        comment="checked",
    )
    assert attestation.decision == ATTESTATION_DECISION_VERIFIED
    assert repo.get_task(task_a.task_id).status == TASK_STATUS_COMPLETED

    task_b = repo.create_pending_task(
        person_id=person_id,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_id=employment_b,
        object_version_id=employment_b,
        policy_id=policy.policy_id,
    )
    assert task_b.status == TASK_STATUS_PENDING
    assert task_b.object_id == task_b.object_version_id == employment_b

    lifecycles = {
        int(row["employment_id"]): str(row["lifecycle_status"])
        for row in db_tx.execute(
            text(
                """
                SELECT employment_id, lifecycle_status
                FROM public.person_external_employment
                WHERE employment_id IN (:a, :b)
                """
            ),
            {"a": employment_a, "b": employment_b},
        ).mappings()
    }
    assert lifecycles[employment_a] == LIFECYCLE_STATUS_ACTIVE
    assert lifecycles[employment_b] == LIFECYCLE_STATUS_ACTIVE

    # PPR verification_status remains untouched by foundation repository.
    statuses = {
        int(row["employment_id"]): str(row["verification_status"])
        for row in db_tx.execute(
            text(
                """
                SELECT employment_id, verification_status
                FROM public.person_external_employment
                WHERE employment_id IN (:a, :b)
                """
            ),
            {"a": employment_a, "b": employment_b},
        ).mappings()
    }
    assert statuses[employment_a] == VERIFICATION_STATUS_PENDING
    assert statuses[employment_b] == VERIFICATION_STATUS_PENDING

    state_service = VerificationStateService(repo)
    verified_state = state_service.resolve_for_version(
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        object_version_id=employment_a,
    )
    pending_state = state_service.resolve_for_version(
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        object_version_id=employment_b,
    )
    assert verified_state.state == VERIFICATION_STATE_VERIFIED
    assert pending_state.state == VERIFICATION_STATE_PENDING


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repository_rejects_object_id_not_equal_object_version_id(seed, db_tx) -> None:
    _require_schema()
    repo = PersonnelVerificationRepository(db_tx)
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"Id Mismatch {uuid4().hex[:6]}")
    policy = _publish_policy(
        repo, user_id=user_id, control_point=CONTROL_POINT_EMPLOYMENT_EPISODE
    )
    employment_a = _insert_employment(
        db_tx, person_id=person_id, employer_name="Clinic A"
    )
    employment_b = _insert_employment(
        db_tx, person_id=person_id, employer_name="Clinic B"
    )

    with pytest.raises(TaskValidationError, match="object_id = object_version_id"):
        repo.create_pending_task(
            person_id=person_id,
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            object_id=employment_a,
            object_version_id=employment_b,
            policy_id=policy.policy_id,
        )

    with pytest.raises((TaskValidationError, ControlledRecordNotFoundError)):
        repo.create_pending_task(
            person_id=person_id,
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            object_id=employment_a,
            object_version_id=9_000_001,
            policy_id=policy.policy_id,
        )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_attestation_rejects_rewrite_and_repository_mutation_api(seed, db_tx) -> None:
    _require_schema()
    repo = PersonnelVerificationRepository(db_tx)
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"Attest {uuid4().hex[:6]}")
    policy = _publish_policy(
        repo, user_id=user_id, control_point=CONTROL_POINT_EMPLOYMENT_EPISODE
    )
    version_id = _insert_employment(db_tx, person_id=person_id, employer_name="Clinic C")
    task = repo.create_pending_task(
        person_id=person_id,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_id=version_id,
        object_version_id=version_id,
        policy_id=policy.policy_id,
    )
    first = repo.create_attestation(
        task_id=task.task_id,
        decision=ATTESTATION_DECISION_REJECTED,
        verifier_user_id=user_id,
    )
    assert repo.get_task(task.task_id).status == TASK_STATUS_REJECTED
    with pytest.raises((AttestationValidationError, TaskValidationError)):
        repo.create_attestation(
            task_id=task.task_id,
            decision=ATTESTATION_DECISION_VERIFIED,
            verifier_user_id=user_id,
        )
    with pytest.raises(AttestationImmutableError):
        repo.update_attestation(attestation_id=first.attestation_id, decision="verified")
    with pytest.raises(AttestationImmutableError):
        repo.delete_attestation(attestation_id=first.attestation_id)

    # DB trigger also blocks raw SQL mutation.
    nested = db_tx.begin_nested()
    with pytest.raises(Exception):
        db_tx.execute(
            text(
                """
                UPDATE public.verification_attestations
                SET comment = 'rewrite'
                WHERE attestation_id = :attestation_id
                """
            ),
            {"attestation_id": first.attestation_id},
        )
    nested.rollback()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_cancel_task_and_unique_pending(seed, db_tx) -> None:
    _require_schema()
    repo = PersonnelVerificationRepository(db_tx)
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"Cancel {uuid4().hex[:6]}")
    policy = _publish_policy(
        repo, user_id=user_id, control_point=CONTROL_POINT_EMPLOYMENT_EPISODE
    )
    version_id = _insert_employment(db_tx, person_id=person_id, employer_name="Clinic D")
    task = repo.create_pending_task(
        person_id=person_id,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_id=version_id,
        object_version_id=version_id,
        policy_id=policy.policy_id,
    )
    with pytest.raises(TaskValidationError):
        repo.create_pending_task(
            person_id=person_id,
            control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
            object_id=version_id,
            object_version_id=version_id,
            policy_id=policy.policy_id,
        )
    cancelled = repo.cancel_task(task.task_id)
    assert cancelled.status == TASK_STATUS_CANCELLED
    # After cancel, a new pending task for same revision+policy is allowed.
    again = repo.create_pending_task(
        person_id=person_id,
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_id=version_id,
        object_version_id=version_id,
        policy_id=policy.policy_id,
    )
    assert again.status == TASK_STATUS_PENDING
    assert again.task_id != task.task_id

"""WP-VER-003 employment_episode pending revision / confirm / reject."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    VERIFICATION_STATUS_PENDING,
)
from app.db.models.personnel_verification import (
    ATTESTATION_DECISION_REJECTED,
    ATTESTATION_DECISION_VERIFIED,
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_REJECTED,
)
from app.personnel_verification.application.employment_revision_service import (
    EmploymentRevisionService,
)
from app.personnel_verification.domain.errors import RevisionConflictError
from app.personnel_verification.infrastructure.repository import PersonnelVerificationRepository
from app.ppr.domain.section_models import SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY
from app.ppr.infrastructure.section_repository import SqlAlchemySectionReadRepository
from tests.conftest import table_exists
from tests.ppr.conftest import insert_person, ppr_db_available

REVISION_ID = "p7q8r9s0t1u2"
PREVIOUS_REVISION = "o6p7q8r9s0t1"


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run alembic upgrade head")
        if not table_exists(conn, "verification_tasks"):
            pytest.skip("verification tables missing — run alembic upgrade head")
        has_col = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'person_external_employment'
                  AND column_name = 'supersedes_employment_id'
                """
            )
        ).first()
        if has_col is None:
            pytest.skip("WP-VER-003 column missing — run alembic upgrade head")


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


def _publish_policy(repo: PersonnelVerificationRepository, *, user_id: int):
    draft = repo.create_policy_draft(
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        effective_from=date(2026, 1, 1),
        decision_basis=f"HR decision {uuid4().hex[:8]}",
        created_by_user_id=user_id,
    )
    return repo.publish_policy(policy_id=draft.policy_id, published_by_user_id=user_id)


def _employment_lifecycle(conn, employment_id: int) -> str:
    return str(
        conn.execute(
            text(
                """
                SELECT lifecycle_status
                FROM public.person_external_employment
                WHERE employment_id = :employment_id
                """
            ),
            {"employment_id": employment_id},
        ).scalar_one()
    )


def _prior_updated_at(conn, employment_id: int):
    return conn.execute(
        text(
            """
            SELECT updated_at
            FROM public.person_external_employment
            WHERE employment_id = :employment_id
            """
        ),
        {"employment_id": employment_id},
    ).scalar_one()


def test_alembic_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revision = script.get_revision(REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_pending_revision_hidden_until_confirm_then_visible(seed, db_tx) -> None:
    _require_schema()
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"VER003 {uuid4().hex[:6]}")
    repo = PersonnelVerificationRepository(db_tx)
    service = EmploymentRevisionService(db_tx)
    reader = SqlAlchemySectionReadRepository(db_tx)
    policy = _publish_policy(repo, user_id=user_id)
    prior_id = _insert_employment(db_tx, person_id=person_id, employer_name="Clinic Prior")

    created = service.create_pending_revision(
        person_id=person_id,
        prior_employment_id=prior_id,
        policy_id=policy.policy_id,
        employer_name="Clinic Pending",
        position_title="Surgeon",
        started_at=date(2021, 1, 1),
        copy_material_fields_from_prior=False,
    )
    assert created.task.object_id == prior_id
    assert created.task.object_version_id == created.revision_employment_id
    assert _employment_lifecycle(db_tx, prior_id) == LIFECYCLE_STATUS_ACTIVE
    assert _employment_lifecycle(db_tx, created.revision_employment_id) == LIFECYCLE_STATUS_ACTIVE

    active = reader.load_active_records(person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY)
    active_ids = {int(r.record_id) for r in active if r.record_id is not None}
    assert active_ids == {prior_id}
    assert reader.load_record(
        person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY, created.revision_employment_id
    ) is not None

    confirmed = service.confirm_pending_revision(
        task_id=created.task.task_id,
        verifier_user_id=user_id,
        expected_prior_updated_at=_prior_updated_at(db_tx, prior_id),
    )
    assert confirmed.task.status == TASK_STATUS_COMPLETED
    assert confirmed.attestation.decision == ATTESTATION_DECISION_VERIFIED
    assert confirmed.prior_lifecycle_status == LIFECYCLE_STATUS_SUPERSEDED
    assert confirmed.revision_lifecycle_status == LIFECYCLE_STATUS_ACTIVE
    assert _employment_lifecycle(db_tx, prior_id) == LIFECYCLE_STATUS_SUPERSEDED
    # verification_status must remain untouched (not SSoT)
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
            {"a": prior_id, "b": created.revision_employment_id},
        ).mappings()
    }
    assert statuses[prior_id] == VERIFICATION_STATUS_PENDING
    assert statuses[created.revision_employment_id] == VERIFICATION_STATUS_PENDING

    active_after = reader.load_active_records(person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY)
    after_ids = {int(r.record_id) for r in active_after if r.record_id is not None}
    assert after_ids == {created.revision_employment_id}


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_reject_voids_revision_keeps_prior(seed, db_tx) -> None:
    _require_schema()
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"VER003rej {uuid4().hex[:6]}")
    repo = PersonnelVerificationRepository(db_tx)
    service = EmploymentRevisionService(db_tx)
    reader = SqlAlchemySectionReadRepository(db_tx)
    policy = _publish_policy(repo, user_id=user_id)
    prior_id = _insert_employment(db_tx, person_id=person_id, employer_name="Clinic A")
    created = service.create_pending_revision(
        person_id=person_id,
        prior_employment_id=prior_id,
        policy_id=policy.policy_id,
        employer_name="Clinic B",
        copy_material_fields_from_prior=False,
        position_title="Nurse",
        started_at=date(2019, 1, 1),
    )
    rejected = service.reject_pending_revision(
        task_id=created.task.task_id,
        verifier_user_id=user_id,
        expected_prior_updated_at=_prior_updated_at(db_tx, prior_id),
    )
    assert rejected.attestation.decision == ATTESTATION_DECISION_REJECTED
    assert rejected.task.status == TASK_STATUS_REJECTED
    assert _employment_lifecycle(db_tx, prior_id) == LIFECYCLE_STATUS_ACTIVE
    assert _employment_lifecycle(db_tx, created.revision_employment_id) == LIFECYCLE_STATUS_VOIDED
    active = reader.load_active_records(person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY)
    assert {int(r.record_id) for r in active if r.record_id is not None} == {prior_id}


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_two_independent_active_episodes_both_visible(seed, db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"VER003ind {uuid4().hex[:6]}")
    a = _insert_employment(db_tx, person_id=person_id, employer_name="A")
    b = _insert_employment(db_tx, person_id=person_id, employer_name="B")
    reader = SqlAlchemySectionReadRepository(db_tx)
    active = reader.load_active_records(person_id, SECTION_CODE_PPR_EMPLOYMENT_BIOGRAPHY)
    assert {int(r.record_id) for r in active if r.record_id is not None} == {a, b}


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_trigger_and_fk_reject_bad_supersedes_and_task_identity(seed, db_tx) -> None:
    _require_schema()
    user_id = int(seed["initiator_user_id"])
    person_a = insert_person(db_tx, full_name=f"VER003a {uuid4().hex[:6]}")
    person_b = insert_person(db_tx, full_name=f"VER003b {uuid4().hex[:6]}")
    emp_a = _insert_employment(db_tx, person_id=person_a, employer_name="A")
    emp_b = _insert_employment(db_tx, person_id=person_b, employer_name="B")
    repo = PersonnelVerificationRepository(db_tx)
    policy = _publish_policy(repo, user_id=user_id)

    nested = db_tx.begin_nested()
    with pytest.raises(Exception):
        db_tx.execute(
            text(
                """
                INSERT INTO public.person_external_employment (
                    person_id, record_kind, employer_name, position_title,
                    started_at, verification_status, lifecycle_status,
                    supersedes_employment_id, metadata
                ) VALUES (
                    :person_id, 'episode', 'X', 'Y', DATE '2020-01-01',
                    'pending', 'active', :supersedes, '{}'::jsonb
                )
                """
            ),
            {"person_id": person_a, "supersedes": emp_b},
        )
    nested.rollback()

    nested = db_tx.begin_nested()
    with pytest.raises(Exception):
        db_tx.execute(
            text(
                """
                INSERT INTO public.verification_tasks (
                    person_id, control_point, object_type, object_id, object_version_id,
                    policy_id, policy_version, status
                ) VALUES (
                    :person_id, :cp, :object_type, :object_id, :object_version_id,
                    :policy_id, 1, 'pending'
                )
                """
            ),
            {
                "person_id": person_a,
                "cp": CONTROL_POINT_EMPLOYMENT_EPISODE,
                "object_type": OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
                "object_id": emp_a,
                "object_version_id": emp_b,
                "policy_id": policy.policy_id,
            },
        )
    nested.rollback()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_repeat_confirm_and_cas_conflict_rollback(seed, db_tx) -> None:
    _require_schema()
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"VER003cas {uuid4().hex[:6]}")
    repo = PersonnelVerificationRepository(db_tx)
    service = EmploymentRevisionService(db_tx)
    policy = _publish_policy(repo, user_id=user_id)
    prior_id = _insert_employment(db_tx, person_id=person_id, employer_name="Clinic CAS")
    created = service.create_pending_revision(
        person_id=person_id,
        prior_employment_id=prior_id,
        policy_id=policy.policy_id,
        employer_name="Clinic CAS v2",
        copy_material_fields_from_prior=False,
        position_title="Doc",
        started_at=date(2022, 1, 1),
    )
    token = _prior_updated_at(db_tx, prior_id)
    service.confirm_pending_revision(
        task_id=created.task.task_id,
        verifier_user_id=user_id,
        expected_prior_updated_at=token,
    )
    nested = db_tx.begin_nested()
    with pytest.raises(RevisionConflictError):
        service.confirm_pending_revision(
            task_id=created.task.task_id,
            verifier_user_id=user_id,
            expected_prior_updated_at=token,
        )
    nested.rollback()
    count = db_tx.execute(
        text("SELECT COUNT(*) FROM public.verification_attestations WHERE task_id = :tid"),
        {"tid": created.task.task_id},
    ).scalar_one()
    assert int(count) == 1

    # Fresh pending + concurrent supersede_pair CAS on prior
    prior2 = _insert_employment(db_tx, person_id=person_id, employer_name="Clinic CAS2")
    created2 = service.create_pending_revision(
        person_id=person_id,
        prior_employment_id=prior2,
        policy_id=policy.policy_id,
        employer_name="Clinic CAS2 v2",
        copy_material_fields_from_prior=False,
        position_title="Doc",
        started_at=date(2023, 1, 1),
    )
    stale = _prior_updated_at(db_tx, prior2)
    # Mutate prior updated_at via direct touch (simulates concurrent supersede CAS loss).
    db_tx.execute(
        text(
            """
            UPDATE public.person_external_employment
            SET updated_at = NOW() + INTERVAL '1 second'
            WHERE employment_id = :employment_id
            """
        ),
        {"employment_id": prior2},
    )
    nested = db_tx.begin_nested()
    with pytest.raises(RevisionConflictError):
        service.confirm_pending_revision(
            task_id=created2.task.task_id,
            verifier_user_id=user_id,
            expected_prior_updated_at=stale,
        )
    nested.rollback()
    assert _employment_lifecycle(db_tx, prior2) == LIFECYCLE_STATUS_ACTIVE
    assert _employment_lifecycle(db_tx, created2.revision_employment_id) == LIFECYCLE_STATUS_ACTIVE
    attest_count = db_tx.execute(
        text("SELECT COUNT(*) FROM public.verification_attestations WHERE task_id = :tid"),
        {"tid": created2.task.task_id},
    ).scalar_one()
    assert int(attest_count) == 0


def test_intake_employment_tenure_does_not_read_ppr_dual_version() -> None:
    source = Path("app/personnel_intake/domain/employment_tenure.py").read_text(encoding="utf-8")
    assert "person_external_employment" not in source
    assert "supersedes_employment_id" not in source
    assert "verification_attestations" not in source

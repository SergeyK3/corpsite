"""Schema tests for WP-VER-002 personnel verification foundation."""
from __future__ import annotations

from datetime import date
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
from app.personnel_verification.domain.types import (
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    CONTROL_POINT_MEDICAL_CATEGORY,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
)
from tests.conftest import table_exists
from tests.ppr.conftest import insert_person, ppr_db_available

REVISION_ID = "o6p7q8r9s0t1"
PREVIOUS_REVISION = "n5o6p7q8r9s0"

WP_VER_002_TABLES = (
    "verification_policies",
    "verification_tasks",
    "verification_attestations",
)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_schema() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, name) for name in WP_VER_002_TABLES):
            pytest.skip(
                f"WP-VER-002 tables missing — run: alembic upgrade head (revision {REVISION_ID})"
            )
        if not table_exists(conn, "person_external_employment"):
            pytest.skip("person_external_employment missing — run alembic upgrade head")


def _expect_sql_failure(conn, sql: str, params: dict | None = None) -> None:
    nested = conn.begin_nested()
    with pytest.raises(Exception):
        conn.execute(text(sql), params or {})
    nested.rollback()


def _insert_employment(
    conn,
    *,
    person_id: int,
    employer_name: str,
    lifecycle_status: str = LIFECYCLE_STATUS_ACTIVE,
) -> int:
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
            "lifecycle_status": lifecycle_status,
        },
    ).mappings().one()
    return int(row["employment_id"])


def _insert_active_policy(conn, *, user_id: int, control_point: str):
    return conn.execute(
        text(
            """
            INSERT INTO public.verification_policies (
                control_point, policy_version, status, effective_from, decision_basis,
                created_by_user_id, published_by_user_id, published_at
            ) VALUES (
                :cp, 1, 'active', CURRENT_DATE, 'basis', :user_id, :user_id, NOW()
            )
            RETURNING policy_id, policy_version
            """
        ),
        {"cp": control_point, "user_id": user_id},
    ).mappings().one()


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


def test_alembic_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revision = script.get_revision(REVISION_ID)
    assert revision is not None
    assert PREVIOUS_REVISION in revision.down_revision if isinstance(
        revision.down_revision, (list, tuple, set)
    ) else revision.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_tables_and_indexes_exist(db_tx) -> None:
    _require_schema()
    for name in WP_VER_002_TABLES:
        assert table_exists(db_tx, name)

    indexes = {
        row[0]
        for row in db_tx.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname IN (
                    'uq_vp_one_active_per_control_point',
                    'uq_vt_one_pending_per_version_policy',
                    'uq_va_task_id'
                  )
                """
            )
        )
    }
    assert "uq_vp_one_active_per_control_point" in indexes
    assert "uq_vt_one_pending_per_version_policy" in indexes
    assert "uq_va_task_id" in indexes

    index_def = db_tx.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'uq_vt_one_pending_per_version_policy'
            """
        )
    ).scalar_one()
    assert "object_type" in index_def
    assert "object_version_id" in index_def
    assert "policy_id" in index_def
    assert "status = 'pending'" in index_def


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_policy_control_point_and_date_checks(seed, db_tx) -> None:
    _require_schema()
    user_id = int(seed["initiator_user_id"])

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.verification_policies (
            control_point, policy_version, status, effective_from, decision_basis, created_by_user_id
        ) VALUES ('external_employment', 1, 'draft', CURRENT_DATE, 'basis', :user_id)
        """,
        {"user_id": user_id},
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.verification_policies (
            control_point, policy_version, status, effective_from, effective_to,
            decision_basis, created_by_user_id
        ) VALUES (
            :cp, 1, 'draft', DATE '2026-05-01', DATE '2026-01-01', 'basis', :user_id
        )
        """,
        {"cp": CONTROL_POINT_EMPLOYMENT_EPISODE, "user_id": user_id},
    )
    # medical_category is allowed on policy
    row = db_tx.execute(
        text(
            """
            INSERT INTO public.verification_policies (
                control_point, policy_version, status, effective_from, decision_basis, created_by_user_id
            ) VALUES (:cp, 1, 'draft', :ef, 'HR order medical', :user_id)
            RETURNING policy_id
            """
        ),
        {
            "cp": CONTROL_POINT_MEDICAL_CATEGORY,
            "ef": date(2026, 1, 1),
            "user_id": user_id,
        },
    ).mappings().one()
    assert int(row["policy_id"]) > 0


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_unique_pending_task_and_attestation_immutability_trigger(seed, db_tx) -> None:
    _require_schema()
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"VER002 {uuid4().hex[:8]}")
    employment_id = _insert_employment(
        db_tx, person_id=person_id, employer_name=f"Clinic {uuid4().hex[:6]}"
    )

    policy = _insert_active_policy(
        db_tx, user_id=user_id, control_point=CONTROL_POINT_EMPLOYMENT_EPISODE
    )

    task = db_tx.execute(
        text(
            """
            INSERT INTO public.verification_tasks (
                person_id, control_point, object_type, object_id, object_version_id,
                policy_id, policy_version, status
            ) VALUES (
                :person_id, :cp, :object_type, :object_id, :object_version_id,
                :policy_id, :policy_version, 'pending'
            )
            RETURNING task_id
            """
        ),
        {
            "person_id": person_id,
            "cp": CONTROL_POINT_EMPLOYMENT_EPISODE,
            "object_type": OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
            "object_id": employment_id,
            "object_version_id": employment_id,
            "policy_id": int(policy["policy_id"]),
            "policy_version": int(policy["policy_version"]),
        },
    ).mappings().one()

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.verification_tasks (
            person_id, control_point, object_type, object_id, object_version_id,
            policy_id, policy_version, status
        ) VALUES (
            :person_id, :cp, :object_type, :object_id, :object_version_id,
            :policy_id, :policy_version, 'pending'
        )
        """,
        {
            "person_id": person_id,
            "cp": CONTROL_POINT_EMPLOYMENT_EPISODE,
            "object_type": OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
            "object_id": employment_id,
            "object_version_id": employment_id,
            "policy_id": int(policy["policy_id"]),
            "policy_version": int(policy["policy_version"]),
        },
    )

    attestation = db_tx.execute(
        text(
            """
            INSERT INTO public.verification_attestations (
                task_id, person_id, control_point, object_type, object_id, object_version_id,
                policy_id, policy_version, decision, verifier_user_id, decided_at
            ) VALUES (
                :task_id, :person_id, :cp, :object_type, :object_id, :object_version_id,
                :policy_id, :policy_version, 'verified', :user_id, NOW()
            )
            RETURNING attestation_id
            """
        ),
        {
            "task_id": int(task["task_id"]),
            "person_id": person_id,
            "cp": CONTROL_POINT_EMPLOYMENT_EPISODE,
            "object_type": OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
            "object_id": employment_id,
            "object_version_id": employment_id,
            "policy_id": int(policy["policy_id"]),
            "policy_version": int(policy["policy_version"]),
            "user_id": user_id,
        },
    ).mappings().one()

    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.verification_attestations
        SET decision = 'rejected'
        WHERE attestation_id = :attestation_id
        """,
        {"attestation_id": int(attestation["attestation_id"])},
    )
    _expect_sql_failure(
        db_tx,
        """
        DELETE FROM public.verification_attestations
        WHERE attestation_id = :attestation_id
        """,
        {"attestation_id": int(attestation["attestation_id"])},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_task_ppr_ref_trigger_rejects_orphan_wrong_person_id_mismatch_and_lifecycle(
    seed, db_tx
) -> None:
    """DB guards for WP-VER-002 foundation identity (object_id = object_version_id).

    Physical lineage / related verified+pending revisions are WP-VER-003.
    """
    _require_schema()
    user_id = int(seed["initiator_user_id"])
    person_a = insert_person(db_tx, full_name=f"VER002 A {uuid4().hex[:6]}")
    person_b = insert_person(db_tx, full_name=f"VER002 B {uuid4().hex[:6]}")
    employment_a = _insert_employment(
        db_tx, person_id=person_a, employer_name="Clinic A"
    )
    employment_a2 = _insert_employment(
        db_tx, person_id=person_a, employer_name="Clinic A2"
    )
    employment_b = _insert_employment(
        db_tx, person_id=person_b, employer_name="Clinic B"
    )
    superseded_id = _insert_employment(
        db_tx,
        person_id=person_a,
        employer_name="Clinic Superseded",
        lifecycle_status=LIFECYCLE_STATUS_SUPERSEDED,
    )
    voided_id = _insert_employment(
        db_tx,
        person_id=person_a,
        employer_name="Clinic Voided",
        lifecycle_status=LIFECYCLE_STATUS_VOIDED,
    )
    policy = _insert_active_policy(
        db_tx, user_id=user_id, control_point=CONTROL_POINT_EMPLOYMENT_EPISODE
    )
    policy_id = int(policy["policy_id"])
    policy_version = int(policy["policy_version"])

    task_sql = """
        INSERT INTO public.verification_tasks (
            person_id, control_point, object_type, object_id, object_version_id,
            policy_id, policy_version, status
        ) VALUES (
            :person_id, :cp, :object_type, :object_id, :object_version_id,
            :policy_id, :policy_version, 'pending'
        )
    """
    base = {
        "cp": CONTROL_POINT_EMPLOYMENT_EPISODE,
        "object_type": OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        "policy_id": policy_id,
        "policy_version": policy_version,
    }

    # Orphan object_version_id (and equal object_id for the equality check order)
    _expect_sql_failure(
        db_tx,
        task_sql,
        {
            **base,
            "person_id": person_a,
            "object_id": 9_000_001,
            "object_version_id": 9_000_001,
        },
    )
    # Task person_id differs from employment person
    _expect_sql_failure(
        db_tx,
        task_sql,
        {
            **base,
            "person_id": person_b,
            "object_id": employment_a,
            "object_version_id": employment_a,
        },
    )
    # Foundation forbids object_id != object_version_id even for two active rows
    # of the same person (same-person existence is not lineage proof).
    _expect_sql_failure(
        db_tx,
        task_sql,
        {
            **base,
            "person_id": person_a,
            "object_id": employment_a,
            "object_version_id": employment_a2,
        },
    )
    # object_id != object_version_id with another person's employment as object_id
    _expect_sql_failure(
        db_tx,
        task_sql,
        {
            **base,
            "person_id": person_a,
            "object_id": employment_b,
            "object_version_id": employment_a,
        },
    )
    # Non-active lifecycle
    _expect_sql_failure(
        db_tx,
        task_sql,
        {
            **base,
            "person_id": person_a,
            "object_id": superseded_id,
            "object_version_id": superseded_id,
        },
    )
    _expect_sql_failure(
        db_tx,
        task_sql,
        {
            **base,
            "person_id": person_a,
            "object_id": voided_id,
            "object_version_id": voided_id,
        },
    )

    # Happy path: real active employment with object_id = object_version_id
    ok = db_tx.execute(
        text(task_sql + " RETURNING task_id"),
        {
            **base,
            "person_id": person_a,
            "object_id": employment_a,
            "object_version_id": employment_a,
        },
    ).mappings().one()
    assert int(ok["task_id"]) > 0

    # UPDATE of referential fields is also guarded
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.verification_tasks
        SET object_version_id = :bad_version
        WHERE task_id = :task_id
        """,
        {"bad_version": 9_000_003, "task_id": int(ok["task_id"])},
    )
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.verification_tasks
        SET object_id = :other_id
        WHERE task_id = :task_id
        """,
        {"other_id": employment_a2, "task_id": int(ok["task_id"])},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_medical_category_task_blocked_until_typed_canonical_home(seed, db_tx) -> None:
    _require_schema()
    user_id = int(seed["initiator_user_id"])
    person_id = insert_person(db_tx, full_name=f"Medical DB {uuid4().hex[:6]}")
    policy = _insert_active_policy(
        db_tx, user_id=user_id, control_point=CONTROL_POINT_MEDICAL_CATEGORY
    )

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.verification_tasks (
            person_id, control_point, object_type, object_id, object_version_id,
            policy_id, policy_version, status
        ) VALUES (
            :person_id, :cp, 'person_medical_category', 1, 1,
            :policy_id, :policy_version, 'pending'
        )
        """,
        {
            "person_id": person_id,
            "cp": CONTROL_POINT_MEDICAL_CATEGORY,
            "policy_id": int(policy["policy_id"]),
            "policy_version": int(policy["policy_version"]),
        },
    )

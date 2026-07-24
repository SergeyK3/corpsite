"""Education plugin + engine integration (WP-006 §11 EDU decide subset)."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import EDUCATION_KIND_BASIC, LIFECYCLE_STATUS_ACTIVE
from app.personnel_intake.application.reconciliation.dto import DecideSectionCommand
from app.personnel_intake.application.reconciliation.engine import ReconciliationDecisionEngine
from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
)
from app.personnel_intake.application.reconciliation.registry import SectionReconciliationRegistry
from app.personnel_intake.domain.reconciliation.actions import (
    APPLY_STATUS_PENDING,
    REASON_MATCH_AMBIGUOUS,
    REASON_MATCH_CONFIDENCE_LOW,
    REASON_MATCH_EXACT_KEEP,
    REASON_MATCH_EXACT_UPDATE,
    REASON_MATCH_NONE_CONFIDENT,
    RECONCILE_ACTION_ADD,
    RECONCILE_ACTION_KEEP_EXISTING,
    RECONCILE_ACTION_MANUAL_REVIEW,
    RECONCILE_ACTION_UPDATE_VERSION,
)
from app.personnel_intake.domain.reconciliation.errors import ReconciliationValidationError
from app.ppr.domain.section_models import EducationRecord
from app.ppr.infrastructure.section_repository import (
    SqlAlchemySectionMutationRepository,
    SqlAlchemySectionReadRepository,
)
from tests.conftest import insert_returning_id, table_exists
from tests.personnel_intake.edu_plugin_helpers import intake_row
from tests.ppr.conftest import insert_person, ppr_db_available

TABLE = "personnel_intake_reconciliation_decisions"


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, TABLE):
            pytest.skip(f"{TABLE} missing — run: alembic upgrade head")
        if not table_exists(conn, "person_education"):
            pytest.skip("person_education missing — run: alembic upgrade head")


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


def _seed(db_tx, seed):
    person_id = insert_person(db_tx, full_name=f"Edu Eng {uuid4().hex[:6]}")
    application_id = insert_returning_id(
        db_tx,
        table="personnel_applications",
        id_col="application_id",
        values={
            "person_id": person_id,
            "application_received_at": date(2026, 7, 24),
            "registered_by_user_id": int(seed["initiator_user_id"]),
            "idempotency_key": f"edu-recon-{uuid4().hex}",
        },
    )
    return person_id, application_id


def _engine(plugin: EducationReconciliationPlugin | None = None) -> ReconciliationDecisionEngine:
    registry = SectionReconciliationRegistry()
    registry.register(plugin or EducationReconciliationPlugin())
    return ReconciliationDecisionEngine(registry)


def _cmd(application_id: int, person_id: int, records: list[dict], **overrides) -> DecideSectionCommand:
    data = dict(
        application_id=application_id,
        person_id=person_id,
        section_code="education",
        section_payload={"records": records},
        decision_source="system",
        correlation_id="edu-corr",
        digest_algorithm_version="canon-json-v1",
    )
    data.update(overrides)
    return DecideSectionCommand(**data)


def _insert_education(
    conn,
    *,
    person_id: int,
    institution_name: str = "МГУ",
    education_kind: str = EDUCATION_KIND_BASIC,
    specialty: str | None = "Математика",
    qualification: str | None = "Бакалавр",
    started_at: date | None = date(2015, 9, 1),
    completed_at: date | None = date(2019, 6, 30),
    diploma_number: str | None = "D-1",
    document_type: str | None = "diploma",
    lifecycle_status: str = LIFECYCLE_STATUS_ACTIVE,
) -> EducationRecord:
    mutation = SqlAlchemySectionMutationRepository(conn)
    metadata = {"document_type": document_type} if document_type is not None else {}
    inserted = mutation.insert_record(
        EducationRecord(
            person_id=person_id,
            education_kind=education_kind,
            institution_name=institution_name,
            specialty=specialty,
            qualification=qualification,
            started_at=started_at,
            completed_at=completed_at,
            diploma_number=diploma_number,
            metadata=metadata or None,
            lifecycle_status=lifecycle_status,
        )
    )
    assert inserted.record_id is not None
    assert inserted.updated_at is not None
    return inserted


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_01_engine_confident_add(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    result = _engine().decide_section(
        db_tx,
        _cmd(application_id, person_id, [intake_row(institution="New Uni")]),
    )
    assert result.decisions[0].action == RECONCILE_ACTION_ADD
    assert result.decisions[0].reason_code == REASON_MATCH_NONE_CONFIDENT
    assert result.decisions[0].decision.apply_status == APPLY_STATUS_PENDING
    assert result.section_apply_mode == "per_record"
    assert result.policy_version == "1.0.0"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_02_engine_keep_existing(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    _insert_education(db_tx, person_id=person_id)
    result = _engine().decide_section(
        db_tx,
        _cmd(application_id, person_id, [intake_row()]),
    )
    outcome = result.decisions[0]
    assert outcome.action == RECONCILE_ACTION_KEEP_EXISTING
    assert outcome.reason_code == REASON_MATCH_EXACT_KEEP


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_03_engine_update_version_row_version(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    row = _insert_education(db_tx, person_id=person_id, specialty=None)
    result = _engine().decide_section(
        db_tx,
        _cmd(application_id, person_id, [intake_row(specialty="Физика")]),
    )
    outcome = result.decisions[0]
    assert outcome.action == RECONCILE_ACTION_UPDATE_VERSION
    assert outcome.reason_code == REASON_MATCH_EXACT_UPDATE
    assert outcome.decision.expected_row_version == row.updated_at.isoformat()
    assert outcome.decision.target_canonical_record_id == row.record_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_04_engine_ambiguous_manual(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    # Same identity would normally be blocked by PPR duplicate guard; insert via raw SQL.
    _insert_education(db_tx, person_id=person_id, institution_name="DupU")
    db_tx.execute(
        text(
            """
            INSERT INTO public.person_education (
                person_id, education_kind, institution_name, specialty,
                started_at, completed_at, lifecycle_status, verification_status
            ) VALUES (
                :person_id, :kind, :inst, 'X',
                DATE '2010-01-02', DATE '2014-01-02', 'active', 'pending'
            )
            """
        ),
        {"person_id": person_id, "kind": EDUCATION_KIND_BASIC, "inst": "DupU"},
    )
    result = _engine().decide_section(
        db_tx,
        _cmd(
            application_id,
            person_id,
            [intake_row(institution="DupU", year_from="2010-01-02", year_to="2014-01-02")],
        ),
    )
    outcome = result.decisions[0]
    assert outcome.action == RECONCILE_ACTION_MANUAL_REVIEW
    assert outcome.reason_code == REASON_MATCH_AMBIGUOUS
    candidates = outcome.decision.evidence["candidate_canonical_record_ids"]
    assert len(candidates) == 2
    assert outcome.decision.evidence["match_kind"] == "ambiguous"
    # Q3 marker stays on MatchOutcome.detail (WP-006 §8.4); WP-005 evidence omits detail.


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_05d_year_only_fix_new_intent(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    eng = _engine()
    first = eng.decide_section(
        db_tx,
        _cmd(
            application_id,
            person_id,
            [intake_row(institution="YearFix", year_from="2019")],
        ),
    )
    assert first.decisions[0].action == RECONCILE_ACTION_MANUAL_REVIEW
    assert first.decisions[0].reason_code == REASON_MATCH_CONFIDENCE_LOW
    second = eng.decide_section(
        db_tx,
        _cmd(
            application_id,
            person_id,
            [intake_row(institution="YearFix", year_from="2019-09-15")],
        ),
    )
    assert second.batch_idempotent_replay is False
    assert second.decisions[0].idempotent_replay is False
    assert second.decision_ids[0] != first.decision_ids[0]
    assert second.decisions[0].action == RECONCILE_ACTION_ADD


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_12_matcher_version_bump_new_key(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    plugin = EducationReconciliationPlugin()
    eng = _engine(plugin)
    first = eng.decide_section(
        db_tx,
        _cmd(application_id, person_id, [intake_row(institution="BumpU")]),
    )
    plugin.matcher_version = "1.0.1"
    second = eng.decide_section(
        db_tx,
        _cmd(application_id, person_id, [intake_row(institution="BumpU")]),
    )
    assert second.decision_ids[0] != first.decision_ids[0]
    assert second.decisions[0].decision.matcher_version == "1.0.1"


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_13_coverage_ordering(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    records = [
        intake_row(institution="A Uni"),
        intake_row(institution="B Uni"),
        intake_row(institution="C Uni"),
    ]
    result = _engine().decide_section(db_tx, _cmd(application_id, person_id, records))
    assert len(result.decision_ids) == 3
    assert [d.proposal_index for d in result.decisions] == [0, 1, 2]
    assert list(result.decision_ids) == [d.decision.decision_id for d in result.decisions]


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_14_inactive_ignored(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    mutation = SqlAlchemySectionMutationRepository(db_tx)
    voided = mutation.insert_record(
        EducationRecord(
            person_id=person_id,
            education_kind=EDUCATION_KIND_BASIC,
            institution_name="SameFP",
            specialty="Old",
            started_at=date(2000, 1, 2),
            completed_at=date(2004, 1, 2),
        )
    )
    assert voided.record_id is not None and voided.updated_at is not None
    mutation.void_record(
        person_id,
        "PPR-EDUCATION",
        voided.record_id,
        expected_updated_at=voided.updated_at,
    )
    active = _insert_education(db_tx, person_id=person_id, institution_name="SameFP")
    read = SqlAlchemySectionReadRepository(db_tx)
    active_only = read.load_active_records(person_id, "PPR-EDUCATION")
    assert [r.record_id for r in active_only] == [active.record_id]

    result = _engine().decide_section(
        db_tx,
        _cmd(application_id, person_id, [intake_row(institution="SameFP")]),
    )
    # Match uses active-only snapshot (voided same FP ignored).
    assert result.decisions[0].action == RECONCILE_ACTION_KEEP_EXISTING
    assert result.decisions[0].decision.target_canonical_record_id == active.record_id


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_edu_15_invalid_later_proposal_zero_rows(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    with pytest.raises(ReconciliationValidationError) as exc:
        _engine().decide_section(
            db_tx,
            _cmd(
                application_id,
                person_id,
                [
                    intake_row(institution="Ok Uni"),
                    intake_row(institution="Bad Uni", education_type="nope"),
                ],
            ),
        )
    assert exc.value.code == "INVALID_EDUCATION_TYPE"
    assert (
        db_tx.execute(
            text(f"SELECT count(*) FROM {TABLE} WHERE application_id = :aid"),
            {"aid": application_id},
        ).scalar_one()
        == 0
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_register_education_plugin_helper(seed, db_tx) -> None:
    _require_schema()
    person_id, application_id = _seed(db_tx, seed)
    from app.personnel_intake.application.reconciliation.plugins import (
        register_default_section_plugins,
    )

    registry = SectionReconciliationRegistry()
    register_default_section_plugins(registry)
    eng = ReconciliationDecisionEngine(registry)
    result = eng.decide_section(
        db_tx,
        _cmd(application_id, person_id, [intake_row(institution="Reg Uni")]),
    )
    assert result.decisions[0].action == RECONCILE_ACTION_ADD

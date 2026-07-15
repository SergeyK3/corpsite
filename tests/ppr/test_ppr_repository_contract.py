# tests/ppr/test_ppr_repository_contract.py
"""Repository contract tests for PPR R1 envelope persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.db.models.personnel_migration import (
    DOMAIN_CODE_EDUCATION,
    EDUCATION_KIND_BASIC,
    LIFECYCLE_STATUS_ACTIVE,
    TRAINING_KIND_COURSE,
)
from app.ppr.domain.errors import (
    PprEnvelopeAlreadyExistsError,
    PprEnvelopeNotFoundError,
    PprOptimisticConcurrencyConflictError,
)
from app.ppr.domain.models import (
    HR_RELATIONSHIP_EMPLOYED,
    HR_RELATIONSHIP_UNKNOWN,
    PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE,
    PPR_ENVELOPE_INITIAL_VERSION,
    PPR_LIFECYCLE_ACTIVE,
    PPR_LIFECYCLE_CREATED,
    PprEnvelope,
)
from app.ppr.infrastructure.ppr_repository import SqlAlchemyPprRepository
from tests.conftest import get_columns, insert_returning_id, table_exists


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_schema() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_record_metadata"):
            pytest.skip(
                "personnel_record_metadata missing — run: alembic upgrade head "
                "(revision j0k1l2m3n4o5)"
            )
        if not table_exists(conn, "persons"):
            pytest.skip("persons table missing — run: alembic upgrade head")


def _insert_person(conn, *, full_name: str) -> int:
    suffix = uuid4().hex[:12]
    match_key = f"ppr-r1:{suffix}"
    cols = get_columns(conn, "persons")
    values: dict[str, Any] = {"full_name": full_name}
    if "match_key" in cols:
        values["match_key"] = match_key
    if "source" in cols:
        values["source"] = "manual"
    if "person_status" in cols:
        values["person_status"] = "active"
    return insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values=values,
    )


def _insert_education(conn, *, person_id: int) -> int:
    return insert_returning_id(
        conn,
        table="person_education",
        id_col="education_id",
        values={
            "person_id": person_id,
            "education_kind": EDUCATION_KIND_BASIC,
            "lifecycle_status": LIFECYCLE_STATUS_ACTIVE,
        },
    )


def _insert_training(conn, *, person_id: int) -> int:
    return insert_returning_id(
        conn,
        table="person_training",
        id_col="training_id",
        values={
            "person_id": person_id,
            "training_kind": TRAINING_KIND_COURSE,
            "lifecycle_status": LIFECYCLE_STATUS_ACTIVE,
        },
    )


def _new_envelope(person_id: int) -> PprEnvelope:
    now = datetime.now(timezone.utc)
    return PprEnvelope(
        person_id=person_id,
        lifecycle_state=PPR_ENVELOPE_INITIAL_LIFECYCLE_STATE,
        hr_relationship_context=HR_RELATIONSHIP_UNKNOWN,
        version=PPR_ENVELOPE_INITIAL_VERSION,
        created_at=now,
        updated_at=now,
    )


def _cleanup_person(conn, *, person_id: int) -> None:
    conn.execute(
        text("DELETE FROM public.personnel_record_events WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.personnel_record_metadata WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.person_education WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.person_training WHERE person_id = :person_id"),
        {"person_id": person_id},
    )
    conn.execute(
        text("DELETE FROM public.persons WHERE person_id = :person_id"),
        {"person_id": person_id},
    )


@pytest.fixture
def ppr_person_id():
    _require_schema()
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        person_id = _insert_person(conn, full_name=f"PPR R1 Person {suffix}")
    yield person_id
    with engine.begin() as conn:
        _cleanup_person(conn, person_id=person_id)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ppr_package_import_smoke() -> None:
    import app.ppr  # noqa: F401
    import app.ppr.domain.models  # noqa: F401
    import app.ppr.domain.repositories  # noqa: F401
    import app.ppr.infrastructure.ppr_repository  # noqa: F401

    from app.ppr.domain.repositories import PprRepository
    from app.ppr.infrastructure.ppr_repository import SqlAlchemyPprRepository

    assert PprRepository is not None
    assert SqlAlchemyPprRepository is not None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_exists_false_before_insert(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        assert repo.exists_envelope(ppr_person_id) is False
        assert repo.load_envelope(ppr_person_id) is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_insert_and_load_envelope(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        inserted = repo.insert_envelope(_new_envelope(ppr_person_id))
        loaded = repo.load_envelope(ppr_person_id)

    assert inserted.person_id == ppr_person_id
    assert inserted.lifecycle_state == PPR_LIFECYCLE_CREATED
    assert inserted.hr_relationship_context == HR_RELATIONSHIP_UNKNOWN
    assert inserted.version == 1
    assert loaded is not None
    assert loaded.person_id == inserted.person_id
    assert loaded.lifecycle_state == inserted.lifecycle_state
    assert loaded.hr_relationship_context == inserted.hr_relationship_context
    assert loaded.version == inserted.version
    assert isinstance(loaded, PprEnvelope)
    assert loaded.created_at is not None
    assert loaded.updated_at is not None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_exists_true_after_insert(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        assert repo.exists_envelope(ppr_person_id) is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_duplicate_insert_rejected(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        with pytest.raises(PprEnvelopeAlreadyExistsError):
            repo.insert_envelope(_new_envelope(ppr_person_id))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_duplicate_insert_uses_db_constraint_not_precheck(
    ppr_person_id: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        monkeypatch.setattr(repo, "exists_envelope", lambda _pid: False)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        with pytest.raises(PprEnvelopeAlreadyExistsError):
            repo.insert_envelope(_new_envelope(ppr_person_id))


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_duplicate_insert_leaves_transaction_usable(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        with pytest.raises(PprEnvelopeAlreadyExistsError):
            repo.insert_envelope(_new_envelope(ppr_person_id))
        loaded = repo.load_envelope(ppr_person_id)
        updated = repo.update_envelope(
            loaded.with_updates(hr_relationship_context=HR_RELATIONSHIP_EMPLOYED),
            expected_version=loaded.version,
        )
        assert updated.hr_relationship_context == HR_RELATIONSHIP_EMPLOYED
        assert updated.version == loaded.version + 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_with_correct_expected_version(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        inserted = repo.insert_envelope(_new_envelope(ppr_person_id))
        updated_input = inserted.with_updates(
            lifecycle_state=PPR_LIFECYCLE_ACTIVE,
            hr_relationship_context=HR_RELATIONSHIP_EMPLOYED,
        )
        updated = repo.update_envelope(updated_input, expected_version=inserted.version)

    assert updated.lifecycle_state == PPR_LIFECYCLE_ACTIVE
    assert updated.hr_relationship_context == HR_RELATIONSHIP_EMPLOYED
    assert updated.version == inserted.version + 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_with_stale_expected_version(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        inserted = repo.insert_envelope(_new_envelope(ppr_person_id))
        stale = inserted.with_updates(lifecycle_state=PPR_LIFECYCLE_ACTIVE)
        with pytest.raises(PprOptimisticConcurrencyConflictError):
            repo.update_envelope(stale, expected_version=inserted.version + 99)

        loaded = repo.load_envelope(ppr_person_id)
        assert loaded is not None
        assert loaded.lifecycle_state == PPR_LIFECYCLE_CREATED
        assert loaded.version == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_update_missing_envelope_not_found(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        missing = _new_envelope(ppr_person_id)
        with pytest.raises(PprEnvelopeNotFoundError):
            repo.update_envelope(missing, expected_version=1)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_insert_with_existing_education_rows(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        education_id = _insert_education(conn, person_id=ppr_person_id)
        repo = SqlAlchemyPprRepository(conn)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        edu_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.person_education
                WHERE education_id = :education_id AND person_id = :person_id
                """
            ),
            {"education_id": education_id, "person_id": ppr_person_id},
        ).scalar_one()
        assert int(edu_count) == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_insert_with_existing_training_rows(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        training_id = _insert_training(conn, person_id=ppr_person_id)
        repo = SqlAlchemyPprRepository(conn)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        trn_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.person_training
                WHERE training_id = :training_id AND person_id = :person_id
                """
            ),
            {"training_id": training_id, "person_id": ppr_person_id},
        ).scalar_one()
        assert int(trn_count) == 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_fk_rejects_nonexistent_person_id() -> None:
    _require_schema()
    bogus_person_id = 9_999_999_999
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM public.persons WHERE person_id = :pid LIMIT 1"),
            {"pid": bogus_person_id},
        ).first()
        if exists is not None:
            pytest.skip("bogus person_id unexpectedly exists")
        repo = SqlAlchemyPprRepository(conn)
        with pytest.raises(IntegrityError) as exc_info:
            repo.insert_envelope(_new_envelope(bogus_person_id))
        assert not isinstance(exc_info.value, PprEnvelopeAlreadyExistsError)
        pgcode = getattr(getattr(exc_info.value, "orig", None), "pgcode", None)
        assert pgcode == "23503"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repository_does_not_create_events(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        event_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.personnel_record_events
                WHERE person_id = :person_id AND domain_code = :domain_code
                """
            ),
            {"person_id": ppr_person_id, "domain_code": DOMAIN_CODE_EDUCATION},
        ).scalar_one()
        assert int(event_count) == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_repository_does_not_create_employee(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        before = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.employees
                WHERE person_id = :person_id
                """
            ),
            {"person_id": ppr_person_id},
        ).scalar_one()
        repo = SqlAlchemyPprRepository(conn)
        repo.insert_envelope(_new_envelope(ppr_person_id))
        after = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.employees
                WHERE person_id = :person_id
                """
            ),
            {"person_id": ppr_person_id},
        ).scalar_one()
        assert int(before) == int(after)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_initial_lifecycle_state_matches_wp_pr_004(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        inserted = repo.insert_envelope(_new_envelope(ppr_person_id))
        assert inserted.lifecycle_state == PPR_LIFECYCLE_CREATED


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_timestamps_set_on_insert(ppr_person_id: int) -> None:
    with engine.begin() as conn:
        repo = SqlAlchemyPprRepository(conn)
        inserted = repo.insert_envelope(_new_envelope(ppr_person_id))

    assert inserted.created_at.tzinfo is not None
    assert inserted.updated_at.tzinfo is not None
    assert inserted.created_at <= inserted.updated_at

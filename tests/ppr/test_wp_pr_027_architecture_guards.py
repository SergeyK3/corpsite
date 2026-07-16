# tests/ppr/test_wp_pr_027_architecture_guards.py
"""Architecture guard tests for WP-PR-027 / WP-PR-026 military registration foundation."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from tests.conftest import table_exists
from tests.ppr.conftest import insert_person


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_has_only_persons_fk() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        rows = conn.execute(
            text(
                """
                SELECT ccu.table_name AS referenced_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.constraint_schema = tc.constraint_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'person_military_service'
                  AND tc.constraint_type = 'FOREIGN KEY'
                """
            )
        ).mappings().all()
    referenced = {str(row["referenced_table"]) for row in rows}
    assert referenced == {"persons"}


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_employee_context_id_is_not_fk() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS fk_count
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.constraint_schema = tc.constraint_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'person_military_service'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND kcu.column_name = 'employee_context_id'
                """
            )
        ).scalar_one()
    assert int(row) == 0


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_has_partial_unique_active_index() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        row = conn.execute(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'person_military_service'
                  AND indexname = 'uq_person_military_service_one_active_per_person'
                """
            )
        ).mappings().first()
    assert row is not None
    indexdef = str(row["indexdef"]).lower()
    assert "unique" in indexdef
    assert "person_id" in indexdef
    assert "lifecycle_status" in indexdef
    assert "active" in indexdef


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_rejects_draft_lifecycle_status() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        person_id = insert_person(
            conn,
            full_name="WP-PR-027 Guard Person",
            prefix="wp-pr-027-guard",
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    """
                    INSERT INTO public.person_military_service (
                        person_id, record_kind, obligation_status, lifecycle_status
                    ) VALUES (
                        :person_id, 'registration', 'liable', 'draft'
                    )
                    """
                ),
                {"person_id": person_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_rejects_second_active_row_per_person() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        person_id = insert_person(
            conn,
            full_name="WP-PR-027 Guard Active Person",
            prefix="wp-pr-027-active",
        )
        conn.execute(
            text(
                """
                INSERT INTO public.person_military_service (
                    person_id, record_kind, military_rank
                ) VALUES (
                    :person_id, 'registration', 'рядовой'
                )
                """
            ),
            {"person_id": person_id},
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    """
                    INSERT INTO public.person_military_service (
                        person_id, record_kind, registration_status
                    ) VALUES (
                        :person_id, 'registration', 'registered'
                    )
                    """
                ),
                {"person_id": person_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_rejects_registration_without_structured_field() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        person_id = insert_person(
            conn,
            full_name="WP-PR-027 Guard MIL-5 Person",
            prefix="wp-pr-027-mil5",
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    """
                    INSERT INTO public.person_military_service (
                        person_id, record_kind, notes
                    ) VALUES (
                        :person_id, 'registration', 'Только примечание'
                    )
                    """
                ),
                {"person_id": person_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_rejects_inverted_date_range() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        person_id = insert_person(
            conn,
            full_name="WP-PR-027 Guard Date Person",
            prefix="wp-pr-027-date",
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    """
                    INSERT INTO public.person_military_service (
                        person_id,
                        record_kind,
                        military_rank,
                        registered_at,
                        deregistered_at
                    ) VALUES (
                        :person_id,
                        'registration',
                        'рядовой',
                        DATE '2020-01-01',
                        DATE '2019-01-01'
                    )
                    """
                ),
                {"person_id": person_id},
            )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_person_military_service_rejects_not_applicable_with_registration_field() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        person_id = insert_person(
            conn,
            full_name="WP-PR-027 Guard MIL-4 Person",
            prefix="wp-pr-027-mil4",
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    """
                    INSERT INTO public.person_military_service (
                        person_id, record_kind, military_rank, notes
                    ) VALUES (
                        :person_id, 'not_applicable', 'рядовой', 'Не подлежит'
                    )
                    """
                ),
                {"person_id": person_id},
            )

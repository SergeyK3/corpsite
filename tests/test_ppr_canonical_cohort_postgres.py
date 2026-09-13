"""Canonical-HR Stage 0 cohort contract."""
from sqlalchemy import text

from app.db.engine import engine
from app.services.ppr_migration_status_projection_service import (
    SECTIONS,
    ensure_canonical_base_cohort,
    ensure_universe,
    rebuild_universe,
)


def test_canonical_cohort_is_import_provenance_free_and_rebuild_is_idempotent():
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == "corpsite_test"
            cohort = ensure_canonical_base_cohort(conn)
            assert ensure_canonical_base_cohort(conn) == cohort
            run = conn.execute(text("""
                SELECT source_type,source_batch_id,source_batch_status
                FROM public.ppr_stage0_cohort_runs WHERE stage0_cohort_run_id=:id
            """), {"id": cohort}).one()
            assert run == ("CANONICAL_HR", None, "CANONICAL")
            expected_members = conn.execute(text("""
                WITH active_primary AS (
                    SELECT pa.person_id
                    FROM public.person_assignments pa
                    WHERE pa.active_flag IS TRUE AND pa.is_primary IS TRUE
                      AND pa.lifecycle_status = 'active'
                      AND pa.start_date <= CURRENT_DATE
                      AND (pa.end_date IS NULL OR pa.end_date >= CURRENT_DATE)
                    GROUP BY pa.person_id
                    HAVING count(*) = 1
                )
                SELECT count(*)
                FROM public.employees e
                JOIN public.persons p ON p.person_id = e.person_id
                JOIN active_primary ap ON ap.person_id = e.person_id
                WHERE COALESCE(e.is_active, true) IS TRUE
                  AND e.operational_status = 'active'
                  AND (e.date_from IS NULL OR e.date_from <= CURRENT_DATE)
                  AND (e.date_to IS NULL OR e.date_to >= CURRENT_DATE)
                  AND p.person_status = 'active'
                  AND p.merged_into_person_id IS NULL
            """)).scalar_one()
            assert conn.execute(text("""
                SELECT count(*) FROM public.ppr_stage0_cohort_participants
                WHERE stage0_cohort_run_id=:id AND source_batch_id IS NULL AND source_row_id IS NULL
            """), {"id": cohort}).scalar_one() == expected_members
            universe = ensure_universe(conn, base_cohort_run_id=cohort)
            assert rebuild_universe(conn, universe_id=universe) == expected_members * len(SECTIONS)
            assert rebuild_universe(conn, universe_id=universe) == expected_members * len(SECTIONS)
            assert conn.execute(text("""
                SELECT count(*) FROM public.ppr_migration_section_status_projection
                WHERE universe_id=:id
            """), {"id": universe}).scalar_one() == expected_members * len(SECTIONS)
            assert conn.execute(text("""
                SELECT count(*) FROM public.ppr_migration_section_status_projection
                WHERE universe_id=:id
                  AND reason_code IN ('RUN_NO_SECTION_RESULT','SECTION_PROCESSING_NOT_CONNECTED')
            """), {"id": universe}).scalar_one() == 0
        finally:
            tx.rollback()

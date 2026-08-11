from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.employee_termination_verification_service import (
    UNVERIFIED,
    VERIFIED,
    archive_import_employee_unverified,
    verify_employee_termination,
)


TARGETS = {
    19970: (340, "910104451323"),
    19971: (340, "871228450917"),
    19974: (341, "941010450828"),
    19975: (341, "020703600282"),
}


def _feature_available() -> bool:
    try:
        with engine.connect() as conn:
            return bool(
                conn.execute(
                    text("SELECT to_regclass('public.employee_termination_records') IS NOT NULL")
                ).scalar()
            )
    except Exception:
        return False


@pytest.mark.skipif(not _feature_available(), reason="termination verification migration missing")
def test_four_import_rows_are_idempotent_inactive_unverified(seed):
    actor = int(seed["initiator_user_id"])
    first: dict[int, tuple[int, int]] = {}
    with engine.begin() as conn:
        for row_id, (position_id, _) in TARGETS.items():
            result = archive_import_employee_unverified(
                conn,
                batch_id=809,
                row_id=row_id,
                org_unit_id=73,
                position_id=position_id,
                actor_user_id=actor,
            )
            first[row_id] = (result.person_id, result.employee_id)

    with engine.begin() as conn:
        for row_id, (position_id, _) in TARGETS.items():
            replay = archive_import_employee_unverified(
                conn,
                batch_id=809,
                row_id=row_id,
                org_unit_id=73,
                position_id=position_id,
                actor_user_id=actor,
            )
            assert (replay.person_id, replay.employee_id) == first[row_id]
            row = conn.execute(
                text(
                    """
                    SELECT e.is_active, e.date_to, e.operational_status,
                           tr.verification_status, tr.termination_date,
                           tr.order_number, tr.order_date,
                           COUNT(pa.assignment_id) FILTER (
                               WHERE pa.active_flag IS TRUE AND pa.lifecycle_status <> 'voided'
                           ) AS active_assignments
                    FROM public.employees e
                    JOIN public.employee_termination_records tr
                      ON tr.employee_id=e.employee_id
                    LEFT JOIN public.person_assignments pa ON pa.person_id=e.person_id
                    WHERE e.employee_id=:employee_id
                    GROUP BY e.employee_id, tr.termination_record_id
                    """
                ),
                {"employee_id": replay.employee_id},
            ).mappings().one()
            assert row["is_active"] is False
            assert row["date_to"] is None
            assert row["operational_status"] == "terminated"
            assert row["verification_status"] == UNVERIFIED
            assert row["termination_date"] is None
            assert row["order_number"] is None
            assert row["order_date"] is None
            assert int(row["active_assignments"]) == 0

        assert conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.persons
                WHERE iin = ANY(:iins) AND person_status <> 'merged'
                """
            ),
            {"iins": [value[1] for value in TARGETS.values()]},
        ).scalar_one() == 4


@pytest.mark.skipif(not _feature_available(), reason="termination verification migration missing")
def test_verified_transition_is_idempotent_and_audited(seed):
    actor = int(seed["initiator_user_id"])
    suffix = uuid4().hex[:12]
    conn = engine.connect()
    transaction = conn.begin()
    try:
        person_id = int(conn.execute(
            text(
                """
                INSERT INTO public.persons (full_name, match_key, person_status, source)
                VALUES (:name, :match_key, 'active', 'manual') RETURNING person_id
                """
            ),
            {"name": f"Termination Verify {suffix}", "match_key": f"pytest:{suffix}"},
        ).scalar_one())
        employee_id = int(conn.execute(
            text(
                """
                INSERT INTO public.employees (
                    person_id, full_name, org_unit_id, position_id, is_active,
                    operational_status, enrollment_source
                ) VALUES (
                    :person_id, :name, 73, 340, FALSE, 'terminated', 'enrollment'
                ) RETURNING employee_id
                """
            ),
            {"person_id": person_id, "name": f"Termination Verify {suffix}"},
        ).scalar_one())
        record_id = int(conn.execute(
            text(
                """
                INSERT INTO public.employee_termination_records (
                    employee_id, verification_status, created_by, updated_by
                ) VALUES (:employee_id, 'UNVERIFIED', :actor, :actor)
                RETURNING termination_record_id
                """
            ),
            {"employee_id": employee_id, "actor": actor},
        ).scalar_one())

        facts = {
            "employee_id": employee_id,
            "termination_date": date(2024, 2, 29),
            "order_number": "15-k",
            "order_date": date(2024, 2, 28),
            "actor_user_id": actor,
        }
        verified = verify_employee_termination(conn, **facts)
        replay = verify_employee_termination(conn, **facts)
        assert verified["verification_status"] == VERIFIED
        assert replay["termination_record_id"] == record_id
        assert conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.employee_termination_record_audit
                WHERE termination_record_id=:record_id AND action='VERIFIED'
                """
            ),
            {"record_id": record_id},
        ).scalar_one() == 1
        assert conn.execute(
            text(
                """
                SELECT COUNT(*) FROM public.employee_events
                WHERE employee_id=:employee_id AND event_type='TERMINATION'
                """
            ),
            {"employee_id": employee_id},
        ).scalar_one() == 1
    finally:
        transaction.rollback()
        conn.close()

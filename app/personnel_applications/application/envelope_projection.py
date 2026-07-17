"""Compatibility Bridge — mirror active application intended_* to PPR envelope (ADR-057 D3)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository


def sync_envelope_intended_projection(conn: Connection, person_id: int) -> None:
    """Idempotent projection: active application → envelope; no active → clear envelope."""
    repo = SqlAlchemyPersonnelApplicationRepository(conn)
    active = repo.get_active_by_person_id(person_id)
    if active is None:
        conn.execute(
            text(
                """
                UPDATE public.personnel_record_metadata
                SET intended_org_group_id = NULL,
                    intended_org_unit_id = NULL,
                    intended_position_id = NULL,
                    intended_employment_rate = NULL,
                    updated_at = now()
                WHERE person_id = :person_id
                """
            ),
            {"person_id": int(person_id)},
        )
        return

    conn.execute(
        text(
            """
            UPDATE public.personnel_record_metadata
            SET intended_org_group_id = :org_group_id,
                intended_org_unit_id = :org_unit_id,
                intended_position_id = :position_id,
                intended_employment_rate = :employment_rate,
                updated_at = now()
            WHERE person_id = :person_id
            """
        ),
        {
            "person_id": int(person_id),
            "org_group_id": active.intended_org_group_id,
            "org_unit_id": active.intended_org_unit_id,
            "position_id": active.intended_position_id,
            "employment_rate": active.intended_employment_rate,
        },
    )

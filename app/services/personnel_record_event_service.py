"""Business event journal writer for person-owned personnel records (PMF-2)."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection


def emit_personnel_record_event(
    conn: Connection,
    *,
    person_id: int,
    domain_code: str,
    record_table_name: str,
    record_id: int,
    event_type: str,
    actor_id: Optional[str] = None,
    employee_context_id: Optional[int] = None,
    event_payload: Optional[dict[str, Any]] = None,
    migration_run_id: Optional[int] = None,
    migration_item_id: Optional[int] = None,
) -> int:
    """Append one business event row; returns event_id."""
    row = conn.execute(
        text(
            """
            INSERT INTO public.personnel_record_events (
                person_id,
                employee_context_id,
                domain_code,
                record_table_name,
                record_id,
                event_type,
                actor_id,
                event_payload,
                migration_run_id,
                migration_item_id
            )
            VALUES (
                :person_id,
                :employee_context_id,
                :domain_code,
                :record_table_name,
                :record_id,
                :event_type,
                :actor_id,
                CAST(:event_payload AS jsonb),
                :migration_run_id,
                :migration_item_id
            )
            RETURNING event_id
            """
        ),
        {
            "person_id": int(person_id),
            "employee_context_id": employee_context_id,
            "domain_code": domain_code,
            "record_table_name": record_table_name,
            "record_id": int(record_id),
            "event_type": event_type,
            "actor_id": actor_id,
            "event_payload": json.dumps(event_payload or {}, ensure_ascii=False),
            "migration_run_id": migration_run_id,
            "migration_item_id": migration_item_id,
        },
    ).one()
    return int(row[0])

"""SQLAlchemy adapter for PprEventRepository (personnel_record_events)."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from app.ppr.domain.errors import PprEventValidationError
from app.ppr.domain.event_models import (
    DEFAULT_PPR_EVENT_SCHEMA_VERSION,
    PPR_PAYLOAD_CATEGORY,
    PPR_PAYLOAD_COMMAND_ID,
    PPR_PAYLOAD_CORRELATION_ID,
    PPR_PAYLOAD_ENVELOPE_KEYS,
    PPR_PAYLOAD_SCHEMA_VERSION,
    PPR_PAYLOAD_SECTION_CODE,
    PPR_PAYLOAD_SOURCE_EVENT_ID,
    PprEventAppendRequest,
    PprEventRecord,
)

_EVENT_SELECT_COLUMNS = """
    event_id,
    person_id,
    employee_context_id,
    domain_code,
    record_table_name,
    record_id,
    event_type,
    event_at,
    actor_id,
    event_payload,
    migration_run_id,
    migration_item_id
"""


def _copy_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return dict(payload)


def _build_stored_payload(request: PprEventAppendRequest) -> dict[str, Any]:
    stored = _copy_payload(request.payload)
    if request.correlation_id is not None:
        stored[PPR_PAYLOAD_CORRELATION_ID] = request.correlation_id
    if request.command_id is not None:
        stored[PPR_PAYLOAD_COMMAND_ID] = request.command_id
    if request.source_event_id is not None:
        stored[PPR_PAYLOAD_SOURCE_EVENT_ID] = request.source_event_id
    if request.schema_version:
        stored[PPR_PAYLOAD_SCHEMA_VERSION] = request.schema_version
    if request.section_code is not None:
        stored[PPR_PAYLOAD_SECTION_CODE] = request.section_code
    if request.category:
        stored[PPR_PAYLOAD_CATEGORY] = request.category
    return stored


def _extract_business_payload(stored: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in stored.items() if key not in PPR_PAYLOAD_ENVELOPE_KEYS}


def _payload_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def _mapping_to_event(row: RowMapping) -> PprEventRecord:
    stored_payload = row["event_payload"] or {}
    if not isinstance(stored_payload, dict):
        stored_payload = dict(stored_payload)

    category = stored_payload.get(PPR_PAYLOAD_CATEGORY)
    if not category:
        category = "LEGACY"

    schema_version = stored_payload.get(PPR_PAYLOAD_SCHEMA_VERSION)
    if not schema_version:
        schema_version = DEFAULT_PPR_EVENT_SCHEMA_VERSION

    section_code = stored_payload.get(PPR_PAYLOAD_SECTION_CODE)

    return PprEventRecord(
        event_id=int(row["event_id"]),
        person_id=int(row["person_id"]),
        event_type=str(row["event_type"]),
        category=str(category),
        domain_code=row.get("domain_code"),
        section_code=str(section_code) if section_code is not None else None,
        record_table_name=str(row["record_table_name"]),
        record_id=int(row["record_id"]),
        occurred_at=row["event_at"],
        actor_id=row.get("actor_id"),
        command_id=stored_payload.get(PPR_PAYLOAD_COMMAND_ID),
        correlation_id=stored_payload.get(PPR_PAYLOAD_CORRELATION_ID),
        source_event_id=stored_payload.get(PPR_PAYLOAD_SOURCE_EVENT_ID),
        payload=_extract_business_payload(stored_payload),
        schema_version=str(schema_version),
        employee_context_id=row.get("employee_context_id"),
        migration_run_id=row.get("migration_run_id"),
        migration_item_id=row.get("migration_item_id"),
    )


class SqlAlchemyPprEventRepository:
    """Append-only event adapter — does not commit; caller owns transaction."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def append(self, request: PprEventAppendRequest) -> PprEventRecord:
        if request.person_id <= 0:
            raise PprEventValidationError("person_id must be positive")
        if not request.event_type:
            raise PprEventValidationError("event_type is required")
        if not request.record_table_name:
            raise PprEventValidationError("record_table_name is required")
        if request.record_id <= 0:
            raise PprEventValidationError("record_id must be positive")
        if request.category not in {
            "LIFECYCLE",
            "SECTION",
            "DERIVED",
            "MERGE",
            "ADMIN",
            "LEGACY",
        }:
            raise PprEventValidationError(f"Unknown event category: {request.category!r}")

        stored_payload = _build_stored_payload(request)

        params: dict[str, Any] = {
            "person_id": int(request.person_id),
            "employee_context_id": request.employee_context_id,
            "domain_code": request.domain_code,
            "record_table_name": request.record_table_name,
            "record_id": int(request.record_id),
            "event_type": request.event_type,
            "actor_id": request.actor_id,
            "event_payload": _payload_text(stored_payload),
            "migration_run_id": request.migration_run_id,
            "migration_item_id": request.migration_item_id,
        }

        if request.occurred_at is not None:
            sql = f"""
                INSERT INTO public.personnel_record_events (
                    person_id,
                    employee_context_id,
                    domain_code,
                    record_table_name,
                    record_id,
                    event_type,
                    event_at,
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
                    :event_at,
                    :actor_id,
                    CAST(:event_payload AS jsonb),
                    :migration_run_id,
                    :migration_item_id
                )
                RETURNING {_EVENT_SELECT_COLUMNS}
            """
            params["event_at"] = request.occurred_at
        else:
            sql = f"""
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
                RETURNING {_EVENT_SELECT_COLUMNS}
            """

        row = self._conn.execute(text(sql), params).mappings().one()
        return _mapping_to_event(row)

    def load_by_id(self, event_id: int) -> PprEventRecord | None:
        row = (
            self._conn.execute(
                text(
                    f"""
                    SELECT {_EVENT_SELECT_COLUMNS}
                    FROM public.personnel_record_events
                    WHERE event_id = :event_id
                    """
                ),
                {"event_id": int(event_id)},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return _mapping_to_event(row)

    def exists_by_correlation(
        self,
        correlation_id: str,
        *,
        event_type: str | None = None,
    ) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.personnel_record_events
                WHERE event_payload->>'correlation_id' = :correlation_id
                  AND (:event_type IS NULL OR event_type = :event_type)
                LIMIT 1
                """
            ),
            {"correlation_id": correlation_id, "event_type": event_type},
        ).first()
        return row is not None

    def exists_by_source_event(
        self,
        source_event_id: str,
        *,
        event_type: str | None = None,
    ) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.personnel_record_events
                WHERE event_payload->>'source_event_id' = :source_event_id
                  AND (:event_type IS NULL OR event_type = :event_type)
                LIMIT 1
                """
            ),
            {"source_event_id": source_event_id, "event_type": event_type},
        ).first()
        return row is not None

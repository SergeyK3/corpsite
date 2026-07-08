"""PMF Commit Engine — controlled write path into person-owned personnel records (PMF-2).

Single transactional entry point for migration commit and void rollback.
See docs/adr/ADR-PMF-001-personnel-migration-framework.md §4.4.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.db.models.personnel_migration import (
    ITEM_STATUS_COMMITTED,
    ITEM_STATUS_DRAFT,
    ITEM_STATUS_VOIDED,
    RUN_STATUS_COMMITTED,
    RUN_STATUS_DRAFT,
    RUN_STATUS_VOIDED,
)
from app.services.personnel_migration_domain_registry import (
    assert_domain_available,
    get_domain_plugin,
)
from app.services.personnel_migration_types import (
    DraftItemContext,
    PersonnelMigrationConflictError,
    PersonnelMigrationNotFoundError,
    PersonnelMigrationValidationError,
    RunContext,
)
from app.services.personnel_record_event_service import emit_personnel_record_event

PMF_TABLES = (
    "personnel_migration_domains",
    "personnel_migration_runs",
    "personnel_migration_items",
    "personnel_record_events",
    "person_education",
    "person_training",
)


def personnel_migration_available(conn: Optional[Connection] = None) -> bool:
    if conn is not None:
        return _tables_exist(conn)
    try:
        with engine.connect() as probe:
            return _tables_exist(probe)
    except Exception:
        return False


def _tables_exist(conn: Connection) -> bool:
    rows = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(CAST(:tables AS text[]))
            """
        ),
        {"tables": list(PMF_TABLES)},
    ).fetchall()
    return len(rows) == len(PMF_TABLES)


def _require_available() -> None:
    if not personnel_migration_available():
        raise PersonnelMigrationValidationError("PMF schema is not available.")


def _normalize_void_reason(void_reason: str) -> str:
    normalized = str(void_reason or "").strip()
    if not normalized:
        raise PersonnelMigrationValidationError("void_reason is required.")
    return normalized


def _resolve_employee_person_id(conn: Connection, employee_context_id: int) -> int:
    row = conn.execute(
        text(
            """
            SELECT employee_id, person_id
            FROM public.employees
            WHERE employee_id = :employee_id
            FOR UPDATE
            """
        ),
        {"employee_id": int(employee_context_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelMigrationNotFoundError(
            f"Employee {employee_context_id} not found."
        )
    person_id = row.get("person_id")
    if person_id is None:
        raise PersonnelMigrationValidationError(
            f"Employee {employee_context_id} has no linked person_id; commit is blocked."
        )
    return int(person_id)


def _fetch_run_row(conn: Connection, run_id: int, *, for_update: bool = False) -> dict[str, Any]:
    lock = "FOR UPDATE" if for_update else ""
    row = conn.execute(
        text(
            f"""
            SELECT
                run_id,
                domain_code,
                employee_context_id,
                person_id,
                run_status,
                metadata
            FROM public.personnel_migration_runs
            WHERE run_id = :run_id
            {lock}
            """
        ),
        {"run_id": int(run_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelMigrationNotFoundError(f"Migration run {run_id} not found.")
    return dict(row)


def _run_context_from_row(row: dict[str, Any]) -> RunContext:
    person_id = row.get("person_id")
    if person_id is None:
        raise PersonnelMigrationValidationError(
            f"Migration run {row['run_id']} has no person_id."
        )
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return RunContext(
        run_id=int(row["run_id"]),
        domain_code=str(row["domain_code"]),
        employee_context_id=row.get("employee_context_id"),
        person_id=int(person_id),
        run_status=str(row["run_status"]),
        metadata=metadata,
    )


def _fetch_items_for_run(
    conn: Connection,
    run_id: int,
    *,
    item_status: Optional[str] = None,
    for_update: bool = False,
) -> list[DraftItemContext]:
    params: dict[str, Any] = {"run_id": int(run_id)}
    status_clause = ""
    if item_status is not None:
        status_clause = "AND item_status = :item_status"
        params["item_status"] = item_status
    lock = "FOR UPDATE" if for_update else ""

    rows = conn.execute(
        text(
            f"""
            SELECT
                item_id,
                run_id,
                domain_code,
                source_kind,
                source_record_id,
                import_batch_id,
                import_row_id,
                record_kind,
                draft_payload,
                source_payload,
                validation_errors
            FROM public.personnel_migration_items
            WHERE run_id = :run_id
              {status_clause}
            ORDER BY item_id ASC
            {lock}
            """
        ),
        params,
    ).mappings().all()

    items: list[DraftItemContext] = []
    for row in rows:
        draft_payload = row.get("draft_payload") or {}
        source_payload = row.get("source_payload") or {}
        validation_errors = row.get("validation_errors") or []
        if not isinstance(draft_payload, dict):
            draft_payload = {}
        if not isinstance(source_payload, dict):
            source_payload = {}
        if not isinstance(validation_errors, list):
            validation_errors = []
        items.append(
            DraftItemContext(
                item_id=int(row["item_id"]),
                run_id=int(row["run_id"]),
                domain_code=str(row["domain_code"]),
                source_kind=str(row["source_kind"]),
                source_record_id=row.get("source_record_id"),
                import_batch_id=row.get("import_batch_id"),
                import_row_id=row.get("import_row_id"),
                record_kind=row.get("record_kind"),
                draft_payload=draft_payload,
                source_payload=source_payload,
                validation_errors=validation_errors,
            )
        )
    return items


def create_draft_run(
    conn: Connection,
    *,
    domain_code: str,
    employee_context_id: int,
    actor_id: str,
    metadata: Optional[dict[str, Any]] = None,
    allow_disabled_domain: bool = False,
) -> dict[str, Any]:
    _require_available()
    assert_domain_available(conn, domain_code, allow_disabled_domain=allow_disabled_domain)
    person_id = _resolve_employee_person_id(conn, employee_context_id)

    row = conn.execute(
        text(
            """
            INSERT INTO public.personnel_migration_runs (
                domain_code,
                employee_context_id,
                person_id,
                run_status,
                started_by,
                metadata
            )
            VALUES (
                :domain_code,
                :employee_context_id,
                :person_id,
                :run_status,
                :started_by,
                CAST(:metadata AS jsonb)
            )
            RETURNING run_id, domain_code, employee_context_id, person_id, run_status, metadata
            """
        ),
        {
            "domain_code": domain_code,
            "employee_context_id": int(employee_context_id),
            "person_id": person_id,
            "run_status": RUN_STATUS_DRAFT,
            "started_by": actor_id,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
        },
    ).mappings().one()
    return dict(row)


def create_draft_run_tx(
    *,
    domain_code: str,
    employee_context_id: int,
    actor_id: str,
    metadata: Optional[dict[str, Any]] = None,
    allow_disabled_domain: bool = False,
) -> dict[str, Any]:
    with engine.begin() as conn:
        return create_draft_run(
            conn,
            domain_code=domain_code,
            employee_context_id=employee_context_id,
            actor_id=actor_id,
            metadata=metadata,
            allow_disabled_domain=allow_disabled_domain,
        )


def add_draft_item(
    conn: Connection,
    *,
    run_id: int,
    source_kind: str,
    source_record_id: Optional[str] = None,
    import_batch_id: Optional[int] = None,
    import_row_id: Optional[int] = None,
    record_kind: Optional[str] = None,
    draft_payload: Optional[dict[str, Any]] = None,
    source_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    _require_available()
    run = _fetch_run_row(conn, run_id, for_update=True)
    if run["run_status"] != RUN_STATUS_DRAFT:
        raise PersonnelMigrationConflictError(
            f"Cannot add items to run {run_id} with status {run['run_status']!r}."
        )

    row = conn.execute(
        text(
            """
            INSERT INTO public.personnel_migration_items (
                run_id,
                domain_code,
                source_kind,
                source_record_id,
                import_batch_id,
                import_row_id,
                record_kind,
                item_status,
                draft_payload,
                source_payload,
                validation_errors
            )
            VALUES (
                :run_id,
                :domain_code,
                :source_kind,
                :source_record_id,
                :import_batch_id,
                :import_row_id,
                :record_kind,
                :item_status,
                CAST(:draft_payload AS jsonb),
                CAST(:source_payload AS jsonb),
                CAST(:validation_errors AS jsonb)
            )
            RETURNING item_id, run_id, record_kind, item_status
            """
        ),
        {
            "run_id": int(run_id),
            "domain_code": run["domain_code"],
            "source_kind": source_kind,
            "source_record_id": source_record_id,
            "import_batch_id": import_batch_id,
            "import_row_id": import_row_id,
            "record_kind": record_kind,
            "item_status": ITEM_STATUS_DRAFT,
            "draft_payload": json.dumps(draft_payload or {}, ensure_ascii=False),
            "source_payload": json.dumps(source_payload or {}, ensure_ascii=False),
            "validation_errors": json.dumps([], ensure_ascii=False),
        },
    ).mappings().one()
    return dict(row)


def add_draft_item_tx(
    *,
    run_id: int,
    source_kind: str,
    source_record_id: Optional[str] = None,
    import_batch_id: Optional[int] = None,
    import_row_id: Optional[int] = None,
    record_kind: Optional[str] = None,
    draft_payload: Optional[dict[str, Any]] = None,
    source_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    with engine.begin() as conn:
        return add_draft_item(
            conn,
            run_id=run_id,
            source_kind=source_kind,
            source_record_id=source_record_id,
            import_batch_id=import_batch_id,
            import_row_id=import_row_id,
            record_kind=record_kind,
            draft_payload=draft_payload,
            source_payload=source_payload,
        )


def commit_run(
    conn: Connection,
    *,
    run_id: int,
    actor_id: str,
) -> dict[str, Any]:
    _require_available()
    run_row = _fetch_run_row(conn, run_id, for_update=True)
    if run_row["run_status"] != RUN_STATUS_DRAFT:
        raise PersonnelMigrationConflictError(
            f"Run {run_id} is not draft (status={run_row['run_status']!r})."
        )

    run_ctx = _run_context_from_row(run_row)
    items = _fetch_items_for_run(conn, run_id, item_status=ITEM_STATUS_DRAFT, for_update=True)
    if not items:
        raise PersonnelMigrationValidationError(f"Run {run_id} has no draft items to commit.")

    plugin = get_domain_plugin(run_ctx.domain_code)
    all_errors: list[str] = []
    for item in items:
        errors = plugin.validate_draft(conn, item=item, run=run_ctx)
        if errors:
            all_errors.extend(f"item {item.item_id}: {err}" for err in errors)
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_migration_items
                    SET validation_errors = CAST(:validation_errors AS jsonb)
                    WHERE item_id = :item_id
                    """
                ),
                {
                    "item_id": item.item_id,
                    "validation_errors": json.dumps(errors, ensure_ascii=False),
                },
            )
    if all_errors:
        raise PersonnelMigrationValidationError("; ".join(all_errors))

    written = plugin.write_records(conn, run=run_ctx, items=items, actor_id=actor_id)
    written_by_item = {record.item_id: record for record in written}

    event_ids: list[int] = []
    committed_items: list[dict[str, Any]] = []

    for item in items:
        record = written_by_item.get(item.item_id)
        if record is None:
            raise PersonnelMigrationValidationError(
                f"Plugin did not return written record for item {item.item_id}."
            )
        conn.execute(
            text(
                """
                UPDATE public.personnel_migration_items
                SET item_status = :item_status,
                    target_table_name = :target_table_name,
                    target_record_id = :target_record_id,
                    committed_at = now(),
                    validation_errors = CAST(:validation_errors AS jsonb)
                WHERE item_id = :item_id
                """
            ),
            {
                "item_status": ITEM_STATUS_COMMITTED,
                "target_table_name": record.target_table_name,
                "target_record_id": record.target_record_id,
                "validation_errors": json.dumps([], ensure_ascii=False),
                "item_id": item.item_id,
            },
        )
        event_id = emit_personnel_record_event(
            conn,
            person_id=run_ctx.person_id,
            domain_code=run_ctx.domain_code,
            record_table_name=record.target_table_name,
            record_id=record.target_record_id,
            event_type=plugin.event_type_for_commit(),
            actor_id=actor_id,
            employee_context_id=run_ctx.employee_context_id,
            event_payload={
                "record_kind": item.record_kind,
                "source_kind": item.source_kind,
                "source_record_id": item.source_record_id,
            },
            migration_run_id=run_ctx.run_id,
            migration_item_id=item.item_id,
        )
        event_ids.append(event_id)
        committed_items.append(
            {
                "item_id": item.item_id,
                "target_table_name": record.target_table_name,
                "target_record_id": record.target_record_id,
                "event_id": event_id,
            }
        )

    conn.execute(
        text(
            """
            UPDATE public.personnel_migration_runs
            SET run_status = :run_status,
                committed_at = now(),
                committed_by = :committed_by
            WHERE run_id = :run_id
            """
        ),
        {
            "run_status": RUN_STATUS_COMMITTED,
            "committed_by": actor_id,
            "run_id": int(run_id),
        },
    )

    return {
        "run_id": int(run_id),
        "run_status": RUN_STATUS_COMMITTED,
        "committed_items": committed_items,
        "event_ids": event_ids,
    }


def commit_run_tx(*, run_id: int, actor_id: str) -> dict[str, Any]:
    with engine.begin() as conn:
        return commit_run(conn, run_id=run_id, actor_id=actor_id)


def void_run(
    conn: Connection,
    *,
    run_id: int,
    actor_id: str,
    void_reason: str,
) -> dict[str, Any]:
    _require_available()
    normalized_reason = _normalize_void_reason(void_reason)
    run_row = _fetch_run_row(conn, run_id, for_update=True)
    if run_row["run_status"] != RUN_STATUS_COMMITTED:
        raise PersonnelMigrationConflictError(
            f"Run {run_id} is not committed (status={run_row['run_status']!r})."
        )

    run_ctx = _run_context_from_row(run_row)
    plugin = get_domain_plugin(run_ctx.domain_code)

    item_rows = conn.execute(
        text(
            """
            SELECT
                item_id,
                target_table_name,
                target_record_id,
                item_status
            FROM public.personnel_migration_items
            WHERE run_id = :run_id
              AND item_status = :item_status
            ORDER BY item_id ASC
            FOR UPDATE
            """
        ),
        {"run_id": int(run_id), "item_status": ITEM_STATUS_COMMITTED},
    ).mappings().all()

    voided_items: list[dict[str, Any]] = []
    event_ids: list[int] = []

    for item_row in item_rows:
        item_id = int(item_row["item_id"])
        target_table = item_row.get("target_table_name")
        target_record_id = item_row.get("target_record_id")
        if not target_table or target_record_id is None:
            raise PersonnelMigrationValidationError(
                f"Committed item {item_id} is missing target reference."
            )

        plugin.void_target_record(
            conn,
            target_table_name=str(target_table),
            target_record_id=int(target_record_id),
            void_reason=normalized_reason,
        )

        conn.execute(
            text(
                """
                UPDATE public.personnel_migration_items
                SET item_status = :item_status,
                    voided_at = now(),
                    void_reason = :void_reason
                WHERE item_id = :item_id
                """
            ),
            {
                "item_status": ITEM_STATUS_VOIDED,
                "void_reason": normalized_reason,
                "item_id": item_id,
            },
        )

        event_id = emit_personnel_record_event(
            conn,
            person_id=run_ctx.person_id,
            domain_code=run_ctx.domain_code,
            record_table_name=str(target_table),
            record_id=int(target_record_id),
            event_type=plugin.event_type_for_void(),
            actor_id=actor_id,
            employee_context_id=run_ctx.employee_context_id,
            event_payload={"void_reason": normalized_reason},
            migration_run_id=run_ctx.run_id,
            migration_item_id=item_id,
        )
        event_ids.append(event_id)
        voided_items.append(
            {
                "item_id": item_id,
                "target_table_name": target_table,
                "target_record_id": int(target_record_id),
                "event_id": event_id,
            }
        )

    conn.execute(
        text(
            """
            UPDATE public.personnel_migration_runs
            SET run_status = :run_status,
                voided_at = now(),
                voided_by = :voided_by,
                void_reason = :void_reason
            WHERE run_id = :run_id
            """
        ),
        {
            "run_status": RUN_STATUS_VOIDED,
            "voided_by": actor_id,
            "void_reason": normalized_reason,
            "run_id": int(run_id),
        },
    )

    return {
        "run_id": int(run_id),
        "run_status": RUN_STATUS_VOIDED,
        "voided_items": voided_items,
        "event_ids": event_ids,
    }


def void_run_tx(*, run_id: int, actor_id: str, void_reason: str) -> dict[str, Any]:
    with engine.begin() as conn:
        return void_run(conn, run_id=run_id, actor_id=actor_id, void_reason=void_reason)


def supersede_record(
    conn: Connection,
    *,
    domain_code: str,
    employee_context_id: int,
    record_table_name: str,
    record_id: int,
    replacement_payload: dict[str, Any],
    actor_id: str,
    provenance: Optional[dict[str, Any]] = None,
    allow_disabled_domain: bool = False,
) -> dict[str, Any]:
    """Supersede an active person-owned record with a new active replacement (no DELETE)."""
    _require_available()
    assert_domain_available(conn, domain_code, allow_disabled_domain=allow_disabled_domain)
    person_id = _resolve_employee_person_id(conn, employee_context_id)
    plugin = get_domain_plugin(domain_code)

    run_ctx = RunContext(
        run_id=0,
        domain_code=domain_code,
        employee_context_id=int(employee_context_id),
        person_id=person_id,
        run_status=RUN_STATUS_COMMITTED,
        metadata={},
    )

    written = plugin.supersede_target_record(
        conn,
        run=run_ctx,
        target_table_name=record_table_name,
        target_record_id=int(record_id),
        replacement_payload=replacement_payload,
        actor_id=actor_id,
        provenance=provenance or {},
    )

    supersede_event_id = emit_personnel_record_event(
        conn,
        person_id=person_id,
        domain_code=domain_code,
        record_table_name=record_table_name,
        record_id=int(record_id),
        event_type=plugin.event_type_for_supersede(),
        actor_id=actor_id,
        employee_context_id=employee_context_id,
        event_payload={
            "superseded_record_id": int(record_id),
            "replacement_record_id": written.target_record_id,
        },
    )
    migrate_event_id = emit_personnel_record_event(
        conn,
        person_id=person_id,
        domain_code=domain_code,
        record_table_name=written.target_table_name,
        record_id=written.target_record_id,
        event_type=plugin.event_type_for_commit(),
        actor_id=actor_id,
        employee_context_id=employee_context_id,
        event_payload={"superseded_record_id": int(record_id)},
    )

    return {
        "superseded_record_id": int(record_id),
        "replacement_record_id": written.target_record_id,
        "target_table_name": written.target_table_name,
        "supersede_event_id": supersede_event_id,
        "migrate_event_id": migrate_event_id,
    }


def supersede_record_tx(
    *,
    domain_code: str,
    employee_context_id: int,
    record_table_name: str,
    record_id: int,
    replacement_payload: dict[str, Any],
    actor_id: str,
    provenance: Optional[dict[str, Any]] = None,
    allow_disabled_domain: bool = False,
) -> dict[str, Any]:
    with engine.begin() as conn:
        return supersede_record(
            conn,
            domain_code=domain_code,
            employee_context_id=employee_context_id,
            record_table_name=record_table_name,
            record_id=record_id,
            replacement_payload=replacement_payload,
            actor_id=actor_id,
            provenance=provenance,
            allow_disabled_domain=allow_disabled_domain,
        )

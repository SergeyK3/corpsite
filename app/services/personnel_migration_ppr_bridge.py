"""PMF ↔ PPR bridge dispatcher (R5 — shared transaction with commit_service).

Branch point: personnel_migration_commit_service delegates here when
``ppr_pmf_bridge_enabled()`` is true after PMF validation and before legacy writers.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_migration import (
    ITEM_STATUS_COMMITTED,
    ITEM_STATUS_VOIDED,
    RUN_STATUS_COMMITTED,
    RUN_STATUS_VOIDED,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EDUCATION,
    COMMAND_TYPE_ADD_TRAINING,
    COMMAND_TYPE_MATERIALIZE_PPR,
    COMMAND_TYPE_SUPERSEDE_EDUCATION,
    COMMAND_TYPE_SUPERSEDE_TRAINING,
    COMMAND_TYPE_VOID_EDUCATION,
    COMMAND_TYPE_VOID_TRAINING,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.config import assert_ppr_pmf_bridge_activation_allowed, ppr_pmf_bridge_enabled
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.pmf_command_id import (
    build_pmf_commit_command_id,
    build_pmf_supersede_command_id,
    build_pmf_void_command_id,
)
from app.ppr.application.results import RESULT_STATUS_ALREADY_MATERIALIZED, RESULT_STATUS_IDEMPOTENT_REPLAY
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.application.uow_participation import bind_participating_uow
from app.ppr.domain.errors import PprPmfCommandMappingError
from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork
from app.services.personnel_migration_types import DraftItemContext, RunContext


def pmf_ppr_bridge_active() -> bool:
    if not ppr_pmf_bridge_enabled():
        return False
    assert_ppr_pmf_bridge_activation_allowed()
    return True


def _table_id_column(table_name: str) -> str:
    if table_name == "person_education":
        return "education_id"
    if table_name == "person_training":
        return "training_id"
    raise PprPmfCommandMappingError(f"Unsupported target table: {table_name!r}")


def _load_updated_at(
    conn: Connection,
    *,
    table_name: str,
    record_id: int,
    person_id: int,
) -> Any:
    """CAS token source for PMF void/supersede — row snapshot in caller transaction."""
    id_col = _table_id_column(table_name)
    row = conn.execute(
        text(
            f"""
            SELECT updated_at
            FROM public.{table_name}
            WHERE {id_col} = :record_id
              AND person_id = :person_id
            """
        ),
        {"record_id": int(record_id), "person_id": int(person_id)},
    ).mappings().one_or_none()
    if row is None:
        raise PprPmfCommandMappingError(
            f"Target record not found for CAS: {table_name} id={record_id}"
        )
    return row["updated_at"]


def _map_commit_payload(item: DraftItemContext) -> dict[str, Any]:
    draft = dict(item.draft_payload or {})
    if item.record_kind == "education":
        return {
            "education_kind": draft.get("education_kind"),
            "institution_type": draft.get("institution_type"),
            "institution_name": draft.get("institution_name"),
            "specialty": draft.get("specialty"),
            "qualification": draft.get("qualification"),
            "started_at": draft.get("started_at"),
            "completed_at": draft.get("completed_at"),
            "diploma_number": draft.get("diploma_number"),
            "document_date": draft.get("document_date"),
            "metadata": draft.get("metadata"),
            "employee_context_id": draft.get("employee_context_id"),
        }
    if item.record_kind == "training":
        return {
            "training_kind": draft.get("training_kind"),
            "title": draft.get("title"),
            "organization_name": draft.get("organization_name"),
            "hours": draft.get("hours"),
            "started_at": draft.get("started_at"),
            "completed_at": draft.get("completed_at"),
            "certificate_number": draft.get("certificate_number"),
            "document_date": draft.get("document_date"),
            "metadata": draft.get("metadata"),
            "employee_context_id": draft.get("employee_context_id"),
        }
    raise PprPmfCommandMappingError(f"Unsupported record_kind: {item.record_kind!r}")


def _ensure_materialized(
    uow: PprApplicationUnitOfWork,
    *,
    run: RunContext,
    actor_id: str,
) -> None:
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    mat_command_id = f"pmf-mat-{run.run_id}-{run.person_id}"
    lifecycle.materialize_ppr_participating(
        uow,
        PprCommandEnvelope(
            command_id=mat_command_id,
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id=actor_id,
            requested_at=datetime.now(UTC),
            payload=MaterializePprPayload(),
            person_id=run.person_id,
            employee_id=run.employee_context_id,
            employee_context_id=run.employee_context_id,
            correlation_id=f"pmf-run-{run.run_id}",
        ),
    )


def commit_run_via_ppr_bridge(
    conn: Connection,
    *,
    run_ctx: RunContext,
    items: list[DraftItemContext],
    actor_id: str,
) -> dict[str, Any]:
    """PPR bridge commit — shared conn with PMF workflow updates; no legacy section writer."""
    uow = bind_participating_uow(conn)
    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    try:
        _ensure_materialized(uow, run=run_ctx, actor_id=actor_id)

        event_ids: list[int] = []
        committed_items: list[dict[str, Any]] = []

        for item in items:
            command_id = build_pmf_commit_command_id(
                migration_run_id=run_ctx.run_id,
                migration_item_id=item.item_id,
            )
            payload = _map_commit_payload(item)
            base = PprCommandEnvelope(
                command_id=command_id,
                command_type=COMMAND_TYPE_ADD_EDUCATION,
                actor_id=actor_id,
                requested_at=datetime.now(UTC),
                payload=payload,
                person_id=run_ctx.person_id,
                employee_id=run_ctx.employee_context_id,
                employee_context_id=run_ctx.employee_context_id,
                correlation_id=f"pmf-run-{run_ctx.run_id}",
            )
            if item.record_kind == "education":
                base = PprCommandEnvelope(
                    command_id=base.command_id,
                    command_type=COMMAND_TYPE_ADD_EDUCATION,
                    actor_id=base.actor_id,
                    requested_at=base.requested_at,
                    payload=base.payload,
                    person_id=base.person_id,
                    employee_id=base.employee_id,
                    employee_context_id=base.employee_context_id,
                    correlation_id=base.correlation_id,
                )
                result = section.add_education_participating(uow, base)
            elif item.record_kind == "training":
                result = section.add_training_participating(
                    uow,
                    PprCommandEnvelope(
                        command_id=base.command_id,
                        command_type=COMMAND_TYPE_ADD_TRAINING,
                        actor_id=base.actor_id,
                        requested_at=base.requested_at,
                        payload=base.payload,
                        person_id=base.person_id,
                        employee_id=base.employee_id,
                        employee_context_id=base.employee_context_id,
                        correlation_id=base.correlation_id,
                    ),
                )
            else:
                raise PprPmfCommandMappingError(f"Unsupported record_kind: {item.record_kind!r}")

            if result.status in {RESULT_STATUS_IDEMPOTENT_REPLAY, RESULT_STATUS_ALREADY_MATERIALIZED}:
                if result.section_record_id is None:
                    raise PprPmfCommandMappingError(
                        f"Idempotent replay missing section_record_id for item {item.item_id}"
                    )

            target_table = result.extra.get("target_table_name") or (
                "person_education" if item.record_kind == "education" else "person_training"
            )
            target_record_id = result.section_record_id or 0

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
                    "target_table_name": target_table,
                    "target_record_id": int(target_record_id),
                    "validation_errors": json.dumps([], ensure_ascii=False),
                    "item_id": item.item_id,
                },
            )
            event_ids.extend(result.event_ids)
            committed_items.append(
                {
                    "item_id": item.item_id,
                    "target_table_name": target_table,
                    "target_record_id": int(target_record_id),
                    "event_id": result.event_ids[0] if result.event_ids else None,
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
                "run_id": int(run_ctx.run_id),
            },
        )
        return {
            "run_id": int(run_ctx.run_id),
            "run_status": RUN_STATUS_COMMITTED,
            "committed_items": committed_items,
            "event_ids": event_ids,
        }
    finally:
        uow.release_participating()


def void_run_via_ppr_bridge(
    conn: Connection,
    *,
    run_ctx: RunContext,
    item_rows: list[dict[str, Any]],
    actor_id: str,
    void_reason: str,
    record_kind_by_item: dict[int, str],
) -> dict[str, Any]:
    uow = bind_participating_uow(conn)
    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    try:
        _ensure_materialized(uow, run=run_ctx, actor_id=actor_id)
        voided_items: list[dict[str, Any]] = []
        event_ids: list[int] = []

        for item_row in item_rows:
            item_id = int(item_row["item_id"])
            target_table = str(item_row["target_table_name"])
            target_record_id = int(item_row["target_record_id"])
            record_kind = record_kind_by_item.get(item_id, "education")
            expected_updated_at = _load_updated_at(
                conn,
                table_name=target_table,
                record_id=target_record_id,
                person_id=run_ctx.person_id,
            )
            command_id = build_pmf_void_command_id(
                migration_run_id=run_ctx.run_id,
                migration_item_id=item_id,
            )
            envelope = PprCommandEnvelope(
                command_id=command_id,
                command_type=COMMAND_TYPE_VOID_EDUCATION,
                actor_id=actor_id,
                requested_at=datetime.now(UTC),
                payload={
                    "record_id": target_record_id,
                    "reason": void_reason,
                    "expected_updated_at": expected_updated_at,
                },
                person_id=run_ctx.person_id,
                employee_id=run_ctx.employee_context_id,
                employee_context_id=run_ctx.employee_context_id,
                correlation_id=f"pmf-run-{run_ctx.run_id}",
            )
            if record_kind == "training":
                result = section.void_training_participating(
                    uow,
                    PprCommandEnvelope(
                        command_id=envelope.command_id,
                        command_type=COMMAND_TYPE_VOID_TRAINING,
                        actor_id=envelope.actor_id,
                        requested_at=envelope.requested_at,
                        payload=envelope.payload,
                        person_id=envelope.person_id,
                        employee_id=envelope.employee_id,
                        employee_context_id=envelope.employee_context_id,
                        correlation_id=envelope.correlation_id,
                    ),
                )
            else:
                result = section.void_education_participating(uow, envelope)

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
                    "void_reason": void_reason,
                    "item_id": item_id,
                },
            )
            if result.event_ids:
                event_ids.append(result.event_ids[0])
            voided_items.append(
                {
                    "item_id": item_id,
                    "target_table_name": target_table,
                    "target_record_id": target_record_id,
                    "event_id": result.event_ids[0] if result.event_ids else None,
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
                "void_reason": void_reason,
                "run_id": int(run_ctx.run_id),
            },
        )
        return {
            "run_id": int(run_ctx.run_id),
            "run_status": RUN_STATUS_VOIDED,
            "voided_items": voided_items,
            "event_ids": event_ids,
        }
    finally:
        uow.release_participating()


def supersede_record_via_ppr_bridge(
    conn: Connection,
    *,
    domain_code: str,
    employee_context_id: int,
    person_id: int,
    record_table_name: str,
    record_id: int,
    replacement_payload: dict[str, Any],
    actor_id: str,
    record_kind: str,
) -> dict[str, Any]:
    uow = bind_participating_uow(conn)
    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    run_ctx = RunContext(
        run_id=0,
        domain_code=domain_code,
        employee_context_id=int(employee_context_id),
        person_id=int(person_id),
        run_status=RUN_STATUS_COMMITTED,
        metadata={},
    )
    try:
        _ensure_materialized(uow, run=run_ctx, actor_id=actor_id)
        expected_updated_at = _load_updated_at(
            conn,
            table_name=record_table_name,
            record_id=record_id,
            person_id=person_id,
        )
        replacement_identity = json.dumps(replacement_payload, sort_keys=True, default=str)
        command_id = build_pmf_supersede_command_id(
            domain_code=domain_code,
            record_table_name=record_table_name,
            old_record_id=record_id,
            replacement_identity=replacement_identity,
        )
        envelope = PprCommandEnvelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_SUPERSEDE_EDUCATION,
            actor_id=actor_id,
            requested_at=datetime.now(UTC),
            payload={
                "record_id": record_id,
                "expected_updated_at": expected_updated_at,
                "replacement": replacement_payload,
            },
            person_id=person_id,
            employee_id=employee_context_id,
            employee_context_id=employee_context_id,
        )
        if record_kind == "training":
            result = section.supersede_training_participating(
                uow,
                PprCommandEnvelope(
                    command_id=envelope.command_id,
                    command_type=COMMAND_TYPE_SUPERSEDE_TRAINING,
                    actor_id=envelope.actor_id,
                    requested_at=envelope.requested_at,
                    payload=envelope.payload,
                    person_id=envelope.person_id,
                    employee_id=envelope.employee_id,
                    employee_context_id=envelope.employee_context_id,
                ),
            )
        else:
            result = section.supersede_education_participating(uow, envelope)

        replacement_id = result.section_record_id or 0
        supersede_event_id = result.event_ids[0] if result.event_ids else 0
        return {
            "superseded_record_id": int(record_id),
            "replacement_record_id": int(replacement_id),
            "target_table_name": record_table_name,
            "supersede_event_id": supersede_event_id,
            "migrate_event_id": supersede_event_id,
        }
    finally:
        uow.release_participating()

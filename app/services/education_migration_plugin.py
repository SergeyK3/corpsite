"""Education domain plugin skeleton for PMF Commit Engine (PMF-2 / ADR-EDU-001)."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_migration import (
    DOMAIN_CODE_EDUCATION,
    EDUCATION_KINDS,
    EVENT_TYPE_EDUCATION_MIGRATED,
    EVENT_TYPE_EDUCATION_SUPERSEDED,
    EVENT_TYPE_EDUCATION_VOIDED,
    LIFECYCLE_STATUS_ACTIVE,
    LIFECYCLE_STATUS_SUPERSEDED,
    LIFECYCLE_STATUS_VOIDED,
    TRAINING_KINDS,
    VERIFICATION_STATUS_PENDING,
)
from app.services.personnel_migration_types import (
    DraftItemContext,
    PersonnelMigrationNotFoundError,
    PersonnelMigrationValidationError,
    RunContext,
    WrittenRecord,
)

RECORD_KIND_EDUCATION = "education"
RECORD_KIND_TRAINING = "training"

TABLE_PERSON_EDUCATION = "person_education"
TABLE_PERSON_TRAINING = "person_training"


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text_value = str(value).strip()
    if not text_value:
        return None
    return date.fromisoformat(text_value[:10])


def _parse_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return {}


class EducationMigrationPlugin:
    domain_code = DOMAIN_CODE_EDUCATION

    def target_table_for_record_kind(self, record_kind: str) -> str:
        if record_kind == RECORD_KIND_EDUCATION:
            return TABLE_PERSON_EDUCATION
        if record_kind == RECORD_KIND_TRAINING:
            return TABLE_PERSON_TRAINING
        raise PersonnelMigrationValidationError(
            f"Unsupported education record_kind: {record_kind!r}"
        )

    def event_type_for_commit(self) -> str:
        return EVENT_TYPE_EDUCATION_MIGRATED

    def event_type_for_void(self) -> str:
        return EVENT_TYPE_EDUCATION_VOIDED

    def event_type_for_supersede(self) -> str:
        return EVENT_TYPE_EDUCATION_SUPERSEDED

    def validate_draft(
        self,
        conn: Connection,
        *,
        item: DraftItemContext,
        run: RunContext,
    ) -> list[str]:
        errors: list[str] = []
        record_kind = item.record_kind
        if not record_kind:
            errors.append("record_kind is required")
            return errors

        payload = item.draft_payload or {}
        if record_kind == RECORD_KIND_EDUCATION:
            education_kind = payload.get("education_kind")
            if not education_kind:
                errors.append("education_kind is required")
            elif education_kind not in EDUCATION_KINDS:
                errors.append(f"invalid education_kind: {education_kind!r}")
        elif record_kind == RECORD_KIND_TRAINING:
            training_kind = payload.get("training_kind")
            if not training_kind:
                errors.append("training_kind is required")
            elif training_kind not in TRAINING_KINDS:
                errors.append(f"invalid training_kind: {training_kind!r}")
        else:
            errors.append(f"unsupported record_kind: {record_kind!r}")

        if run.person_id is None:
            errors.append("run.person_id is required for commit")

        return errors

    def write_records(
        self,
        conn: Connection,
        *,
        run: RunContext,
        items: list[DraftItemContext],
        actor_id: str,
    ) -> list[WrittenRecord]:
        written: list[WrittenRecord] = []
        for item in items:
            record_kind = item.record_kind or ""
            if record_kind == RECORD_KIND_EDUCATION:
                record_id = self._insert_education(conn, run=run, item=item, actor_id=actor_id)
                table_name = TABLE_PERSON_EDUCATION
            elif record_kind == RECORD_KIND_TRAINING:
                record_id = self._insert_training(conn, run=run, item=item, actor_id=actor_id)
                table_name = TABLE_PERSON_TRAINING
            else:
                raise PersonnelMigrationValidationError(
                    f"Cannot write record_kind {record_kind!r} for item {item.item_id}"
                )
            written.append(
                WrittenRecord(
                    item_id=item.item_id,
                    target_table_name=table_name,
                    target_record_id=record_id,
                )
            )
        return written

    def void_target_record(
        self,
        conn: Connection,
        *,
        target_table_name: str,
        target_record_id: int,
        void_reason: str,
    ) -> None:
        if target_table_name == TABLE_PERSON_EDUCATION:
            id_col = "education_id"
        elif target_table_name == TABLE_PERSON_TRAINING:
            id_col = "training_id"
        else:
            raise PersonnelMigrationValidationError(
                f"Cannot void unknown education target table: {target_table_name!r}"
            )

        result = conn.execute(
            text(
                f"""
                UPDATE public.{target_table_name}
                SET lifecycle_status = :lifecycle_status,
                    updated_at = now()
                WHERE {id_col} = :record_id
                  AND lifecycle_status = :active_status
                """
            ),
            {
                "lifecycle_status": LIFECYCLE_STATUS_VOIDED,
                "record_id": int(target_record_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
            },
        )
        if result.rowcount == 0:
            raise PersonnelMigrationNotFoundError(
                f"Active {target_table_name} record {target_record_id} not found for void."
            )

    def supersede_target_record(
        self,
        conn: Connection,
        *,
        run: RunContext,
        target_table_name: str,
        target_record_id: int,
        replacement_payload: dict[str, Any],
        actor_id: str,
        provenance: dict[str, Any],
    ) -> WrittenRecord:
        if target_table_name not in (TABLE_PERSON_EDUCATION, TABLE_PERSON_TRAINING):
            raise PersonnelMigrationValidationError(
                f"Cannot supersede unknown education target table: {target_table_name!r}"
            )

        id_col = "education_id" if target_table_name == TABLE_PERSON_EDUCATION else "training_id"
        result = conn.execute(
            text(
                f"""
                UPDATE public.{target_table_name}
                SET lifecycle_status = :superseded_status,
                    updated_at = now()
                WHERE {id_col} = :record_id
                  AND lifecycle_status = :active_status
                """
            ),
            {
                "superseded_status": LIFECYCLE_STATUS_SUPERSEDED,
                "record_id": int(target_record_id),
                "active_status": LIFECYCLE_STATUS_ACTIVE,
            },
        )
        if result.rowcount == 0:
            raise PersonnelMigrationNotFoundError(
                f"Active {target_table_name} record {target_record_id} not found for supersede."
            )

        merged_payload = {**replacement_payload, **provenance}
        if target_table_name == TABLE_PERSON_EDUCATION:
            new_id = self._insert_education_from_payload(
                conn,
                run=run,
                draft_payload=merged_payload,
                import_batch_id=provenance.get("import_batch_id"),
                import_row_id=provenance.get("import_row_id"),
                actor_id=actor_id,
            )
        else:
            new_id = self._insert_training_from_payload(
                conn,
                run=run,
                draft_payload=merged_payload,
                import_batch_id=provenance.get("import_batch_id"),
                import_row_id=provenance.get("import_row_id"),
                actor_id=actor_id,
            )

        return WrittenRecord(
            item_id=0,
            target_table_name=target_table_name,
            target_record_id=new_id,
        )

    def _insert_education(
        self,
        conn: Connection,
        *,
        run: RunContext,
        item: DraftItemContext,
        actor_id: str,
    ) -> int:
        return self._insert_education_from_payload(
            conn,
            run=run,
            draft_payload=item.draft_payload or {},
            import_batch_id=item.import_batch_id,
            import_row_id=item.import_row_id,
            actor_id=actor_id,
        )

    def _insert_training(
        self,
        conn: Connection,
        *,
        run: RunContext,
        item: DraftItemContext,
        actor_id: str,
    ) -> int:
        return self._insert_training_from_payload(
            conn,
            run=run,
            draft_payload=item.draft_payload or {},
            import_batch_id=item.import_batch_id,
            import_row_id=item.import_row_id,
            actor_id=actor_id,
        )

    def _insert_education_from_payload(
        self,
        conn: Connection,
        *,
        run: RunContext,
        draft_payload: dict[str, Any],
        import_batch_id: Optional[int],
        import_row_id: Optional[int],
        actor_id: str,
    ) -> int:
        payload = draft_payload or {}
        verification_status = payload.get("verification_status") or VERIFICATION_STATUS_PENDING
        row = conn.execute(
            text(
                """
                INSERT INTO public.person_education (
                    person_id,
                    employee_context_id,
                    education_kind,
                    institution_type,
                    institution_name,
                    specialty,
                    qualification,
                    started_at,
                    completed_at,
                    diploma_number,
                    document_date,
                    verification_status,
                    lifecycle_status,
                    import_batch_id,
                    import_row_id,
                    source_field,
                    source_text,
                    parse_method,
                    confidence,
                    migrated_at,
                    migrated_by,
                    metadata
                )
                VALUES (
                    :person_id,
                    :employee_context_id,
                    :education_kind,
                    :institution_type,
                    :institution_name,
                    :specialty,
                    :qualification,
                    :started_at,
                    :completed_at,
                    :diploma_number,
                    :document_date,
                    :verification_status,
                    :lifecycle_status,
                    :import_batch_id,
                    :import_row_id,
                    :source_field,
                    :source_text,
                    :parse_method,
                    :confidence,
                    now(),
                    :migrated_by,
                    CAST(:metadata AS jsonb)
                )
                RETURNING education_id
                """
            ),
            {
                "person_id": int(run.person_id),
                "employee_context_id": run.employee_context_id,
                "education_kind": payload.get("education_kind"),
                "institution_type": payload.get("institution_type"),
                "institution_name": payload.get("institution_name"),
                "specialty": payload.get("specialty"),
                "qualification": payload.get("qualification"),
                "started_at": _parse_date(payload.get("started_at")),
                "completed_at": _parse_date(payload.get("completed_at")),
                "diploma_number": payload.get("diploma_number"),
                "document_date": _parse_date(payload.get("document_date")),
                "verification_status": verification_status,
                "lifecycle_status": LIFECYCLE_STATUS_ACTIVE,
                "import_batch_id": import_batch_id,
                "import_row_id": import_row_id,
                "source_field": payload.get("source_field"),
                "source_text": payload.get("source_text"),
                "parse_method": payload.get("parse_method"),
                "confidence": payload.get("confidence"),
                "migrated_by": actor_id,
                "metadata": json.dumps(_parse_metadata(payload.get("metadata")), ensure_ascii=False),
            },
        ).one()
        return int(row[0])

    def _insert_training_from_payload(
        self,
        conn: Connection,
        *,
        run: RunContext,
        draft_payload: dict[str, Any],
        import_batch_id: Optional[int],
        import_row_id: Optional[int],
        actor_id: str,
    ) -> int:
        payload = draft_payload or {}
        verification_status = payload.get("verification_status") or VERIFICATION_STATUS_PENDING
        row = conn.execute(
            text(
                """
                INSERT INTO public.person_training (
                    person_id,
                    employee_context_id,
                    training_kind,
                    title,
                    organization_name,
                    hours,
                    started_at,
                    completed_at,
                    certificate_number,
                    document_date,
                    verification_status,
                    lifecycle_status,
                    import_batch_id,
                    import_row_id,
                    source_field,
                    source_text,
                    parse_method,
                    confidence,
                    migrated_at,
                    migrated_by,
                    metadata
                )
                VALUES (
                    :person_id,
                    :employee_context_id,
                    :training_kind,
                    :title,
                    :organization_name,
                    :hours,
                    :started_at,
                    :completed_at,
                    :certificate_number,
                    :document_date,
                    :verification_status,
                    :lifecycle_status,
                    :import_batch_id,
                    :import_row_id,
                    :source_field,
                    :source_text,
                    :parse_method,
                    :confidence,
                    now(),
                    :migrated_by,
                    CAST(:metadata AS jsonb)
                )
                RETURNING training_id
                """
            ),
            {
                "person_id": int(run.person_id),
                "employee_context_id": run.employee_context_id,
                "training_kind": payload.get("training_kind"),
                "title": payload.get("title"),
                "organization_name": payload.get("organization_name"),
                "hours": payload.get("hours"),
                "started_at": _parse_date(payload.get("started_at")),
                "completed_at": _parse_date(payload.get("completed_at")),
                "certificate_number": payload.get("certificate_number"),
                "document_date": _parse_date(payload.get("document_date")),
                "verification_status": verification_status,
                "lifecycle_status": LIFECYCLE_STATUS_ACTIVE,
                "import_batch_id": import_batch_id,
                "import_row_id": import_row_id,
                "source_field": payload.get("source_field"),
                "source_text": payload.get("source_text"),
                "parse_method": payload.get("parse_method"),
                "confidence": payload.get("confidence"),
                "migrated_by": actor_id,
                "metadata": json.dumps(_parse_metadata(payload.get("metadata")), ensure_ascii=False),
            },
        ).one()
        return int(row[0])

"""ADR-059 Phase 2 — import review exception diff viewer and resolution."""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.mrd.domain.candidate_builder import CONFLICT_ATTRIBUTE, RECORD_PRESENCE_ATTRIBUTE
from app.mrd.domain.difference_models import ConfirmDifferenceCommand, RejectDifferenceCommand
from app.mrd.domain.field_labels import get_field_label
from app.services.hr_import_training_date_quality_service import (
    _effective_roster_training_fields,
    assess_normalized_record_date_quality,
    assess_roster_training_raw_quality,
)
from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_DETECTED,
    TECHNICAL_DIFF_CONFLICT,
)
from app.services.hr_canonical_snapshot_service import (
    NORMALIZED_COMPARE_FIELDS,
    RECORD_KIND_ROSTER,
    ROSTER_COMPARE_FIELDS,
    build_normalized_effective_payload,
    build_roster_effective_payload,
)
from app.services.hr_import_analytics_service import (
    BatchNotFoundError,
    _ensure_batch_exists,
    _load_staging_rows,
    is_real_employee_row,
    load_row_payload,
)
from app.services.hr_import_diff_removal_decision_service import (
    DECISION_CONFIRM_REMOVAL,
    DECISION_RESTORE,
    DiffRemovalAlreadyDecidedError,
    DiffRemovalNotFoundError,
    record_diff_removal_decision,
)
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_CHANGED,
    DIFF_STATUS_CONFLICT,
    DIFF_STATUS_NEW,
    DIFF_STATUS_REMOVED,
    DIFF_STATUS_UNCHANGED,
    DIFF_STATUSES_VISIBLE_IN_REVIEW,
    compute_field_diffs,
)
from app.services.hr_import_review_exception_service import detected_differences_available

BASELINE_SOURCE_LABEL = "Canonical Baseline"
IMPORT_SOURCE_LABEL = "Current Import"

RESOLUTION_ACCEPT_IMPORT = "accept_import"
RESOLUTION_KEEP_BASELINE = "keep_baseline"

RECORD_KIND_LABELS = {
    "training": "Обучение",
    "education": "Образование",
    "certificate": "Сертификат",
    "category": "Категория",
    "roster": "Список",
}

ROSTER_IMPORT_CORRECTABLE_FIELDS = frozenset(
    {
        "full_name",
        "department",
        "position_raw",
        "training_raw",
        "certification_raw",
        "education_raw",
        "degree_raw",
        "experience_raw",
        "note_raw",
    }
)


class ReviewExceptionNotFoundError(LookupError):
    def __init__(self, exception_key: str) -> None:
        super().__init__(f"review exception {exception_key!r} not found")
        self.exception_key = exception_key


class ReviewExceptionAlreadyResolvedError(RuntimeError):
    def __init__(self, exception_key: str) -> None:
        super().__init__(f"review exception {exception_key!r} is already resolved")
        self.exception_key = exception_key


class InvalidReviewExceptionKeyError(ValueError):
    pass


class InvalidReviewExceptionResolutionError(ValueError):
    pass


def _display_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _format_field_value(value: Any) -> str | None:
    normalized = _display_value(value)
    if normalized is None:
        return None
    text_val = str(normalized).strip()
    return text_val or None


def _lookup_org_unit_name(conn: Connection, org_unit_id: Any) -> str | None:
    try:
        unit_id = int(org_unit_id)
    except (TypeError, ValueError):
        return None
    if unit_id < 1:
        return None
    row = conn.execute(
        text(
            """
            SELECT name
            FROM public.org_units
            WHERE unit_id = :unit_id
            LIMIT 1
            """
        ),
        {"unit_id": unit_id},
    ).scalar()
    return str(row).strip() if row else None


def _lookup_medical_specialty_name(conn: Connection, specialty_id: Any) -> str | None:
    try:
        medical_specialty_id = int(specialty_id)
    except (TypeError, ValueError):
        return None
    if medical_specialty_id < 1:
        return None
    row = conn.execute(
        text(
            """
            SELECT name
            FROM public.medical_specialties
            WHERE medical_specialty_id = :medical_specialty_id
            LIMIT 1
            """
        ),
        {"medical_specialty_id": medical_specialty_id},
    ).scalar()
    return str(row).strip() if row else None


def _resolve_reference_display_value(
    conn: Connection,
    *,
    field: str,
    value: Any,
    record_kind: str,
) -> str | None:
    raw = _format_field_value(value)
    if raw is None:
        return None
    if field == "org_unit_id":
        resolved = _lookup_org_unit_name(conn, value)
        return resolved or raw
    if field == "medical_specialty_id":
        resolved = _lookup_medical_specialty_name(conn, value)
        return resolved or raw
    if field == "record_kind":
        return RECORD_KIND_LABELS.get(raw, raw)
    return raw


def _serialize_field_value(
    conn: Connection,
    *,
    field: str,
    value: Any,
    record_kind: str,
) -> dict[str, Any]:
    raw = _format_field_value(value)
    display = _resolve_reference_display_value(
        conn,
        field=field,
        value=value,
        record_kind=record_kind,
    )
    return {
        "value": raw,
        "display_value": display,
    }


def _load_row_import_review_override(conn: Connection, batch_id: int, row_id: int) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND row_id = :row_id
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    ).mappings().first()
    if row is None:
        return {}
    payload = dict(row.get("normalized_payload") or {})
    metadata = dict(payload.get("metadata") or {})
    override = metadata.get("import_review_override")
    if isinstance(override, dict):
        return dict(override)
    return {}


def _editable_import_fields(*, entity_type: str, record_kind: str) -> list[str]:
    if entity_type == "row":
        return sorted(ROSTER_IMPORT_CORRECTABLE_FIELDS)
    from app.services.hr_import_normalized_record_service import OVERRIDABLE_FIELDS_BY_KIND

    allowed = OVERRIDABLE_FIELDS_BY_KIND.get(record_kind, frozenset())
    return sorted(allowed)


def _quality_remarks_for_row(conn: Connection, batch_id: int, row_id: int) -> list[str]:
    row = conn.execute(
        text(
            """
            SELECT normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND row_id = :row_id
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    ).mappings().first()
    if row is None:
        return []
    training_raw, education_raw = _effective_roster_training_fields(dict(row))
    return assess_roster_training_raw_quality(
        training_raw=training_raw,
        education_raw=education_raw,
    )


def _quality_remarks_for_normalized(row: dict[str, Any]) -> list[str]:
    from app.services.hr_import_normalized_record_service import merge_review_override

    effective = merge_review_override(dict(row))
    return assess_normalized_record_date_quality(effective)


def parse_exception_key(exception_key: str) -> tuple[str, int]:
    raw = str(exception_key or "").strip().strip("/")
    if raw.startswith("rows/"):
        entity_id = int(raw.split("/", 1)[1])
        return "row", entity_id
    if raw.startswith("normalized/"):
        entity_id = int(raw.split("/", 1)[1])
        return "normalized", entity_id
    if raw.startswith("removals/"):
        entity_id = int(raw.split("/", 1)[1])
        return "removal", entity_id
    raise InvalidReviewExceptionKeyError(
        f"invalid exception key {exception_key!r}; expected rows/{{id}}, normalized/{{id}}, or removals/{{id}}"
    )


def build_exception_key(*, entity_type: str, entity_id: int) -> str:
    if entity_type == "row":
        return f"rows/{entity_id}"
    if entity_type == "normalized":
        return f"normalized/{entity_id}"
    if entity_type == "removal":
        return f"removals/{entity_id}"
    raise InvalidReviewExceptionKeyError(f"unsupported entity_type {entity_type!r}")


def _compare_fields_for_record_kind(record_kind: str) -> frozenset[str]:
    if record_kind == RECORD_KIND_ROSTER:
        return ROSTER_COMPARE_FIELDS
    return NORMALIZED_COMPARE_FIELDS


def _load_canonical_payload(conn: Connection, *, canonical_entry_id: int | None) -> dict[str, Any]:
    if canonical_entry_id is None:
        return {}
    row = conn.execute(
        text(
            """
            SELECT payload
            FROM public.hr_canonical_snapshot_entries
            WHERE entry_id = :entry_id
            """
        ),
        {"entry_id": canonical_entry_id},
    ).mappings().first()
    if row is None:
        return {}
    payload = row.get("payload")
    if isinstance(payload, str):
        payload = json.loads(payload)
    return dict(payload or {})


def _serialize_field_rows(
    conn: Connection,
    payload: dict[str, Any],
    *,
    compare_fields: frozenset[str],
    record_kind: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in sorted(compare_fields):
        serialized = _serialize_field_value(
            conn,
            field=field,
            value=payload.get(field),
            record_kind=record_kind,
        )
        rows.append(
            {
                "key": field,
                "label": get_field_label(field, record_kind=record_kind),
                "value": serialized["value"],
                "display_value": serialized["display_value"],
            }
        )
    return rows


def _serialize_diff_rows(
    conn: Connection,
    *,
    baseline_payload: dict[str, Any],
    import_payload: dict[str, Any],
    compare_fields: frozenset[str],
    record_kind: str,
    field_diffs: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    diffs = field_diffs or compute_field_diffs(
        canonical_payload=baseline_payload,
        incoming_payload=import_payload,
        compare_fields=compare_fields,
    )
    rows: list[dict[str, Any]] = []
    for field in sorted(compare_fields):
        baseline_serialized = _serialize_field_value(
            conn,
            field=field,
            value=baseline_payload.get(field),
            record_kind=record_kind,
        )
        import_serialized = _serialize_field_value(
            conn,
            field=field,
            value=import_payload.get(field),
            record_kind=record_kind,
        )
        changed = field in diffs or baseline_serialized["value"] != import_serialized["value"]
        rows.append(
            {
                "key": field,
                "label": get_field_label(field, record_kind=record_kind),
                "baseline_value": baseline_serialized["value"],
                "baseline_display_value": baseline_serialized["display_value"],
                "import_value": import_serialized["value"],
                "import_display_value": import_serialized["display_value"],
                "changed": changed,
            }
        )
    return rows


def _row_is_unresolved_exception(diff_status: str | None, *, employee_id: int | None) -> bool:
    status = str(diff_status or "")
    if status in {DIFF_STATUS_CHANGED, DIFF_STATUS_CONFLICT}:
        return True
    if status == DIFF_STATUS_NEW and employee_id is None:
        return True
    return False


def _load_row_exception_summary(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                r.row_id,
                r.diff_status,
                r.employee_id,
                r.field_diffs,
                r.canonical_entry_id,
                COALESCE(r.normalized_payload->>'full_name', '') AS full_name,
                COALESCE(r.normalized_payload->>'position_raw', '') AS position_raw,
                COALESCE(r.normalized_payload->>'department', '') AS department
            FROM public.hr_import_rows r
            WHERE r.batch_id = :batch_id
              AND r.diff_status = ANY(:statuses)
            ORDER BY r.row_id
            """
        ),
        {
            "batch_id": batch_id,
            "statuses": list(DIFF_STATUSES_VISIBLE_IN_REVIEW - {DIFF_STATUS_REMOVED}),
        },
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for row in rows:
        diff_status = str(row.get("diff_status") or "")
        employee_id = int(row["employee_id"]) if row.get("employee_id") is not None else None
        if not _row_is_unresolved_exception(diff_status, employee_id=employee_id):
            continue
        row_id = int(row["row_id"])
        items.append(
            {
                "exception_key": build_exception_key(entity_type="row", entity_id=row_id),
                "entity_type": "row",
                "entity_id": row_id,
                "diff_status": diff_status,
                "record_kind": RECORD_KIND_ROSTER,
                "title": str(row.get("full_name") or "").strip() or f"Строка #{row_id}",
                "subtitle": str(row.get("position_raw") or "").strip() or None,
                "department": str(row.get("department") or "").strip() or None,
                "resolved": False,
            }
        )
    return items


def _load_normalized_exception_summary(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    table = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_normalized_records'
            LIMIT 1
            """
        )
    ).first()
    if table is None:
        return []

    rows = conn.execute(
        text(
            """
            SELECT
                nr.normalized_record_id,
                nr.row_id,
                nr.diff_status,
                nr.record_kind,
                nr.title,
                nr.employee_id,
                COALESCE(r.employee_id, nr.employee_id) AS effective_employee_id,
                COALESCE(r.normalized_payload->>'full_name', '') AS full_name,
                COALESCE(r.normalized_payload->>'department', '') AS department
            FROM public.hr_import_normalized_records nr
            LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
            WHERE nr.batch_id = :batch_id
              AND nr.diff_status = ANY(:statuses)
            ORDER BY nr.normalized_record_id
            """
        ),
        {
            "batch_id": batch_id,
            "statuses": list(DIFF_STATUSES_VISIBLE_IN_REVIEW - {DIFF_STATUS_REMOVED}),
        },
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for row in rows:
        diff_status = str(row.get("diff_status") or "")
        employee_id = (
            int(row["effective_employee_id"])
            if row.get("effective_employee_id") is not None
            else None
        )
        if not _row_is_unresolved_exception(diff_status, employee_id=employee_id):
            continue
        normalized_record_id = int(row["normalized_record_id"])
        record_kind = str(row.get("record_kind") or "")
        items.append(
            {
                "exception_key": build_exception_key(entity_type="normalized", entity_id=normalized_record_id),
                "entity_type": "normalized",
                "entity_id": normalized_record_id,
                "diff_status": diff_status,
                "record_kind": record_kind,
                "title": str(row.get("title") or row.get("full_name") or "").strip()
                or f"Запись #{normalized_record_id}",
                "subtitle": record_kind or None,
                "department": str(row.get("department") or "").strip() or None,
                "resolved": False,
            }
        )
    return items


def _load_removal_exception_summary(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    column = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_import_diff_removals'
              AND column_name = 'decision'
            LIMIT 1
            """
        )
    ).first()
    if column is None:
        return []

    rows = conn.execute(
        text(
            """
            SELECT
                removal_id,
                match_key,
                record_kind,
                payload,
                decision
            FROM public.hr_import_diff_removals
            WHERE batch_id = :batch_id
              AND decision IS NULL
            ORDER BY removal_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for row in rows:
        removal_id = int(row["removal_id"])
        payload = dict(row.get("payload") or {})
        if isinstance(payload, str):
            payload = json.loads(payload)
        title = str(payload.get("full_name") or payload.get("title") or row.get("match_key") or "").strip()
        items.append(
            {
                "exception_key": build_exception_key(entity_type="removal", entity_id=removal_id),
                "entity_type": "removal",
                "entity_id": removal_id,
                "diff_status": DIFF_STATUS_REMOVED,
                "record_kind": str(row.get("record_kind") or RECORD_KIND_ROSTER),
                "title": title or f"Удаление #{removal_id}",
                "subtitle": str(payload.get("position_raw") or payload.get("record_kind") or "").strip() or None,
                "department": str(payload.get("department") or "").strip() or None,
                "resolved": False,
            }
        )
    return items


def list_review_exceptions(
    conn: Connection,
    batch_id: int,
    *,
    diff_status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    items = (
        _load_row_exception_summary(conn, batch_id)
        + _load_normalized_exception_summary(conn, batch_id)
        + _load_removal_exception_summary(conn, batch_id)
    )
    if diff_status:
        items = [item for item in items if item["diff_status"] == diff_status]
    total = len(items)
    page = items[offset : offset + limit]
    return {"batch_id": batch_id, "total": total, "items": page}


def _load_row_exception_detail(
    conn: Connection,
    batch_id: int,
    row_id: int,
    *,
    allow_resolved: bool = False,
) -> dict[str, Any]:
    row = load_row_payload(conn, batch_id, row_id)
    diff_row = conn.execute(
        text(
            """
            SELECT diff_status, canonical_entry_id, field_diffs, employee_id
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND row_id = :row_id
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    ).mappings().first()
    if diff_row is None:
        raise ReviewExceptionNotFoundError(build_exception_key(entity_type="row", entity_id=row_id))

    diff_status = str(diff_row.get("diff_status") or "")
    employee_id = int(diff_row["employee_id"]) if diff_row.get("employee_id") is not None else None
    if not allow_resolved and not _row_is_unresolved_exception(diff_status, employee_id=employee_id):
        raise ReviewExceptionAlreadyResolvedError(build_exception_key(entity_type="row", entity_id=row_id))

    field_diffs = diff_row.get("field_diffs")
    if isinstance(field_diffs, str):
        field_diffs = json.loads(field_diffs)

    import_payload, _, match_key = build_roster_effective_payload(conn, batch_id=batch_id, row=row)
    baseline_payload = _load_canonical_payload(
        conn,
        canonical_entry_id=int(diff_row["canonical_entry_id"])
        if diff_row.get("canonical_entry_id") is not None
        else None,
    )
    compare_fields = _compare_fields_for_record_kind(RECORD_KIND_ROSTER)
    payload = row["payload"]
    quality_remarks = _quality_remarks_for_row(conn, batch_id, row_id)

    return {
        "exception_key": build_exception_key(entity_type="row", entity_id=row_id),
        "entity_type": "row",
        "entity_id": row_id,
        "batch_id": batch_id,
        "diff_status": diff_status,
        "record_kind": RECORD_KIND_ROSTER,
        "match_key": match_key,
        "title": str(payload.get("full_name") or "").strip() or f"Строка #{row_id}",
        "subtitle": str(payload.get("position_raw") or "").strip() or None,
        "department": str(payload.get("department") or "").strip() or None,
        "baseline": {
            "source_label": BASELINE_SOURCE_LABEL,
            "fields": _serialize_field_rows(
                conn,
                baseline_payload,
                compare_fields=compare_fields,
                record_kind=RECORD_KIND_ROSTER,
            ),
        },
        "import_data": {
            "source_label": IMPORT_SOURCE_LABEL,
            "fields": _serialize_field_rows(
                conn,
                import_payload,
                compare_fields=compare_fields,
                record_kind=RECORD_KIND_ROSTER,
            ),
        },
        "diff": {
            "fields": _serialize_diff_rows(
                conn,
                baseline_payload=baseline_payload,
                import_payload=import_payload,
                compare_fields=compare_fields,
                record_kind=RECORD_KIND_ROSTER,
                field_diffs=field_diffs,
            ),
        },
        "quality_remarks": quality_remarks,
        "editable_import_fields": _editable_import_fields(
            entity_type="row",
            record_kind=RECORD_KIND_ROSTER,
        ),
        "import_review_override": _load_row_import_review_override(conn, batch_id, row_id),
        "correct_action_available": _row_is_unresolved_exception(diff_status, employee_id=employee_id),
        "resolved": not _row_is_unresolved_exception(diff_status, employee_id=employee_id),
        "resolved_by_correction": allow_resolved and diff_status == DIFF_STATUS_UNCHANGED,
        "actions_available": _row_is_unresolved_exception(diff_status, employee_id=employee_id),
        "removal_actions_available": False,
    }


def _load_normalized_exception_detail(
    conn: Connection,
    batch_id: int,
    normalized_record_id: int,
    *,
    allow_resolved: bool = False,
) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT nr.*, COALESCE(r.employee_id, nr.employee_id) AS effective_employee_id
            FROM public.hr_import_normalized_records nr
            LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
            WHERE nr.batch_id = :batch_id
              AND nr.normalized_record_id = :normalized_record_id
            """
        ),
        {"batch_id": batch_id, "normalized_record_id": normalized_record_id},
    ).mappings().first()
    if row is None:
        raise ReviewExceptionNotFoundError(
            build_exception_key(entity_type="normalized", entity_id=normalized_record_id)
        )

    diff_status = str(row.get("diff_status") or "")
    employee_id = (
        int(row["effective_employee_id"]) if row.get("effective_employee_id") is not None else None
    )
    if not allow_resolved and not _row_is_unresolved_exception(diff_status, employee_id=employee_id):
        raise ReviewExceptionAlreadyResolvedError(
            build_exception_key(entity_type="normalized", entity_id=normalized_record_id)
        )

    field_diffs = row.get("field_diffs")
    if isinstance(field_diffs, str):
        field_diffs = json.loads(field_diffs)

    record_kind = str(row.get("record_kind") or "")
    compare_fields = _compare_fields_for_record_kind(record_kind)
    import_payload = build_normalized_effective_payload(dict(row))
    baseline_payload = _load_canonical_payload(
        conn,
        canonical_entry_id=int(row["canonical_entry_id"])
        if row.get("canonical_entry_id") is not None
        else None,
    )
    from app.services.hr_import_normalized_record_service import _parse_review_override_json

    quality_remarks = _quality_remarks_for_normalized(dict(row))
    unresolved = _row_is_unresolved_exception(diff_status, employee_id=employee_id)

    return {
        "exception_key": build_exception_key(entity_type="normalized", entity_id=normalized_record_id),
        "entity_type": "normalized",
        "entity_id": normalized_record_id,
        "batch_id": batch_id,
        "diff_status": diff_status,
        "record_kind": record_kind,
        "match_key": None,
        "title": str(row.get("title") or "").strip() or f"Запись #{normalized_record_id}",
        "subtitle": RECORD_KIND_LABELS.get(record_kind, record_kind) or None,
        "department": None,
        "baseline": {
            "source_label": BASELINE_SOURCE_LABEL,
            "fields": _serialize_field_rows(
                conn,
                baseline_payload,
                compare_fields=compare_fields,
                record_kind=record_kind,
            ),
        },
        "import_data": {
            "source_label": IMPORT_SOURCE_LABEL,
            "fields": _serialize_field_rows(
                conn,
                import_payload,
                compare_fields=compare_fields,
                record_kind=record_kind,
            ),
        },
        "diff": {
            "fields": _serialize_diff_rows(
                conn,
                baseline_payload=baseline_payload,
                import_payload=import_payload,
                compare_fields=compare_fields,
                record_kind=record_kind,
                field_diffs=field_diffs,
            ),
        },
        "quality_remarks": quality_remarks,
        "editable_import_fields": _editable_import_fields(
            entity_type="normalized",
            record_kind=record_kind,
        ),
        "import_review_override": _parse_review_override_json(row.get("review_override_json")),
        "correct_action_available": unresolved,
        "resolved": not unresolved,
        "resolved_by_correction": allow_resolved and diff_status == DIFF_STATUS_UNCHANGED,
        "actions_available": unresolved,
        "removal_actions_available": False,
    }


def _load_removal_exception_detail(
    conn: Connection,
    batch_id: int,
    removal_id: int,
    *,
    allow_resolved: bool = False,
) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.hr_import_diff_removals
            WHERE batch_id = :batch_id
              AND removal_id = :removal_id
            """
        ),
        {"batch_id": batch_id, "removal_id": removal_id},
    ).mappings().first()
    if row is None:
        raise ReviewExceptionNotFoundError(build_exception_key(entity_type="removal", entity_id=removal_id))

    if row.get("decision") is not None:
        raise ReviewExceptionAlreadyResolvedError(build_exception_key(entity_type="removal", entity_id=removal_id))

    payload = dict(row.get("payload") or {})
    if isinstance(payload, str):
        payload = json.loads(payload)
    record_kind = str(row.get("record_kind") or RECORD_KIND_ROSTER)
    compare_fields = _compare_fields_for_record_kind(record_kind)
    import_payload: dict[str, Any] = {}

    return {
        "exception_key": build_exception_key(entity_type="removal", entity_id=removal_id),
        "entity_type": "removal",
        "entity_id": removal_id,
        "batch_id": batch_id,
        "diff_status": DIFF_STATUS_REMOVED,
        "record_kind": record_kind,
        "match_key": str(row.get("match_key") or ""),
        "title": str(payload.get("full_name") or payload.get("title") or row.get("match_key") or "").strip()
        or f"Удаление #{removal_id}",
        "subtitle": str(payload.get("position_raw") or "").strip() or None,
        "department": str(payload.get("department") or "").strip() or None,
        "baseline": {
            "source_label": BASELINE_SOURCE_LABEL,
            "fields": _serialize_field_rows(
                conn,
                payload,
                compare_fields=compare_fields,
                record_kind=record_kind,
            ),
        },
        "import_data": {
            "source_label": IMPORT_SOURCE_LABEL,
            "fields": _serialize_field_rows(
                conn,
                import_payload,
                compare_fields=compare_fields,
                record_kind=record_kind,
            ),
        },
        "diff": {
            "fields": _serialize_diff_rows(
                conn,
                baseline_payload=payload,
                import_payload=import_payload,
                compare_fields=compare_fields,
                record_kind=record_kind,
                field_diffs=None,
            ),
        },
        "quality_remarks": [],
        "editable_import_fields": [],
        "import_review_override": {},
        "correct_action_available": False,
        "resolved": False,
        "actions_available": False,
        "removal_actions_available": True,
    }


def get_review_exception_detail(
    conn: Connection,
    batch_id: int,
    exception_key: str,
    *,
    allow_resolved: bool = False,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    entity_type, entity_id = parse_exception_key(exception_key)
    if entity_type == "row":
        return _load_row_exception_detail(conn, batch_id, entity_id, allow_resolved=allow_resolved)
    if entity_type == "normalized":
        return _load_normalized_exception_detail(
            conn,
            batch_id,
            entity_id,
            allow_resolved=allow_resolved,
        )
    if entity_type == "removal":
        return _load_removal_exception_detail(conn, batch_id, entity_id, allow_resolved=allow_resolved)
    raise InvalidReviewExceptionKeyError(f"unsupported entity_type {entity_type!r}")


def _find_mrd_differences_for_exception(
    conn: Connection,
    batch_id: int,
    *,
    row_id: int | None = None,
    normalized_record_id: int | None = None,
) -> list[dict[str, Any]]:
    if not detected_differences_available(conn):
        return []

    params: dict[str, Any] = {
        "batch_id": batch_id,
        "detected": DIFFERENCE_LIFECYCLE_DETECTED,
    }
    origin_filter = ""
    if row_id is not None:
        origin_filter = "AND (d.origin_context->>'row_id')::bigint = :row_id"
        params["row_id"] = row_id
    elif normalized_record_id is not None:
        origin_filter = "AND (d.origin_context->>'normalized_record_id')::bigint = :normalized_record_id"
        params["normalized_record_id"] = normalized_record_id
    else:
        return []

    rows = conn.execute(
        text(
            f"""
            SELECT
                difference_id,
                attribute,
                technical_diff_class,
                row_version,
                lifecycle_status
            FROM public.hr_detected_differences d
            WHERE d.lifecycle_status = :detected
              AND (
                    (d.origin_context->>'batch_id')::bigint = :batch_id
                 OR d.last_comparison_run_id IN (
                        SELECT comparison_run_id
                        FROM public.hr_comparison_runs
                        WHERE batch_id = :batch_id
                    )
              )
              {origin_filter}
            ORDER BY difference_id
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _mark_staging_exception_resolved(
    conn: Connection,
    *,
    batch_id: int,
    row_id: int | None = None,
    normalized_record_id: int | None = None,
) -> None:
    if row_id is not None:
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET diff_status = :unchanged
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {
                "batch_id": batch_id,
                "row_id": row_id,
                "unchanged": DIFF_STATUS_UNCHANGED,
            },
        )
    if normalized_record_id is not None:
        conn.execute(
            text(
                """
                UPDATE public.hr_import_normalized_records
                SET diff_status = :unchanged
                WHERE batch_id = :batch_id
                  AND normalized_record_id = :normalized_record_id
                """
            ),
            {
                "batch_id": batch_id,
                "normalized_record_id": normalized_record_id,
                "unchanged": DIFF_STATUS_UNCHANGED,
            },
        )


def _resolve_mrd_differences(
    conn: Connection,
    differences: list[dict[str, Any]],
    *,
    resolution: str,
    actor_user_id: int,
    batch_id: int,
) -> None:
    if not differences:
        return

    from app.mrd.application.confirm_service import ConfirmDifferenceService
    from app.mrd.application.reject_service import RejectDifferenceService
    from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository

    repo = SqlAlchemyMrdRepository(conn)
    confirm_service = ConfirmDifferenceService(repo)
    reject_service = RejectDifferenceService(repo)
    command_id_base = uuid.uuid4().hex

    for index, diff in enumerate(differences):
        difference_id = int(diff["difference_id"])
        row_version = int(diff["row_version"])
        attribute = str(diff.get("attribute") or "")
        technical = str(diff.get("technical_diff_class") or "")

        if resolution == RESOLUTION_ACCEPT_IMPORT:
            if technical == TECHNICAL_DIFF_CONFLICT or attribute == CONFLICT_ATTRIBUTE:
                confirm_service.confirm(
                    ConfirmDifferenceCommand(
                        difference_id=difference_id,
                        confirmed_by=actor_user_id,
                        expected_row_version=row_version,
                        basis=f"ADR-059 accept import (batch {batch_id})",
                        resolve_conflict=True,
                    )
                )
            elif attribute == RECORD_PRESENCE_ATTRIBUTE:
                reject_service.reject(
                    RejectDifferenceCommand(
                        difference_id=difference_id,
                        rejected_by=actor_user_id,
                        expected_row_version=row_version,
                        basis=f"ADR-059 accept import (batch {batch_id})",
                    )
                )
            else:
                confirm_service.confirm(
                    ConfirmDifferenceCommand(
                        difference_id=difference_id,
                        confirmed_by=actor_user_id,
                        expected_row_version=row_version,
                        basis=f"ADR-059 accept import (batch {batch_id})",
                    )
                )
        elif resolution == RESOLUTION_KEEP_BASELINE:
            reject_service.reject(
                RejectDifferenceCommand(
                    difference_id=difference_id,
                    rejected_by=actor_user_id,
                    expected_row_version=row_version,
                    basis=f"ADR-059 keep baseline (batch {batch_id})",
                )
            )
        else:
            raise InvalidReviewExceptionResolutionError(f"unsupported resolution {resolution!r}")
        _ = command_id_base, index


def resolve_review_exception(
    conn: Connection,
    batch_id: int,
    exception_key: str,
    *,
    resolution: str,
    actor_user_id: int,
    basis: str | None = None,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    if resolution not in {RESOLUTION_ACCEPT_IMPORT, RESOLUTION_KEEP_BASELINE}:
        raise InvalidReviewExceptionResolutionError(
            f"invalid resolution {resolution!r}; expected accept_import or keep_baseline"
        )

    entity_type, entity_id = parse_exception_key(exception_key)
    detail = get_review_exception_detail(conn, batch_id, exception_key)

    if entity_type == "removal":
        raise InvalidReviewExceptionResolutionError(
            "use removal decision endpoints for REMOVED exceptions"
        )

    row_id = entity_id if entity_type == "row" else None
    normalized_record_id = entity_id if entity_type == "normalized" else None
    differences = _find_mrd_differences_for_exception(
        conn,
        batch_id,
        row_id=row_id,
        normalized_record_id=normalized_record_id,
    )
    _resolve_mrd_differences(
        conn,
        differences,
        resolution=resolution,
        actor_user_id=actor_user_id,
        batch_id=batch_id,
    )
    _mark_staging_exception_resolved(
        conn,
        batch_id=batch_id,
        row_id=row_id,
        normalized_record_id=normalized_record_id,
    )

    from app.services.hr_import_complete_review_service import maybe_auto_complete_import_review

    auto_review = maybe_auto_complete_import_review(conn, batch_id, actor_user_id=actor_user_id)
    return {
        "exception_key": exception_key,
        "resolution": resolution,
        "basis": basis,
        "batch_id": batch_id,
        "resolved": True,
        "differences_resolved": len(differences),
        "auto_review": auto_review,
        "detail": detail,
    }


def _build_row_import_review_override(
    conn: Connection,
    batch_id: int,
    row_id: int,
    submitted: dict[str, Any],
) -> dict[str, Any]:
    staging = load_row_payload(conn, batch_id, row_id)
    payload = staging["payload"]
    sparse: dict[str, Any] = {}
    for field in ROSTER_IMPORT_CORRECTABLE_FIELDS:
        if field not in submitted:
            continue
        normalized = _format_field_value(submitted.get(field))
        base = _format_field_value(payload.get(field))
        if normalized != base:
            sparse[field] = normalized
    return sparse


def clear_import_review_overrides_for_batch(conn: Connection, batch_id: int) -> dict[str, int]:
    """Drop staging review overrides after canonical baseline is published (Apply)."""
    from app.services.hr_import_normalized_record_service import review_override_available

    normalized_cleared = 0
    if review_override_available(conn):
        normalized_cleared = int(
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_normalized_records
                    SET
                        review_override_json = NULL,
                        review_override_updated_by = NULL,
                        review_override_updated_at = NULL,
                        updated_at = NOW()
                    WHERE batch_id = :batch_id
                      AND review_override_json IS NOT NULL
                    """
                ),
                {"batch_id": batch_id},
            ).rowcount
            or 0
        )

    rows_cleared = 0
    override_rows = conn.execute(
        text(
            """
            SELECT row_id, normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND normalized_payload->'metadata'->'import_review_override' IS NOT NULL
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    for row in override_rows:
        payload = row["normalized_payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            continue
        metadata = dict(payload.get("metadata") or {})
        if "import_review_override" not in metadata:
            continue
        metadata.pop("import_review_override")
        payload["metadata"] = metadata
        conn.execute(
            text(
                """
                UPDATE public.hr_import_rows
                SET normalized_payload = CAST(:normalized_payload AS JSONB)
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {
                "batch_id": batch_id,
                "row_id": int(row["row_id"]),
                "normalized_payload": json.dumps(payload, ensure_ascii=False, default=str),
            },
        )
        rows_cleared += 1

    return {
        "normalized_records_cleared": normalized_cleared,
        "rows_cleared": rows_cleared,
    }


def _auto_dismiss_mrd_differences_when_unchanged(
    conn: Connection,
    batch_id: int,
    *,
    entity_type: str,
    entity_id: int,
    actor_user_id: int,
) -> int:
    row_id = entity_id if entity_type == "row" else None
    normalized_record_id = entity_id if entity_type == "normalized" else None

    if row_id is not None:
        diff_status = conn.execute(
            text(
                """
                SELECT diff_status
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {"batch_id": batch_id, "row_id": row_id},
        ).scalar_one_or_none()
    else:
        diff_status = conn.execute(
            text(
                """
                SELECT diff_status
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                  AND normalized_record_id = :normalized_record_id
                """
            ),
            {"batch_id": batch_id, "normalized_record_id": normalized_record_id},
        ).scalar_one_or_none()

    if diff_status != DIFF_STATUS_UNCHANGED:
        return 0

    differences = _find_mrd_differences_for_exception(
        conn,
        batch_id,
        row_id=row_id,
        normalized_record_id=normalized_record_id,
    )
    if not differences:
        return 0

    _resolve_mrd_differences(
        conn,
        differences,
        resolution=RESOLUTION_KEEP_BASELINE,
        actor_user_id=actor_user_id,
        batch_id=batch_id,
    )
    return len(differences)


def _save_row_import_review_override(
    conn: Connection,
    batch_id: int,
    row_id: int,
    *,
    submitted: dict[str, Any],
) -> dict[str, Any]:
    staging = load_row_payload(conn, batch_id, row_id)
    payload = dict(staging["payload"])
    metadata = dict(staging["metadata"])
    sparse = _build_row_import_review_override(conn, batch_id, row_id, submitted)
    if sparse:
        metadata["import_review_override"] = sparse
    elif "import_review_override" in metadata:
        metadata.pop("import_review_override")

    full_payload = {**payload, "metadata": metadata}
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET normalized_payload = CAST(:normalized_payload AS JSONB)
            WHERE batch_id = :batch_id
              AND row_id = :row_id
            """
        ),
        {
            "batch_id": batch_id,
            "row_id": row_id,
            "normalized_payload": json.dumps(full_payload, ensure_ascii=False, default=str),
        },
    )
    return sparse


def correct_review_exception_import(
    conn: Connection,
    batch_id: int,
    exception_key: str,
    *,
    corrections: dict[str, Any],
    actor_user_id: int,
) -> dict[str, Any]:
    _ensure_batch_exists(conn, batch_id)
    if not isinstance(corrections, dict):
        raise InvalidReviewExceptionResolutionError("corrections must be an object")

    entity_type, entity_id = parse_exception_key(exception_key)
    if entity_type == "removal":
        raise InvalidReviewExceptionResolutionError(
            "corrections are not supported for REMOVED exceptions"
        )

    get_review_exception_detail(conn, batch_id, exception_key)

    if entity_type == "row":
        unknown = set(corrections.keys()) - ROSTER_IMPORT_CORRECTABLE_FIELDS
        if unknown:
            raise InvalidReviewExceptionResolutionError(
                f"unsupported correction fields for roster row: {sorted(unknown)}"
            )
        saved = _save_row_import_review_override(
            conn,
            batch_id,
            entity_id,
            submitted=corrections,
        )
    elif entity_type == "normalized":
        from app.services.hr_import_normalized_record_service import (
            NormalizedRecordNotFoundError,
            update_normalized_record_review_override,
        )

        try:
            update_normalized_record_review_override(
                conn,
                entity_id,
                review_override=corrections,
                updated_by=actor_user_id,
                allow_non_pending=True,
            )
        except NormalizedRecordNotFoundError as exc:
            raise ReviewExceptionNotFoundError(exception_key) from exc
        saved = corrections
    else:
        raise InvalidReviewExceptionKeyError(f"unsupported entity_type {entity_type!r}")

    from app.services.hr_import_monthly_diff_service import compute_batch_monthly_diff

    diff_summary = compute_batch_monthly_diff(conn, batch_id)
    mrd_dismissed = _auto_dismiss_mrd_differences_when_unchanged(
        conn,
        batch_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
    )
    detail = get_review_exception_detail(
        conn,
        batch_id,
        exception_key,
        allow_resolved=True,
    )
    return {
        "exception_key": exception_key,
        "batch_id": batch_id,
        "saved_corrections": saved,
        "detail": detail,
        "diff_summary": diff_summary,
        "diff_recomputed": True,
        "mrd_differences_dismissed": mrd_dismissed,
    }


def resolve_review_removal_exception(
    conn: Connection,
    batch_id: int,
    removal_id: int,
    *,
    decision: str,
    actor_user_id: int,
    basis: str | None = None,
) -> dict[str, Any]:
    normalized = str(decision or "").strip().lower()
    if normalized not in {DECISION_RESTORE, DECISION_CONFIRM_REMOVAL}:
        raise InvalidReviewExceptionResolutionError(
            f"invalid removal decision {decision!r}; expected restore or confirm_removal"
        )
    try:
        result = record_diff_removal_decision(
            conn,
            removal_id,
            decision=normalized,
            decided_by=actor_user_id,
            decision_basis=basis,
            expected_batch_id=batch_id,
        )
    except DiffRemovalNotFoundError as exc:
        raise ReviewExceptionNotFoundError(build_exception_key(entity_type="removal", entity_id=removal_id)) from exc
    except DiffRemovalAlreadyDecidedError as exc:
        raise ReviewExceptionAlreadyResolvedError(
            build_exception_key(entity_type="removal", entity_id=removal_id)
        ) from exc
    return {
        "exception_key": build_exception_key(entity_type="removal", entity_id=removal_id),
        "decision": normalized,
        "batch_id": batch_id,
        "resolved": True,
        "removal": result,
    }

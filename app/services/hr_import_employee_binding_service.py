"""ADR-039 Phase 3G — auto/manual employee binding for HR import rows and normalized records."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.db.models.hr_import import MATCH_STATUS_AUTO, MATCH_STATUS_NO_MATCH, MATCH_STATUS_REVIEW
from app.services.hr_import_normalized_record_service import (
    REVIEW_STATUS_SUPERSEDED,
    compute_source_record_key,
    dedupe_open_normalized_records,
)

logger = logging.getLogger(__name__)

BINDING_STATUS_BOUND = "bound"
BINDING_STATUS_UNBOUND = "unbound"
BINDING_STATUS_CONFLICT = "conflict"

BINDING_METHOD_IIN = "iin"
BINDING_METHOD_FULL_NAME = "full_name"
BINDING_METHOD_ROW_LINK = "row_link"
BINDING_METHOD_MANUAL = "manual"

REBUILDABLE_REVIEW_STATUSES = ("pending", "approved", "rejected", "superseded")
OPEN_EMPLOYEE_DEDUP_STATUSES = ("pending", "approved")


class EmployeeBindingDuplicateKeyError(Exception):
    """Raised when binding would violate uq_hinr_employee_source_key_open."""

    def __init__(self, message: str, *, employee_id: int, source_record_key: str) -> None:
        self.message = message
        self.employee_id = employee_id
        self.source_record_key = source_record_key
        super().__init__(message)


def _norm_name(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _parse_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return json.loads(value) if value.strip() else {}
    return {}


@dataclass
class EmployeeBindingResult:
    employee_id: Optional[int]
    status: str
    method: Optional[str] = None
    reason: Optional[str] = None
    candidate_employee_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "status": self.status,
            "method": self.method,
            "reason": self.reason,
            "candidate_employee_ids": list(self.candidate_employee_ids),
        }


def _lookup_employees_by_iin(conn: Connection, iin_digits: str) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT ei.employee_id
            FROM public.employee_identities ei
            WHERE ei.identity_type = 'IIN'
              AND ei.valid_to IS NULL
              AND regexp_replace(COALESCE(ei.identity_value, ''), '[^0-9]', '', 'g') = :iin
            ORDER BY ei.employee_id
            """
        ),
        {"iin": iin_digits},
    ).fetchall()
    return [int(row[0]) for row in rows if row and row[0]]


def _lookup_employees_by_full_name(conn: Connection, full_name: str) -> list[int]:
    norm_name = _norm_name(full_name)
    rows = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE lower(replace(trim(full_name), 'ё', 'е')) = :norm_name
            ORDER BY employee_id
            """
        ),
        {"norm_name": norm_name},
    ).fetchall()
    return [int(row[0]) for row in rows if row and row[0]]


def resolve_employee_binding(
    conn: Connection,
    *,
    row_employee_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
) -> EmployeeBindingResult:
    """Resolve directory employee from staging row link or import payload (IIN, then FIO)."""
    if row_employee_id:
        return EmployeeBindingResult(
            employee_id=int(row_employee_id),
            status=BINDING_STATUS_BOUND,
            method=BINDING_METHOD_ROW_LINK,
        )

    if not payload:
        return EmployeeBindingResult(
            employee_id=None,
            status=BINDING_STATUS_UNBOUND,
            reason="Нет данных для сопоставления (ИИН/ФИО)",
        )

    iin_digits = _digits_only(str(payload.get("iin", "") or ""))
    if len(iin_digits) == 12:
        employee_ids = _lookup_employees_by_iin(conn, iin_digits)
        if len(employee_ids) > 1:
            return EmployeeBindingResult(
                employee_id=None,
                status=BINDING_STATUS_CONFLICT,
                method=BINDING_METHOD_IIN,
                reason=f"ИИН {iin_digits}: найдено несколько сотрудников ({len(employee_ids)})",
                candidate_employee_ids=employee_ids,
            )
        if len(employee_ids) == 1:
            return EmployeeBindingResult(
                employee_id=employee_ids[0],
                status=BINDING_STATUS_BOUND,
                method=BINDING_METHOD_IIN,
            )

    full_name = str(payload.get("full_name", "") or "").strip()
    if not full_name:
        if len(iin_digits) == 12:
            return EmployeeBindingResult(
                employee_id=None,
                status=BINDING_STATUS_UNBOUND,
                method=BINDING_METHOD_IIN,
                reason="Сотрудник с указанным ИИН не найден в справочнике",
            )
        return EmployeeBindingResult(
            employee_id=None,
            status=BINDING_STATUS_UNBOUND,
            reason="Не указаны ИИН и ФИО для сопоставления",
        )

    employee_ids = _lookup_employees_by_full_name(conn, full_name)
    if len(employee_ids) > 1:
        return EmployeeBindingResult(
            employee_id=None,
            status=BINDING_STATUS_CONFLICT,
            method=BINDING_METHOD_FULL_NAME,
            reason=f"ФИО «{full_name}»: найдено несколько сотрудников ({len(employee_ids)})",
            candidate_employee_ids=employee_ids,
        )
    if len(employee_ids) == 1:
        return EmployeeBindingResult(
            employee_id=employee_ids[0],
            status=BINDING_STATUS_BOUND,
            method=BINDING_METHOD_FULL_NAME,
        )

    if len(iin_digits) == 12:
        return EmployeeBindingResult(
            employee_id=None,
            status=BINDING_STATUS_UNBOUND,
            method=BINDING_METHOD_IIN,
            reason="Сотрудник с указанным ИИН не найден в справочнике",
        )
    return EmployeeBindingResult(
        employee_id=None,
        status=BINDING_STATUS_UNBOUND,
        method=BINDING_METHOD_FULL_NAME,
        reason=f"Сотрудник «{full_name}» не найден в справочнике",
    )


def _binding_metadata_patch(
    payload: dict[str, Any],
    binding: EmployeeBindingResult,
) -> dict[str, Any]:
    updated = dict(payload)
    metadata = dict(updated.get("metadata") or {})
    metadata["employee_binding_status"] = binding.status
    metadata["employee_binding_method"] = binding.method
    metadata["employee_binding_reason"] = binding.reason
    metadata["employee_binding_candidate_ids"] = binding.candidate_employee_ids or None
    updated["metadata"] = metadata
    return updated


def _match_status_for_binding(binding: EmployeeBindingResult) -> str:
    if binding.status == BINDING_STATUS_BOUND:
        return MATCH_STATUS_AUTO
    if binding.status == BINDING_STATUS_CONFLICT:
        return MATCH_STATUS_REVIEW
    return MATCH_STATUS_NO_MATCH


def _load_import_row(conn: Connection, row_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT row_id, batch_id, employee_id, normalized_payload, match_status
            FROM public.hr_import_rows
            WHERE row_id = :row_id
            """
        ),
        {"row_id": row_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def _employee_exists(conn: Connection, employee_id: int) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM public.employees WHERE employee_id = :employee_id"),
        {"employee_id": employee_id},
    ).first()
    return row is not None


def persist_row_binding_metadata(
    conn: Connection,
    row_id: int,
    binding: EmployeeBindingResult,
) -> None:
    """Store binding status/method/reason in row normalized_payload metadata."""
    row = _load_import_row(conn, row_id)
    if row is None:
        raise ValueError(f"import row {row_id} not found")
    payload = _parse_payload(row["normalized_payload"])
    payload = _binding_metadata_patch(payload, binding)
    match_status = _match_status_for_binding(binding)
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET
                match_status = :match_status,
                normalized_payload = CAST(:normalized_payload AS JSONB)
            WHERE row_id = :row_id
            """
        ),
        {
            "row_id": row_id,
            "match_status": match_status,
            "normalized_payload": json.dumps(payload, ensure_ascii=False),
        },
    )


def persist_row_employee_binding(
    conn: Connection,
    row_id: int,
    binding: EmployeeBindingResult,
    *,
    force: bool = False,
) -> EmployeeBindingResult:
    """Persist employee_id on hr_import_rows and propagate to rebuildable normalized records."""
    row = _load_import_row(conn, row_id)
    if row is None:
        raise ValueError(f"import row {row_id} not found")

    if binding.status != BINDING_STATUS_BOUND or binding.employee_id is None:
        if not force:
            persist_row_binding_metadata(conn, row_id, binding)
            return binding
        raise ValueError("cannot persist binding without a resolved employee_id")

    payload = _parse_payload(row["normalized_payload"])
    payload = _binding_metadata_patch(payload, binding)
    match_status = _match_status_for_binding(binding)

    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET
                employee_id = :employee_id,
                match_status = :match_status,
                normalized_payload = CAST(:normalized_payload AS JSONB)
            WHERE row_id = :row_id
            """
        ),
        {
            "row_id": row_id,
            "employee_id": int(binding.employee_id),
            "match_status": match_status,
            "normalized_payload": json.dumps(payload, ensure_ascii=False),
        },
    )
    propagate_employee_id_to_normalized_records(conn, row_id, int(binding.employee_id))
    return binding


def _find_open_record_by_employee_source_key(
    conn: Connection,
    *,
    employee_id: int,
    source_record_key: str,
    exclude_record_id: Optional[int] = None,
) -> Optional[int]:
    params: dict[str, Any] = {
        "employee_id": int(employee_id),
        "source_record_key": source_record_key,
        "statuses": list(OPEN_EMPLOYEE_DEDUP_STATUSES),
    }
    exclude_sql = ""
    if exclude_record_id is not None:
        exclude_sql = "AND normalized_record_id <> :exclude_record_id"
        params["exclude_record_id"] = int(exclude_record_id)
    row = conn.execute(
        text(
            f"""
            SELECT normalized_record_id
            FROM public.hr_import_normalized_records
            WHERE employee_id = :employee_id
              AND source_record_key = :source_record_key
              AND promoted_document_id IS NULL
              AND review_status = ANY(:statuses)
              {exclude_sql}
            ORDER BY normalized_record_id
            LIMIT 1
            """
        ),
        params,
    ).scalar_one_or_none()
    return int(row) if row is not None else None


def _supersede_normalized_record(
    conn: Connection,
    record_id: int,
    *,
    reason: str,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.hr_import_normalized_records
            SET
                review_status = :review_status,
                review_notes = COALESCE(review_notes, '') || CASE
                    WHEN COALESCE(review_notes, '') = '' THEN :reason
                    ELSE E'\n' || :reason
                END,
                updated_at = NOW()
            WHERE normalized_record_id = :record_id
              AND promoted_document_id IS NULL
              AND review_status = ANY(:open_statuses)
            """
        ),
        {
            "record_id": int(record_id),
            "review_status": REVIEW_STATUS_SUPERSEDED,
            "reason": reason,
            "open_statuses": list(OPEN_EMPLOYEE_DEDUP_STATUSES),
        },
    )


def propagate_employee_id_to_normalized_records(
    conn: Connection,
    row_id: int,
    employee_id: int,
) -> dict[str, int]:
    """Update employee_id and recompute source_record_key for rebuildable normalized records."""
    rows = conn.execute(
        text(
            """
            SELECT
                normalized_record_id,
                record_kind,
                title,
                issue_date,
                end_date,
                hours,
                document_number,
                source_field,
                fragment_index
            FROM public.hr_import_normalized_records
            WHERE row_id = :row_id
              AND promoted_document_id IS NULL
              AND review_status = ANY(:statuses)
            ORDER BY normalized_record_id
            """
        ),
        {"row_id": row_id, "statuses": list(REBUILDABLE_REVIEW_STATUSES)},
    ).mappings().all()

    updated = 0
    superseded = 0
    skipped = 0
    assigned_keys: set[tuple[int, str]] = set()

    for record in rows:
        record_id = int(record["normalized_record_id"])
        new_key = compute_source_record_key(
            row_id=row_id,
            employee_id=employee_id,
            record_kind=str(record["record_kind"]),
            title=str(record.get("title") or ""),
            issue_date=record.get("issue_date"),
            end_date=record.get("end_date"),
            hours=int(record["hours"]) if record.get("hours") is not None else None,
            document_number=str(record.get("document_number") or ""),
            source_field=str(record.get("source_field") or ""),
            fragment_index=int(record.get("fragment_index") or 0),
        )
        open_key = (employee_id, new_key)
        if open_key in assigned_keys:
            _supersede_normalized_record(
                conn,
                record_id,
                reason="[binding] duplicate source_record_key within import row",
            )
            superseded += 1
            continue

        existing_id = _find_open_record_by_employee_source_key(
            conn,
            employee_id=employee_id,
            source_record_key=new_key,
            exclude_record_id=record_id,
        )
        if existing_id is not None:
            _supersede_normalized_record(
                conn,
                record_id,
                reason=f"[binding] duplicate of normalized_record_id={existing_id}",
            )
            superseded += 1
            continue

        try:
            result = conn.execute(
                text(
                    """
                    UPDATE public.hr_import_normalized_records
                    SET
                        employee_id = :employee_id,
                        source_record_key = :source_record_key,
                        updated_at = NOW()
                    WHERE normalized_record_id = :record_id
                      AND promoted_document_id IS NULL
                      AND review_status = ANY(:open_statuses)
                    """
                ),
                {
                    "record_id": record_id,
                    "employee_id": employee_id,
                    "source_record_key": new_key,
                    "open_statuses": list(OPEN_EMPLOYEE_DEDUP_STATUSES),
                },
            )
            if int(result.rowcount or 0) == 0:
                skipped += 1
                continue
        except IntegrityError as exc:
            if "uq_hinr_employee_source_key_open" not in str(exc):
                raise
            existing_id = _find_open_record_by_employee_source_key(
                conn,
                employee_id=employee_id,
                source_record_key=new_key,
                exclude_record_id=record_id,
            )
            if existing_id is not None:
                _supersede_normalized_record(
                    conn,
                    record_id,
                    reason=f"[binding] duplicate of normalized_record_id={existing_id}",
                )
                superseded += 1
            else:
                skipped += 1
            continue

        assigned_keys.add(open_key)
        updated += 1

    return {"updated": updated, "superseded": superseded, "skipped": skipped}


def auto_bind_import_row(conn: Connection, row_id: int) -> EmployeeBindingResult:
    """Try to auto-bind an import row; persist when a unique match is found."""
    row = _load_import_row(conn, row_id)
    if row is None:
        raise ValueError(f"import row {row_id} not found")

    row_employee_id = int(row["employee_id"]) if row.get("employee_id") else None
    payload = _parse_payload(row["normalized_payload"])
    binding = resolve_employee_binding(
        conn,
        row_employee_id=row_employee_id,
        payload=payload,
    )

    if row_employee_id is not None:
        propagate_employee_id_to_normalized_records(conn, row_id, row_employee_id)
        return binding

    if binding.status == BINDING_STATUS_BOUND and binding.employee_id is not None:
        persist_row_employee_binding(conn, row_id, binding)
    else:
        persist_row_binding_metadata(conn, row_id, binding)

    return binding


def _sum_propagate_stats(stats: dict[str, int]) -> int:
    return int(stats.get("updated") or 0)


def repair_batch_employee_bindings(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Backfill/repair employee bindings for all rows in a batch."""
    dedupe_result = dedupe_open_normalized_records(conn, batch_id=batch_id)
    rows = conn.execute(
        text(
            """
            SELECT row_id, employee_id
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    summary = {
        "batch_id": batch_id,
        "rows_processed": 0,
        "bound": 0,
        "already_bound": 0,
        "unbound": 0,
        "conflict": 0,
        "normalized_records_updated": 0,
        "normalized_records_superseded": 0,
        "dedupe": dedupe_result,
        "items": [],
    }

    for row in rows:
        row_id = int(row["row_id"])
        summary["rows_processed"] += 1
        if row.get("employee_id"):
            stats = propagate_employee_id_to_normalized_records(conn, row_id, int(row["employee_id"]))
            summary["normalized_records_updated"] += _sum_propagate_stats(stats)
            summary["normalized_records_superseded"] += int(stats.get("superseded") or 0)
            summary["already_bound"] += 1
            summary["items"].append(
                {
                    "row_id": row_id,
                    "status": BINDING_STATUS_BOUND,
                    "method": BINDING_METHOD_ROW_LINK,
                    "employee_id": int(row["employee_id"]),
                    "normalized_records_updated": _sum_propagate_stats(stats),
                    "normalized_records_superseded": int(stats.get("superseded") or 0),
                }
            )
            continue

        binding = auto_bind_import_row(conn, row_id)
        item = {"row_id": row_id, **binding.to_dict()}
        if binding.status == BINDING_STATUS_BOUND:
            summary["bound"] += 1
            stats = propagate_employee_id_to_normalized_records(
                conn, row_id, int(binding.employee_id)  # type: ignore[arg-type]
            )
            item["normalized_records_updated"] = _sum_propagate_stats(stats)
            item["normalized_records_superseded"] = int(stats.get("superseded") or 0)
            summary["normalized_records_updated"] += item["normalized_records_updated"]
            summary["normalized_records_superseded"] += item["normalized_records_superseded"]
        elif binding.status == BINDING_STATUS_CONFLICT:
            summary["conflict"] += 1
        else:
            summary["unbound"] += 1
        summary["items"].append(item)

    post_dedupe = dedupe_open_normalized_records(conn, batch_id=batch_id)
    summary["post_bind_dedupe"] = post_dedupe
    return summary


class NormalizedRecordNotFoundError(Exception):
    def __init__(self, record_id: int) -> None:
        self.record_id = record_id
        super().__init__(f"Normalized record {record_id} not found")


class EmployeeBindingNotAllowedError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def bind_normalized_record_to_employee(
    conn: Connection,
    record_id: int,
    *,
    employee_id: int,
    bound_by: int,
) -> int:
    """Manually bind a normalized record (via its import row) to a directory employee. Returns row_id."""
    row = conn.execute(
        text(
            """
            SELECT nr.normalized_record_id, nr.row_id, nr.batch_id, nr.review_status
            FROM public.hr_import_normalized_records nr
            WHERE nr.normalized_record_id = :record_id
            """
        ),
        {"record_id": record_id},
    ).mappings().first()
    if row is None:
        raise NormalizedRecordNotFoundError(record_id)

    if str(row.get("review_status")) == "promoted":
        raise EmployeeBindingNotAllowedError("cannot rebind a promoted normalized record")

    if not _employee_exists(conn, employee_id):
        raise ValueError(f"employee {employee_id} not found")

    dedupe_open_normalized_records(conn, batch_id=int(row["batch_id"]))

    row_id = int(row["row_id"])
    binding = EmployeeBindingResult(
        employee_id=int(employee_id),
        status=BINDING_STATUS_BOUND,
        method=BINDING_METHOD_MANUAL,
        reason=f"Ручная привязка пользователем {bound_by}",
    )
    persist_row_employee_binding(conn, row_id, binding, force=True)
    return row_id


def binding_info_for_row(
    conn: Connection,
    *,
    row_employee_id: Optional[int],
    payload: Optional[dict[str, Any]],
    directory_employee_name: Optional[str] = None,
) -> dict[str, Any]:
    """Binding status for API serialization."""
    if row_employee_id:
        metadata = dict((payload or {}).get("metadata") or {})
        method = metadata.get("employee_binding_method") or BINDING_METHOD_ROW_LINK
        reason = metadata.get("employee_binding_reason")
        return {
            "status": BINDING_STATUS_BOUND,
            "method": method,
            "reason": reason,
            "employee_id": int(row_employee_id),
            "directory_employee_name": directory_employee_name,
            "candidate_employee_ids": [],
        }

    metadata = dict((payload or {}).get("metadata") or {})
    stored_status = str(metadata.get("employee_binding_status") or "").strip().lower()
    if stored_status in {BINDING_STATUS_UNBOUND, BINDING_STATUS_CONFLICT}:
        candidates = metadata.get("employee_binding_candidate_ids") or []
        return {
            "status": stored_status,
            "method": metadata.get("employee_binding_method"),
            "reason": metadata.get("employee_binding_reason"),
            "employee_id": None,
            "directory_employee_name": directory_employee_name,
            "candidate_employee_ids": [int(x) for x in candidates if x is not None],
        }

    binding = resolve_employee_binding(conn, payload=payload)
    return {
        "status": binding.status,
        "method": binding.method,
        "reason": binding.reason,
        "employee_id": binding.employee_id,
        "directory_employee_name": directory_employee_name,
        "candidate_employee_ids": binding.candidate_employee_ids,
    }

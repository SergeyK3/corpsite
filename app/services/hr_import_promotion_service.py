"""ADR-039 Phase 3F — promote staging normalized records to employee_documents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_normalized_record_service import (
    RECORD_KIND_CATEGORY,
    RECORD_KIND_CERTIFICATE,
    RECORD_KIND_TRAINING,
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_PROMOTED,
    merge_review_override,
    normalized_records_available,
)

OUTCOME_PROMOTED = "promoted"
OUTCOME_WOULD_PROMOTE = "would_promote"
OUTCOME_SKIPPED = "skipped"
OUTCOME_WOULD_SKIP = "would_skip"
OUTCOME_FAILED = "failed"
OUTCOME_WOULD_FAIL = "would_fail"

BLOCKER_NOT_APPROVED = "NOT_APPROVED"
BLOCKER_EMPLOYEE_REQUIRED = "EMPLOYEE_REQUIRED"
BLOCKER_DOCUMENT_TYPE_UNRESOLVED = "DOCUMENT_TYPE_UNRESOLVED"
BLOCKER_MEDICAL_SPECIALTY_UNRESOLVED = "MEDICAL_SPECIALTY_UNRESOLVED"
BLOCKER_VALIDATION_MISSING_VALID_UNTIL = "VALIDATION_MISSING_VALID_UNTIL"
BLOCKER_VALIDATION_MISSING_HOURS_OR_ISSUED_AT = "VALIDATION_MISSING_HOURS_OR_ISSUED_AT"

SKIP_ALREADY_PROMOTED = "ALREADY_PROMOTED"
SKIP_DUPLICATE_ACTIVE_DOCUMENT = "DUPLICATE_ACTIVE_DOCUMENT"

PARSE_METHOD_IMPORT_PROMOTED = "import_promoted"
VERIFICATION_STATUS_UNVERIFIED = "UNVERIFIED"
LIFECYCLE_ACTIVE = "ACTIVE"


class PromotionRequestError(Exception):
    """Invalid promotion request parameters."""


@dataclass
class PromotionBlocker:
    code: str
    message: str
    field: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field is not None:
            payload["field"] = self.field
        return payload


@dataclass
class PromotionItemResult:
    record_id: int
    normalized_record_id: int
    record_kind: str
    employee_id: Optional[int]
    outcome: str
    document_id: Optional[int] = None
    reason: Optional[str] = None
    blockers: list[PromotionBlocker] = field(default_factory=list)
    preview: Optional[dict[str, Any]] = None
    resolved_document_type_code: Optional[str] = None
    resolved_medical_specialty_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "record_id": self.record_id,
            "normalized_record_id": self.normalized_record_id,
            "record_kind": self.record_kind,
            "employee_id": self.employee_id,
            "outcome": self.outcome,
        }
        if self.document_id is not None:
            payload["document_id"] = self.document_id
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.blockers:
            payload["blockers"] = [blocker.to_dict() for blocker in self.blockers]
        if self.preview is not None:
            payload["preview"] = self.preview
        if self.resolved_document_type_code is not None:
            payload["resolved_document_type_code"] = self.resolved_document_type_code
        if self.resolved_medical_specialty_id is not None:
            payload["resolved_medical_specialty_id"] = self.resolved_medical_specialty_id
        return payload


@dataclass
class _PromotionInsertPlan:
    document_type_id: int
    medical_specialty_id: Optional[int]
    issue_date: Optional[date]
    expiry_date: Optional[date]
    hours_int: Optional[int]
    document_type_code: str


def _norm_specialty(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("ё", "е").split())


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text_val = str(value).strip()
    if not text_val:
        return None
    try:
        return date.fromisoformat(text_val[:10])
    except ValueError:
        return None


def _fetch_normalized_record_row(conn: Connection, record_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.hr_import_normalized_records
            WHERE normalized_record_id = :record_id
            """
        ),
        {"record_id": int(record_id)},
    ).mappings().first()
    return dict(row) if row is not None else None


def _load_document_type(conn: Connection, document_type_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                document_type_id,
                code,
                name,
                has_valid_until,
                requires_medical_specialty,
                tracks_hours,
                is_active
            FROM public.document_types
            WHERE document_type_id = :document_type_id
            """
        ),
        {"document_type_id": int(document_type_id)},
    ).mappings().first()
    return dict(row) if row is not None else None


def _lookup_document_type_id_by_code(conn: Connection, code: str) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT document_type_id
            FROM public.document_types
            WHERE code = :code
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"code": str(code).strip()},
    ).first()
    return int(row[0]) if row is not None else None


def resolve_document_type(conn: Connection, row: dict[str, Any]) -> tuple[Optional[int], Optional[str]]:
    document_type_id = row.get("document_type_id")
    document_type_code = row.get("document_type_code")
    if document_type_id is not None:
        doc_type = _load_document_type(conn, int(document_type_id))
        if doc_type and bool(doc_type.get("is_active")):
            return int(document_type_id), str(doc_type["code"])
    if document_type_code:
        looked_up = _lookup_document_type_id_by_code(conn, str(document_type_code))
        if looked_up is not None:
            return looked_up, str(document_type_code).strip()
    return None, str(document_type_code).strip() if document_type_code else None


def resolve_medical_specialty_id(
    conn: Connection,
    *,
    specialty_text: Optional[str],
    existing_id: Optional[int],
) -> Optional[int]:
    """Exact-only specialty resolution (no fuzzy matching)."""
    if existing_id is not None:
        row = conn.execute(
            text(
                """
                SELECT medical_specialty_id
                FROM public.medical_specialties
                WHERE medical_specialty_id = :medical_specialty_id
                  AND is_active = TRUE
                """
            ),
            {"medical_specialty_id": int(existing_id)},
        ).first()
        return int(existing_id) if row is not None else None

    raw = (specialty_text or "").strip()
    if not raw:
        return None

    norm = _norm_specialty(raw)
    rows = conn.execute(
        text(
            """
            SELECT medical_specialty_id
            FROM public.medical_specialties
            WHERE is_active = TRUE
              AND (
                    lower(trim(replace(name, 'ё', 'е'))) = :norm_name
                 OR upper(trim(:raw_text)) = code
              )
            """
        ),
        {"norm_name": norm, "raw_text": raw},
    ).all()
    if len(rows) == 1:
        return int(rows[0][0])
    return None


def _find_active_duplicate_document_id(
    conn: Connection,
    *,
    employee_id: int,
    source_record_key: str,
) -> Optional[int]:
    row = conn.execute(
        text(
            """
            SELECT document_id
            FROM public.employee_documents
            WHERE employee_id = :employee_id
              AND source_record_key = :source_record_key
              AND lifecycle_status = 'ACTIVE'
            LIMIT 1
            """
        ),
        {
            "employee_id": int(employee_id),
            "source_record_key": str(source_record_key),
        },
    ).first()
    return int(row[0]) if row is not None else None


def _isoformat_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _specialty_required_for_promotion(record_kind: str, doc_type: dict[str, Any]) -> bool:
    """Certificates keep ADR-037 specialty FK rules; category/training import rows do not."""
    if record_kind in (RECORD_KIND_CATEGORY, RECORD_KIND_TRAINING):
        return False
    if record_kind == RECORD_KIND_CERTIFICATE:
        return bool(doc_type.get("requires_medical_specialty"))
    return bool(doc_type.get("requires_medical_specialty"))


def _resolve_optional_medical_specialty_id(
    conn: Connection,
    row: dict[str, Any],
) -> Optional[int]:
    return resolve_medical_specialty_id(
        conn,
        specialty_text=str(row.get("specialty_text") or ""),
        existing_id=int(row["medical_specialty_id"])
        if row.get("medical_specialty_id") is not None
        else None,
    )


def _map_titles(row: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    title_val = row.get("title")
    title = str(title_val).strip() if title_val else None
    if row.get("record_kind") == RECORD_KIND_TRAINING:
        return None, title
    if row.get("record_kind") == RECORD_KIND_CATEGORY:
        specialty = str(row.get("specialty_text") or "").strip()
        if title and specialty and specialty.lower() not in title.lower():
            title = f"{title} — {specialty}"
        elif not title and specialty:
            title = specialty
    return title, None


def _build_preview_payload(
    *,
    row: dict[str, Any],
    document_type_code: str,
    medical_specialty_id: Optional[int],
) -> dict[str, Any]:
    title, training_title = _map_titles(row)
    return {
        "document_type_code": document_type_code,
        "medical_specialty_id": medical_specialty_id,
        "title": title,
        "training_title": training_title,
        "issued_by": row.get("provider"),
        "issued_at": _isoformat_or_none(row.get("issue_date")),
        "end_date": _isoformat_or_none(row.get("end_date")),
        "valid_until": _isoformat_or_none(row.get("expiry_date")),
        "hours": row.get("hours"),
        "document_number": row.get("document_number"),
        "file_url": row.get("file_url"),
        "source_record_key": row.get("source_record_key"),
    }


def _base_item(row: dict[str, Any]) -> tuple[int, str, Optional[int]]:
    record_id = int(row["normalized_record_id"])
    employee_id = int(row["employee_id"]) if row.get("employee_id") is not None else None
    return record_id, str(row.get("record_kind") or ""), employee_id


def evaluate_promotion(
    conn: Connection,
    row: dict[str, Any],
    *,
    dry_run: bool,
) -> tuple[PromotionItemResult, Optional[_PromotionInsertPlan]]:
    record_id, record_kind, employee_id = _base_item(row)
    fail_outcome = OUTCOME_WOULD_FAIL if dry_run else OUTCOME_FAILED
    skip_outcome = OUTCOME_WOULD_SKIP if dry_run else OUTCOME_SKIPPED

    if row.get("promoted_document_id") is not None or str(row.get("review_status")) == REVIEW_STATUS_PROMOTED:
        return (
            PromotionItemResult(
                record_id=record_id,
                normalized_record_id=record_id,
                record_kind=record_kind,
                employee_id=employee_id,
                outcome=skip_outcome,
                reason=SKIP_ALREADY_PROMOTED,
                document_id=int(row["promoted_document_id"])
                if row.get("promoted_document_id") is not None
                else None,
            ),
            None,
        )

    if str(row.get("review_status")) != REVIEW_STATUS_APPROVED:
        return (
            PromotionItemResult(
                record_id=record_id,
                normalized_record_id=record_id,
                record_kind=record_kind,
                employee_id=employee_id,
                outcome=fail_outcome,
                blockers=[
                    PromotionBlocker(
                        code=BLOCKER_NOT_APPROVED,
                        message="Only approved normalized records can be promoted",
                        field="review_status",
                    )
                ],
            ),
            None,
        )

    if employee_id is None:
        return (
            PromotionItemResult(
                record_id=record_id,
                normalized_record_id=record_id,
                record_kind=record_kind,
                employee_id=None,
                outcome=fail_outcome,
                blockers=[
                    PromotionBlocker(
                        code=BLOCKER_EMPLOYEE_REQUIRED,
                        message="employee_id is required for promotion",
                        field="employee_id",
                    )
                ],
            ),
            None,
        )

    document_type_id, document_type_code = resolve_document_type(conn, row)
    if document_type_id is None or not document_type_code:
        return (
            PromotionItemResult(
                record_id=record_id,
                normalized_record_id=record_id,
                record_kind=record_kind,
                employee_id=employee_id,
                outcome=fail_outcome,
                blockers=[
                    PromotionBlocker(
                        code=BLOCKER_DOCUMENT_TYPE_UNRESOLVED,
                        message="document_type_id could not be resolved",
                        field="document_type_id",
                    )
                ],
            ),
            None,
        )

    doc_type = _load_document_type(conn, document_type_id)
    if doc_type is None or not bool(doc_type.get("is_active")):
        return (
            PromotionItemResult(
                record_id=record_id,
                normalized_record_id=record_id,
                record_kind=record_kind,
                employee_id=employee_id,
                outcome=fail_outcome,
                blockers=[
                    PromotionBlocker(
                        code=BLOCKER_DOCUMENT_TYPE_UNRESOLVED,
                        message="document type is missing or inactive",
                        field="document_type_id",
                    )
                ],
            ),
            None,
        )

    if _specialty_required_for_promotion(record_kind, doc_type):
        medical_specialty_id = _resolve_optional_medical_specialty_id(conn, row)
        if medical_specialty_id is None:
            return (
                PromotionItemResult(
                    record_id=record_id,
                    normalized_record_id=record_id,
                    record_kind=record_kind,
                    employee_id=employee_id,
                    outcome=fail_outcome,
                    blockers=[
                        PromotionBlocker(
                            code=BLOCKER_MEDICAL_SPECIALTY_UNRESOLVED,
                            message="medical_specialty_id could not be determined",
                            field="medical_specialty_id",
                        )
                    ],
                ),
                None,
            )
    else:
        medical_specialty_id = _resolve_optional_medical_specialty_id(conn, row)

    issue_date = _coerce_date(row.get("issue_date"))
    expiry_date = _coerce_date(row.get("expiry_date"))
    hours = row.get("hours")
    hours_int: Optional[int]
    if hours is None:
        hours_int = None
    else:
        hours_int = int(hours)

    if bool(doc_type.get("has_valid_until")) and expiry_date is None:
        return (
            PromotionItemResult(
                record_id=record_id,
                normalized_record_id=record_id,
                record_kind=record_kind,
                employee_id=employee_id,
                outcome=fail_outcome,
                blockers=[
                    PromotionBlocker(
                        code=BLOCKER_VALIDATION_MISSING_VALID_UNTIL,
                        message="valid_until is required for this document type",
                        field="expiry_date",
                    )
                ],
            ),
            None,
        )

    if bool(doc_type.get("tracks_hours")):
        if issue_date is None or hours_int is None or hours_int <= 0:
            return (
                PromotionItemResult(
                    record_id=record_id,
                    normalized_record_id=record_id,
                    record_kind=record_kind,
                    employee_id=employee_id,
                    outcome=fail_outcome,
                    blockers=[
                        PromotionBlocker(
                            code=BLOCKER_VALIDATION_MISSING_HOURS_OR_ISSUED_AT,
                            message="issued_at and hours > 0 are required for this document type",
                            field="issue_date" if issue_date is None else "hours",
                        )
                    ],
                ),
                None,
            )

    preview = _build_preview_payload(
        row=row,
        document_type_code=str(doc_type["code"]),
        medical_specialty_id=medical_specialty_id,
    )
    source_record_key = str(row.get("source_record_key") or "").strip()
    duplicate_document_id = _find_active_duplicate_document_id(
        conn,
        employee_id=employee_id,
        source_record_key=source_record_key,
    )
    if duplicate_document_id is not None:
        return (
            PromotionItemResult(
                record_id=record_id,
                normalized_record_id=record_id,
                record_kind=record_kind,
                employee_id=employee_id,
                outcome=skip_outcome,
                reason=SKIP_DUPLICATE_ACTIVE_DOCUMENT,
                document_id=duplicate_document_id,
                resolved_document_type_code=str(doc_type["code"]),
                resolved_medical_specialty_id=medical_specialty_id,
                preview=preview,
            ),
            None,
        )

    success_outcome = OUTCOME_WOULD_PROMOTE if dry_run else OUTCOME_PROMOTED
    plan = _PromotionInsertPlan(
        document_type_id=int(document_type_id),
        medical_specialty_id=medical_specialty_id,
        issue_date=issue_date,
        expiry_date=expiry_date,
        hours_int=hours_int,
        document_type_code=str(doc_type["code"]),
    )
    return (
        PromotionItemResult(
            record_id=record_id,
            normalized_record_id=record_id,
            record_kind=record_kind,
            employee_id=employee_id,
            outcome=success_outcome,
            resolved_document_type_code=plan.document_type_code,
            resolved_medical_specialty_id=medical_specialty_id,
            preview=preview,
        ),
        plan,
    )


def _insert_promoted_document(
    conn: Connection,
    *,
    row: dict[str, Any],
    promoted_by: int,
    plan: _PromotionInsertPlan,
) -> int:
    title, training_title = _map_titles(row)
    confidence = row.get("confidence")
    parse_confidence: Optional[float]
    if isinstance(confidence, Decimal):
        parse_confidence = float(confidence)
    elif confidence is None:
        parse_confidence = None
    else:
        parse_confidence = float(confidence)

    parse_method = str(row.get("parse_method") or PARSE_METHOD_IMPORT_PROMOTED)
    end_date = _coerce_date(row.get("end_date"))

    inserted = conn.execute(
        text(
            """
            INSERT INTO public.employee_documents (
                employee_id,
                document_type_id,
                medical_specialty_id,
                title,
                training_title,
                document_number,
                issued_by,
                issued_at,
                end_date,
                hours,
                valid_until,
                file_url,
                lifecycle_status,
                created_by,
                source_batch_id,
                source_row_id,
                source_normalized_record_id,
                source_record_key,
                source_text,
                parse_method,
                parse_confidence,
                verification_status
            )
            VALUES (
                :employee_id,
                :document_type_id,
                :medical_specialty_id,
                :title,
                :training_title,
                :document_number,
                :issued_by,
                :issued_at,
                :end_date,
                :hours,
                :valid_until,
                :file_url,
                :lifecycle_status,
                :created_by,
                :source_batch_id,
                :source_row_id,
                :source_normalized_record_id,
                :source_record_key,
                :source_text,
                :parse_method,
                :parse_confidence,
                :verification_status
            )
            RETURNING document_id
            """
        ),
        {
            "employee_id": int(row["employee_id"]),
            "document_type_id": plan.document_type_id,
            "medical_specialty_id": plan.medical_specialty_id,
            "title": title,
            "training_title": training_title,
            "document_number": row.get("document_number"),
            "issued_by": row.get("provider"),
            "issued_at": plan.issue_date,
            "end_date": end_date,
            "hours": plan.hours_int,
            "valid_until": plan.expiry_date,
            "file_url": row.get("file_url"),
            "lifecycle_status": LIFECYCLE_ACTIVE,
            "created_by": int(promoted_by),
            "source_batch_id": int(row["batch_id"]),
            "source_row_id": int(row["row_id"]),
            "source_normalized_record_id": int(row["normalized_record_id"]),
            "source_record_key": str(row.get("source_record_key") or ""),
            "source_text": row.get("source_text"),
            "parse_method": parse_method,
            "parse_confidence": parse_confidence,
            "verification_status": VERIFICATION_STATUS_UNVERIFIED,
        },
    ).mappings().first()
    return int(inserted["document_id"])


def _mark_record_promoted(
    conn: Connection,
    *,
    record_id: int,
    document_id: int,
    promoted_by: int,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.hr_import_normalized_records
            SET
                review_status = :review_status,
                promoted_document_id = :document_id,
                promoted_at = NOW(),
                promoted_by = :promoted_by,
                updated_at = NOW()
            WHERE normalized_record_id = :record_id
            """
        ),
        {
            "record_id": int(record_id),
            "document_id": int(document_id),
            "promoted_by": int(promoted_by),
            "review_status": REVIEW_STATUS_PROMOTED,
        },
    )


def promote_normalized_record(
    conn: Connection,
    record_id: int,
    *,
    promoted_by: int,
    dry_run: bool = False,
) -> PromotionItemResult:
    if not normalized_records_available(conn):
        raise PromotionRequestError("hr_import_normalized_records is not available")

    row = _fetch_normalized_record_row(conn, record_id)
    if row is None:
        raise PromotionRequestError(f"normalized record not found: {record_id}")

    row = merge_review_override(row)
    item, plan = evaluate_promotion(conn, row, dry_run=dry_run)
    if dry_run or plan is None:
        return item

    document_id = _insert_promoted_document(conn, row=row, promoted_by=promoted_by, plan=plan)
    _mark_record_promoted(
        conn,
        record_id=record_id,
        document_id=document_id,
        promoted_by=promoted_by,
    )
    item.document_id = document_id
    return item


def _resolve_target_record_ids(
    conn: Connection,
    *,
    record_ids: Optional[list[int]],
    batch_id: Optional[int],
    employee_id: Optional[int],
    record_kind: Optional[str],
    review_status: Optional[str],
) -> list[int]:
    if record_ids:
        return sorted({int(record_id) for record_id in record_ids})

    if batch_id is None:
        raise PromotionRequestError("record_ids or batch_id is required")

    clauses = ["batch_id = :batch_id"]
    params: dict[str, Any] = {"batch_id": int(batch_id)}
    effective_review_status = review_status or REVIEW_STATUS_APPROVED
    clauses.append("review_status = :review_status")
    params["review_status"] = effective_review_status
    if employee_id is not None:
        clauses.append("employee_id = :employee_id")
        params["employee_id"] = int(employee_id)
    if record_kind is not None:
        clauses.append("record_kind = :record_kind")
        params["record_kind"] = str(record_kind)

    where_sql = " AND ".join(clauses)
    rows = conn.execute(
        text(
            f"""
            SELECT normalized_record_id
            FROM public.hr_import_normalized_records
            WHERE {where_sql}
            ORDER BY normalized_record_id
            """
        ),
        params,
    ).all()
    return [int(row[0]) for row in rows]


def promote_normalized_records(
    conn: Connection,
    *,
    promoted_by: int,
    dry_run: bool = False,
    record_ids: Optional[list[int]] = None,
    batch_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    record_kind: Optional[str] = None,
    review_status: Optional[str] = None,
    stop_on_first_error: bool = False,
) -> dict[str, Any]:
    if not normalized_records_available(conn):
        return {
            "dry_run": dry_run,
            "requested": 0,
            "promoted": 0,
            "would_promote": 0,
            "skipped": 0,
            "would_skip": 0,
            "failed": 0,
            "would_fail": 0,
            "items": [],
            "summary_by_blocker": {},
            "skipped_unavailable": True,
        }

    target_ids = _resolve_target_record_ids(
        conn,
        record_ids=record_ids,
        batch_id=batch_id,
        employee_id=employee_id,
        record_kind=record_kind,
        review_status=review_status,
    )

    items: list[PromotionItemResult] = []
    summary_by_blocker: dict[str, int] = {}
    counts = {
        "promoted": 0,
        "would_promote": 0,
        "skipped": 0,
        "would_skip": 0,
        "failed": 0,
        "would_fail": 0,
    }

    for record_id in target_ids:
        savepoint = conn.begin_nested()
        try:
            item = promote_normalized_record(
                conn,
                record_id,
                promoted_by=promoted_by,
                dry_run=dry_run,
            )
            savepoint.commit()
        except Exception:
            savepoint.rollback()
            raise

        items.append(item)
        if item.outcome in counts:
            counts[item.outcome] += 1
        for blocker in item.blockers:
            summary_by_blocker[blocker.code] = summary_by_blocker.get(blocker.code, 0) + 1
        if stop_on_first_error and item.outcome in {OUTCOME_FAILED, OUTCOME_WOULD_FAIL}:
            break

    result = {
        "dry_run": dry_run,
        "requested": len(target_ids),
        "promoted": counts["promoted"],
        "would_promote": counts["would_promote"],
        "skipped": counts["skipped"],
        "would_skip": counts["would_skip"],
        "failed": counts["failed"],
        "would_fail": counts["would_fail"],
        "items": [item.to_dict() for item in items],
        "summary_by_blocker": summary_by_blocker,
    }

    if not dry_run:
        effective_batch_id = batch_id
        if effective_batch_id is None and target_ids:
            batch_row = conn.execute(
                text(
                    """
                    SELECT batch_id
                    FROM public.hr_import_normalized_records
                    WHERE normalized_record_id = :record_id
                    LIMIT 1
                    """
                ),
                {"record_id": int(target_ids[0])},
            ).first()
            if batch_row:
                effective_batch_id = int(batch_row[0])
        if effective_batch_id is not None:
            from app.services.hr_canonical_snapshot_service import refresh_canonical_snapshot_after_promotion

            snapshot_result = refresh_canonical_snapshot_after_promotion(
                conn,
                int(effective_batch_id),
                promoted_by=promoted_by,
            )
            if snapshot_result is not None:
                result["canonical_snapshot"] = snapshot_result

    return result

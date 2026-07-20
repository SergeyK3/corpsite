"""Import review exception queue for complete-review gate (ADR-059 Phase 1)."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_DETECTED,
    TECHNICAL_DIFF_CHANGED,
    TECHNICAL_DIFF_CONFLICT,
    TECHNICAL_DIFF_NEW,
    TECHNICAL_DIFF_REMOVED,
)
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_CHANGED,
    DIFF_STATUS_CONFLICT,
    DIFF_STATUS_NEW,
    monthly_diff_available,
)

logger = logging.getLogger(__name__)

BLOCKER_UNRESOLVED_EXCEPTIONS = "UNRESOLVED_EXCEPTIONS"

_EMP_MATCH = re.compile(r"^emp:(\d+)$")

_MANUAL_REVIEW_TECHNICAL_CLASSES = frozenset(
    {
        TECHNICAL_DIFF_CHANGED,
        TECHNICAL_DIFF_CONFLICT,
        TECHNICAL_DIFF_NEW,
    }
)


def detected_differences_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_detected_differences'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _resolve_batch_imported_by(conn: Connection, batch_id: int) -> int:
    value = conn.execute(
        text(
            """
            SELECT imported_by
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).scalar_one_or_none()
    if value is None:
        raise ValueError(f"batch_id={batch_id} not found")
    return int(value)


def _parse_employee_id_from_match_key(match_key: str | None) -> int | None:
    if not match_key:
        return None
    matched = _EMP_MATCH.match(str(match_key).strip())
    if not matched:
        return None
    return int(matched.group(1))


def new_exception_requires_manual_review(
    conn: Connection,
    *,
    batch_id: int,
    origin_context: dict[str, Any] | None,
    entity_scope: str | None = None,
) -> bool:
    """ADR-059 NEW policy (N1): manual review only when employee binding is missing."""
    origin = origin_context or {}
    match_key = str(origin.get("match_key") or entity_scope or "").split("|", 1)[0]
    if _parse_employee_id_from_match_key(match_key) is not None:
        return False

    row_id = origin.get("row_id")
    if row_id is not None:
        employee_id = conn.execute(
            text(
                """
                SELECT employee_id
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND row_id = :row_id
                """
            ),
            {"batch_id": batch_id, "row_id": int(row_id)},
        ).scalar_one_or_none()
        if employee_id is not None:
            return False

    normalized_record_id = origin.get("normalized_record_id")
    if normalized_record_id is not None:
        employee_id = conn.execute(
            text(
                """
                SELECT COALESCE(nr.employee_id, r.employee_id) AS employee_id
                FROM public.hr_import_normalized_records nr
                LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
                WHERE nr.batch_id = :batch_id
                  AND nr.normalized_record_id = :normalized_record_id
                """
            ),
            {
                "batch_id": batch_id,
                "normalized_record_id": int(normalized_record_id),
            },
        ).scalar_one_or_none()
        if employee_id is not None:
            return False

    return True


def _difference_requires_manual_review(
    conn: Connection,
    *,
    batch_id: int,
    technical_diff_class: str | None,
    origin_context: dict[str, Any] | None,
    entity_scope: str | None,
) -> bool:
    technical = str(technical_diff_class or "")
    if technical == TECHNICAL_DIFF_REMOVED:
        return False
    if technical in {TECHNICAL_DIFF_CHANGED, TECHNICAL_DIFF_CONFLICT}:
        return True
    if technical == TECHNICAL_DIFF_NEW:
        return new_exception_requires_manual_review(
            conn,
            batch_id=batch_id,
            origin_context=origin_context,
            entity_scope=entity_scope,
        )
    return False


def _count_unresolved_detected_differences(conn: Connection, batch_id: int) -> int:
    rows = conn.execute(
        text(
            """
            SELECT
                d.technical_diff_class,
                d.origin_context,
                d.entity_scope
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
            """
        ),
        {
            "batch_id": batch_id,
            "detected": DIFFERENCE_LIFECYCLE_DETECTED,
        },
    ).mappings().all()
    count = 0
    for row in rows:
        if _difference_requires_manual_review(
            conn,
            batch_id=batch_id,
            technical_diff_class=str(row.get("technical_diff_class") or ""),
            origin_context=dict(row.get("origin_context") or {}),
            entity_scope=str(row.get("entity_scope") or ""),
        ):
            count += 1
    return count


def _count_unresolved_staging_diff_exceptions(conn: Connection, batch_id: int) -> int:
    if not monthly_diff_available(conn):
        return 0

    changed_conflict = conn.execute(
        text(
            """
            SELECT COUNT(*)::bigint
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND diff_status IN (:changed, :conflict)
            """
        ),
        {
            "batch_id": batch_id,
            "changed": DIFF_STATUS_CHANGED,
            "conflict": DIFF_STATUS_CONFLICT,
        },
    ).scalar_one()
    count = int(changed_conflict or 0)

    new_rows = int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)::bigint
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                  AND diff_status = :new_status
                  AND employee_id IS NULL
                """
            ),
            {"batch_id": batch_id, "new_status": DIFF_STATUS_NEW},
        ).scalar_one()
        or 0
    )
    count += new_rows

    row = conn.execute(
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
    if row is not None:
        count += int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_import_normalized_records nr
                    LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
                    WHERE nr.batch_id = :batch_id
                      AND nr.diff_status IN (:changed, :conflict)
                    """
                ),
                {
                    "batch_id": batch_id,
                    "changed": DIFF_STATUS_CHANGED,
                    "conflict": DIFF_STATUS_CONFLICT,
                },
            ).scalar_one()
            or 0
        )
        count += int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_import_normalized_records nr
                    LEFT JOIN public.hr_import_rows r ON r.row_id = nr.row_id
                    WHERE nr.batch_id = :batch_id
                      AND nr.diff_status = :new_status
                      AND COALESCE(nr.employee_id, r.employee_id) IS NULL
                    """
                ),
                {
                    "batch_id": batch_id,
                    "new_status": DIFF_STATUS_NEW,
                },
            ).scalar_one()
            or 0
        )

    return count


def count_unresolved_exceptions(conn: Connection, batch_id: int) -> int:
    """Count HR review work items for complete-review gate (ADR-059)."""
    if detected_differences_available(conn):
        return _count_unresolved_detected_differences(conn, batch_id)

    comparison_baseline_id = conn.execute(
        text(
            """
            SELECT comparison_baseline_id
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).scalar_one_or_none()
    if comparison_baseline_id is None:
        return 0
    return _count_unresolved_staging_diff_exceptions(conn, batch_id)


def run_post_diff_review_completion(
    conn: Connection,
    batch_id: int,
    *,
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    """After monthly diff: maybe auto-complete review (IMPORT_COMPARE hooks separately)."""
    actor = int(actor_user_id) if actor_user_id is not None else _resolve_batch_imported_by(conn, batch_id)

    from app.services.hr_import_complete_review_service import maybe_auto_complete_import_review

    return maybe_auto_complete_import_review(conn, batch_id, actor_user_id=actor)


def run_post_difference_review_completion(
    conn: Connection,
    *,
    batch_id: int,
    actor_user_id: int,
) -> dict[str, Any]:
    from app.services.hr_import_complete_review_service import maybe_auto_complete_import_review

    return maybe_auto_complete_import_review(conn, batch_id, actor_user_id=int(actor_user_id))

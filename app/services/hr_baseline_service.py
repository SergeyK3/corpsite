"""HR control-list Baseline + PublicationOrigin services."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.hr_baseline import (
    BASELINE_DELETION_HARD,
    BASELINE_DELETION_SOFT,
    BATCH_DIFF_STATUS_CURRENT,
    BATCH_DIFF_STATUS_NOT_COMPUTED,
    BATCH_DIFF_STATUS_STALE,
    SOURCE_TYPE_HR_CONTROL_LIST,
)
from app.services.hr_canonical_snapshot_service import (
    CanonicalSnapshotError,
    _serialize_json,
    dedupe_snapshot_entries,
)
from app.services.hr_import_diff_removal_decision_service import (
    collect_mrd_forming_entries_from_batch,
    count_pending_diff_removals,
)
from app.db.models.hr_import import (
    BATCH_STATUS_APPLY_PENDING,
    BATCH_STATUS_APPLIED,
    BATCH_STATUS_CANCELLED,
    BATCH_STATUS_FAILED,
    BATCH_STATUS_IN_REVIEW,
    BATCH_STATUS_PARTIALLY_APPLIED,
    BATCH_STATUS_PARSED,
    BATCH_STATUS_UPLOADED,
)
from app.services.hr_import_analytics_service import BatchNotFoundError, _ensure_batch_exists
from app.services.hr_import_control_list_storage import is_legacy_import_code
from app.services.hr_import_normalized_record_service import (
    REVIEW_STATUS_PENDING,
    normalized_records_available,
)

logger = logging.getLogger(__name__)


class BaselineNotFoundError(LookupError):
    pass


class BaselineDeleteError(RuntimeError):
    pass


class BaselineRestoreError(RuntimeError):
    pass


class BaselinePublishError(CanonicalSnapshotError):
    def __init__(self, message: str, *, blockers: Optional[list[str]] = None) -> None:
        super().__init__(message)
        self.blockers = list(blockers or [])


BASELINE_PUBLISH_ALLOWED_BATCH_STATUSES = frozenset(
    {
        BATCH_STATUS_APPLY_PENDING,
        BATCH_STATUS_APPLIED,
        BATCH_STATUS_PARTIALLY_APPLIED,
    }
)

BASELINE_PUBLISH_BLOCKED_BATCH_STATUSES = frozenset(
    {
        BATCH_STATUS_UPLOADED,
        BATCH_STATUS_PARSED,
        BATCH_STATUS_IN_REVIEW,
        BATCH_STATUS_FAILED,
        BATCH_STATUS_CANCELLED,
    }
)


def baseline_tables_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_control_list_baselines'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def publication_origin_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_publication_origins'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def assess_baseline_publish_readiness(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Return publish gate verdict for a batch (no writes)."""
    _ensure_batch_exists(conn, batch_id)
    batch = conn.execute(
        text(
            """
            SELECT batch_id, import_code, status, error_rows
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().one()
    import_code = str(batch.get("import_code") or "").strip() or f"batch {batch_id}"
    status = str(batch.get("status") or "")
    blockers: list[str] = []

    if status == BATCH_STATUS_IN_REVIEW:
        blockers.append(
            f"Импорт {import_code} ещё в Review (статус IN_REVIEW). "
            "Завершите проверку и переведите импорт в APPLY_PENDING."
        )
    elif status in BASELINE_PUBLISH_BLOCKED_BATCH_STATUSES:
        blockers.append(
            f"Импорт {import_code} имеет статус {status}. "
            "Публикация Baseline разрешена только после завершения Review "
            "(статусы APPLY_PENDING, APPLIED или PARTIALLY_APPLIED)."
        )
    elif status not in BASELINE_PUBLISH_ALLOWED_BATCH_STATUSES:
        blockers.append(
            f"Импорт {import_code} имеет неподдерживаемый статус {status} для публикации Baseline."
        )

    error_rows = int(batch.get("error_rows") or 0)
    if error_rows > 0:
        blockers.append(
            f"Импорт {import_code} содержит {error_rows} строк с ошибками парсинга. "
            "Исправьте или исключите их до публикации Baseline."
        )

    pending_normalized = 0
    if normalized_records_available(conn):
        pending_normalized = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.hr_import_normalized_records
                    WHERE batch_id = :batch_id
                      AND review_status = :pending
                    """
                ),
                {"batch_id": batch_id, "pending": REVIEW_STATUS_PENDING},
            ).scalar_one()
            or 0
        )
    if pending_normalized > 0:
        blockers.append(
            f"Импорт {import_code} содержит {pending_normalized} normalized-записей "
            "в статусе pending. Завершите Review normalized-данных."
        )

    pending_removals = count_pending_diff_removals(conn, batch_id)
    if pending_removals > 0:
        blockers.append(
            f"Импорт {import_code} содержит {pending_removals} записей, "
            "отсутствующих в файле без решения. Примите решение restore/confirm_removal."
        )

    return {
        "import_code": import_code,
        "batch_status": status,
        "publish_allowed": not blockers,
        "blockers": blockers,
    }


def assert_baseline_publish_allowed(conn: Connection, batch_id: int) -> dict[str, Any]:
    readiness = assess_baseline_publish_readiness(conn, batch_id)
    if readiness["publish_allowed"]:
        return readiness
    message = "Публикация Baseline заблокирована:\n" + "\n".join(
        f"- {item}" for item in readiness["blockers"]
    )
    raise BaselinePublishError(message, blockers=readiness["blockers"])


def _baseline_row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row)
    published_at = data.get("published_at") or data.get("promoted_at")
    published_by = data.get("published_by") if data.get("published_by") is not None else data.get("promoted_by")
    data["published_at"] = published_at
    data["published_by"] = published_by
    data["promoted_at"] = published_at
    data["promoted_by"] = published_by
    data["snapshot_id"] = int(data["baseline_id"])
    import_code = str(data.get("source_import_code") or data.get("batch_import_code") or "").strip()
    data["source_import_code"] = import_code or None
    data["is_legacy_import"] = is_legacy_import_code(import_code)
    linked_batch_id = data.get("source_batch_id") or data.get("origin_batch_id")
    data["linked_batch_id"] = int(linked_batch_id) if linked_batch_id is not None else None
    file_name = data.get("original_filename") or data.get("file_name")
    data["source_file_name"] = str(file_name).strip() if file_name else None
    if data["is_legacy_import"]:
        legacy_suffix = import_code.split("-", 1)[1] if import_code.startswith("legacy-") else str(data["baseline_id"])
        data["import_display_label"] = f"До миграции (импорт #{legacy_suffix})"
    elif import_code:
        data["import_display_label"] = import_code
    else:
        data["import_display_label"] = f"Baseline #{data['baseline_id']}"
    return data


def _resolve_batch_report_period(conn: Connection, batch_id: int) -> date:
    row = conn.execute(
        text(
            """
            SELECT COALESCE(sf.report_month, date_trunc('month', b.imported_at)::date) AS report_period
            FROM public.hr_import_batches b
            LEFT JOIN public.hr_source_files sf ON sf.source_file_id = b.source_file_id
            WHERE b.batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if row is None or row["report_period"] is None:
        raise BatchNotFoundError(batch_id)
    value = row["report_period"]
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _previous_report_period(report_period: date) -> date:
    if report_period.month == 1:
        return date(report_period.year - 1, 12, 1)
    return date(report_period.year, report_period.month - 1, 1)


def resolve_effective_baseline(conn: Connection, report_period: date) -> Optional[dict[str, Any]]:
    """Latest non-deleted baseline for a report period (max published_at)."""
    if not baseline_tables_available(conn):
        return None
    row = conn.execute(
        text(
            """
            SELECT
                bl.baseline_id,
                bl.publication_origin_id,
                bl.source_batch_id,
                bl.source_type,
                bl.report_period,
                bl.published_at,
                bl.published_by,
                bl.entry_count,
                bl.deleted_at,
                po.source_import_code,
                po.published_at AS origin_published_at
            FROM public.hr_control_list_baselines bl
            LEFT JOIN public.hr_publication_origins po
                ON po.publication_origin_id = bl.publication_origin_id
            WHERE bl.report_period = :report_period
              AND bl.deleted_at IS NULL
            ORDER BY bl.published_at DESC, bl.baseline_id DESC
            LIMIT 1
            """
        ),
        {"report_period": report_period},
    ).mappings().first()
    return _baseline_row_to_dict(row) if row else None


def resolve_comparison_baseline(conn: Connection, import_report_period: date) -> Optional[dict[str, Any]]:
    """Baseline used for monthly diff of an import batch."""
    same_period = resolve_effective_baseline(conn, import_report_period)
    if same_period is not None:
        return same_period
    cursor = import_report_period
    for _ in range(24):
        cursor = _previous_report_period(cursor)
        found = resolve_effective_baseline(conn, cursor)
        if found is not None:
            return found
    return None


def get_baseline(conn: Connection, baseline_id: int, *, include_deleted: bool = False) -> dict[str, Any]:
    if not baseline_tables_available(conn):
        raise BaselineNotFoundError(baseline_id)
    row = conn.execute(
        text(
            """
            SELECT
                bl.baseline_id,
                bl.publication_origin_id,
                bl.source_batch_id,
                bl.source_type,
                bl.report_period,
                bl.published_at,
                bl.published_by,
                bl.entry_count,
                bl.deleted_at,
                bl.deleted_by,
                bl.deletion_reason,
                bl.publication_notes,
                po.source_import_code,
                po.batch_id AS origin_batch_id,
                b.import_code AS batch_import_code,
                b.file_name,
                sf.original_filename
            FROM public.hr_control_list_baselines bl
            LEFT JOIN public.hr_publication_origins po
                ON po.publication_origin_id = bl.publication_origin_id
            LEFT JOIN public.hr_import_batches b
                ON b.batch_id = COALESCE(bl.source_batch_id, po.batch_id)
            LEFT JOIN public.hr_source_files sf
                ON sf.source_file_id = b.source_file_id
            WHERE bl.baseline_id = :baseline_id
              AND (:include_deleted OR bl.deleted_at IS NULL)
            """
        ),
        {"baseline_id": baseline_id, "include_deleted": include_deleted},
    ).mappings().first()
    if row is None:
        raise BaselineNotFoundError(baseline_id)
    return _baseline_row_to_dict(row)


def list_baselines(
    conn: Connection,
    *,
    report_period: Optional[date] = None,
    include_deleted: bool = False,
) -> dict[str, Any]:
    if not baseline_tables_available(conn):
        return {"items": []}
    params: dict[str, Any] = {"include_deleted": include_deleted}
    period_filter = ""
    if report_period is not None:
        period_filter = "AND bl.report_period = :report_period"
        params["report_period"] = report_period
    rows = conn.execute(
        text(
            f"""
            SELECT
                bl.baseline_id,
                bl.publication_origin_id,
                bl.source_batch_id,
                bl.report_period,
                bl.published_at,
                bl.published_by,
                bl.entry_count,
                bl.deleted_at,
                po.source_import_code,
                po.batch_id AS origin_batch_id,
                b.import_code AS batch_import_code,
                b.file_name,
                sf.original_filename
            FROM public.hr_control_list_baselines bl
            LEFT JOIN public.hr_publication_origins po
                ON po.publication_origin_id = bl.publication_origin_id
            LEFT JOIN public.hr_import_batches b
                ON b.batch_id = COALESCE(bl.source_batch_id, po.batch_id)
            LEFT JOIN public.hr_source_files sf
                ON sf.source_file_id = b.source_file_id
            WHERE (:include_deleted OR bl.deleted_at IS NULL)
            {period_filter}
            ORDER BY bl.report_period DESC, bl.published_at DESC, bl.baseline_id DESC
            """
        ),
        params,
    ).mappings().all()
    return {"items": [_baseline_row_to_dict(dict(r)) for r in rows]}


def preview_baseline_publish(conn: Connection, batch_id: int) -> dict[str, Any]:
    """Estimate baseline composition before publish (no writes)."""
    from app.services.hr_canonical_snapshot_service import (
        RECORD_KIND_ROSTER,
        dedupe_snapshot_entries,
    )
    from app.services.hr_import_analytics_service import _load_staging_rows, is_real_employee_row
    from app.services.hr_import_normalized_record_service import (
        REVIEW_STATUS_APPROVED,
        REVIEW_STATUS_PROMOTED,
        normalized_records_available,
    )

    _ensure_batch_exists(conn, batch_id)
    batch = conn.execute(
        text(
            """
            SELECT batch_id, import_code, file_name, total_rows, valid_rows, error_rows, status
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().one()

    staging_rows = _load_staging_rows(conn, batch_id)
    roster_candidate_rows = [row for row in staging_rows if is_real_employee_row(row)]
    raw_entries = collect_mrd_forming_entries_from_batch(conn, batch_id)
    entries, duplicate_match_keys_merged = dedupe_snapshot_entries(raw_entries)

    roster_entries = sum(1 for entry in entries if entry.get("record_kind") == RECORD_KIND_ROSTER)
    normalized_entries = len(entries) - roster_entries

    normalized_pending = 0
    normalized_approved = 0
    if normalized_records_available(conn):
        counts = conn.execute(
            text(
                """
                SELECT review_status, COUNT(*) AS cnt
                FROM public.hr_import_normalized_records
                WHERE batch_id = :batch_id
                GROUP BY review_status
                """
            ),
            {"batch_id": batch_id},
        ).mappings().all()
        for row in counts:
            status = str(row["review_status"] or "")
            count = int(row["cnt"] or 0)
            if status in {REVIEW_STATUS_APPROVED, REVIEW_STATUS_PROMOTED}:
                normalized_approved += count
            elif status == "pending":
                normalized_pending += count

    total_excel_rows = int(batch.get("total_rows") or len(staging_rows))
    excluded_excel_rows = max(total_excel_rows - len(roster_candidate_rows), 0)
    existing = _get_baseline_by_batch(conn, batch_id)

    return {
        "batch_id": int(batch_id),
        "import_code": batch.get("import_code"),
        "batch_status": batch.get("status"),
        "total_excel_rows": total_excel_rows,
        "roster_candidate_rows": len(roster_candidate_rows),
        "roster_baseline_entries": roster_entries,
        "normalized_baseline_entries": normalized_entries,
        "normalized_approved_or_promoted": normalized_approved,
        "normalized_pending_excluded": normalized_pending,
        "excluded_excel_rows": excluded_excel_rows,
        "duplicate_match_keys_merged": duplicate_match_keys_merged,
        "baseline_entry_count": len(entries),
        "existing_baseline_id": int(existing["baseline_id"]) if existing else None,
        "explanation": (
            "Baseline содержит утверждённый состав контрольного списка: roster-сотрудники "
            f"({roster_entries}) и normalized-записи со статусом approved/promoted ({normalized_entries}). "
            f"Из {total_excel_rows} строк Excel будут исключены {excluded_excel_rows} "
            "(декларации, служебные строки и прочие non-roster записи). "
            f"Normalized pending ({normalized_pending}) в baseline не попадают до review."
        ),
        **assess_baseline_publish_readiness(conn, batch_id),
    }


def _get_baseline_by_batch(conn: Connection, batch_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT baseline_id
            FROM public.hr_control_list_baselines
            WHERE source_batch_id = :batch_id
              AND deleted_at IS NULL
            ORDER BY published_at DESC, baseline_id DESC
            LIMIT 1
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if row is None:
        return None
    return get_baseline(conn, int(row["baseline_id"]))


def publish_baseline_from_batch(
    conn: Connection,
    batch_id: int,
    *,
    published_by: int,
    force: bool = False,
    publication_notes: Optional[str] = None,
) -> dict[str, Any]:
    if not baseline_tables_available(conn) or not publication_origin_available(conn):
        raise CanonicalSnapshotError("baseline tables are not available")

    _ensure_batch_exists(conn, batch_id)
    existing = _get_baseline_by_batch(conn, batch_id)
    if existing and not force:
        return {
            "created": False,
            "baseline_id": int(existing["baseline_id"]),
            "snapshot_id": int(existing["baseline_id"]),
            "publication_origin_id": int(existing["publication_origin_id"]),
            "source_batch_id": existing.get("source_batch_id"),
            "entry_count": int(existing["entry_count"]),
        }

    assert_baseline_publish_allowed(conn, batch_id)

    batch = conn.execute(
        text(
            """
            SELECT batch_id, source_type, import_code
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if not batch:
        raise BatchNotFoundError(f"batch_id={batch_id} not found")

    report_period = _resolve_batch_report_period(conn, batch_id)
    source_type = str(batch["source_type"] or SOURCE_TYPE_HR_CONTROL_LIST)
    raw_entries = collect_mrd_forming_entries_from_batch(conn, batch_id)
    entries, duplicate_match_keys_merged = dedupe_snapshot_entries(raw_entries)
    now = datetime.now(timezone.utc)

    origin_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_publication_origins (
                report_period,
                published_at,
                published_by,
                source_import_code,
                batch_id,
                entry_count
            )
            VALUES (
                :report_period,
                :published_at,
                :published_by,
                :source_import_code,
                :batch_id,
                :entry_count
            )
            RETURNING publication_origin_id
            """
        ),
        {
            "report_period": report_period,
            "published_at": now,
            "published_by": int(published_by),
            "source_import_code": batch.get("import_code"),
            "batch_id": batch_id,
            "entry_count": len(entries),
        },
    ).scalar_one()

    baseline_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_control_list_baselines (
                publication_origin_id,
                source_batch_id,
                source_type,
                report_period,
                entry_count,
                published_by,
                published_at,
                publication_notes
            )
            VALUES (
                :publication_origin_id,
                :source_batch_id,
                :source_type,
                :report_period,
                :entry_count,
                :published_by,
                :published_at,
                :publication_notes
            )
            RETURNING baseline_id
            """
        ),
        {
            "publication_origin_id": int(origin_id),
            "source_batch_id": batch_id,
            "source_type": source_type,
            "report_period": report_period,
            "entry_count": len(entries),
            "published_by": int(published_by),
            "published_at": now,
            "publication_notes": publication_notes,
        },
    ).scalar_one()

    conn.execute(
        text(
            """
            UPDATE public.hr_publication_origins
            SET baseline_id = :baseline_id
            WHERE publication_origin_id = :publication_origin_id
            """
        ),
        {"baseline_id": int(baseline_id), "publication_origin_id": int(origin_id)},
    )

    for entry in entries:
        conn.execute(
            text(
                """
                INSERT INTO public.hr_baseline_entries (
                    baseline_id,
                    entity_scope,
                    record_kind,
                    match_key,
                    canonical_hash,
                    employee_id,
                    iin,
                    effective_payload,
                    source_row_id,
                    source_normalized_record_id
                )
                VALUES (
                    :baseline_id,
                    :entity_scope,
                    :record_kind,
                    :match_key,
                    :canonical_hash,
                    :employee_id,
                    :iin,
                    CAST(:effective_payload AS JSONB),
                    :source_row_id,
                    :source_normalized_record_id
                )
                """
            ),
            {
                "baseline_id": int(baseline_id),
                "entity_scope": entry["entity_scope"],
                "record_kind": entry["record_kind"],
                "match_key": entry["match_key"],
                "canonical_hash": entry["canonical_hash"],
                "employee_id": entry["employee_id"],
                "iin": entry["iin"],
                "effective_payload": _serialize_json(entry["payload"]),
                "source_row_id": entry["source_row_id"],
                "source_normalized_record_id": entry["source_normalized_record_id"],
            },
        )

    prior = resolve_comparison_baseline(conn, report_period)
    prior_baseline_id = int(prior["baseline_id"]) if prior else None
    if prior_baseline_id == int(baseline_id):
        prior_baseline_id = None

    result = {
        "created": True,
        "baseline_id": int(baseline_id),
        "snapshot_id": int(baseline_id),
        "publication_origin_id": int(origin_id),
        "source_batch_id": batch_id,
        "report_period": report_period.isoformat(),
        "entry_count": len(entries),
        "duplicate_match_keys_merged": duplicate_match_keys_merged,
        "superseded_snapshot_id": prior_baseline_id,
    }

    from app.services.hr_snapshot_comparison_service import maybe_materialize_change_events_after_snapshot

    change_events_result = maybe_materialize_change_events_after_snapshot(conn, result)
    if change_events_result is not None:
        result["change_events"] = change_events_result

    documents_updated = attach_publication_origin_to_batch_documents(
        conn,
        batch_id,
        publication_origin_id=int(origin_id),
        baseline_id=int(baseline_id),
    )
    if documents_updated:
        result["documents_provenance_updated"] = documents_updated

    from app.services.hr_import_review_exception_detail_service import (
        clear_import_review_overrides_for_batch,
    )

    overrides_cleared = clear_import_review_overrides_for_batch(conn, batch_id)
    result["review_overrides_cleared"] = overrides_cleared

    return result


def mark_batches_stale_for_baseline(conn: Connection, baseline_id: int) -> int:
    result = conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET comparison_baseline_id = NULL,
                diff_status = :stale
            WHERE comparison_baseline_id = :baseline_id
            """
        ),
        {"baseline_id": baseline_id, "stale": BATCH_DIFF_STATUS_STALE},
    )
    return int(result.rowcount or 0)


def soft_delete_baseline(
    conn: Connection,
    baseline_id: int,
    *,
    deleted_by: int,
    deletion_reason: Optional[str] = None,
) -> dict[str, Any]:
    baseline = get_baseline(conn, baseline_id, include_deleted=True)
    if baseline.get("deleted_at") is not None:
        raise BaselineDeleteError("Baseline уже удалён (soft delete).")

    origin_id = int(baseline["publication_origin_id"])
    conn.execute(
        text(
            """
            UPDATE public.hr_control_list_baselines
            SET deleted_at = NOW(),
                deleted_by = :deleted_by,
                deletion_reason = :deletion_reason
            WHERE baseline_id = :baseline_id
            """
        ),
        {
            "baseline_id": baseline_id,
            "deleted_by": int(deleted_by),
            "deletion_reason": deletion_reason,
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO public.hr_baseline_deletion_log (
                baseline_id,
                publication_origin_id,
                deletion_kind,
                report_period,
                published_at,
                published_by,
                source_import_code,
                entry_count,
                deleted_by,
                deletion_reason
            )
            SELECT
                bl.baseline_id,
                bl.publication_origin_id,
                :kind,
                bl.report_period,
                bl.published_at,
                bl.published_by,
                po.source_import_code,
                bl.entry_count,
                :deleted_by,
                :deletion_reason
            FROM public.hr_control_list_baselines bl
            LEFT JOIN public.hr_publication_origins po
                ON po.publication_origin_id = bl.publication_origin_id
            WHERE bl.baseline_id = :baseline_id
            """
        ),
        {
            "baseline_id": baseline_id,
            "kind": BASELINE_DELETION_SOFT,
            "deleted_by": int(deleted_by),
            "deletion_reason": deletion_reason,
        },
    )
    stale_batches = mark_batches_stale_for_baseline(conn, baseline_id)
    return {
        "baseline_id": baseline_id,
        "soft_deleted": True,
        "publication_origin_id": origin_id,
        "stale_batches": stale_batches,
    }


def restore_baseline(conn: Connection, baseline_id: int, *, restored_by: int) -> dict[str, Any]:
    baseline = get_baseline(conn, baseline_id, include_deleted=True)
    if baseline.get("deleted_at") is None:
        raise BaselineRestoreError("Baseline не находится в soft delete.")

    conn.execute(
        text(
            """
            UPDATE public.hr_control_list_baselines
            SET deleted_at = NULL,
                deleted_by = NULL,
                deletion_reason = NULL
            WHERE baseline_id = :baseline_id
            """
        ),
        {"baseline_id": baseline_id},
    )
    conn.execute(
        text(
            """
            UPDATE public.hr_baseline_deletion_log
            SET restored_at = NOW(),
                restored_by = :restored_by
            WHERE baseline_id = :baseline_id
              AND deletion_kind = :kind
              AND restored_at IS NULL
            """
        ),
        {
            "baseline_id": baseline_id,
            "restored_by": int(restored_by),
            "kind": BASELINE_DELETION_SOFT,
        },
    )
    return {"baseline_id": baseline_id, "restored": True}


def hard_delete_baseline(
    conn: Connection,
    baseline_id: int,
    *,
    deleted_by: int,
    deletion_reason: Optional[str] = None,
) -> dict[str, Any]:
    baseline = get_baseline(conn, baseline_id, include_deleted=True)
    origin_id = int(baseline["publication_origin_id"])

    conn.execute(
        text(
            """
            INSERT INTO public.hr_baseline_deletion_log (
                baseline_id,
                publication_origin_id,
                deletion_kind,
                report_period,
                published_at,
                published_by,
                source_import_code,
                entry_count,
                deleted_by,
                deletion_reason
            )
            SELECT
                bl.baseline_id,
                bl.publication_origin_id,
                :kind,
                bl.report_period,
                bl.published_at,
                bl.published_by,
                po.source_import_code,
                bl.entry_count,
                :deleted_by,
                :deletion_reason
            FROM public.hr_control_list_baselines bl
            LEFT JOIN public.hr_publication_origins po
                ON po.publication_origin_id = bl.publication_origin_id
            WHERE bl.baseline_id = :baseline_id
            """
        ),
        {
            "baseline_id": baseline_id,
            "kind": BASELINE_DELETION_HARD,
            "deleted_by": int(deleted_by),
            "deletion_reason": deletion_reason,
        },
    )

    stale_batches = mark_batches_stale_for_baseline(conn, baseline_id)

    conn.execute(
        text(
            """
            UPDATE public.employee_documents
            SET baseline_id = NULL
            WHERE baseline_id = :baseline_id
            """
        ),
        {"baseline_id": baseline_id},
    )

    conn.execute(
        text(
            """
            DELETE FROM public.hr_control_list_baselines
            WHERE baseline_id = :baseline_id
            """
        ),
        {"baseline_id": baseline_id},
    )

    return {
        "baseline_id": baseline_id,
        "hard_deleted": True,
        "publication_origin_id": origin_id,
        "stale_batches": stale_batches,
    }


def update_batch_diff_tracking(
    conn: Connection,
    batch_id: int,
    *,
    comparison_baseline_id: Optional[int],
    comparison_publication_origin_id: Optional[int],
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET comparison_baseline_id = :comparison_baseline_id,
                comparison_publication_origin_id = :comparison_publication_origin_id,
                diff_status = :current,
                diff_computed_at = NOW()
            WHERE batch_id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "comparison_baseline_id": comparison_baseline_id,
            "comparison_publication_origin_id": comparison_publication_origin_id,
            "current": BATCH_DIFF_STATUS_CURRENT,
        },
    )


def ensure_batch_diff_fresh(conn: Connection, batch_id: int) -> Optional[dict[str, Any]]:
    """Lazy recalc when batch diff is STALE."""
    row = conn.execute(
        text(
            """
            SELECT diff_status
            FROM public.hr_import_batches
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if row is None:
        raise BatchNotFoundError(batch_id)
    if row.get("diff_status") != BATCH_DIFF_STATUS_STALE:
        return None
    from app.services.hr_import_monthly_diff_service import compute_batch_monthly_diff

    return compute_batch_monthly_diff(conn, batch_id)


def attach_publication_origin_to_batch_documents(
    conn: Connection,
    batch_id: int,
    *,
    publication_origin_id: int,
    baseline_id: Optional[int] = None,
) -> int:
    params: dict[str, Any] = {
        "batch_id": batch_id,
        "publication_origin_id": int(publication_origin_id),
        "baseline_id": baseline_id,
    }
    result = conn.execute(
        text(
            """
            UPDATE public.employee_documents
            SET publication_origin_id = COALESCE(publication_origin_id, :publication_origin_id),
                baseline_id = COALESCE(baseline_id, :baseline_id)
            WHERE source_batch_id = :batch_id
            """
        ),
        params,
    )
    return int(result.rowcount or 0)

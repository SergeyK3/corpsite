"""Shared helpers for HR import integration tests."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_control_list_storage import remove_stored_control_list_file
from tests.test_import_hr_control_list import _build_sample_workbook

# Canonical IINs from tests/test_import_hr_control_list._build_sample_workbook
SAMPLE_WORKBOOK_IINS: frozenset[str] = frozenset(
    {
        "900101300123",
        "850505400456",
        "800316400190",
        "740826400893",
        "760111450360",
    }
)

# Baselines/imports with at most this many rows/entries and only sample IINs are test artifacts.
SAMPLE_WORKBOOK_MAX_ENTRIES = 10
SAMPLE_WORKBOOK_MAX_ROWS = 10
PYTEST_INITIATOR_FULL_NAME = "Pytest Initiator"


def write_control_list_workbook(tmp_path: Path, yymm: str = "2606") -> Path:
    dest = tmp_path / f"контрольный{yymm}.xlsx"
    _build_sample_workbook(dest)
    return dest


def _baseline_tables_available(conn: Connection) -> bool:
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


def _collect_baseline_ids_for_batch(conn: Connection, batch_id: int) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT bl.baseline_id
            FROM public.hr_control_list_baselines bl
            LEFT JOIN public.hr_publication_origins po
                ON po.publication_origin_id = bl.publication_origin_id
            WHERE bl.source_batch_id = :batch_id
               OR po.batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).scalars().all()
    return [int(row) for row in rows]


def _collect_origin_ids_for_batch(conn: Connection, batch_id: int) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT po.publication_origin_id
            FROM public.hr_publication_origins po
            WHERE po.batch_id = :batch_id
               OR po.publication_origin_id IN (
                    SELECT publication_origin_id
                    FROM public.hr_control_list_baselines
                    WHERE source_batch_id = :batch_id
               )
            """
        ),
        {"batch_id": batch_id},
    ).scalars().all()
    return [int(row) for row in rows]


def _delete_baseline_artifacts(
    conn: Connection,
    *,
    baseline_ids: list[int],
    origin_ids: list[int],
    batch_id: int | None = None,
) -> None:
    if batch_id is not None:
        conn.execute(
            text(
                """
                UPDATE public.employee_documents
                SET publication_origin_id = NULL,
                    baseline_id = NULL
                WHERE source_batch_id = :batch_id
                """
            ),
            {"batch_id": batch_id},
        )
    if baseline_ids:
        conn.execute(
            text(
                """
                DELETE FROM public.hr_baseline_deletion_log
                WHERE baseline_id = ANY(:baseline_ids)
                   OR publication_origin_id = ANY(:origin_ids)
                """
            ),
            {"baseline_ids": baseline_ids, "origin_ids": origin_ids or [-1]},
        )
        conn.execute(
            text(
                """
                DELETE FROM public.hr_control_list_baselines
                WHERE baseline_id = ANY(:baseline_ids)
                """
            ),
            {"baseline_ids": baseline_ids},
        )
    if origin_ids:
        conn.execute(
            text(
                """
                DELETE FROM public.hr_publication_origins
                WHERE publication_origin_id = ANY(:origin_ids)
                """
            ),
            {"origin_ids": origin_ids},
        )


def cleanup_baseline_for_batch(conn: Connection, batch_id: int) -> None:
    """Remove baselines, deletion audit rows, and origins tied to a batch."""
    conn.execute(
        text(
            """
            DELETE FROM public.hr_baseline_deletion_log
            WHERE publication_origin_id IN (
                SELECT publication_origin_id
                FROM public.hr_publication_origins
                WHERE batch_id = :batch_id
            )
               OR baseline_id IN (
                SELECT bl.baseline_id
                FROM public.hr_control_list_baselines bl
                LEFT JOIN public.hr_publication_origins po
                    ON po.publication_origin_id = bl.publication_origin_id
                WHERE bl.source_batch_id = :batch_id
                   OR po.batch_id = :batch_id
            )
            """
        ),
        {"batch_id": batch_id},
    )
    baseline_ids = _collect_baseline_ids_for_batch(conn, batch_id)
    origin_ids = _collect_origin_ids_for_batch(conn, batch_id)
    _delete_baseline_artifacts(
        conn,
        baseline_ids=baseline_ids,
        origin_ids=origin_ids,
        batch_id=batch_id,
    )


def cleanup_baseline_by_id(conn: Connection, baseline_id: int) -> None:
    row = conn.execute(
        text(
            """
            SELECT bl.source_batch_id, bl.publication_origin_id, po.batch_id AS origin_batch_id
            FROM public.hr_control_list_baselines bl
            LEFT JOIN public.hr_publication_origins po
                ON po.publication_origin_id = bl.publication_origin_id
            WHERE bl.baseline_id = :baseline_id
            """
        ),
        {"baseline_id": baseline_id},
    ).mappings().first()
    origin_ids = [int(row["publication_origin_id"])] if row and row.get("publication_origin_id") else []
    batch_id = None
    if row:
        batch_id = row.get("source_batch_id") or row.get("origin_batch_id")
    _delete_baseline_artifacts(
        conn,
        baseline_ids=[baseline_id],
        origin_ids=origin_ids,
        batch_id=int(batch_id) if batch_id is not None else None,
    )


def is_sample_workbook_baseline(conn: Connection, baseline_id: int) -> bool:
    """True when baseline entries match pytest sample workbook fingerprint."""
    summary = conn.execute(
        text(
            """
            SELECT
                COUNT(*) AS entry_count,
                COUNT(*) FILTER (
                    WHERE COALESCE(iin, '') = ANY(:sample_iins)
                ) AS sample_iin_matches
            FROM public.hr_baseline_entries
            WHERE baseline_id = :baseline_id
              AND record_kind = 'roster'
            """
        ),
        {"baseline_id": baseline_id, "sample_iins": list(SAMPLE_WORKBOOK_IINS)},
    ).mappings().one()
    entry_count = int(summary["entry_count"] or 0)
    if entry_count == 0 or entry_count > SAMPLE_WORKBOOK_MAX_ENTRIES:
        return False
    return int(summary["sample_iin_matches"] or 0) == entry_count


def find_sample_workbook_baseline_ids(conn: Connection) -> list[int]:
    if not _baseline_tables_available(conn):
        return []
    rows = conn.execute(
        text(
            """
            SELECT bl.baseline_id
            FROM public.hr_control_list_baselines bl
            WHERE bl.entry_count <= :max_entries
            ORDER BY bl.baseline_id
            """
        ),
        {"max_entries": SAMPLE_WORKBOOK_MAX_ENTRIES},
    ).scalars().all()
    return [int(bid) for bid in rows if is_sample_workbook_baseline(conn, int(bid))]


def cleanup_sample_workbook_baselines(conn: Connection) -> list[int]:
    """Delete orphaned pytest/sample-workbook baselines. Returns removed baseline ids."""
    removed: list[int] = []
    for baseline_id in find_sample_workbook_baseline_ids(conn):
        cleanup_baseline_by_id(conn, baseline_id)
        removed.append(baseline_id)
    return removed


def find_orphan_test_publication_origin_ids(conn: Connection) -> list[int]:
    """PublicationOrigin rows left after hard-deleting sample-workbook baselines."""
    if not _baseline_tables_available(conn):
        return []
    rows = conn.execute(
        text(
            """
            SELECT po.publication_origin_id
            FROM public.hr_publication_origins po
            WHERE po.baseline_id IS NULL
              AND po.entry_count <= :max_entries
              AND po.source_import_code NOT LIKE 'legacy-%'
              AND NOT EXISTS (
                    SELECT 1
                    FROM public.hr_control_list_baselines bl
                    WHERE bl.publication_origin_id = po.publication_origin_id
              )
            ORDER BY po.publication_origin_id
            """
        ),
        {"max_entries": SAMPLE_WORKBOOK_MAX_ENTRIES},
    ).scalars().all()
    return [int(origin_id) for origin_id in rows]


def cleanup_orphan_test_publication_origins(conn: Connection) -> list[int]:
    """Remove orphaned pytest PublicationOrigin rows. Returns removed origin ids."""
    origin_ids = find_orphan_test_publication_origin_ids(conn)
    if not origin_ids:
        return []
    conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET comparison_publication_origin_id = NULL
            WHERE comparison_publication_origin_id = ANY(:origin_ids)
            """
        ),
        {"origin_ids": origin_ids},
    )
    conn.execute(
        text(
            """
            UPDATE public.employee_documents
            SET publication_origin_id = NULL
            WHERE publication_origin_id = ANY(:origin_ids)
            """
        ),
        {"origin_ids": origin_ids},
    )
    conn.execute(
        text(
            """
            DELETE FROM public.hr_baseline_deletion_log
            WHERE publication_origin_id = ANY(:origin_ids)
            """
        ),
        {"origin_ids": origin_ids},
    )
    conn.execute(
        text(
            """
            DELETE FROM public.hr_publication_origins
            WHERE publication_origin_id = ANY(:origin_ids)
            """
        ),
        {"origin_ids": origin_ids},
    )
    return origin_ids


def is_pytest_storage_ref(storage_ref: str | None) -> bool:
    if not storage_ref:
        return False
    normalized = str(storage_ref).replace("\\", "/").lower()
    return "pytest-of-" in normalized or "/pytest-" in normalized


def is_pytest_import_user_row(user_row: dict[str, object] | None) -> bool:
    if not user_row:
        return False
    full_name = str(user_row.get("full_name") or "").strip()
    if full_name == PYTEST_INITIATOR_FULL_NAME:
        return True
    google_login = str(user_row.get("google_login") or "")
    return google_login.startswith("pytest_google_")


def is_sample_workbook_import_batch(conn: Connection, batch_id: int) -> bool:
    """True when import batch matches pytest sample-workbook fingerprint."""
    row = conn.execute(
        text(
            """
            SELECT
                b.batch_id,
                b.import_code,
                b.total_rows,
                b.imported_by,
                sf.storage_ref,
                u.full_name,
                u.google_login
            FROM public.hr_import_batches b
            LEFT JOIN public.hr_source_files sf
                ON sf.source_file_id = b.source_file_id
            LEFT JOIN public.users u
                ON u.user_id = b.imported_by
            WHERE b.batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if row is None:
        return False
    import_code = str(row.get("import_code") or "")
    if import_code.startswith("legacy-"):
        return False
    total_rows = int(row.get("total_rows") or 0)
    if total_rows <= 0 or total_rows > SAMPLE_WORKBOOK_MAX_ROWS:
        return False
    pytest_signals = is_pytest_storage_ref(row.get("storage_ref")) or is_pytest_import_user_row(dict(row))
    if not pytest_signals:
        return False
    summary = conn.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE COALESCE(normalized_payload->>'iin', '') <> ''
                ) AS iin_rows,
                COUNT(*) FILTER (
                    WHERE COALESCE(normalized_payload->>'iin', '') = ANY(:sample_iins)
                ) AS sample_iin_rows
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id, "sample_iins": list(SAMPLE_WORKBOOK_IINS)},
    ).mappings().one()
    iin_rows = int(summary["iin_rows"] or 0)
    sample_iin_rows = int(summary["sample_iin_rows"] or 0)
    if iin_rows == 0 or sample_iin_rows != iin_rows:
        return False
    return True


def find_orphan_test_import_batches(conn: Connection) -> list[dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT b.batch_id, b.import_code, b.total_rows, b.status
            FROM public.hr_import_batches b
            WHERE b.import_code NOT LIKE 'legacy-%'
              AND b.total_rows <= :max_rows
            ORDER BY b.import_code, b.batch_id
            """
        ),
        {"max_rows": SAMPLE_WORKBOOK_MAX_ROWS},
    ).mappings().all()
    matches: list[dict[str, object]] = []
    for row in rows:
        batch_id = int(row["batch_id"])
        if is_sample_workbook_import_batch(conn, batch_id):
            matches.append(dict(row))
    return matches


def cleanup_orphan_test_import_batches(conn: Connection) -> list[str]:
    """Delete orphaned pytest import batches. Returns removed import codes."""
    removed_codes: list[str] = []
    for row in find_orphan_test_import_batches(conn):
        batch_id = int(row["batch_id"])
        import_code = str(row["import_code"])
        cleanup_import_batch_with_baselines(conn, batch_id)
        still = conn.execute(
            text("SELECT 1 FROM public.hr_import_batches WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        ).first()
        if still is None:
            removed_codes.append(import_code)
    return removed_codes


def complete_import_review_for_baseline_publish(conn: Connection, batch_id: int) -> None:
    """Test helper: resolve normalized review and mark batch ready for baseline publish."""
    from app.services.hr_import_complete_review_service import complete_import_review
    from app.services.hr_import_normalized_record_service import (
        REVIEW_STATUS_APPROVED,
        normalized_records_available,
    )

    if normalized_records_available(conn):
        conn.execute(
            text(
                """
                UPDATE public.hr_import_normalized_records
                SET review_status = :approved
                WHERE batch_id = :batch_id
                  AND review_status = 'pending'
                """
            ),
            {"batch_id": batch_id, "approved": REVIEW_STATUS_APPROVED},
        )
    import_code = conn.execute(
        text("SELECT import_code FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).scalar_one()
    complete_import_review(conn, str(import_code), completed_by=1)


def cleanup_import_batch(conn: Connection, batch_id: int | None) -> None:
    if batch_id is None:
        return
    row = conn.execute(
        text(
            """
            SELECT b.source_file_id, sf.storage_ref
            FROM public.hr_import_batches b
            LEFT JOIN public.hr_source_files sf
                ON sf.source_file_id = b.source_file_id
            WHERE b.batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().first()
    if row is None:
        return
    conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET comparison_publication_origin_id = NULL,
                comparison_baseline_id = NULL
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    )
    conn.execute(
        text("DELETE FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    )
    source_file_id = row.get("source_file_id")
    if source_file_id is not None:
        conn.execute(
            text("DELETE FROM public.hr_source_files WHERE source_file_id = :source_file_id"),
            {"source_file_id": source_file_id},
        )
    storage_ref = row.get("storage_ref")
    if storage_ref:
        remove_stored_control_list_file(str(storage_ref))


def cleanup_import_batch_with_baselines(conn: Connection, batch_id: int | None) -> None:
    """Remove baseline/origin artifacts first, then staging batch + source file."""
    if batch_id is None:
        return
    cleanup_baseline_for_batch(conn, int(batch_id))
    cleanup_import_batch(conn, int(batch_id))

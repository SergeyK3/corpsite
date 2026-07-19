"""Persist operator choice of import batch as initial baseline source per report period.

Lifecycle (transitional workflow — not SoT after MRD CREATE):

1. ACTIVE — operator may change `source_batch_id` while no MRD version exists for the period.
2. CONSUMED — frozen after `create_initial_mrd_from_review`; provenance moves to
   `hr_monthly_references.source_batch_id` and `hr_reference_version_events` (CREATE).
3. Any MRD row for the period (ACTIVE or CLOSED) permanently freezes the choice — first CREATE
   is irreversible regardless of later version/status transitions.
4. While ACTIVE selection, selected batch cannot be deleted (FK RESTRICT + delete assessment).

See docs-work/WP-MRD-initial-baseline-source-selection-lifecycle.md
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

SELECTION_STATUS_ACTIVE = "ACTIVE"
SELECTION_STATUS_CONSUMED = "CONSUMED"

MRD_CREATE_EVENT_CONTEXT_SOURCE_BATCH_ID = "source_batch_id"


class InitialBaselineSourceError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InitialBaselineSourceBatchNotFoundError(InitialBaselineSourceError):
    pass


class InitialBaselineSourceBatchPeriodMismatchError(InitialBaselineSourceError):
    pass


class InitialBaselineSourceSelectionFrozenError(InitialBaselineSourceError):
    """Selection cannot change: period already has MRD or selection is consumed."""


def initial_baseline_source_table_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_initial_baseline_source_selections'
            """
        ),
    ).first()
    return row is not None


def _selection_lifecycle_columns_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_initial_baseline_source_selections'
              AND column_name = 'lifecycle_status'
            """
        ),
    ).first()
    return row is not None


def _normalize_report_period(value: date | str) -> date:
    if isinstance(value, date):
        report_period = value
    else:
        report_period = date.fromisoformat(str(value)[:10])
    return date(report_period.year, report_period.month, 1)


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
        raise InitialBaselineSourceBatchNotFoundError(f"Import batch {batch_id} not found")
    value = row["report_period"]
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _ensure_batch_exists(conn: Connection, batch_id: int) -> None:
    exists = conn.execute(
        text("SELECT 1 FROM public.hr_import_batches WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).first()
    if not exists:
        raise InitialBaselineSourceBatchNotFoundError(f"Import batch {batch_id} not found")


def _mrd_table_available(conn: Connection) -> bool:
    return conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_monthly_references'
            """
        ),
    ).first() is not None


def _period_has_mrd(conn: Connection, report_period: date) -> bool:
    """True once any MRD version was created for the period (first CREATE is irreversible)."""
    if not _mrd_table_available(conn):
        return False
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.hr_monthly_references
            WHERE report_period = :report_period
            LIMIT 1
            """
        ),
        {"report_period": report_period},
    ).first()
    return row is not None


def _first_mrd_id_for_period(conn: Connection, report_period: date) -> int | None:
    if not _mrd_table_available(conn):
        return None
    row = conn.execute(
        text(
            """
            SELECT mrd_id
            FROM public.hr_monthly_references
            WHERE report_period = :report_period
            ORDER BY version ASC, mrd_id ASC
            LIMIT 1
            """
        ),
        {"report_period": report_period},
    ).scalar_one_or_none()
    return int(row) if row is not None else None


def _selection_is_mutable(conn: Connection, report_period: date, lifecycle_status: str) -> bool:
    if lifecycle_status != SELECTION_STATUS_ACTIVE:
        return False
    return not _period_has_mrd(conn, report_period)


def _assert_selection_mutable(conn: Connection, report_period: date) -> None:
    if _selection_lifecycle_columns_available(conn):
        existing = conn.execute(
            text(
                """
                SELECT lifecycle_status
                FROM public.hr_initial_baseline_source_selections
                WHERE report_period = :report_period
                """
            ),
            {"report_period": report_period},
        ).scalar_one_or_none()
        if existing == SELECTION_STATUS_CONSUMED:
            raise InitialBaselineSourceSelectionFrozenError(
                f"Выбор источника для периода {report_period.isoformat()} уже использован "
                "при создании MRD и не может быть изменён."
            )

    first_mrd_id = _first_mrd_id_for_period(conn, report_period)
    if first_mrd_id is not None:
        raise InitialBaselineSourceSelectionFrozenError(
            f"Для периода {report_period.isoformat()} уже создан MRD "
            f"(mrd_id={first_mrd_id}). Выбор источника первичного эталона зафиксирован."
        )


def _serialize_selection_row(conn: Connection, row: dict[str, Any]) -> dict[str, Any]:
    report_period = row["report_period"]
    if isinstance(report_period, datetime):
        report_period = report_period.date()
    selected_at = row.get("selected_at")
    updated_at = row.get("updated_at")
    consumed_at = row.get("consumed_at")
    lifecycle_status = str(row.get("lifecycle_status") or SELECTION_STATUS_ACTIVE)
    consumed_mrd_id = row.get("consumed_mrd_id")
    return {
        "report_period": report_period.isoformat(),
        "source_batch_id": int(row["source_batch_id"]),
        "import_code": str(row.get("import_code") or "").strip() or None,
        "selected_by": int(row["selected_by"]),
        "selected_at": selected_at.isoformat() if isinstance(selected_at, datetime) else selected_at,
        "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
        "lifecycle_status": lifecycle_status,
        "consumed_at": consumed_at.isoformat() if isinstance(consumed_at, datetime) else consumed_at,
        "consumed_mrd_id": int(consumed_mrd_id) if consumed_mrd_id is not None else None,
        "mutable": _selection_is_mutable(conn, report_period, lifecycle_status),
    }


def _selection_select_sql(*, report_period: date | None = None) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    where_clause = ""
    if report_period is not None:
        where_clause = "WHERE s.report_period = :report_period"
        params["report_period"] = report_period
    sql = f"""
        SELECT
            s.report_period,
            s.source_batch_id,
            s.selected_by,
            s.selected_at,
            s.updated_at,
            s.lifecycle_status,
            s.consumed_at,
            s.consumed_mrd_id,
            b.import_code
        FROM public.hr_initial_baseline_source_selections s
        JOIN public.hr_import_batches b
            ON b.batch_id = s.source_batch_id
        {where_clause}
        ORDER BY s.report_period DESC
    """
    return sql, params


def list_initial_baseline_source_selections(conn: Connection) -> dict[str, Any]:
    if not initial_baseline_source_table_available(conn):
        return {"items": []}
    sql, params = _selection_select_sql()
    rows = conn.execute(text(sql), params).mappings().all()
    return {"items": [_serialize_selection_row(conn, dict(row)) for row in rows]}


def get_initial_baseline_source_selection(
    conn: Connection,
    report_period: date | str,
) -> Optional[dict[str, Any]]:
    if not initial_baseline_source_table_available(conn):
        return None
    period = _normalize_report_period(report_period)
    sql, params = _selection_select_sql(report_period=period)
    row = conn.execute(text(sql), params).mappings().first()
    if row is None:
        return None
    return _serialize_selection_row(conn, dict(row))


def set_initial_baseline_source_selection(
    conn: Connection,
    *,
    report_period: date | str,
    source_batch_id: int,
    selected_by: int,
) -> dict[str, Any]:
    if not initial_baseline_source_table_available(conn):
        raise InitialBaselineSourceError(
            "Таблица выбора источника первичного эталона не развёрнута. Выполните миграцию Alembic."
        )

    period = _normalize_report_period(report_period)
    _assert_selection_mutable(conn, period)

    _ensure_batch_exists(conn, int(source_batch_id))

    batch_period = _resolve_batch_report_period(conn, int(source_batch_id))
    if batch_period != period:
        raise InitialBaselineSourceBatchPeriodMismatchError(
            f"Импорт batch_id={source_batch_id} относится к периоду {batch_period.isoformat()}, "
            f"а не к {period.isoformat()}."
        )

    now = datetime.now(timezone.utc)
    conn.execute(
        text(
            """
            INSERT INTO public.hr_initial_baseline_source_selections (
                report_period,
                source_batch_id,
                selected_by,
                selected_at,
                updated_at,
                lifecycle_status
            )
            VALUES (
                :report_period,
                :source_batch_id,
                :selected_by,
                :selected_at,
                :updated_at,
                :lifecycle_status
            )
            ON CONFLICT (report_period) DO UPDATE
            SET source_batch_id = EXCLUDED.source_batch_id,
                selected_by = EXCLUDED.selected_by,
                selected_at = EXCLUDED.selected_at,
                updated_at = EXCLUDED.updated_at
            WHERE public.hr_initial_baseline_source_selections.lifecycle_status = :lifecycle_status
            """
        ),
        {
            "report_period": period,
            "source_batch_id": int(source_batch_id),
            "selected_by": int(selected_by),
            "selected_at": now,
            "updated_at": now,
            "lifecycle_status": SELECTION_STATUS_ACTIVE,
        },
    )
    selection = get_initial_baseline_source_selection(conn, period)
    if selection is None or not selection["mutable"]:
        raise InitialBaselineSourceSelectionFrozenError(
            f"Не удалось обновить выбор источника для периода {period.isoformat()}."
        )
    return selection


def consume_initial_baseline_source_selection(
    conn: Connection,
    *,
    report_period: date | str,
    mrd_id: int,
) -> dict[str, Any]:
    """Mark workflow selection consumed after create_initial_mrd_from_review.

    Future create_initial_mrd_from_review should also persist:
    - hr_monthly_references.source_batch_id
    - hr_reference_version_events (CREATE) with event_context[source_batch_id]
    """
    if not initial_baseline_source_table_available(conn):
        raise InitialBaselineSourceError(
            "Таблица выбора источника первичного эталона не развёрнута. Выполните миграцию Alembic."
        )
    if not _selection_lifecycle_columns_available(conn):
        raise InitialBaselineSourceError(
            "Lifecycle-колонки выбора источника не развёрнуты. Выполните миграцию Alembic."
        )

    period = _normalize_report_period(report_period)
    row = conn.execute(
        text(
            """
            SELECT source_batch_id, lifecycle_status
            FROM public.hr_initial_baseline_source_selections
            WHERE report_period = :report_period
            """
        ),
        {"report_period": period},
    ).mappings().first()
    if row is None:
        raise InitialBaselineSourceError(
            f"Для периода {period.isoformat()} не зафиксирован выбор источника первичного эталона."
        )
    if str(row["lifecycle_status"]) == SELECTION_STATUS_CONSUMED:
        selection = get_initial_baseline_source_selection(conn, period)
        assert selection is not None
        return selection

    now = datetime.now(timezone.utc)
    conn.execute(
        text(
            """
            UPDATE public.hr_initial_baseline_source_selections
            SET lifecycle_status = :consumed,
                consumed_at = :consumed_at,
                consumed_mrd_id = :mrd_id,
                updated_at = :consumed_at
            WHERE report_period = :report_period
              AND lifecycle_status = :active
            """
        ),
        {
            "report_period": period,
            "mrd_id": int(mrd_id),
            "consumed_at": now,
            "active": SELECTION_STATUS_ACTIVE,
            "consumed": SELECTION_STATUS_CONSUMED,
        },
    )
    selection = get_initial_baseline_source_selection(conn, period)
    if selection is None or selection["lifecycle_status"] != SELECTION_STATUS_CONSUMED:
        raise InitialBaselineSourceError(
            f"Не удалось зафиксировать использование выбора источника для периода {period.isoformat()}."
        )
    return selection


def assess_batch_delete_initial_baseline_source_block(
    conn: Connection,
    batch_id: int,
) -> list[str]:
    if not initial_baseline_source_table_available(conn):
        return []
    if not _selection_lifecycle_columns_available(conn):
        return []

    rows = conn.execute(
        text(
            """
            SELECT report_period
            FROM public.hr_initial_baseline_source_selections
            WHERE source_batch_id = :batch_id
              AND lifecycle_status = :active
            ORDER BY report_period
            """
        ),
        {"batch_id": int(batch_id), "active": SELECTION_STATUS_ACTIVE},
    ).mappings().all()
    return [
        (
            f"Импорт выбран как источник первичного эталона для периода "
            f"{row['report_period'].isoformat() if hasattr(row['report_period'], 'isoformat') else row['report_period']}."
        )
        for row in rows
    ]

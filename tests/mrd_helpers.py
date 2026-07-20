"""Test helpers for MRD integration tests."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Connection, text

from app.mrd.domain.types import ORIGIN_IMPORT_COMPARE
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository
from app.services.hr_canonical_snapshot_service import compute_canonical_hash


def unique_report_period() -> date:
    """Isolated period for tests that roll back (years 2080–2094).

    Do not use for API/integration tests that commit — they leave orphan rows
    visible until manually purged. Prefer get_creation_window_periods() for committed tests.
    """
    suffix = uuid4().hex
    year = 2080 + int(suffix[:2], 16) % 15
    month = int(suffix[2:4], 16) % 12 + 1
    return date(year, month, 1)


def seed_active_mrd(
    conn: Connection,
    *,
    report_period: date,
    created_by: int,
    version: int = 1,
) -> int:
    if version == 1:
        purge_mrd_report_period(conn, report_period)
    repo = SqlAlchemyMrdRepository(conn)
    row = conn.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by
            )
            VALUES (:report_period, :version, 'ACTIVE', :created_by)
            RETURNING mrd_id
            """
        ),
        {"report_period": report_period, "version": version, "created_by": created_by},
    ).scalar_one()
    return int(row)


def insert_ephemeral_active_mrd(
    conn: Connection,
    *,
    report_period: date,
    created_by: int,
) -> int:
    """Insert ACTIVE MRD without purging (safe when hr_detected_differences cannot be deleted)."""
    conn.execute(
        text(
            """
            UPDATE public.hr_monthly_references
            SET status = 'CLOSED',
                closed_at = NOW(),
                closed_by = :created_by
            WHERE report_period = :report_period
              AND status = 'ACTIVE'
            """
        ),
        {"report_period": report_period, "created_by": created_by},
    )
    next_version = int(
        conn.execute(
            text(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                """
            ),
            {"report_period": report_period},
        ).scalar_one()
    )
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.hr_monthly_references (
                    report_period, version, status, created_by
                )
                VALUES (:report_period, :version, 'ACTIVE', :created_by)
                RETURNING mrd_id
                """
            ),
            {
                "report_period": report_period,
                "version": next_version,
                "created_by": created_by,
            },
        ).scalar_one()
    )


def seed_mrd_entry(
    conn: Connection,
    *,
    mrd_id: int,
    match_key: str,
    payload: dict,
    record_kind: str = "roster",
) -> int:
    entity_scope = match_key
    entry_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_monthly_reference_entries (
                mrd_id, entity_scope, record_kind, match_key, canonical_hash, effective_payload
            )
            VALUES (
                :mrd_id, :entity_scope, :record_kind, :match_key, :canonical_hash,
                CAST(:effective_payload AS jsonb)
            )
            RETURNING entry_id
            """
        ),
        {
            "mrd_id": mrd_id,
            "entity_scope": entity_scope,
            "record_kind": record_kind,
            "match_key": match_key,
            "canonical_hash": compute_canonical_hash(
                record_kind=record_kind,
                entity_scope=entity_scope,
                payload=payload,
            ),
            "effective_payload": __import__("json").dumps(payload, ensure_ascii=False),
        },
    ).scalar_one()
    conn.execute(
        text(
            """
            UPDATE public.hr_monthly_references
            SET entry_count = entry_count + 1
            WHERE mrd_id = :mrd_id
            """
        ),
        {"mrd_id": mrd_id},
    )
    return int(entry_id)


def seed_import_batch(
    conn: Connection,
    *,
    imported_by: int,
    report_period: date | None = None,
) -> int:
    suffix = uuid4().hex[:8]
    imported_at = None
    if report_period is not None:
        imported_at = datetime(report_period.year, report_period.month, 1, tzinfo=timezone.utc)
    params: dict = {
        "file_name": f"pytest_{suffix}.xlsx",
        "import_code": f"pytest-{suffix}",
        "imported_by": imported_by,
    }
    if imported_at is not None:
        params["imported_at"] = imported_at
        batch_id = conn.execute(
            text(
                """
                INSERT INTO public.hr_import_batches (
                    source_type, file_name, import_code, imported_by, status,
                    total_rows, valid_rows, error_rows, imported_at
                )
                VALUES (
                    'HR_CONTROL_LIST', :file_name, :import_code, :imported_by, 'PARSED',
                    1, 1, 0, :imported_at
                )
                RETURNING batch_id
                """
            ),
            params,
        ).scalar_one()
    else:
        batch_id = conn.execute(
            text(
                """
                INSERT INTO public.hr_import_batches (
                    source_type, file_name, import_code, imported_by, status,
                    total_rows, valid_rows, error_rows
                )
                VALUES (
                    'HR_CONTROL_LIST', :file_name, :import_code, :imported_by, 'PARSED',
                    1, 1, 0
                )
                RETURNING batch_id
                """
            ),
            params,
        ).scalar_one()
    return int(batch_id)


def seed_import_row(
    conn: Connection,
    *,
    batch_id: int,
    full_name: str,
    iin: str,
    position: str,
    department: str = "Test Dept",
    org_unit_id: int,
) -> int:
    employee_id = conn.execute(
        text(
            """
            INSERT INTO public.employees (full_name, org_unit_id, is_active, employment_rate)
            VALUES (:full_name, :org_unit_id, TRUE, 1.00)
            RETURNING employee_id
            """
        ),
        {"full_name": full_name, "org_unit_id": org_unit_id},
    ).scalar_one()

    normalized = {
        "full_name": full_name,
        "iin": iin,
        "position_raw": position,
        "department": department,
        "metadata": {
            "row_type": "EMPLOYEE",
            "is_employee_roster": True,
            "classification": "NORMAL",
            "sheet_type": "doctors",
        },
    }
    row_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_import_rows (
                batch_id, source_sheet, source_row_number,
                raw_payload, normalized_payload, match_status, employee_id
            )
            VALUES (
                :batch_id, 'doctors', 8,
                CAST(:raw_payload AS jsonb),
                CAST(:normalized_payload AS jsonb),
                'AUTO_MATCH', :employee_id
            )
            RETURNING row_id
            """
        ),
        {
            "batch_id": batch_id,
            "raw_payload": __import__("json").dumps(normalized, ensure_ascii=False),
            "normalized_payload": __import__("json").dumps(normalized, ensure_ascii=False),
            "employee_id": employee_id,
        },
    ).scalar_one()
    return int(row_id)


def seed_closed_mrd(
    conn: Connection,
    *,
    report_period: date,
    created_by: int,
    version: int,
    closed_by: int,
) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.hr_monthly_references (
                report_period, version, status, created_by, closed_by, closed_at
            )
            VALUES (
                :report_period, :version, 'CLOSED', :created_by, :closed_by, NOW()
            )
            RETURNING mrd_id
            """
        ),
        {
            "report_period": report_period,
            "version": version,
            "created_by": created_by,
            "closed_by": closed_by,
        },
    ).scalar_one()
    return int(row)


def mrd_command_table_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_mrd_command_executions'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def purge_mrd_report_period(conn: Connection, report_period: date) -> None:
    """Test cleanup: delete all MRD versions for a report period."""
    initial_ids = [
        int(row)
        for row in conn.execute(
            text(
                """
                SELECT mrd_id
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                """
            ),
            {"report_period": report_period},
        ).scalars()
    ]
    if not initial_ids:
        return

    conn.execute(
        text(
            """
            UPDATE public.hr_monthly_references
            SET forked_from_reference_id = NULL
            WHERE forked_from_reference_id = ANY(:mrd_ids)
            """
        ),
        {"mrd_ids": initial_ids},
    )
    conn.execute(
        text(
            """
            UPDATE public.hr_monthly_references
            SET forked_from_reference_id = NULL
            WHERE report_period = :report_period
            """
        ),
        {"report_period": report_period},
    )

    conn.execute(
        text(
            """
            DELETE FROM public.hr_comparison_runs
            WHERE mrd_id = ANY(:mrd_ids)
            """
        ),
        {"mrd_ids": initial_ids},
    )
    conn.execute(
        text(
            """
            DELETE FROM public.hr_reference_version_events
            WHERE report_period = :report_period
               OR mrd_id = ANY(:mrd_ids)
               OR source_mrd_id = ANY(:mrd_ids)
            """
        ),
        {"report_period": report_period, "mrd_ids": initial_ids},
    )
    conn.execute(
        text(
            """
            DELETE FROM public.hr_mrd_command_executions
            WHERE (result_payload->>'source_mrd_id')::bigint = ANY(:mrd_ids)
               OR (result_payload->>'target_mrd_id')::bigint = ANY(:mrd_ids)
            """
        ),
        {"mrd_ids": initial_ids},
    )

    while True:
        mrd_rows = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT mrd_id, status, version, created_by
                    FROM public.hr_monthly_references
                    WHERE report_period = :report_period
                    ORDER BY version ASC
                    """
                ),
                {"report_period": report_period},
            ).mappings()
        ]
        if not mrd_rows:
            break

        closed_rows = [row for row in mrd_rows if row["status"] == "CLOSED"]
        active_row = next((row for row in mrd_rows if row["status"] == "ACTIVE"), None)
        target = closed_rows[0] if closed_rows else mrd_rows[0]

        if target["status"] == "CLOSED":
            if active_row is not None:
                conn.execute(
                    text(
                        """
                        UPDATE public.hr_monthly_references
                        SET status = 'CLOSED',
                            closed_at = NOW(),
                            closed_by = :closed_by
                        WHERE mrd_id = :mrd_id
                        """
                    ),
                    {
                        "mrd_id": active_row["mrd_id"],
                        "closed_by": active_row["created_by"],
                    },
                )
            conn.execute(
                text(
                    """
                    UPDATE public.hr_monthly_references
                    SET status = 'ACTIVE',
                        closed_at = NULL,
                        closed_by = NULL
                    WHERE mrd_id = :mrd_id
                    """
                ),
                {"mrd_id": target["mrd_id"]},
            )

        mrd_id = int(target["mrd_id"])
        conn.execute(
            text("DELETE FROM public.hr_detected_differences WHERE mrd_id = :mrd_id"),
            {"mrd_id": mrd_id},
        )
        conn.execute(
            text("DELETE FROM public.hr_monthly_reference_entries WHERE mrd_id = :mrd_id"),
            {"mrd_id": mrd_id},
        )
        conn.execute(
            text("DELETE FROM public.hr_monthly_references WHERE mrd_id = :mrd_id"),
            {"mrd_id": mrd_id},
        )


def insert_detected_difference(
    conn: Connection,
    *,
    report_period: date,
    mrd_id: int,
    logical_key: str,
    entity_scope: str,
    attribute: str,
    business_type: str,
    old_value,
    new_value,
    lifecycle_status: str = "DETECTED",
    technical_diff_class: str = "CHANGED",
    origin_context: dict | None = None,
) -> int:
    repo = SqlAlchemyMrdRepository(conn)
    if lifecycle_status == "DETECTED":
        row = repo.insert_difference(
            __import__("app.mrd.domain.difference_models", fromlist=["CreateDifferenceCommand"]).CreateDifferenceCommand(
                report_period=report_period,
                mrd_id=mrd_id,
                logical_key=logical_key,
                entity_scope=entity_scope,
                attribute=attribute,
                business_type=business_type,
                difference_origin_code=ORIGIN_IMPORT_COMPARE,
                origin_context=origin_context or {"batch_id": 1, "match_key": entity_scope},
                old_value=old_value,
                new_value=new_value,
                record_kind="roster",
                technical_diff_class=technical_diff_class,
            )
        )
        return row.difference_id
    raise ValueError("use repo helpers for non-DETECTED seed")


def release_test_mrd(conn: Connection, mrd_id: int) -> None:
    """Test cleanup: supersede differences and detach MRD from ephemeral test user."""
    conn.execute(
        text(
            """
            UPDATE public.hr_detected_differences
            SET lifecycle_status = 'SUPERSEDED'
            WHERE mrd_id = :mrd_id
            """
        ),
        {"mrd_id": mrd_id},
    )
    fallback_user = conn.execute(
        text("SELECT user_id FROM public.users ORDER BY user_id LIMIT 1")
    ).scalar_one_or_none()
    if fallback_user is not None:
        conn.execute(
            text(
                """
                UPDATE public.hr_monthly_references
                SET created_by = :created_by,
                    status = 'CLOSED',
                    closed_at = NOW(),
                    closed_by = :created_by
                WHERE mrd_id = :mrd_id
                """
            ),
            {"mrd_id": mrd_id, "created_by": int(fallback_user)},
        )

"""Prepare import batch with NEW/CONFLICT/REMOVED review exceptions for Phase 2 UI screenshots."""
from __future__ import annotations

import json

from sqlalchemy import text

from app.db.engine import engine
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_CONFLICT,
    DIFF_STATUS_NEW,
    compute_batch_monthly_diff,
)


def main() -> None:
    with engine.begin() as conn:
        batch_id = conn.execute(
            text(
                """
                SELECT batch_id
                FROM public.hr_import_rows
                GROUP BY batch_id
                ORDER BY COUNT(*) DESC, batch_id DESC
                LIMIT 1
                """
            )
        ).scalar_one_or_none()
        if batch_id is None:
            batch_id = conn.execute(
                text(
                    """
                    SELECT batch_id
                    FROM public.hr_import_batches
                    ORDER BY batch_id DESC
                    LIMIT 1
                    """
                )
            ).scalar_one_or_none()
        if batch_id is None:
            raise SystemExit("No import batches found")
        batch_id = int(batch_id)
        compute_batch_monthly_diff(conn, batch_id)
        rows = conn.execute(
            text(
                """
                SELECT row_id
                FROM public.hr_import_rows
                WHERE batch_id = :batch_id
                ORDER BY row_id
                LIMIT 3
                """
            ),
            {"batch_id": batch_id},
        ).scalars().all()
        if rows:
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET diff_status = :new_status,
                        employee_id = NULL,
                        field_diffs = NULL
                    WHERE batch_id = :batch_id
                      AND row_id = :row_id
                    """
                ),
                {"batch_id": batch_id, "row_id": rows[0], "new_status": DIFF_STATUS_NEW},
            )
        if len(rows) > 1:
            conn.execute(
                text(
                    """
                    UPDATE public.hr_import_rows
                    SET diff_status = :conflict,
                        field_diffs = CAST(:field_diffs AS JSONB)
                    WHERE batch_id = :batch_id
                      AND row_id = :row_id
                    """
                ),
                {
                    "batch_id": batch_id,
                    "row_id": rows[1],
                    "conflict": DIFF_STATUS_CONFLICT,
                    "field_diffs": json.dumps(
                        {"full_name": {"canonical": "Эталонное ФИО", "incoming": "Импортное ФИО"}}
                    ),
                },
            )
        pending_removals = conn.execute(
            text(
                """
                SELECT COUNT(*)::bigint
                FROM public.hr_import_diff_removals
                WHERE batch_id = :batch_id
                  AND decision IS NULL
                """
            ),
            {"batch_id": batch_id},
        ).scalar_one()
        print(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "prepared_rows": len(rows),
                    "pending_removals": int(pending_removals or 0),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()

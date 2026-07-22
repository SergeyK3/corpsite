"""Prepare ADR-059 Phase 1 UI verification batch (UNCHANGED-only, no gate blockers).

Prints JSON with batch_id/import_code. By default resets diff artifacts so UI
"Пересчитать diff" performs the auto-complete transition.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.hr_baseline import BATCH_DIFF_STATUS_NOT_COMPUTED
from app.db.models.hr_import import BATCH_STATUS_IN_REVIEW
from app.services.hr_import_complete_review_service import assess_complete_import_review
from app.services.hr_import_diff_removal_decision_service import count_pending_diff_removals
from app.services.hr_import_employee_binding_service import repair_batch_employee_bindings
from app.services.hr_import_monthly_diff_service import (
    DIFF_STATUS_UNCHANGED,
    compute_batch_monthly_diff,
    get_batch_diff_summary,
)
from app.services.hr_import_review_exception_service import count_unresolved_exceptions
from tests.test_hr_import_diff_removal_decisions import (
    _import_multi_employee_batch_named,
    _promote_and_snapshot_ready,
)
from tests.test_hr_import_phase_040b_monthly_diff_business_scenarios import _employee_spec


def _resolve_actor(user_id: int | None) -> dict:
    with engine.connect() as conn:
        if user_id is not None:
            row = conn.execute(
                text(
                    """
                    SELECT user_id, unit_id
                    FROM public.users
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            ).mappings().first()
            if row is None:
                raise SystemExit(f"user_id={user_id} not found")
            return {"initiator_user_id": int(row["user_id"]), "unit_id": int(row["unit_id"])}

        row = conn.execute(
            text(
                """
                SELECT user_id, unit_id
                FROM public.users
                ORDER BY user_id
                LIMIT 1
                """
            )
        ).mappings().one()
        return {"initiator_user_id": int(row["user_id"]), "unit_id": int(row["unit_id"])}


def _reset_batch_diff_for_ui_recalc(conn, batch_id: int) -> None:
    conn.execute(
        text("DELETE FROM public.hr_import_diff_removals WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    )
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET diff_status = NULL
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    )
    conn.execute(
        text(
            """
            UPDATE public.hr_import_normalized_records
            SET diff_status = NULL
            WHERE batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    )
    conn.execute(
        text(
            """
            UPDATE public.hr_import_batches
            SET status = :in_review,
                diff_status = :not_computed,
                comparison_baseline_id = NULL,
                comparison_publication_origin_id = NULL
            WHERE batch_id = :batch_id
            """
        ),
        {
            "batch_id": batch_id,
            "in_review": BATCH_STATUS_IN_REVIEW,
            "not_computed": BATCH_DIFF_STATUS_NOT_COMPUTED,
        },
    )


def _pick_fresh_yymm(conn) -> str:
    for attempt in range(24):
        month = ((int(uuid4().hex[:6], 16) + attempt) % 12) + 1
        yymm = f"26{month:02d}"
        occupied = conn.execute(
            text(
                """
                SELECT 1
                FROM public.hr_import_batches
                WHERE import_code LIKE :prefix
                LIMIT 1
                """
            ),
            {"prefix": f"{yymm}-%"},
        ).first()
        if occupied is None:
            return yymm
    raise RuntimeError("Could not allocate a fresh YYMM for UI batch")


def prepare_batch(*, actor_user_id: int | None, reset_for_ui: bool) -> dict:
    seed = _resolve_actor(actor_user_id)
    suffix = uuid4().hex[:8]
    with engine.connect() as conn:
        yymm = _pick_fresh_yymm(conn)
    department = f"ADR059 Phase1 UI {suffix}"
    employee = _employee_spec(label="GateUi", suffix=suffix, position="Врач терапевт")
    tmpdir = Path(tempfile.mkdtemp(prefix="adr059_ui_"))

    batch_baseline = _import_multi_employee_batch_named(
        seed,
        tmpdir,
        rows=[employee],
        department=department,
        yymm=yymm,
    )
    _promote_and_snapshot_ready(seed, batch_baseline)

    batch_review = _import_multi_employee_batch_named(
        seed,
        tmpdir,
        rows=[employee],
        department=department,
        yymm=yymm,
    )

    with engine.begin() as conn:
        repair_batch_employee_bindings(conn, batch_review)
        verify_diff = compute_batch_monthly_diff(conn, batch_review)
        import_code = str(
            conn.execute(
                text(
                    """
                    SELECT import_code
                    FROM public.hr_import_batches
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_review},
            ).scalar_one()
        )
        summary_after_verify = get_batch_diff_summary(conn, batch_review)
        status_after_verify = str(
            conn.execute(
                text(
                    """
                    SELECT status
                    FROM public.hr_import_batches
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_review},
            ).scalar_one()
        )
        pending_normalized = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_import_normalized_records
                    WHERE batch_id = :batch_id
                      AND review_status = 'pending'
                    """
                ),
                {"batch_id": batch_review},
            ).scalar_one()
            or 0
        )

        if reset_for_ui:
            _reset_batch_diff_for_ui_recalc(conn, batch_review)

        summary_for_ui = get_batch_diff_summary(conn, batch_review)
        status_for_ui = str(
            conn.execute(
                text(
                    """
                    SELECT status
                    FROM public.hr_import_batches
                    WHERE batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_review},
            ).scalar_one()
        )
        assessment = assess_complete_import_review(conn, import_code)

    diff_counts = summary_after_verify.get("summary") or {}
    visibility = summary_after_verify.get("review_visibility") or {}
    auto_complete = (verify_diff or {}).get("auto_complete_review") or {}

    return {
        "baseline_batch_id": batch_baseline,
        "batch_id": batch_review,
        "import_code": import_code,
        "yymm": yymm,
        "actor_user_id": seed["initiator_user_id"],
        "department": department,
        "employee_iin": employee["iin"],
        "verify_diff_summary": diff_counts,
        "verify_review_visibility": visibility,
        "verify_status_after_diff": status_after_verify,
        "verify_auto_complete": (verify_diff or {}).get("auto_complete_review"),
        "ui_ready_status": status_for_ui,
        "ui_ready_diff_summary": summary_for_ui.get("summary"),
        "pending_normalized": pending_normalized,
        "assessment_blockers_for_ui": [item["code"] for item in assessment["blockers"]],
        "review_progress_for_ui": assessment.get("review_progress"),
        "scenario_valid": (
            int(diff_counts.get("UNCHANGED", 0) or 0) > 0
            and int(diff_counts.get("CHANGED", 0) or 0) == 0
            and int(diff_counts.get("CONFLICT", 0) or 0) == 0
            and int(diff_counts.get("REMOVED", 0) or 0) == 0
            and int(visibility.get("visible_records", 0) or 0) == 0
            and auto_complete.get("auto_completed") is True
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, default=34)
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Keep computed diff/status (skip UI recalc setup).",
    )
    args = parser.parse_args()
    payload = prepare_batch(actor_user_id=args.user_id, reset_for_ui=not args.no_reset)
    with engine.connect() as conn:
        payload["pending_removals_for_ui"] = count_pending_diff_removals(conn, payload["batch_id"])
        payload["unresolved_for_ui"] = count_unresolved_exceptions(conn, payload["batch_id"])
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()

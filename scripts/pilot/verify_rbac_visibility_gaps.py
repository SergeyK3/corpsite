#!/usr/bin/env python3
"""Verify RBAC visibility gaps after rbac_visibility_gaps_fixture.sql."""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import text

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from app.db.engine import engine  # noqa: E402
from app.services.tasks_service import (  # noqa: E402
    _is_task_visible_to_user,
    ensure_task_visible_or_404,
    get_user_role_id,
    load_task_full,
)
from app.services.tasks_router import (  # noqa: E402
    _user_is_approver_for_task,
    _user_reported_task,
)

FIXTURE_CASES = (
    {
        "case": "1_pure_legacy_approver",
        "user_id": 5,
        "task_id": 10001,
        "list_predicate": "legacy_approver_visibility",
        "ensure_gap_predicate": "_can_view (missing legacy target_role_id check)",
    },
    {
        "case": "2_historical_report_author",
        "user_id": 3,
        "task_id": 10002,
        "list_predicate": "report_visibility (EXISTS any report by user)",
        "ensure_gap_predicate": "_is_report_author (latest report_submitted_by only)",
    },
)


def list_mine(conn, user_id: int, role_id: int, task_id: int) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public.tasks t
                    LEFT JOIN public.task_statuses ts ON ts.status_id = t.status_id
                    WHERE t.task_id = :task_id
                      AND (
                        (t.executor_role_id = :role_id)
                        OR EXISTS (
                            SELECT 1 FROM public.task_reports rr
                            WHERE rr.task_id = t.task_id AND rr.submitted_by = :uid
                        )
                        OR (
                            COALESCE(t.approver_user_id, 0) = :uid
                            AND COALESCE(ts.code, '') = 'WAITING_APPROVAL'
                        )
                        OR (
                            EXISTS (
                                SELECT 1 FROM public.regular_tasks rt2
                                WHERE rt2.regular_task_id = t.regular_task_id
                                  AND COALESCE(rt2.target_role_id, 0) = :role_id
                            )
                            AND COALESCE(ts.code, '') = 'WAITING_APPROVAL'
                        )
                      )
                ) AS ok
                """
            ),
            {"task_id": task_id, "uid": user_id, "role_id": role_id},
        ).scalar()
    )


def simulate_get(conn, user_id: int, role_id: int, task_id: int) -> Dict[str, Any]:
    task = load_task_full(conn, task_id=task_id)
    try:
        ensure_task_visible_or_404(
            conn=conn,
            current_user_id=user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=True,
        )
        return {"status": 200, "via": "ensure"}
    except HTTPException as exc:
        if exc.status_code not in (403, 404):
            return {"status": exc.status_code, "via": "ensure_error"}
        if _user_reported_task(conn, task_id=task_id, user_id=user_id):
            return {"status": 200, "via": "fallback_report"}
        if _user_is_approver_for_task(conn, task_id=task_id, user_id=user_id, role_id=role_id):
            return {"status": 200, "via": "fallback_approver"}
        return {"status": 404, "via": "ensure_no_fallback"}


def simulate_ensure_only(conn, user_id: int, role_id: int, task_id: int) -> int:
    task = load_task_full(conn, task_id=task_id)
    try:
        ensure_task_visible_or_404(
            conn=conn,
            current_user_id=user_id,
            current_role_id=role_id,
            task_row=task,
            include_archived=False,
        )
        return 200
    except HTTPException as exc:
        return int(exc.status_code)


def predicate_flags(conn, user_id: int, role_id: int, task_id: int, task_row: Dict[str, Any]) -> Dict[str, bool]:
    status = str(task_row.get("status_code") or "")
    executor_role_id = int(task_row.get("executor_role_id") or 0)

    legacy = conn.execute(
        text(
            """
            SELECT COALESCE(rt.target_role_id, 0) AS target_role_id
            FROM public.tasks t
            LEFT JOIN public.regular_tasks rt ON rt.regular_task_id = t.regular_task_id
            WHERE t.task_id = :task_id
            """
        ),
        {"task_id": task_id},
    ).mappings().first()

    has_any_report = (
        conn.execute(
            text(
                "SELECT 1 FROM public.task_reports WHERE task_id=:tid AND submitted_by=:uid LIMIT 1"
            ),
            {"tid": task_id, "uid": user_id},
        ).first()
        is not None
    )
    latest_by = task_row.get("report_submitted_by")
    is_latest_report = latest_by is not None and int(latest_by) == int(user_id)

    return {
        "list_executor_role_eq": executor_role_id == int(role_id),
        "list_report_exists": has_any_report,
        "list_legacy_approver": bool(
            legacy
            and int(legacy["target_role_id"]) == int(role_id)
            and status == "WAITING_APPROVAL"
        ),
        "ensure_can_view": _is_task_visible_to_user(
            conn,
            current_user_id=user_id,
            current_role_id=role_id,
            task_row=task_row,
        ),
        "ensure_is_latest_report_author": is_latest_report,
        "ensure_team_scope": False,
    }


def main() -> int:
    results: List[Dict[str, Any]] = []

    with engine.begin() as conn:
        for case in FIXTURE_CASES:
            uid = int(case["user_id"])
            tid = int(case["task_id"])
            rid = get_user_role_id(conn, uid)
            task = load_task_full(conn, task_id=tid)
            if not task:
                print(f"MISSING fixture task_id={tid}")
                return 1

            flags = predicate_flags(conn, uid, rid, tid, task)
            row = {
                **case,
                "role_id": rid,
                "list_mine": list_mine(conn, uid, rid, tid),
                "GET": simulate_get(conn, uid, rid, tid),
                "POST_report_ensure_only": simulate_ensure_only(conn, uid, rid, tid),
                "PATCH_ensure_only": simulate_ensure_only(conn, uid, rid, tid),
                "predicates": flags,
            }
            row["gap_confirmed"] = bool(row["list_mine"] and not flags["ensure_can_view"])
            results.append(row)

    print("RBAC visibility gap verification\n")
    for row in results:
        print("=" * 72)
        print(f"Case: {row['case']}")
        print(f"Pair: user_id={row['user_id']} role_id={row['role_id']} task_id={row['task_id']}")
        print(f"list_mine (GET /tasks?scope=mine): {row['list_mine']}")
        print(f"ensure._can_view: {row['predicates']['ensure_can_view']}")
        print(f"Gap confirmed (list yes, ensure no): {row['gap_confirmed']}")
        print(f"List predicate: {row['list_predicate']}")
        print(f"Ensure gap predicate: {row['ensure_gap_predicate']}")
        print("Predicate flags:")
        for k, v in row["predicates"].items():
            print(f"  {k}: {v}")
        print(f"GET /tasks/{{id}} (with router fallbacks): {row['GET']}")
        endpoint_404 = []
        if row["GET"]["status"] == 404:
            endpoint_404.append("GET /tasks/{id}")
        if row["POST_report_ensure_only"] == 404:
            endpoint_404.append("POST /tasks/{id}/report")
        if row["PATCH_ensure_only"] == 404:
            endpoint_404.append("PATCH /tasks/{id}")
        print(f"Endpoints returning 404 (ensure-only where noted): {endpoint_404 or ['none — GET saved by router fallback']}")

    ok = all(r["list_mine"] and r["predicates"]["ensure_can_view"] for r in results)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

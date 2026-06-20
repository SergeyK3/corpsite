"""ADR-042 Phase B3 — assignment snapshot reconciliation (dry-run default)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

_SNAPSHOT_FIELDS = (
    ("org_unit_id", "org_unit_id"),
    ("position_id", "position_id"),
    ("employment_rate", "rate"),
    ("date_from", "start_date"),
    ("date_to", "end_date"),
)


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table
                LIMIT 1
                """
            ),
            {"table": table},
        ).first()
        is not None
    )


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _values_differ(left: Any, right: Any) -> bool:
    nl = _normalize_value(left)
    nr = _normalize_value(right)
    if nl is None and nr is None:
        return False
    if isinstance(nl, float) and isinstance(nr, float):
        return abs(nl - nr) > 1e-9
    return nl != nr


def compare_employee_snapshot_to_primary_assignment(employee_id: int) -> Dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    e.employee_id,
                    e.person_id,
                    e.full_name,
                    e.org_unit_id,
                    e.position_id,
                    e.employment_rate,
                    e.date_from,
                    e.date_to,
                    e.is_active,
                    pa.assignment_id,
                    pa.org_unit_id AS pa_org_unit_id,
                    pa.position_id AS pa_position_id,
                    pa.rate AS pa_rate,
                    pa.start_date AS pa_start_date,
                    pa.end_date AS pa_end_date,
                    pa.active_flag,
                    pa.is_primary
                FROM public.employees e
                LEFT JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                 AND pa.is_primary = TRUE
                 AND pa.lifecycle_status = 'active'
                WHERE e.employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"employee_id": int(employee_id)},
        ).mappings().first()

    if not row:
        raise ValueError(f"Employee not found: {employee_id}")

    data = dict(row)
    if data.get("assignment_id") is None:
        return {
            "employee_id": int(employee_id),
            "has_primary_assignment": False,
            "has_drift": False,
            "diff": {},
            "employee": data,
        }

    diff: Dict[str, Dict[str, Any]] = {}
    mapping = {
        "org_unit_id": ("org_unit_id", "pa_org_unit_id"),
        "position_id": ("position_id", "pa_position_id"),
        "employment_rate": ("employment_rate", "pa_rate"),
        "date_from": ("date_from", "pa_start_date"),
        "date_to": ("date_to", "pa_end_date"),
    }
    for field, (emp_col, pa_col) in mapping.items():
        emp_val = data.get(emp_col)
        pa_val = data.get(pa_col)
        if _values_differ(emp_val, pa_val):
            diff[field] = {"employee": emp_val, "assignment": pa_val}

    return {
        "employee_id": int(employee_id),
        "person_id": data.get("person_id"),
        "assignment_id": int(data["assignment_id"]),
        "has_primary_assignment": True,
        "has_drift": bool(diff),
        "diff": diff,
    }


def list_assignment_drift(*, limit: int = 500, offset: int = 0) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 2000))
    offset = max(0, int(offset))

    with engine.connect() as conn:
        if not _table_exists(conn, "person_assignments"):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        rows = conn.execute(
            text(
                """
                SELECT e.employee_id
                FROM public.employees e
                JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                 AND pa.is_primary = TRUE
                 AND pa.lifecycle_status = 'active'
                WHERE e.person_id IS NOT NULL
                  AND (
                      e.org_unit_id IS DISTINCT FROM pa.org_unit_id
                      OR e.position_id IS DISTINCT FROM pa.position_id
                      OR e.employment_rate IS DISTINCT FROM pa.rate
                      OR e.date_from IS DISTINCT FROM pa.start_date
                      OR e.date_to IS DISTINCT FROM pa.end_date
                  )
                ORDER BY e.employee_id
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).scalars().all()

        total = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.employees e
                    JOIN public.person_assignments pa
                      ON pa.person_id = e.person_id
                     AND pa.is_primary = TRUE
                     AND pa.lifecycle_status = 'active'
                    WHERE e.person_id IS NOT NULL
                      AND (
                          e.org_unit_id IS DISTINCT FROM pa.org_unit_id
                          OR e.position_id IS DISTINCT FROM pa.position_id
                          OR e.employment_rate IS DISTINCT FROM pa.rate
                          OR e.date_from IS DISTINCT FROM pa.start_date
                          OR e.date_to IS DISTINCT FROM pa.end_date
                      )
                    """
                )
            ).scalar_one()
        )

    items = [compare_employee_snapshot_to_primary_assignment(int(eid)) for eid in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def reconcile_employee_primary_assignment(
    employee_id: int,
    *,
    dry_run: bool = True,
    actor_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    comparison = compare_employee_snapshot_to_primary_assignment(int(employee_id))
    if not comparison.get("has_primary_assignment"):
        return {**comparison, "applied": False, "dry_run": dry_run, "reason": "no_primary_assignment"}
    if not comparison.get("has_drift"):
        return {**comparison, "applied": False, "dry_run": dry_run, "reason": "no_drift"}

    diff = comparison["diff"]
    if dry_run:
        return {
            **comparison,
            "applied": False,
            "dry_run": True,
            "would_update": {k: v["assignment"] for k, v in diff.items()},
        }

    with engine.begin() as conn:
        pa = conn.execute(
            text(
                """
                SELECT
                    pa.org_unit_id,
                    pa.position_id,
                    pa.rate,
                    pa.start_date,
                    pa.end_date,
                    p.full_name
                FROM public.employees e
                JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                 AND pa.is_primary = TRUE
                 AND pa.lifecycle_status = 'active'
                LEFT JOIN public.persons p ON p.person_id = e.person_id
                WHERE e.employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"employee_id": int(employee_id)},
        ).mappings().first()
        if not pa:
            return {**comparison, "applied": False, "dry_run": False, "reason": "assignment_missing"}

        conn.execute(
            text(
                """
                UPDATE public.employees
                SET
                    org_unit_id = :org_unit_id,
                    position_id = :position_id,
                    employment_rate = :rate,
                    date_from = :start_date,
                    date_to = :end_date,
                    full_name = COALESCE(:full_name, full_name),
                    updated_at = now()
                WHERE employee_id = :employee_id
                """
            ),
            {
                "employee_id": int(employee_id),
                "org_unit_id": pa["org_unit_id"],
                "position_id": pa["position_id"],
                "rate": pa["rate"],
                "start_date": pa["start_date"],
                "end_date": pa["end_date"],
                "full_name": pa.get("full_name"),
            },
        )

        write_security_event(
            event_type="ACCESS_CHANGED",
            actor_user_id=actor_user_id,
            target_employee_id=int(employee_id),
            metadata={
                "action": "assignment_reconciled",
                "employee_id": int(employee_id),
                "diff_fields": list(diff.keys()),
                "dry_run": False,
            },
            conn=conn,
        )

    after = compare_employee_snapshot_to_primary_assignment(int(employee_id))
    return {
        **after,
        "applied": True,
        "dry_run": False,
        "previous_diff": diff,
    }


def reconcile_all(
    *,
    dry_run: bool = True,
    actor_user_id: Optional[int] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    drift = list_assignment_drift(limit=limit, offset=0)
    results: List[Dict[str, Any]] = []
    applied_count = 0

    for item in drift["items"]:
        eid = int(item["employee_id"])
        result = reconcile_employee_primary_assignment(
            eid,
            dry_run=dry_run,
            actor_user_id=actor_user_id,
        )
        results.append(result)
        if result.get("applied"):
            applied_count += 1

    return {
        "dry_run": dry_run,
        "total_drift": drift["total"],
        "processed": len(results),
        "applied_count": applied_count,
        "results": results,
    }

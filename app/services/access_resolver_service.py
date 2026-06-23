"""ADR-042 Phase B3 — effective access resolver (read-only, no enforcement)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text

from app.db.engine import engine

IMPLICIT_NONE = {
    "effective_role_code": "IMPLICIT_NONE",
    "access_level": "NONE",
    "level_rank": 0,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _fetch_user_context(conn, user_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                u.user_id,
                u.role_id,
                u.employee_id,
                e.person_id,
                e.operational_status
            FROM public.users u
            LEFT JOIN public.employees e ON e.employee_id = u.employee_id
            WHERE u.user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": int(user_id)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_person_context(conn, person_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT person_id, full_name, person_status, match_key
            FROM public.persons
            WHERE person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    return dict(row) if row else None


def _collect_subject_ids(
    conn,
    *,
    user_id: Optional[int],
    employee_id: Optional[int],
    person_id: Optional[int],
    role_id: Optional[int] = None,
) -> Dict[str, Set[int]]:
    subjects: Dict[str, Set[int]] = {
        "USER": set(),
        "ROLE": set(),
        "EMPLOYEE": set(),
        "PERSON": set(),
        "ASSIGNMENT": set(),
        "POSITION": set(),
        "ORG_UNIT": set(),
    }

    if user_id is not None:
        subjects["USER"].add(int(user_id))
    if role_id is not None:
        subjects["ROLE"].add(int(role_id))
    if employee_id is not None:
        subjects["EMPLOYEE"].add(int(employee_id))
    if person_id is not None:
        subjects["PERSON"].add(int(person_id))

        assignment_rows = conn.execute(
            text(
                """
                SELECT pa.assignment_id, pa.position_id, pa.org_unit_id
                FROM public.person_assignments pa
                WHERE pa.person_id = :person_id
                  AND pa.active_flag = TRUE
                  AND pa.lifecycle_status = 'active'
                """
            ),
            {"person_id": int(person_id)},
        ).mappings().all()
        for ar in assignment_rows:
            subjects["ASSIGNMENT"].add(int(ar["assignment_id"]))
            if ar["position_id"] is not None:
                subjects["POSITION"].add(int(ar["position_id"]))
            if ar["org_unit_id"] is not None:
                subjects["ORG_UNIT"].add(int(ar["org_unit_id"]))

    if employee_id is not None and person_id is None:
        emp = conn.execute(
            text(
                """
                SELECT person_id FROM public.employees
                WHERE employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"employee_id": int(employee_id)},
        ).mappings().first()
        if emp and emp["person_id"] is not None:
            nested = _collect_subject_ids(
                conn,
                user_id=user_id,
                employee_id=employee_id,
                person_id=int(emp["person_id"]),
                role_id=role_id,
            )
            for key, values in nested.items():
                subjects[key].update(values)

    return subjects


def _load_active_grants(conn, subjects: Dict[str, Set[int]]) -> List[Dict[str, Any]]:
    clauses: List[str] = []
    params: Dict[str, Any] = {}

    idx = 0
    for target_type, ids in subjects.items():
        if not ids:
            continue
        key = f"ids_{idx}"
        clauses.append(f"(g.target_type = :tt_{idx} AND g.target_id = ANY(:{key}))")
        params[f"tt_{idx}"] = target_type
        params[key] = list(ids)
        idx += 1

    if not clauses:
        return []

    where_targets = " OR ".join(clauses)
    rows = conn.execute(
        text(
            f"""
            SELECT
                g.grant_id,
                g.access_role_id,
                r.code AS access_role_code,
                r.access_level,
                r.level_rank,
                g.target_type,
                g.target_id,
                g.resource_key,
                g.scope_type,
                g.scope_id,
                g.include_subtree,
                g.starts_at,
                g.ends_at,
                g.reason
            FROM public.access_grants g
            JOIN public.access_roles r ON r.access_role_id = g.access_role_id
            WHERE g.active_flag = TRUE
              AND g.starts_at <= now()
              AND (g.ends_at IS NULL OR g.ends_at > now())
              AND r.is_active = TRUE
              AND ({where_targets})
            ORDER BY r.level_rank DESC, g.grant_id
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


def _resolve_from_grants(
    grants: List[Dict[str, Any]],
) -> Dict[str, Any]:
    deny_grants = [g for g in grants if g.get("access_level") == "NONE"]
    allow_grants = [g for g in grants if g.get("access_level") != "NONE"]

    if not allow_grants:
        result = dict(IMPLICIT_NONE)
        result["matched_grants"] = []
        result["deny_grants"] = deny_grants
        result["explanation"] = {
            "summary": "No active allow grants matched; implicit NONE.",
            "deny_enforcement_applied": False,
            "note": (
                "Explicit ACCESS_NONE deny grants are listed but not applied "
                "to effective rank in Phase B3."
            ),
        }
        return result

    best = max(allow_grants, key=lambda g: int(g["level_rank"]))
    matched = [g for g in allow_grants if int(g["level_rank"]) == int(best["level_rank"])]

    return {
        "effective_role_code": best["access_role_code"],
        "access_level": best["access_level"],
        "level_rank": int(best["level_rank"]),
        "matched_grants": matched,
        "deny_grants": deny_grants,
        "explanation": {
            "summary": f"Effective access = MAX(level_rank) = {best['level_rank']} ({best['access_level']}).",
            "winning_grant_ids": [int(g["grant_id"]) for g in matched],
            "deny_enforcement_applied": False,
            "deny_grant_count": len(deny_grants),
        },
    }


def resolve_person_access(person_id: int) -> Dict[str, Any]:
    with engine.connect() as conn:
        if not _table_exists(conn, "access_grants"):
            return {**IMPLICIT_NONE, "matched_grants": [], "deny_grants": [], "explanation": {"error": "tables missing"}}

        person = _fetch_person_context(conn, int(person_id))
        if not person:
            raise ValueError(f"Person not found: {person_id}")

        subjects = _collect_subject_ids(conn, user_id=None, employee_id=None, person_id=int(person_id))
        grants = _load_active_grants(conn, subjects)
        result = _resolve_from_grants(grants)
        result["person_id"] = int(person_id)
        result["subjects"] = {k: sorted(v) for k, v in subjects.items()}
        return result


def resolve_effective_access(user_id: int) -> Dict[str, Any]:
    with engine.connect() as conn:
        if not _table_exists(conn, "access_grants"):
            return {**IMPLICIT_NONE, "matched_grants": [], "deny_grants": [], "explanation": {"error": "tables missing"}}

        ctx = _fetch_user_context(conn, int(user_id))
        if not ctx:
            raise ValueError(f"User not found: {user_id}")

        employee_id = int(ctx["employee_id"]) if ctx.get("employee_id") is not None else None
        person_id = int(ctx["person_id"]) if ctx.get("person_id") is not None else None
        role_id = int(ctx["role_id"]) if ctx.get("role_id") is not None else None

        subjects = _collect_subject_ids(
            conn,
            user_id=int(user_id),
            employee_id=employee_id,
            person_id=person_id,
            role_id=role_id,
        )
        grants = _load_active_grants(conn, subjects)
        result = _resolve_from_grants(grants)
        result["user_id"] = int(user_id)
        result["employee_id"] = employee_id
        result["person_id"] = person_id
        result["subjects"] = {k: sorted(v) for k, v in subjects.items()}
        return result


def list_active_access_role_codes(user_id: int) -> List[str]:
    """Return distinct access_role codes from active allow grants for the user."""
    with engine.connect() as conn:
        if not _table_exists(conn, "access_grants"):
            return []

        ctx = _fetch_user_context(conn, int(user_id))
        if not ctx:
            raise ValueError(f"User not found: {user_id}")

        employee_id = int(ctx["employee_id"]) if ctx.get("employee_id") is not None else None
        person_id = int(ctx["person_id"]) if ctx.get("person_id") is not None else None
        role_id = int(ctx["role_id"]) if ctx.get("role_id") is not None else None

        subjects = _collect_subject_ids(
            conn,
            user_id=int(user_id),
            employee_id=employee_id,
            person_id=person_id,
            role_id=role_id,
        )
        grants = _load_active_grants(conn, subjects)

    codes = sorted(
        {
            str(g["access_role_code"])
            for g in grants
            if g.get("access_level") != "NONE" and g.get("access_role_code")
        }
    )
    return codes


def explain_effective_access(
    *,
    user_id: Optional[int] = None,
    person_id: Optional[int] = None,
) -> Dict[str, Any]:
    if user_id is not None and person_id is not None:
        raise ValueError("Provide user_id or person_id, not both.")
    if user_id is None and person_id is None:
        raise ValueError("user_id or person_id is required.")

    if user_id is not None:
        base = resolve_effective_access(int(user_id))
        base["explain_mode"] = "user"
    else:
        base = resolve_person_access(int(person_id))
        base["explain_mode"] = "person"

    steps: List[str] = []
    subjects = base.get("subjects") or {}
    for stype, ids in subjects.items():
        if ids:
            steps.append(f"Collected {stype} targets: {ids}")

    matched = base.get("matched_grants") or []
    if matched:
        for g in matched:
            steps.append(
                f"Grant #{g['grant_id']}: {g['access_role_code']} "
                f"({g['access_level']}, rank={g['level_rank']}) "
                f"on {g['target_type']}:{g['target_id']} resource={g['resource_key']}"
            )
        base["explanation"]["resolution_sources"] = [
            {
                "grant_id": int(g["grant_id"]),
                "access_role_code": g["access_role_code"],
                "access_level": g["access_level"],
                "level_rank": int(g["level_rank"]),
                "source_type": g["target_type"],
                "target_id": int(g["target_id"]),
            }
            for g in matched
        ]
    else:
        steps.append("No matching allow grants → implicit NONE.")
        base["explanation"]["resolution_sources"] = []

    deny = base.get("deny_grants") or []
    if deny:
        steps.append(f"{len(deny)} explicit NONE/deny grant(s) present (not enforced in B3).")

    base["explanation"]["steps"] = steps
    return base

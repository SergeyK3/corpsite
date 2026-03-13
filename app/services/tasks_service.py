# FILE: app/services/tasks_service.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException
from sqlalchemy import bindparam, text

from app.db.engine import engine
from app.services.org_units_service import OrgUnitsService


SYSTEM_ADMIN_ROLE_ID = 2


def parse_int_set_env(name: str) -> Set[int]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return set()
    out: Set[int] = set()
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except Exception:
            pass
    return out


SUPERVISOR_ROLE_IDS: Set[int] = parse_int_set_env("SUPERVISOR_ROLE_IDS")
DEPUTY_ROLE_IDS: Set[int] = parse_int_set_env("DEPUTY_ROLE_IDS")
DIRECTOR_ROLE_IDS: Set[int] = parse_int_set_env("DIRECTOR_ROLE_IDS")


def is_system_admin_role_id(role_id: Any) -> bool:
    try:
        return int(role_id) == SYSTEM_ADMIN_ROLE_ID
    except Exception:
        return False


def get_current_user_id(x_user_id: Optional[int]) -> int:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    try:
        uid = int(x_user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="X-User-Id header must be an integer")
    if uid <= 0:
        raise HTTPException(status_code=401, detail="X-User-Id header must be a positive integer")
    return uid


def get_user_role_id(conn, user_id: int) -> int:
    row = conn.execute(
        text("SELECT user_id, role_id FROM users WHERE user_id = :uid"),
        {"uid": int(user_id)},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row["role_id"] is None:
        raise HTTPException(status_code=400, detail="User role_id is NULL")
    return int(row["role_id"])

def load_role_meta(conn, *, role_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT role_id, code, name
            FROM public.roles
            WHERE role_id = :rid
            """
        ),
        {"rid": int(role_id)},
    ).mappings().first()

    if not row:
        return {
            "role_id": int(role_id),
            "code": None,
            "name": None,
        }

    return dict(row)

def _looks_like_manager_role(*, role_code: Any, role_name: Any) -> bool:
    code = str(role_code or "").strip().upper()
    name = str(role_name or "").strip().lower()

    if code in {"ADMIN", "SYSTEM_ADMIN", "DIRECTOR"}:
        return True

    if code.startswith("DEP_"):
        return True

    if code.endswith("_HEAD"):
        return True

    if code.endswith("_HEAD_DEPUTY"):
        return True

    if code.endswith("_DEPUTY"):
        return True

    if "руководител" in name:
        return True

    if "директор" in name:
        return True

    if "заместител" in name:
        return True

    if "head" in name or "deputy" in name or "supervisor" in name:
        return True

    return False

def load_user_context(conn, *, user_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                u.user_id,
                u.role_id,
                u.unit_id,
                u.full_name,
                u.login,
                u.is_active
            FROM public.users u
            WHERE u.user_id = :uid
            """
        ),
        {"uid": int(user_id)},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return dict(row)


def get_status_id_by_code(conn, code: str) -> int:
    if code is None:
        raise HTTPException(status_code=400, detail="Unknown status code: None")

    normalized = str(code).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Unknown status code: ''")

    row = conn.execute(
        text(
            """
            SELECT status_id
            FROM task_statuses
            WHERE upper(trim(code)) = upper(trim(:code))
            """
        ),
        {"code": normalized},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=400, detail=f"Unknown status code: {code}")
    return int(row["status_id"])


def load_assignment_scope_enum_labels(conn) -> Set[str]:
    rows = conn.execute(
        text(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'assignment_scope_t'
            ORDER BY e.enumsortorder
            """
        )
    ).all()
    return {r[0] for r in rows}


def scope_label_or_none(allowed: Set[str], wanted_lower: str) -> Optional[str]:
    for lbl in allowed:
        if lbl.lower() == wanted_lower:
            return lbl
    return None


def _pick_default_scope(allowed: Set[str]) -> str:
    for lbl in allowed:
        if lbl.lower() == "functional":
            return lbl
    return sorted(allowed)[0]


def normalize_assignment_scope(conn, value: Any) -> str:
    allowed = load_assignment_scope_enum_labels(conn)
    if not allowed:
        raise HTTPException(status_code=500, detail="assignment_scope_t enum not found in DB")

    if value is None or (isinstance(value, str) and not value.strip()):
        return _pick_default_scope(allowed)

    raw = str(value).strip()

    if raw in allowed:
        return raw

    raw_l = raw.lower()
    for lbl in allowed:
        if lbl.lower() == raw_l:
            return lbl

    legacy_map = {
        "role": "functional",
        "any": "functional",
        "user": "admin",
    }
    if raw_l in legacy_map:
        target_l = legacy_map[raw_l].lower()
        mapped = scope_label_or_none(allowed, target_l)
        if mapped:
            return mapped

    raise HTTPException(
        status_code=422,
        detail=f"assignment_scope must be one of: {', '.join(sorted(allowed))}",
    )


def compute_visible_executor_role_ids_for_tasks(
    *,
    user_id: int,
    include_inactive_units: bool = False,
    include_inactive_users: bool = False,
) -> Set[int]:
    svc = OrgUnitsService(engine)
    return set(
        svc.compute_visible_executor_role_ids_for_tasks(
            user_id=int(user_id),
            include_inactive_units=bool(include_inactive_units),
            include_inactive_users=bool(include_inactive_users),
        )
    )


def _is_task_manager_role(
    *,
    current_user_id: int,
    current_role_id: int,
    visible_executor_role_ids: Set[int],
) -> bool:
    privileged_role_ids = parse_int_set_env("DIRECTORY_PRIVILEGED_ROLE_IDS")
    privileged_user_ids = parse_int_set_env("DIRECTORY_PRIVILEGED_USER_IDS")

    other_visible_roles = {
        int(x)
        for x in visible_executor_role_ids
        if int(x) > 0 and int(x) != int(current_role_id)
    }

    return (
        is_system_admin_role_id(current_role_id)
        or (int(current_user_id) in privileged_user_ids)
        or (int(current_role_id) in privileged_role_ids)
        or (int(current_role_id) in DIRECTOR_ROLE_IDS)
        or (int(current_role_id) in DEPUTY_ROLE_IDS)
        or (int(current_role_id) in SUPERVISOR_ROLE_IDS)
        or bool(other_visible_roles)
    )


def can_view_team_tasks(
    conn,
    *,
    current_user_id: int,
    current_role_id: int,
) -> bool:
    if is_system_admin_role_id(current_role_id):
        return True

    role_meta = load_role_meta(conn, role_id=int(current_role_id))
    if _looks_like_manager_role(
        role_code=role_meta.get("code"),
        role_name=role_meta.get("name"),
    ):
        return True

    visible_roles = compute_visible_executor_role_ids_for_tasks(user_id=int(current_user_id))
    return _is_task_manager_role(
        current_user_id=int(current_user_id),
        current_role_id=int(current_role_id),
        visible_executor_role_ids=visible_roles,
    )

def get_team_scope_context(
    conn,
    *,
    current_user_id: int,
    current_role_id: int,
) -> Dict[str, Any]:
    if not can_view_team_tasks(
        conn,
        current_user_id=int(current_user_id),
        current_role_id=int(current_role_id),
    ):
        raise HTTPException(status_code=403, detail="Team task scope is not allowed")

    user_ctx = load_user_context(conn, user_id=int(current_user_id))
    current_unit_id = int(user_ctx["unit_id"]) if user_ctx.get("unit_id") is not None else None

    if current_unit_id is None:
        if is_system_admin_role_id(current_role_id):
            return {
                "current_unit_id": None,
                "team_user_ids": [],
            }
        raise HTTPException(status_code=403, detail="Team task scope is not available without unit_id")

    rows = conn.execute(
        text(
            """
            SELECT
                u.user_id,
                u.role_id
            FROM public.users u
            WHERE u.unit_id = :unit_id
              AND u.user_id <> :current_user_id
              AND u.role_id IS NOT NULL
              AND COALESCE(u.is_active, TRUE) = TRUE
            ORDER BY u.user_id
            """
        ),
        {
            "unit_id": int(current_unit_id),
            "current_user_id": int(current_user_id),
        },
    ).mappings().all()

    team_user_ids: List[int] = [int(r["user_id"]) for r in rows if r.get("user_id") is not None]

    return {
        "current_unit_id": int(current_unit_id),
        "team_user_ids": team_user_ids,
    }


def get_manual_task_role_options_for_user(
    conn,
    *,
    current_user_id: int,
) -> Dict[str, Any]:
    current_user_id = int(current_user_id)

    user_row = conn.execute(
        text(
            """
            SELECT user_id, role_id, unit_id, is_active
            FROM public.users
            WHERE user_id = :uid
            """
        ),
        {"uid": current_user_id},
    ).mappings().first()

    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    current_role_id = int(user_row["role_id"])
    current_unit_id = int(user_row["unit_id"]) if user_row.get("unit_id") is not None else None

    privileged_role_ids = parse_int_set_env("DIRECTORY_PRIVILEGED_ROLE_IDS")
    privileged_user_ids = parse_int_set_env("DIRECTORY_PRIVILEGED_USER_IDS")

    is_privileged = (
        is_system_admin_role_id(current_role_id)
        or current_user_id in privileged_user_ids
        or current_role_id in privileged_role_ids
    )

    if is_system_admin_role_id(current_role_id):
        rows = (
            conn.execute(
                text(
                    """
                    SELECT
                        r.role_id,
                        r.code AS role_code,
                        r.name AS role_name,
                        r.name AS role_name_ru
                    FROM public.roles r
                    WHERE r.role_id IS NOT NULL
                    ORDER BY r.name
                    """
                )
            )
            .mappings()
            .all()
        )

        items: List[Dict[str, Any]] = []
        for row in rows:
            rid = int(row["role_id"])
            if rid == int(current_role_id):
                continue
            items.append(
                {
                    "role_id": rid,
                    "role_code": row.get("role_code"),
                    "role_name": row.get("role_name"),
                    "role_name_ru": row.get("role_name_ru"),
                }
            )

        return {
            "can_create_manual_task": bool(items),
            "items": items,
        }

    visible_roles: Set[int] = compute_visible_executor_role_ids_for_tasks(user_id=current_user_id)
    visible_role_ids = sorted({int(x) for x in visible_roles if int(x) > 0})

    if not visible_role_ids:
        visible_role_ids = [int(current_role_id)]

    is_manager = (
        is_privileged
        or (int(current_role_id) in DIRECTOR_ROLE_IDS)
        or (int(current_role_id) in DEPUTY_ROLE_IDS)
        or (int(current_role_id) in SUPERVISOR_ROLE_IDS)
        or (len(visible_role_ids) > 1)
    )

    if not is_manager:
        return {
            "can_create_manual_task": False,
            "items": [],
        }

    if len(visible_role_ids) <= 1 and current_unit_id is not None:
        fallback_rows = (
            conn.execute(
                text(
                    """
                    WITH RECURSIVE subtree AS (
                        SELECT ou.unit_id
                        FROM public.org_units ou
                        WHERE ou.unit_id = :unit_id

                        UNION ALL

                        SELECT child.unit_id
                        FROM public.org_units child
                        JOIN subtree s ON s.unit_id = child.parent_unit_id
                    )
                    SELECT DISTINCT
                        u.role_id,
                        r.code AS role_code,
                        r.name AS role_name,
                        r.name AS role_name_ru
                    FROM public.users u
                    JOIN public.roles r ON r.role_id = u.role_id
                    WHERE u.unit_id IN (SELECT unit_id FROM subtree)
                      AND COALESCE(u.is_active, TRUE) = TRUE
                      AND u.role_id IS NOT NULL
                      AND u.role_id <> :current_role_id
                    ORDER BY r.name
                    """
                ),
                {
                    "unit_id": int(current_unit_id),
                    "current_role_id": int(current_role_id),
                },
            )
            .mappings()
            .all()
        )

        fallback_items: List[Dict[str, Any]] = []
        for row in fallback_rows:
            rid = int(row["role_id"])
            fallback_items.append(
                {
                    "role_id": rid,
                    "role_code": row.get("role_code"),
                    "role_name": row.get("role_name"),
                    "role_name_ru": row.get("role_name_ru"),
                }
            )

        return {
            "can_create_manual_task": bool(fallback_items),
            "items": fallback_items,
        }

    rows = (
        conn.execute(
            text(
                """
                SELECT
                    r.role_id,
                    r.code AS role_code,
                    r.name AS role_name,
                    r.name AS role_name_ru
                FROM public.roles r
                WHERE r.role_id IN :role_ids
                ORDER BY r.name
                """
            ).bindparams(bindparam("role_ids", expanding=True)),
            {"role_ids": visible_role_ids},
        )
        .mappings()
        .all()
    )

    items: List[Dict[str, Any]] = []
    for row in rows:
        rid = int(row["role_id"])
        if rid == int(current_role_id):
            continue

        items.append(
            {
                "role_id": rid,
                "role_code": row.get("role_code"),
                "role_name": row.get("role_name"),
                "role_name_ru": row.get("role_name_ru"),
            }
        )

    return {
        "can_create_manual_task": bool(items),
        "items": items,
    }


def load_task_full(conn, *, task_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                t.task_id,
                t.period_id,
                t.regular_task_id,
                t.title,
                t.description,
                t.initiator_user_id,
                t.created_by_user_id,
                t.approver_user_id,
                t.executor_role_id,
                er.code AS executor_role_code,
                er.name AS executor_role_name,
                er.name AS executor_role_name_ru,
                ex.executor_user_id,
                ex.executor_name,
                t.assignment_scope,
                t.status_id,
                t.task_kind,
                t.requires_report,
                t.requires_approval,
                t.source_kind,
                t.source_note,
                t.due_date,
                ts.code AS status_code,
                ts.name_ru AS status_name_ru,

                tr.report_link AS report_link,
                tr.submitted_at AS report_submitted_at,
                tr.submitted_by AS report_submitted_by,
                rs.name AS report_submitted_by_role_name,
                rs.code AS report_submitted_by_role_code,

                tr.approved_at AS report_approved_at,
                tr.approved_by AS report_approved_by,
                ra.name AS report_approved_by_role_name,
                ra.code AS report_approved_by_role_code,

                tr.current_comment AS report_current_comment
            FROM public.tasks t
            LEFT JOIN public.task_statuses ts ON ts.status_id = t.status_id
            LEFT JOIN public.roles er ON er.role_id = t.executor_role_id
            LEFT JOIN LATERAL (
                SELECT
                    ue.user_id AS executor_user_id,
                    ue.full_name AS executor_name
                FROM public.users ue
                WHERE ue.role_id = t.executor_role_id
                  AND COALESCE(ue.is_active, TRUE) = TRUE
                ORDER BY ue.user_id
                LIMIT 1
            ) ex ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    r.report_link,
                    r.submitted_at,
                    r.submitted_by,
                    r.approved_at,
                    r.approved_by,
                    r.current_comment
                FROM public.task_reports r
                WHERE r.task_id = t.task_id
                ORDER BY
                    r.submitted_at DESC NULLS LAST,
                    r.approved_at  DESC NULLS LAST,
                    r.report_id    DESC
                LIMIT 1
            ) tr ON TRUE
            LEFT JOIN public.users us ON us.user_id = tr.submitted_by
            LEFT JOIN public.roles rs ON rs.role_id = us.role_id
            LEFT JOIN public.users ua ON ua.user_id = tr.approved_by
            LEFT JOIN public.roles ra ON ra.role_id = ua.role_id
            WHERE t.task_id = :task_id
            """
        ),
        {"task_id": int(task_id)},
    ).mappings().first()
    return dict(row) if row else None

def _is_initiator(*, current_user_id: int, task_row: Dict[str, Any]) -> bool:
    try:
        return int(task_row["initiator_user_id"]) == int(current_user_id)
    except Exception:
        return False


def _is_created_by(*, current_user_id: int, task_row: Dict[str, Any]) -> bool:
    try:
        return int(task_row.get("created_by_user_id") or 0) == int(current_user_id)
    except Exception:
        return False


def _is_executor_role(*, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    try:
        return int(task_row["executor_role_id"]) == int(current_role_id)
    except Exception:
        return False


def _is_report_author(*, current_user_id: int, task_row: Dict[str, Any]) -> bool:
    try:
        submitted_by = task_row.get("report_submitted_by")
        if submitted_by is None:
            return False
        return int(submitted_by) == int(current_user_id)
    except Exception:
        return False


def _is_explicit_approver_user(*, current_user_id: int, task_row: Dict[str, Any]) -> bool:
    try:
        approver_user_id = task_row.get("approver_user_id")
        if approver_user_id is None:
            return False
        return int(approver_user_id) == int(current_user_id)
    except Exception:
        return False


def _task_requires_report(task_row: Dict[str, Any]) -> bool:
    v = task_row.get("requires_report")
    if isinstance(v, bool):
        return v
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"false", "0", "no", "off"}:
            return False
        if s in {"true", "1", "yes", "on"}:
            return True
    try:
        return bool(v)
    except Exception:
        return True


def _task_requires_approval(task_row: Dict[str, Any]) -> bool:
    v = task_row.get("requires_approval")
    if isinstance(v, bool):
        return v
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"false", "0", "no", "off"}:
            return False
        if s in {"true", "1", "yes", "on"}:
            return True
    try:
        return bool(v)
    except Exception:
        return True


def _task_kind(task_row: Dict[str, Any]) -> str:
    raw = str(task_row.get("task_kind") or "").strip().lower()
    return raw if raw in {"regular", "adhoc"} else "regular"


def _can_view(
    *,
    current_user_id: int,
    current_role_id: int,
    visible_executor_role_ids: Set[int],
    task_row: Dict[str, Any],
) -> bool:
    if is_system_admin_role_id(current_role_id):
        return True

    if _is_initiator(current_user_id=current_user_id, task_row=task_row):
        return True

    if _is_created_by(current_user_id=current_user_id, task_row=task_row):
        return True

    if _is_report_author(current_user_id=current_user_id, task_row=task_row):
        return True

    if _is_explicit_approver_user(current_user_id=current_user_id, task_row=task_row):
        return True

    try:
        erid = int(task_row.get("executor_role_id") or 0)
    except Exception:
        erid = 0

    return erid in visible_executor_role_ids


def _task_matches_team_scope(
    conn,
    *,
    current_user_id: int,
    current_role_id: int,
    task_row: Dict[str, Any],
) -> bool:
    if not can_view_team_tasks(
        conn,
        current_user_id=int(current_user_id),
        current_role_id=int(current_role_id),
    ):
        return False

    try:
        executor_role_id = int(task_row.get("executor_role_id") or 0)
    except Exception:
        executor_role_id = 0

    if executor_role_id <= 0:
        return False

    if is_system_admin_role_id(current_role_id):
        return executor_role_id != int(current_role_id)

    user_ctx = load_user_context(conn, user_id=int(current_user_id))
    current_unit_id = int(user_ctx["unit_id"]) if user_ctx.get("unit_id") is not None else None
    if current_unit_id is None:
        return False

    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.users ux
            WHERE ux.role_id = :executor_role_id
              AND ux.unit_id = :unit_id
              AND ux.user_id <> :current_user_id
              AND COALESCE(ux.is_active, TRUE) = TRUE
            LIMIT 1
            """
        ),
        {
            "executor_role_id": int(executor_role_id),
            "unit_id": int(current_unit_id),
            "current_user_id": int(current_user_id),
        },
    ).mappings().first()

    return bool(row)


def ensure_task_visible_or_404(
    *,
    conn=None,
    current_user_id: int,
    current_role_id: int,
    task_row: Optional[Dict[str, Any]],
    include_archived: bool,
) -> Dict[str, Any]:
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")

    if is_system_admin_role_id(current_role_id):
        return task_row

    visible = compute_visible_executor_role_ids_for_tasks(user_id=int(current_user_id))
    if not _can_view(
        current_user_id=current_user_id,
        current_role_id=current_role_id,
        visible_executor_role_ids=visible,
        task_row=task_row,
    ):
        if conn is None or not _task_matches_team_scope(
            conn,
            current_user_id=int(current_user_id),
            current_role_id=int(current_role_id),
            task_row=task_row,
        ):
            raise HTTPException(status_code=404, detail="Task not found")

    if (not include_archived) and (str(task_row.get("status_code") or "") == "ARCHIVED"):
        raise HTTPException(status_code=404, detail="Task not found")

    return task_row


def can_report_or_update(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    if is_system_admin_role_id(current_role_id):
        code = str(task_row.get("status_code") or "")
        return code in ("IN_PROGRESS", "WAITING_REPORT", "REJECTED")

    if not _task_requires_report(task_row):
        return False

    if not _is_executor_role(current_role_id=current_role_id, task_row=task_row):
        return False

    code = str(task_row.get("status_code") or "")
    return code in ("IN_PROGRESS", "WAITING_REPORT", "REJECTED")


def can_approve(*, current_user_id: int, current_role_id: int, task_row: Dict[str, Any]) -> bool:
    code = str(task_row.get("status_code") or "")

    if is_system_admin_role_id(current_role_id):
        if code != "WAITING_APPROVAL":
            return False
        return bool(_task_requires_approval(task_row))

    if code != "WAITING_APPROVAL":
        return False

    if not _task_requires_approval(task_row):
        return False

    try:
        submitted_by = task_row.get("report_submitted_by")
        if submitted_by is not None and int(submitted_by) == int(current_user_id):
            return False
    except Exception:
        return False

    if _is_explicit_approver_user(current_user_id=current_user_id, task_row=task_row):
        return True

    rid = task_row.get("regular_task_id")
    if rid is not None:
        try:
            rid_i = int(rid)
        except Exception:
            rid_i = 0

        if rid_i > 0:
            with engine.begin() as conn:
                r = conn.execute(
                    text(
                        """
                        SELECT target_role_id
                        FROM public.regular_tasks
                        WHERE regular_task_id = :rid
                        """
                    ),
                    {"rid": int(rid_i)},
                ).mappings().first()

            if r and r.get("target_role_id") is not None:
                try:
                    if int(r["target_role_id"]) == int(current_role_id):
                        return True
                except Exception:
                    pass

    try:
        erid = int(task_row.get("executor_role_id") or 0)
        if erid > 0 and erid == int(current_role_id):
            return True
    except Exception:
        pass

    return False


def _allowed_actions_for_user(
    *,
    task_row: Dict[str, Any],
    current_user_id: int,
    current_role_id: int,
) -> List[str]:
    code = str(task_row.get("status_code") or "")

    if is_system_admin_role_id(current_role_id):
        actions: List[str] = ["delete"]

        if code not in ("ARCHIVED", "DONE"):
            actions.append("archive")

        if code in ("IN_PROGRESS", "WAITING_REPORT", "REJECTED") and _task_requires_report(task_row):
            actions.append("report")

        if code == "WAITING_APPROVAL" and _task_requires_approval(task_row):
            actions.append("approve")
            actions.append("reject")

        seen_admin: Set[str] = set()
        out_admin: List[str] = []
        for a in actions:
            if a in seen_admin:
                continue
            seen_admin.add(a)
            out_admin.append(a)
        return out_admin

    actions: List[str] = []

    if _task_requires_report(task_row) and code in ("IN_PROGRESS", "WAITING_REPORT", "REJECTED"):
        if can_report_or_update(
            current_user_id=current_user_id,
            current_role_id=current_role_id,
            task_row=task_row,
        ):
            actions.append("report")

    if _task_requires_approval(task_row) and code == "WAITING_APPROVAL":
        if can_approve(
            current_user_id=current_user_id,
            current_role_id=current_role_id,
            task_row=task_row,
        ):
            actions.append("approve")
            actions.append("reject")

    if (
        _is_initiator(current_user_id=current_user_id, task_row=task_row)
        and code not in ("ARCHIVED", "DONE")
    ):
        actions.append("archive")

    seen: Set[str] = set()
    out: List[str] = []
    for a in actions:
        if a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out


def attach_allowed_actions(
    *,
    task: Dict[str, Any],
    current_user_id: int,
    current_role_id: int,
) -> Dict[str, Any]:
    t = dict(task)
    t["allowed_actions"] = _allowed_actions_for_user(
        task_row=t,
        current_user_id=current_user_id,
        current_role_id=current_role_id,
    )
    return t


def write_task_audit(
    conn,
    *,
    task_id: int,
    actor_user_id: int,
    actor_role_id: Optional[int],
    action: str,
    fields_changed: Optional[Dict[str, Any]] = None,
    request_body: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    event_type: Optional[str] = None,
    event_payload: Optional[Dict[str, Any]] = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO task_audit_log (
                task_id,
                actor_user_id,
                action,
                fields_changed,
                request_body,
                meta,
                event_type,
                actor_id,
                actor_role,
                payload
            )
            VALUES (
                :task_id,
                :actor_user_id,
                :action,
                CAST(:fields_changed AS jsonb),
                CAST(:request_body AS jsonb),
                CAST(:meta AS jsonb),
                CASE WHEN :event_type IS NULL THEN NULL ELSE (:event_type)::task_event_type END,
                :actor_id,
                :actor_role,
                CAST(:payload AS jsonb)
            )
            """
        ),
        {
            "task_id": int(task_id),
            "actor_user_id": int(actor_user_id),
            "action": action,
            "fields_changed": json.dumps(fields_changed) if fields_changed is not None else None,
            "request_body": json.dumps(request_body) if request_body is not None else None,
            "meta": json.dumps(meta) if meta is not None else None,
            "event_type": event_type,
            "actor_id": int(actor_user_id),
            "actor_role": str(actor_role_id) if actor_role_id is not None else None,
            "payload": json.dumps(event_payload or {}) if event_type is not None else json.dumps({}),
        },
    )
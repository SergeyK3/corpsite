# FILE: app/services/regular_tasks_public_service.py
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.org_scope.apply import apply_org_scope
from app.org_scope.types import OrgScopeParams, OrgScopeStrategy
from app.services.regular_tasks_service import _validate_template_schedule


def _as_int_or_none(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _as_bool_or_none(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "yes", "y", "on"):
            return True
        if s in ("0", "false", "no", "n", "off"):
            return False
    return None


def _as_str_or_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _as_dict_or_none(v: Any) -> Optional[Dict[str, Any]]:
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    return None


def _schedule_params_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _validate_regular_task_schedule(
    schedule_type: Optional[str],
    schedule_params: Dict[str, Any],
) -> None:
    st = _as_str_or_none(schedule_type)
    if not st:
        return
    err = _validate_template_schedule(st, schedule_params)
    if err:
        raise ValueError(err)


def _ensure_owner_unit_exists(conn: Connection, owner_unit_id: int) -> None:
    found = conn.execute(
        text(
            """
            SELECT 1
            FROM public.org_units
            WHERE unit_id = :unit_id
            """
        ),
        {"unit_id": int(owner_unit_id)},
    ).scalar()

    if not found:
        raise ValueError(f"owner_unit_id={owner_unit_id} not found in org_units")


def _row_to_out(r: Any) -> Dict[str, Any]:
    return {
        "regular_task_id": int(r["regular_task_id"]),
        "code": r.get("code"),
        "title": r.get("title"),
        "description": r.get("description"),
        "is_active": bool(r.get("is_active")),
        "executor_role_id": _as_int_or_none(r.get("executor_role_id")),
        "executor_role_name": r.get("executor_role_name"),
        "executor_role_code": r.get("executor_role_code"),
        "assignment_scope": r.get("assignment_scope"),
        "schedule_type": r.get("schedule_type"),
        "schedule_params": r.get("schedule_params") or {},
        "create_offset_days": int(r.get("create_offset_days") or 0),
        "due_offset_days": int(r.get("due_offset_days") or 0),
        "owner_unit_id": _as_int_or_none(r.get("owner_unit_id")),
        "owner_unit_name": r.get("owner_unit_name"),
        "created_by_user_id": _as_int_or_none(r.get("created_by_user_id")),
        "created_at": r.get("created_at").isoformat() if r.get("created_at") else None,
        "archived_at": r.get("archived_at").isoformat() if r.get("archived_at") else None,
        "updated_at": r.get("updated_at").isoformat() if r.get("updated_at") else None,
    }


def _select_regular_task_row(conn: Connection, regular_task_id: int) -> Any:
    sql = text(
        """
        SELECT
          t.regular_task_id,
          t.code,
          t.title,
          t.description,
          t.is_active,
          t.periodicity,
          t.initiator_role_id,
          t.target_role_id,
          t.assignment_scope,
          t.template_link,
          t.order_link,
          t.executor_role_id,
          r.name AS executor_role_name,
          r.code AS executor_role_code,
          t.schedule_type,
          t.schedule_params,
          t.create_offset_days,
          t.due_offset_days,
          t.deadline_offset_days,
          t.escalation_offset_days,
          t.owner_unit_id,
          ou.name AS owner_unit_name,
          t.created_by_user_id,
          t.created_at,
          t.archived_at,
          t.updated_at
        FROM public.regular_tasks t
        LEFT JOIN public.roles r
          ON r.role_id = t.executor_role_id
        LEFT JOIN public.org_units ou
          ON ou.unit_id = t.owner_unit_id
        WHERE t.regular_task_id = :rid
        """
    )
    return conn.execute(sql, {"rid": int(regular_task_id)}).mappings().first()


def _ensure_template_editable(r: Any) -> None:
    if r and not bool(r.get("is_active")):
        raise ValueError("archived regular task template cannot be edited")


def _generate_copy_code(source_id: int) -> str:
    suffix = int(time.time() * 1_000_000) % 1_000_000_000
    return f"rt_copy_{int(source_id)}_{suffix}"


def list_regular_tasks_tx(
    conn: Connection,
    *,
    status: str = "active",
    q: Optional[str] = None,
    schedule_type: Optional[str] = None,
    executor_role_id: Optional[int] = None,
    org_group_id: Optional[int] = None,
    org_unit_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    status = (status or "active").strip().lower()
    if status not in ("active", "inactive", "all"):
        status = "active"

    filters: List[str] = []
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if status == "active":
        filters.append("t.is_active = true")
    elif status == "inactive":
        filters.append("t.is_active = false")

    if q:
        params["q"] = f"%{q.strip()}%"
        filters.append(
            "("
            "t.title ILIKE :q "
            "OR COALESCE(t.description, '') ILIKE :q "
            "OR COALESCE(t.code, '') ILIKE :q "
            "OR COALESCE(r.name, '') ILIKE :q "
            "OR COALESCE(r.code, '') ILIKE :q "
            "OR COALESCE(ou.name, '') ILIKE :q "
            "OR CAST(COALESCE(t.owner_unit_id, 0) AS TEXT) ILIKE :q"
            ")"
        )

    if schedule_type:
        params["schedule_type"] = schedule_type.strip()
        filters.append("t.schedule_type = :schedule_type")

    if executor_role_id is not None:
        params["executor_role_id"] = int(executor_role_id)
        filters.append("t.executor_role_id = :executor_role_id")

    org_scope = apply_org_scope(
        strategy=OrgScopeStrategy.OWNER_UNIT,
        params=OrgScopeParams(
            org_group_id=int(org_group_id) if org_group_id is not None else None,
            org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
        ),
        regular_task_alias="t",
        owner_unit_column="owner_unit_id",
    )
    params.update(org_scope.params)
    if org_scope.where_sql != "TRUE":
        filters.append(f"({org_scope.where_sql})")

    scope_prefix = f"{org_scope.cte_sql}\n" if org_scope.cte_sql else ""

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    total_sql = text(
        f"""
        {scope_prefix}
        SELECT COUNT(1) AS cnt
        FROM public.regular_tasks t
        LEFT JOIN public.roles r
          ON r.role_id = t.executor_role_id
        LEFT JOIN public.org_units ou
          ON ou.unit_id = t.owner_unit_id
        {where_sql}
        """
    )
    total = int(conn.execute(total_sql, params).scalar() or 0)

    sql = text(
        f"""
        {scope_prefix}
        SELECT
          t.regular_task_id,
          t.code,
          t.title,
          t.description,
          t.is_active,
          t.executor_role_id,
          r.name AS executor_role_name,
          r.code AS executor_role_code,
          t.assignment_scope,
          t.schedule_type,
          t.schedule_params,
          t.create_offset_days,
          t.due_offset_days,
          t.owner_unit_id,
          ou.name AS owner_unit_name,
          t.created_by_user_id,
          t.created_at,
          t.archived_at,
          t.updated_at
        FROM public.regular_tasks t
        LEFT JOIN public.roles r
          ON r.role_id = t.executor_role_id
        LEFT JOIN public.org_units ou
          ON ou.unit_id = t.owner_unit_id
        {where_sql}
        ORDER BY t.updated_at DESC, t.regular_task_id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    rows = conn.execute(sql, params).mappings().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_row_to_out(r) for r in rows],
    }


def get_regular_task_tx(conn: Connection, regular_task_id: int) -> Dict[str, Any]:
    r = _select_regular_task_row(conn, int(regular_task_id))
    if not r:
        raise KeyError("regular_task not found")
    return _row_to_out(r)


def create_regular_task_tx(
    conn: Connection,
    *,
    payload: Dict[str, Any],
    created_by_user_id: Optional[int],
) -> Dict[str, Any]:
    title = _as_str_or_none(payload.get("title"))
    if not title:
        raise ValueError("title is required")

    code = _as_str_or_none(payload.get("code"))
    description = _as_str_or_none(payload.get("description"))

    is_active = _as_bool_or_none(payload.get("is_active"))
    if is_active is None:
        is_active = True

    executor_role_id = _as_int_or_none(payload.get("executor_role_id"))
    owner_unit_id = _as_int_or_none(payload.get("owner_unit_id"))
    if owner_unit_id is None or owner_unit_id <= 0:
        raise ValueError("owner_unit_id is required and must be a positive integer")
    _ensure_owner_unit_exists(conn, owner_unit_id)

    schedule_type = _as_str_or_none(payload.get("schedule_type"))
    schedule_params = _as_dict_or_none(payload.get("schedule_params")) or {}
    _validate_regular_task_schedule(schedule_type, schedule_params)

    create_offset_days = _as_int_or_none(payload.get("create_offset_days"))
    if create_offset_days is None:
        create_offset_days = 0

    due_offset_days = _as_int_or_none(payload.get("due_offset_days"))
    if due_offset_days is None:
        due_offset_days = 0

    sql = text(
        """
        INSERT INTO public.regular_tasks (
          code,
          title,
          description,
          is_active,
          executor_role_id,
          owner_unit_id,
          schedule_type,
          schedule_params,
          create_offset_days,
          due_offset_days,
          created_by_user_id,
          updated_at
        ) VALUES (
          :code,
          :title,
          :description,
          :is_active,
          :executor_role_id,
          :owner_unit_id,
          :schedule_type,
          CAST(:schedule_params AS jsonb),
          :create_offset_days,
          :due_offset_days,
          :created_by_user_id,
          now()
        )
        RETURNING regular_task_id
        """
    )
    rid = conn.execute(
        sql,
        {
            "code": code,
            "title": title,
            "description": description,
            "is_active": bool(is_active),
            "executor_role_id": executor_role_id,
            "owner_unit_id": owner_unit_id,
            "schedule_type": schedule_type,
            "schedule_params": json.dumps(schedule_params, ensure_ascii=False),
            "create_offset_days": int(create_offset_days),
            "due_offset_days": int(due_offset_days),
            "created_by_user_id": int(created_by_user_id) if created_by_user_id is not None else None,
        },
    ).scalar()

    return get_regular_task_tx(conn, int(rid))


def patch_regular_task_tx(
    conn: Connection,
    regular_task_id: int,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    rid = int(regular_task_id)

    existing = _select_regular_task_row(conn, rid)
    if not existing:
        raise KeyError("regular_task not found")
    _ensure_template_editable(existing)

    sets: List[str] = []
    params: Dict[str, Any] = {"rid": rid}

    if "title" in payload:
        title = _as_str_or_none(payload.get("title"))
        if not title:
            raise ValueError("title cannot be empty")
        sets.append("title = :title")
        params["title"] = title

    if "code" in payload:
        code = _as_str_or_none(payload.get("code"))
        sets.append("code = :code")
        params["code"] = code

    if "description" in payload:
        sets.append("description = :description")
        params["description"] = _as_str_or_none(payload.get("description"))

    if "is_active" in payload:
        b = _as_bool_or_none(payload.get("is_active"))
        if b is None:
            raise ValueError("is_active must be boolean")
        sets.append("is_active = :is_active")
        params["is_active"] = bool(b)

    if "executor_role_id" in payload:
        sets.append("executor_role_id = :executor_role_id")
        params["executor_role_id"] = _as_int_or_none(payload.get("executor_role_id"))

    if "owner_unit_id" in payload:
        owner_unit_id = _as_int_or_none(payload.get("owner_unit_id"))
        if owner_unit_id is None or owner_unit_id <= 0:
            raise ValueError("owner_unit_id must be a positive integer")
        _ensure_owner_unit_exists(conn, owner_unit_id)
        sets.append("owner_unit_id = :owner_unit_id")
        params["owner_unit_id"] = owner_unit_id

    if "schedule_type" in payload:
        sets.append("schedule_type = :schedule_type")
        params["schedule_type"] = _as_str_or_none(payload.get("schedule_type"))

    if "schedule_params" in payload:
        sp = _as_dict_or_none(payload.get("schedule_params"))
        if sp is None:
            raise ValueError("schedule_params must be an object")
        sets.append("schedule_params = CAST(:schedule_params AS jsonb)")
        params["schedule_params"] = json.dumps(sp, ensure_ascii=False)

    if "create_offset_days" in payload:
        v = _as_int_or_none(payload.get("create_offset_days"))
        if v is None:
            raise ValueError("create_offset_days must be int")
        sets.append("create_offset_days = :create_offset_days")
        params["create_offset_days"] = int(v)

    if "due_offset_days" in payload:
        v = _as_int_or_none(payload.get("due_offset_days"))
        if v is None:
            raise ValueError("due_offset_days must be int")
        sets.append("due_offset_days = :due_offset_days")
        params["due_offset_days"] = int(v)

    if not sets:
        return get_regular_task_tx(conn, rid)

    effective_schedule_type = (
        _as_str_or_none(payload.get("schedule_type"))
        if "schedule_type" in payload
        else _as_str_or_none(existing.get("schedule_type"))
    )
    effective_schedule_params = (
        _as_dict_or_none(payload.get("schedule_params"))
        if "schedule_params" in payload
        else _schedule_params_dict(existing.get("schedule_params"))
    )
    if effective_schedule_params is None:
        effective_schedule_params = {}
    _validate_regular_task_schedule(effective_schedule_type, effective_schedule_params)

    sets.append("updated_at = now()")

    sql = text(
        f"""
        UPDATE public.regular_tasks
        SET {", ".join(sets)}
        WHERE regular_task_id = :rid
        """
    )
    res = conn.execute(sql, params)
    if res.rowcount == 0:
        raise KeyError("regular_task not found")

    return get_regular_task_tx(conn, rid)


def set_regular_task_active_tx(conn: Connection, regular_task_id: int, is_active: bool) -> Dict[str, Any]:
    rid = int(regular_task_id)
    if is_active:
        sql = text(
            """
            UPDATE public.regular_tasks
            SET is_active = true, archived_at = NULL, updated_at = now()
            WHERE regular_task_id = :rid
            """
        )
        params: Dict[str, Any] = {"rid": rid}
    else:
        sql = text(
            """
            UPDATE public.regular_tasks
            SET is_active = false, archived_at = COALESCE(archived_at, now()), updated_at = now()
            WHERE regular_task_id = :rid
            """
        )
        params = {"rid": rid}

    res = conn.execute(sql, params)
    if res.rowcount == 0:
        raise KeyError("regular_task not found")
    return get_regular_task_tx(conn, rid)


def archive_regular_task_tx(conn: Connection, regular_task_id: int) -> Dict[str, Any]:
    rid = int(regular_task_id)
    sql = text(
        """
        UPDATE public.regular_tasks
        SET is_active = false, archived_at = now(), updated_at = now()
        WHERE regular_task_id = :rid
        """
    )
    res = conn.execute(sql, {"rid": rid})
    if res.rowcount == 0:
        raise KeyError("regular_task not found")
    return get_regular_task_tx(conn, rid)


def copy_regular_task_tx(
    conn: Connection,
    regular_task_id: int,
    *,
    created_by_user_id: Optional[int],
) -> Dict[str, Any]:
    source = _select_regular_task_row(conn, int(regular_task_id))
    if not source:
        raise KeyError("regular_task not found")

    source_title = _as_str_or_none(source.get("title")) or f"Шаблон #{int(regular_task_id)}"
    copy_title = f"{source_title} — копия"
    copy_code = _generate_copy_code(int(regular_task_id))

    sql = text(
        """
        INSERT INTO public.regular_tasks (
          code,
          title,
          description,
          periodicity,
          initiator_role_id,
          target_role_id,
          assignment_scope,
          template_link,
          order_link,
          is_active,
          executor_role_id,
          owner_unit_id,
          schedule_type,
          schedule_params,
          create_offset_days,
          due_offset_days,
          deadline_offset_days,
          escalation_offset_days,
          created_by_user_id,
          archived_at,
          updated_at
        ) VALUES (
          :code,
          :title,
          :description,
          :periodicity,
          :initiator_role_id,
          :target_role_id,
          :assignment_scope,
          :template_link,
          :order_link,
          true,
          :executor_role_id,
          :owner_unit_id,
          :schedule_type,
          CAST(:schedule_params AS jsonb),
          :create_offset_days,
          :due_offset_days,
          :deadline_offset_days,
          :escalation_offset_days,
          :created_by_user_id,
          NULL,
          now()
        )
        RETURNING regular_task_id
        """
    )
    schedule_params = source.get("schedule_params") or {}
    if not isinstance(schedule_params, dict):
        schedule_params = {}

    rid = conn.execute(
        sql,
        {
            "code": copy_code,
            "title": copy_title,
            "description": source.get("description"),
            "periodicity": source.get("periodicity"),
            "initiator_role_id": _as_int_or_none(source.get("initiator_role_id")),
            "target_role_id": _as_int_or_none(source.get("target_role_id")),
            "assignment_scope": source.get("assignment_scope"),
            "template_link": source.get("template_link"),
            "order_link": source.get("order_link"),
            "executor_role_id": _as_int_or_none(source.get("executor_role_id")),
            "owner_unit_id": _as_int_or_none(source.get("owner_unit_id")),
            "schedule_type": source.get("schedule_type"),
            "schedule_params": json.dumps(schedule_params, ensure_ascii=False),
            "create_offset_days": int(source.get("create_offset_days") or 0),
            "due_offset_days": int(source.get("due_offset_days") or 0),
            "deadline_offset_days": int(source.get("deadline_offset_days") or 0),
            "escalation_offset_days": int(source.get("escalation_offset_days") or 0),
            "created_by_user_id": int(created_by_user_id) if created_by_user_id is not None else None,
        },
    ).scalar()

    return get_regular_task_tx(conn, int(rid))


def delete_regular_task_tx(conn: Connection, regular_task_id: int) -> Dict[str, Any]:
    rid = int(regular_task_id)

    existing = conn.execute(
        text(
            """
            SELECT regular_task_id, code, title
            FROM public.regular_tasks
            WHERE regular_task_id = :rid
            """
        ),
        {"rid": rid},
    ).mappings().first()

    if not existing:
        raise KeyError("regular_task not found")

    res = conn.execute(
        text(
            """
            DELETE FROM public.regular_tasks
            WHERE regular_task_id = :rid
            """
        ),
        {"rid": rid},
    )

    if res.rowcount == 0:
        raise KeyError("regular_task not found")

    return {
        "ok": True,
        "deleted": {
            "regular_task_id": int(existing["regular_task_id"]),
            "code": existing.get("code"),
            "title": existing.get("title"),
        },
    }
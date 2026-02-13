# FILE: app/services/regular_tasks_public_service.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection


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


def _row_to_out(r: Any) -> Dict[str, Any]:
    return {
        "regular_task_id": int(r["regular_task_id"]),
        "code": r.get("code"),
        "title": r.get("title"),
        "is_active": bool(r.get("is_active")),
        "executor_role_id": _as_int_or_none(r.get("executor_role_id")),
        "schedule_type": r.get("schedule_type"),
        "schedule_params": r.get("schedule_params") or {},
        "create_offset_days": int(r.get("create_offset_days") or 0),
        "due_offset_days": int(r.get("due_offset_days") or 0),
        "created_by_user_id": _as_int_or_none(r.get("created_by_user_id")),
        "updated_at": r.get("updated_at").isoformat() if r.get("updated_at") else None,
    }


def list_regular_tasks_tx(
    conn: Connection,
    *,
    status: str = "active",
    q: Optional[str] = None,
    schedule_type: Optional[str] = None,
    executor_role_id: Optional[int] = None,
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
        filters.append("(t.title ILIKE :q OR t.code ILIKE :q)")

    if schedule_type:
        params["schedule_type"] = schedule_type.strip()
        filters.append("t.schedule_type = :schedule_type")

    if executor_role_id is not None:
        params["executor_role_id"] = int(executor_role_id)
        filters.append("t.executor_role_id = :executor_role_id")

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    total_sql = text(f"SELECT COUNT(1) AS cnt FROM public.regular_tasks t {where_sql}")
    total = int(conn.execute(total_sql, params).scalar() or 0)

    sql = text(
        f"""
        SELECT
          t.regular_task_id,
          t.code,
          t.title,
          t.is_active,
          t.executor_role_id,
          t.schedule_type,
          t.schedule_params,
          t.create_offset_days,
          t.due_offset_days,
          t.created_by_user_id,
          t.updated_at
        FROM public.regular_tasks t
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
    sql = text(
        """
        SELECT
          t.regular_task_id,
          t.code,
          t.title,
          t.is_active,
          t.executor_role_id,
          t.schedule_type,
          t.schedule_params,
          t.create_offset_days,
          t.due_offset_days,
          t.created_by_user_id,
          t.updated_at
        FROM public.regular_tasks t
        WHERE t.regular_task_id = :rid
        """
    )
    r = conn.execute(sql, {"rid": int(regular_task_id)}).mappings().first()
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
    is_active = _as_bool_or_none(payload.get("is_active"))
    if is_active is None:
        is_active = True

    executor_role_id = _as_int_or_none(payload.get("executor_role_id"))
    schedule_type = _as_str_or_none(payload.get("schedule_type"))
    schedule_params = _as_dict_or_none(payload.get("schedule_params")) or {}

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
          is_active,
          executor_role_id,
          schedule_type,
          schedule_params,
          create_offset_days,
          due_offset_days,
          created_by_user_id,
          updated_at
        ) VALUES (
          :code,
          :title,
          :is_active,
          :executor_role_id,
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
            "is_active": bool(is_active),
            "executor_role_id": executor_role_id,
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

    if "is_active" in payload:
        b = _as_bool_or_none(payload.get("is_active"))
        if b is None:
            raise ValueError("is_active must be boolean")
        sets.append("is_active = :is_active")
        params["is_active"] = bool(b)

    if "executor_role_id" in payload:
        sets.append("executor_role_id = :executor_role_id")
        params["executor_role_id"] = _as_int_or_none(payload.get("executor_role_id"))

    if "schedule_type" in payload:
        sets.append("schedule_type = :schedule_type")
        params["schedule_type"] = _as_str_or_none(payload.get("schedule_type"))

    if "schedule_params" in payload:
        sp = _as_dict_or_none(payload.get("schedule_params"))
        if sp is None:
            raise ValueError("schedule_params must be an object")
        # ВАЖНО: Postgres + SQLAlchemy безопаснее через CAST(:param AS jsonb), чем через :param::jsonb
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
    sql = text(
        """
        UPDATE public.regular_tasks
        SET is_active = :is_active, updated_at = now()
        WHERE regular_task_id = :rid
        """
    )
    res = conn.execute(sql, {"rid": rid, "is_active": bool(is_active)})
    if res.rowcount == 0:
        raise KeyError("regular_task not found")
    return get_regular_task_tx(conn, rid)

# tests/conftest.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app.db.engine import engine
from app.main import app


# =============================
# Helpers
# =============================

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def fetch_one(conn, sql: str, **params) -> Dict[str, Any]:
    row = conn.execute(text(sql), params).mappings().first()
    if not row:
        raise RuntimeError(f"Expected row, got none. SQL={sql!r}, params={params!r}")
    return dict(row)


def fetch_opt(conn, sql: str, **params) -> Optional[Dict[str, Any]]:
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def exec_sql(conn, sql: str, **params) -> None:
    conn.execute(text(sql), params)


def table_exists(conn, table: str, schema: str = "public") -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).first()
    return row is not None


def get_columns(conn, table: str, schema: str = "public") -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            """
        ),
        {"schema": schema, "table": table},
    ).fetchall()
    return {r[0] for r in rows}


def safe_delete(conn, table: str, where_sql: str, params: Dict[str, Any], schema: str = "public") -> None:
    if not table_exists(conn, table, schema=schema):
        return
    conn.execute(text(f"DELETE FROM {schema}.{table} WHERE {where_sql}"), params)


def safe_delete_many(conn, table: str, col: str, ids: list[int], schema: str = "public") -> None:
    if not ids:
        return
    if not table_exists(conn, table, schema=schema):
        return
    conn.execute(text(f"DELETE FROM {schema}.{table} WHERE {col} = ANY(:ids)"), {"ids": ids})


def insert_returning_id(
    conn,
    *,
    table: str,
    id_col: str,
    values: Dict[str, Any],
    schema: str = "public",
) -> int:
    """
    Insert only columns that exist in the target table.
    """
    if not table_exists(conn, table, schema=schema):
        raise RuntimeError(f"Table {schema}.{table} does not exist")

    cols = get_columns(conn, table, schema=schema)
    filtered = {k: v for k, v in values.items() if k in cols}
    if not filtered:
        raise RuntimeError(f"No compatible columns to insert into {schema}.{table}. Have cols={sorted(cols)}")

    col_list = ", ".join(filtered.keys())
    bind_list = ", ".join(f":{k}" for k in filtered.keys())

    sql = f"""
        INSERT INTO {schema}.{table} ({col_list})
        VALUES ({bind_list})
        RETURNING {id_col}
    """
    row = fetch_one(conn, sql, **filtered)
    return int(row[id_col])


# =============================
# Detect helpers
# =============================

def _detect_unit_table(conn) -> Optional[str]:
    if table_exists(conn, "org_units"):
        return "org_units"
    if table_exists(conn, "units"):
        return "units"
    return None


def _detect_roles_table(conn) -> Optional[str]:
    return "roles" if table_exists(conn, "roles") else None


def _detect_users_table(conn) -> Optional[str]:
    return "users" if table_exists(conn, "users") else None


def _detect_tasks_table(conn) -> Optional[str]:
    return "tasks" if table_exists(conn, "tasks") else None


def _detect_user_role_table(conn, schema: str = "public") -> Optional[str]:
    """
    Detect a membership table (user<->role) by:
    1) common names
    2) fallback: any table that has BOTH columns user_id and role_id
    """
    common = [
        "user_roles",
        "users_roles",
        "role_users",
        "user_role",
        "user_role_map",
        "user_role_memberships",
        "role_memberships",
        "memberships",
        "role_assignments",
        "user_role_links",
    ]
    for t in common:
        if table_exists(conn, t, schema=schema):
            cols = get_columns(conn, t, schema=schema)
            if "user_id" in cols and "role_id" in cols:
                return t

    rows = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND column_name IN ('user_id','role_id')
            GROUP BY table_name
            HAVING COUNT(DISTINCT column_name) = 2
            ORDER BY table_name
            """
        ),
        {"schema": schema},
    ).fetchall()

    for (tname,) in rows:
        # исключим очевидные "не то"
        if tname in ("users", "roles", "tasks"):
            continue
        cols = get_columns(conn, tname, schema=schema)
        if "user_id" in cols and "role_id" in cols:
            return tname

    return None


# =============================
# Enum helpers
# =============================

def _get_enum_labels(conn, enum_type: str, schema: str = "public") -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT e.enumlabel
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE n.nspname = :schema AND t.typname = :typname
            ORDER BY e.enumsortorder
            """
        ),
        {"schema": schema, "typname": enum_type},
    ).fetchall()
    return [r[0] for r in rows]


def _normalize_assignment_scope(conn, value: Optional[str]) -> Optional[str]:
    """
    ВАЖНО ДЛЯ СОВМЕСТИМОСТИ С app/tasks.py:
    Backend разрешает доступ исполнителю только при scope == 'functional'
    (см. _can_view / _can_report_or_update).

    Тесты же исторически передают 'unit'. Поэтому:
    - если пришло 'unit' и в enum есть 'functional' -> возвращаем 'functional' (реальную метку enum).
    - остальное поведение сохраняем как было.
    """
    if value is None:
        return None

    labels = _get_enum_labels(conn, "assignment_scope_t")
    if not labels:
        return value

    if value in labels:
        return value

    v = value.strip()

    # --- КЛЮЧЕВАЯ ПРАВКА: unit -> functional, если есть ---
    if v.lower() == "unit":
        for lbl in labels:
            if lbl.lower() == "functional":
                return lbl
        # если functional вдруг нет, оставим вашу прежнюю эвристику
    # ------------------------------------------------------

    candidates = [v, v.upper(), v.lower(), v.capitalize()]

    if v.lower() == "unit":
        candidates.extend(["UNIT", "BY_UNIT", "UNIT_ONLY", "ORG_UNIT", "ORGANIZATIONAL_UNIT"])

    for c in candidates:
        if c in labels:
            return c

    for lbl in labels:
        if "unit" in lbl.lower():
            return lbl

    return labels[0]


# =============================
# Unit column helpers
# =============================

def _user_unit_col(conn) -> Optional[str]:
    if not table_exists(conn, "users"):
        return None
    cols = get_columns(conn, "users")
    if "unit_id" in cols:
        return "unit_id"
    if "org_unit_id" in cols:
        return "org_unit_id"
    return None


def _task_unit_col(conn) -> Optional[str]:
    if not table_exists(conn, "tasks"):
        return None
    cols = get_columns(conn, "tasks")
    if "unit_id" in cols:
        return "unit_id"
    if "org_unit_id" in cols:
        return "org_unit_id"
    return None


# =============================
# Membership writer (user<->role)
# =============================

def _ensure_user_role_membership(conn, *, user_id: int, role_id: int) -> None:
    """
    If the project stores roles in a separate membership table, write user_id<->role_id there.
    Safe: if no membership table exists, does nothing.
    """
    t = _detect_user_role_table(conn)
    if not t:
        return

    cols = get_columns(conn, t)
    values: Dict[str, Any] = {"user_id": user_id, "role_id": role_id}

    now = utcnow()
    # common optional cols (insert_returning_id-like behavior manually)
    if "created_at" in cols:
        values["created_at"] = now
    if "updated_at" in cols:
        values["updated_at"] = now
    if "is_active" in cols:
        values["is_active"] = True

    filtered = {k: v for k, v in values.items() if k in cols}
    if not filtered or "user_id" not in filtered or "role_id" not in filtered:
        return

    col_list = ", ".join(filtered.keys())
    bind_list = ", ".join(f":{k}" for k in filtered.keys())

    sql = f"""
        INSERT INTO public.{t} ({col_list})
        VALUES ({bind_list})
        ON CONFLICT DO NOTHING
    """
    conn.execute(text(sql), filtered)


# =============================
# Executor user-id resolution (for ACL-compat)
# =============================

def _resolve_executor_user_id(conn, executor_role_id: int, preferred_unit_id: Optional[int]) -> Optional[int]:
    if not table_exists(conn, "users"):
        return None

    ucols = get_columns(conn, "users")
    if "user_id" not in ucols:
        return None

    # if role_id is NOT in users, we cannot select by it
    if "role_id" not in ucols:
        return None

    unit_col = _user_unit_col(conn)

    if preferred_unit_id is not None and unit_col and unit_col in ucols:
        row = fetch_opt(
            conn,
            f"""
            SELECT user_id
            FROM public.users
            WHERE role_id = :rid AND {unit_col} = :uid
            ORDER BY user_id
            LIMIT 1
            """,
            rid=executor_role_id,
            uid=preferred_unit_id,
        )
        if row and row.get("user_id") is not None:
            return int(row["user_id"])

    row = fetch_opt(
        conn,
        """
        SELECT user_id
        FROM public.users
        WHERE role_id = :rid
        ORDER BY user_id
        LIMIT 1
        """,
        rid=executor_role_id,
    )
    if row and row.get("user_id") is not None:
        return int(row["user_id"])

    return None


# =============================
# Core creators
# =============================

def create_unit(conn, name: str) -> Optional[int]:
    ut = _detect_unit_table(conn)
    if not ut:
        return None

    now = utcnow()
    cols = get_columns(conn, ut)

    if "unit_id" in cols:
        id_col = "unit_id"
    elif "org_unit_id" in cols:
        id_col = "org_unit_id"
    elif "id" in cols:
        id_col = "id"
    else:
        raise RuntimeError(f"Cannot detect unit id column in public.{ut}. cols={sorted(cols)}")

    values: Dict[str, Any] = {"name": name, "created_at": now}
    return insert_returning_id(conn, table=ut, id_col=id_col, values=values)


def create_role(conn, name: str) -> int:
    now = utcnow()
    if not table_exists(conn, "roles"):
        raise RuntimeError("Table public.roles does not exist")

    cols = get_columns(conn, "roles")
    values: Dict[str, Any] = {"name": name, "created_at": now}
    if "code" in cols:
        values["code"] = name

    return insert_returning_id(conn, table="roles", id_col="role_id", values=values)


def create_user(conn, *, full_name: str, role_id: int, unit_id: Optional[int] = None) -> int:
    """
    Важно: роль может храниться в users.role_id ИЛИ в отдельной таблице membership.
    Мы:
    - вставляем в users (role_id будет вставлен только если колонка существует),
    - и всегда делаем best-effort вставку membership user<->role.
    """
    now = utcnow()
    gl = f"pytest_google_{int(now.timestamp() * 1_000_000)}_{role_id}"

    values: Dict[str, Any] = {
        "full_name": full_name,
        "google_login": gl,
        "role_id": role_id,           # вставится только если есть колонка
        "unit_id": unit_id,           # вставится только если есть колонка
        "org_unit_id": unit_id,       # вставится только если есть колонка
        "is_active": True,
        "created_at": now,
    }
    user_id = insert_returning_id(conn, table="users", id_col="user_id", values=values)

    _ensure_user_role_membership(conn, user_id=user_id, role_id=role_id)

    return user_id


def _set_user_unit(conn, user_id: int, unit_id: Optional[int]) -> None:
    col = _user_unit_col(conn)
    if not col:
        return
    conn.execute(
        text(f"UPDATE public.users SET {col} = :unit_id WHERE user_id = :user_id"),
        {"unit_id": unit_id, "user_id": user_id},
    )


def _get_user_unit_id(conn, user_id: int) -> Optional[int]:
    col = _user_unit_col(conn)
    if not col:
        return None
    row = fetch_opt(conn, f"SELECT {col} AS unit FROM public.users WHERE user_id = :uid", uid=user_id)
    if not row:
        return None
    return row.get("unit")


def get_status_id(conn, code: str) -> int:
    row = fetch_opt(conn, "SELECT status_id FROM public.task_statuses WHERE code = :code", code=code)
    if not row:
        raise RuntimeError(f"task_statuses.code='{code}' not found")
    return int(row["status_id"])


def create_task(
    *,
    period_id: int,
    title: str,
    initiator_user_id: int,
    executor_role_id: int,
    assignment_scope: Optional[str],
    status_code: str,
    unit_id: Optional[int] = None,
) -> int:
    """
    Compatibility signature for existing tests.

    Критично:
    1) Если tasks.*unit* существует и unit_id не передали — берём unit инициатора.
    2) Если tasks имеет executor_user_id (или аналог) — пытаемся заполнить,
       но это вторично.
    """
    with engine.begin() as conn:
        status_id = get_status_id(conn, status_code)
        now = utcnow()

        tcols = get_columns(conn, "tasks")

        # assignment_scope (enum-safe)
        scope_val = assignment_scope
        if "assignment_scope" in tcols:
            scope_val = _normalize_assignment_scope(conn, assignment_scope or "unit")

        # unit_id auto-fill for ACL
        unit_val = unit_id
        if unit_val is None:
            unit_val = _get_user_unit_id(conn, initiator_user_id)

        # Optional executor user linkage (only if users.role_id exists and tasks has such column)
        executor_user_id_val: Optional[int] = None
        if any(c in tcols for c in ("executor_user_id", "executor_id", "assignee_user_id")):
            executor_user_id_val = _resolve_executor_user_id(conn, executor_role_id, unit_val)

        values: Dict[str, Any] = {
            "period_id": period_id,
            "title": title,
            "description": None,
            "initiator_user_id": initiator_user_id,
            "executor_role_id": executor_role_id,
            "unit_id": unit_val,
            "org_unit_id": unit_val,
            "assignment_scope": scope_val,
            "status_id": status_id,
            "created_at": now,
            "updated_at": now,
        }

        if executor_user_id_val is not None:
            values.update(
                {
                    "executor_user_id": executor_user_id_val,
                    "executor_id": executor_user_id_val,
                    "assignee_user_id": executor_user_id_val,
                }
            )

        return insert_returning_id(conn, table="tasks", id_col="task_id", values=values)


def cleanup_task(task_id: int) -> None:
    with engine.begin() as conn:
        safe_delete(conn, "tasks", "task_id = :tid", {"tid": task_id})


def upsert_report(*, task_id: int, submitted_by: int, report_link: str, current_comment: str) -> None:
    with engine.begin() as conn:
        now = utcnow()

        # 1) task_reports
        if table_exists(conn, "task_reports"):
            cols = get_columns(conn, "task_reports")
            values: Dict[str, Any] = {
                "task_id": task_id,
                "submitted_by": submitted_by,
                "report_link": report_link,
                "current_comment": current_comment,
                "submitted_at": now,
                "created_at": now,
                "updated_at": now,
            }
            filtered = {k: v for k, v in values.items() if k in cols}
            if filtered:
                col_list = ", ".join(filtered.keys())
                bind_list = ", ".join(f":{k}" for k in filtered.keys())
                conn.execute(
                    text(
                        f"""
                        INSERT INTO public.task_reports ({col_list})
                        VALUES ({bind_list})
                        """
                    ),
                    filtered,
                )
                return

        # 2) tasks columns fallback
        if not table_exists(conn, "tasks"):
            return

        tcols = get_columns(conn, "tasks")
        sets: list[str] = []
        params: Dict[str, Any] = {"task_id": task_id}

        def _set(col: str, val: Any) -> None:
            if col in tcols:
                sets.append(f"{col} = :{col}")
                params[col] = val

        _set("report_link", report_link)
        _set("report_url", report_link)
        _set("report_submitted_by", submitted_by)
        _set("submitted_by", submitted_by)
        _set("report_submitted_at", now)
        _set("submitted_at", now)
        _set("current_comment", current_comment)
        _set("report_comment", current_comment)
        _set("updated_at", now)

        if not sets:
            return

        conn.execute(
            text(f"UPDATE public.tasks SET {', '.join(sets)} WHERE task_id = :task_id"),
            params,
        )


# =============================
# Backward-compatible names expected by older tests
# =============================

_create_unit = create_unit
_create_role = create_role
_create_user = create_user

_table_exists = table_exists
_get_columns = get_columns
_safe_delete = safe_delete
_safe_delete_many = safe_delete_many


# =============================
# Fixtures
# =============================

@pytest.fixture(scope="function")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="function")
def seed() -> Iterator[Dict[str, Any]]:
    created_unit_id: Optional[int] = None
    created_role_ids: list[int] = []
    created_user_ids: list[int] = []

    with engine.begin() as conn:
        created_unit_id = create_unit(conn, "pytest_unit")

        executor_role_id = create_role(conn, "pytest_executor")
        initiator_role_id = create_role(conn, "pytest_initiator")
        created_role_ids = [executor_role_id, initiator_role_id]

        executor_user_id = create_user(
            conn,
            full_name="Pytest Executor",
            role_id=executor_role_id,
            unit_id=created_unit_id,
        )
        initiator_user_id = create_user(
            conn,
            full_name="Pytest Initiator",
            role_id=initiator_role_id,
            unit_id=created_unit_id,
        )
        created_user_ids = [executor_user_id, initiator_user_id]

        data: Dict[str, Any] = {
            "period_id": 2,
            "title": "Pytest Task",
            "unit_id": created_unit_id,
            "executor_role_id": executor_role_id,
            "initiator_role_id": initiator_role_id,
            "executor_user_id": executor_user_id,
            "initiator_user_id": initiator_user_id,
            "assignment_scope": "unit",
        }

    try:
        yield data
    finally:
        with engine.begin() as conn:
            # tasks
            if table_exists(conn, "tasks"):
                tcols = get_columns(conn, "tasks")
                t_unit_col = _task_unit_col(conn)
                if created_unit_id is not None and t_unit_col and t_unit_col in tcols:
                    exec_sql(conn, f"DELETE FROM public.tasks WHERE {t_unit_col} = :u", u=created_unit_id)
                else:
                    if "initiator_user_id" in tcols and created_user_ids:
                        conn.execute(
                            text("DELETE FROM public.tasks WHERE initiator_user_id = ANY(:uids)"),
                            {"uids": created_user_ids},
                        )

            # task_reports
            if table_exists(conn, "task_reports"):
                cols = get_columns(conn, "task_reports")
                if "submitted_by" in cols and created_user_ids:
                    conn.execute(
                        text("DELETE FROM public.task_reports WHERE submitted_by = ANY(:uids)"),
                        {"uids": created_user_ids},
                    )

            # users
            if table_exists(conn, "users"):
                ucols = get_columns(conn, "users")
                u_unit_col = _user_unit_col(conn)
                if created_unit_id is not None and u_unit_col and u_unit_col in ucols:
                    exec_sql(conn, f"DELETE FROM public.users WHERE {u_unit_col} = :u", u=created_unit_id)
                else:
                    safe_delete_many(conn, "users", "user_id", created_user_ids)

            # roles
            if table_exists(conn, "roles"):
                safe_delete_many(conn, "roles", "role_id", created_role_ids)

            # membership (user<->role)
            mrt = _detect_user_role_table(conn)
            if mrt and created_user_ids and created_role_ids:
                # удалить все записи по нашим пользователям
                safe_delete_many(conn, mrt, "user_id", created_user_ids)

            # units / org_units
            ut = _detect_unit_table(conn)
            if created_unit_id is not None and ut:
                ucols = get_columns(conn, ut)
                if "unit_id" in ucols:
                    exec_sql(conn, f"DELETE FROM public.{ut} WHERE unit_id = :u", u=created_unit_id)
                elif "org_unit_id" in ucols:
                    exec_sql(conn, f"DELETE FROM public.{ut} WHERE org_unit_id = :u", u=created_unit_id)
                elif "id" in ucols:
                    exec_sql(conn, f"DELETE FROM public.{ut} WHERE id = :u", u=created_unit_id)

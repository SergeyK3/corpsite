# tests/_seed_acl.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine


def _headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(int(user_id))}


def _table_exists(conn, table: str, schema: str = "public") -> bool:
    q = text(
        """
        SELECT EXISTS(
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = :schema AND table_name = :table
        )
        """
    )
    return bool(conn.execute(q, {"schema": schema, "table": table}).scalar())


def _users_columns_meta(conn, schema: str = "public") -> List[Dict[str, Any]]:
    """
    Return column metadata for users table:
      - name
      - is_nullable
      - column_default
      - data_type
      - identity_generation (YES/NO or ALWAYS/BY DEFAULT depending on PG)
    """
    q = text(
        """
        SELECT
            column_name,
            is_nullable,
            column_default,
            data_type,
            identity_generation
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = 'users'
        ORDER BY ordinal_position
        """
    )
    rows = conn.execute(q, {"schema": schema}).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "name": r[0],
                "nullable": (r[1] == "YES"),
                "default": r[2],  # may be None
                "data_type": r[3],
                "identity_generation": r[4],  # may be None / 'ALWAYS' / 'BY DEFAULT'
            }
        )
    return out


def _safe_delete(conn, table: str, where_sql: str, params: Dict[str, object], schema: str = "public") -> None:
    conn.execute(text(f"DELETE FROM {schema}.{table} WHERE {where_sql}"), params)


@dataclass(frozen=True)
class SeededUser:
    user_id: int


def _value_for_required_column(
    *,
    col_name: str,
    data_type: str,
    role_id: int,
    seed_tag: str,
    full_name: str,
) -> Any:
    """
    Generate a safe placeholder value for NOT NULL column without default.
    We prefer business-meaningful values for known columns.
    """
    n = col_name.lower()
    dt = (data_type or "").lower()

    # --- strong name-based rules first ---
    if n in ("role_id",):
        return int(role_id)

    if n in ("full_name", "fio", "name"):
        return full_name

    # Your schema requires this one (NotNullViolation in stacktrace)
    if n in ("google_login", "google_email"):
        return f"{seed_tag}@example.local"

    if n in ("email", "mail"):
        return f"{seed_tag}@example.local"

    if n in ("login", "username", "user_name"):
        return seed_tag

    if n in ("is_active", "active", "enabled"):
        return True

    # --- type-based fallbacks ---
    if "bool" in dt:
        return True

    if dt in ("integer", "bigint", "smallint"):
        return 1

    if dt in ("numeric", "double precision", "real", "decimal"):
        return 0

    if "timestamp" in dt or dt == "date":
        return datetime.now(timezone.utc)

    # default for strings / unknown
    return seed_tag


def create_user(*, role_id: int, name: str) -> SeededUser:
    """
    Create a user row and return generated user_id.

    Handles NOT NULL columns with no default (e.g. google_login) by introspecting
    users table schema and filling required fields.
    """
    with engine.begin() as conn:
        assert _table_exists(conn, "users"), "Table users does not exist"

        meta = _users_columns_meta(conn)
        cols = {m["name"] for m in meta}

        # PK column name (in your schema: user_id identity GENERATED ALWAYS)
        id_col = "user_id" if "user_id" in cols else "id" if "id" in cols else None
        assert id_col is not None, f"Cannot determine PK column for users; cols={sorted(cols)}"

        # Build list of required insert columns:
        # - NOT NULL
        # - no column_default
        # - not identity column
        required_cols = []
        for m in meta:
            if m["name"] == id_col:
                continue
            if m["identity_generation"] is not None:
                # identity column (rare beyond PK) -> skip
                continue
            if (not m["nullable"]) and (m["default"] is None):
                required_cols.append(m)

        # Also include optional-but-helpful columns if exist and not already required
        # (does not hurt, but keeps rows readable)
        def _add_if_exists(col: str) -> None:
            if col in cols and all(m["name"] != col for m in required_cols):
                # include it only if it is not identity; ok even if nullable
                m = next(x for x in meta if x["name"] == col)
                if m["identity_generation"] is None and m["name"] != id_col:
                    required_cols.append(m)

        _add_if_exists("role_id")
        _add_if_exists("full_name")

        # generate seed tag to satisfy uniqueness-ish constraints
        # we avoid importing uuid; timestamp+role is enough for tests
        seed_tag = f"seed_{int(role_id)}_{int(datetime.now(timezone.utc).timestamp() * 1_000_000)}"

        insert_cols: List[str] = []
        params: Dict[str, Any] = {}

        for m in required_cols:
            c = m["name"]
            insert_cols.append(c)
            params[c] = _value_for_required_column(
                col_name=c,
                data_type=m["data_type"],
                role_id=role_id,
                seed_tag=seed_tag,
                full_name=name,
            )

        if not insert_cols:
            # extreme case: everything has defaults; just insert default row
            row = conn.execute(text(f"INSERT INTO users DEFAULT VALUES RETURNING {id_col}")).fetchone()
            assert row and row[0], "Failed to create user (DEFAULT VALUES)"
            return SeededUser(user_id=int(row[0]))

        cols_sql = ", ".join(insert_cols)
        vals_sql = ", ".join([f":{c}" for c in insert_cols])

        row = conn.execute(
            text(f"INSERT INTO users ({cols_sql}) VALUES ({vals_sql}) RETURNING {id_col}"),
            params,
        ).fetchone()
        assert row and row[0], f"Failed to create user; insert_cols={insert_cols}"
        return SeededUser(user_id=int(row[0]))


def cleanup_user_related_data(user_id: int) -> None:
    """
    Best-effort cleanup: remove tasks/events/reports created under initiator_user_id=user_id, then remove user.
    """
    with engine.begin() as conn:
        # tasks created by this user
        task_ids = [
            int(r[0])
            for r in conn.execute(
                text("SELECT task_id FROM tasks WHERE initiator_user_id = :uid"),
                {"uid": int(user_id)},
            ).fetchall()
        ]

        if task_ids:
            # events table might be task_events or events
            if _table_exists(conn, "task_events"):
                conn.execute(
                    text("DELETE FROM task_events WHERE task_id = ANY(:ids)"),
                    {"ids": task_ids},
                )
            elif _table_exists(conn, "events"):
                conn.execute(
                    text("DELETE FROM events WHERE task_id = ANY(:ids)"),
                    {"ids": task_ids},
                )

            if _table_exists(conn, "task_reports"):
                conn.execute(
                    text("DELETE FROM task_reports WHERE task_id = ANY(:ids)"),
                    {"ids": task_ids},
                )

            conn.execute(
                text("DELETE FROM tasks WHERE task_id = ANY(:ids)"),
                {"ids": task_ids},
            )

        # delete user row
        meta = _users_columns_meta(conn)
        cols = {m["name"] for m in meta}
        id_col = "user_id" if "user_id" in cols else "id" if "id" in cols else None
        if id_col:
            _safe_delete(conn, "users", f"{id_col} = :id", {"id": int(user_id)})


def seed_task_with_event(
    client: TestClient,
    *,
    initiator_user_id: int,
    executor_user_id: int,
    executor_role_id: int,
    title: str,
    period_id: int,
) -> int:
    """
    Create task + submit report to guarantee at least one event.
    Returns task_id.
    """
    payload = {
        "title": title,
        "description": "seed",
        "period_id": int(period_id),
        "executor_role_id": int(executor_role_id),
        "assignment_scope": "functional",
        "status_code": "IN_PROGRESS",
    }
    r = client.post("/tasks", json=payload, headers=_headers(initiator_user_id))
    assert r.status_code == 200, r.text
    task_id = int(r.json()["task_id"])

    r2 = client.post(
        f"/tasks/{task_id}/report",
        json={"report_link": "https://example.com/seed", "current_comment": "seed"},
        headers=_headers(executor_user_id),
    )
    assert r2.status_code == 200, r2.text

    return task_id


def fetch_event_task_ids(client: TestClient, user_id: int) -> List[int]:
    r = client.get("/tasks/me/events?limit=200", headers=_headers(user_id))
    assert r.status_code == 200, r.text
    events = r.json()
    return [int(e["task_id"]) for e in events]

def pick_two_non_priv_role_ids() -> tuple[int, int]:
    """
    Pick 2 role_ids that are NOT supervisor/deputy (so they do not have broad ACL).
    Falls back to (1, 2) if roles table not found or not enough data.
    """
    # from env (same semantics as backend)
    def _parse_int_set(name: str) -> set[int]:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return set()
        out: set[int] = set()
        for p in raw.split(","):
            p = p.strip()
            if not p:
                continue
            try:
                out.add(int(p))
            except Exception:
                continue
        return out

    import os

    supervisor = _parse_int_set("SUPERVISOR_ROLE_IDS")
    deputy = _parse_int_set("DEPUTY_ROLE_IDS")
    banned = supervisor.union(deputy)

    with engine.begin() as conn:
        if not _table_exists(conn, "roles"):
            return (1, 2)

        # try to get two roles that are not privileged
        rows = conn.execute(
            text(
                """
                SELECT role_id
                FROM roles
                WHERE role_id IS NOT NULL
                ORDER BY role_id ASC
                """
            )
        ).fetchall()

        role_ids = [int(r[0]) for r in rows if int(r[0]) not in banned]

        # need 2 distinct roles
        if len(role_ids) >= 2:
            return (role_ids[0], role_ids[1])

    return (1, 2)

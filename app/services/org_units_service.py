from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class OrgUnit:
    unit_id: int
    parent_unit_id: Optional[int]
    name: str
    code: Optional[str]
    is_active: bool


class OrgUnitsService:
    def __init__(
        self,
        engine: Engine,
        schema: str = "public",
        org_units_table: str = "org_units",
        users_table: str = "users",
    ) -> None:
        self._engine = engine
        self._schema = schema
        self._org_units_table = org_units_table
        self._users_table = users_table

    # ---------------------------
    # Users
    # ---------------------------
    def get_user_unit_and_role(self, user_id: int) -> Tuple[Optional[int], Optional[int], bool]:
        sql = text(f"""
            SELECT unit_id, role_id, COALESCE(is_active, true) AS is_active
            FROM {self._schema}.{self._users_table}
            WHERE user_id = :uid
            LIMIT 1
        """)
        with self._engine.begin() as c:
            row = c.execute(sql, {"uid": user_id}).mappings().first()

        if not row:
            return None, None, False

        return (
            int(row["unit_id"]) if row["unit_id"] is not None else None,
            int(row["role_id"]) if row["role_id"] is not None else None,
            bool(row["is_active"]),
        )

    # ---------------------------
    # Org units tree
    # ---------------------------
    def _load_units(self) -> List[Tuple[int, Optional[int]]]:
        sql = text(f"""
            SELECT unit_id, parent_unit_id
            FROM {self._schema}.{self._org_units_table}
            WHERE COALESCE(is_active, true) = true
        """)
        with self._engine.begin() as c:
            rows = c.execute(sql).mappings().all()

        return [
            (int(r["unit_id"]), int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None)
            for r in rows
        ]

    def get_scope_unit_ids(self, root_unit_id: int) -> Set[int]:
        edges = self._load_units()

        children: Dict[int, List[int]] = {}
        for uid, pid in edges:
            if pid is not None:
                children.setdefault(pid, []).append(uid)

        result: Set[int] = {root_unit_id}
        stack: List[int] = [root_unit_id]

        while stack:
            cur = stack.pop()
            for ch in children.get(cur, []):
                if ch not in result:
                    result.add(ch)
                    stack.append(ch)

        return result

    # ---------------------------
    # RBAC
    # ---------------------------
    @staticmethod
    def _parse_int_set_env(name: str) -> Set[int]:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return set()
        out: Set[int] = set()
        for p in raw.split(","):
            try:
                out.add(int(p.strip()))
            except ValueError:
                pass
        return out

    @staticmethod
    def _rbac_mode() -> str:
        v = (os.getenv("DIRECTORY_RBAC_MODE") or "dept").strip().lower()
        return v if v in ("off", "dept") else "dept"

    def compute_user_scope_unit_ids(self, user_id: int) -> Optional[Set[int]]:
        if self._rbac_mode() == "off":
            return None

        privileged_users = self._parse_int_set_env("DIRECTORY_PRIVILEGED_USER_IDS")
        privileged_roles = self._parse_int_set_env("DIRECTORY_PRIVILEGED_ROLE_IDS")

        unit_id, role_id, is_active = self.get_user_unit_and_role(user_id)

        if not is_active:
            raise PermissionError(f"user_id={user_id} inactive or not found")

        if user_id in privileged_users:
            return None

        if role_id is not None and role_id in privileged_roles:
            return None

        if unit_id is None:
            raise PermissionError(
                f"RBAC: cannot determine department scope for user_id={user_id}: unit_id is null"
            )

        return self.get_scope_unit_ids(unit_id)

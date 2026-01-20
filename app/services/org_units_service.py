# FILE: app/services/org_units_service.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any

from sqlalchemy import text, bindparam
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
        sql = text(
            f"""
            SELECT unit_id, role_id, COALESCE(is_active, true) AS is_active
            FROM {self._schema}.{self._users_table}
            WHERE user_id = :uid
            LIMIT 1
        """
        )
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
    # RBAC helpers
    # ---------------------------
    @staticmethod
    def _parse_int_set_env(name: str) -> Set[int]:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return set()
        out: Set[int] = set()
        for p in raw.split(","):
            s = p.strip()
            if not s:
                continue
            try:
                out.add(int(s))
            except ValueError:
                pass
        return out

    @staticmethod
    def _rbac_mode() -> str:
        v = (os.getenv("DIRECTORY_RBAC_MODE") or "dept").strip().lower()
        return v if v in ("off", "dept") else "dept"

    # ---------------------------
    # Org units load (ids only)
    # ---------------------------
    def _load_unit_edges(self) -> List[Tuple[int, Optional[int]]]:
        sql = text(
            f"""
            SELECT unit_id, parent_unit_id
            FROM {self._schema}.{self._org_units_table}
            WHERE COALESCE(is_active, true) = true
        """
        )
        with self._engine.begin() as c:
            rows = c.execute(sql).mappings().all()

        return [
            (int(r["unit_id"]), int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None)
            for r in rows
        ]

    def get_scope_unit_ids(self, root_unit_id: int) -> Set[int]:
        edges = self._load_unit_edges()

        children: Dict[int, List[int]] = {}
        for uid, pid in edges:
            if pid is not None:
                children.setdefault(pid, []).append(uid)

        result: Set[int] = {int(root_unit_id)}
        stack: List[int] = [int(root_unit_id)]

        while stack:
            cur = stack.pop()
            for ch in children.get(cur, []):
                if ch not in result:
                    result.add(ch)
                    stack.append(ch)

        return result

    def compute_user_scope_unit_ids(self, user_id: int) -> Optional[Set[int]]:
        """
        Returns:
          - None: no restrictions (rbac off or privileged)
          - Set[int]: allowed unit_ids (user unit + descendants)
        """
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

    # ---------------------------
    # Org units (full rows) + tree
    # ---------------------------
    def list_org_units(
        self,
        scope_unit_ids: Optional[List[int]] = None,
    ) -> List[OrgUnit]:
        """
        Flat list of active org units.
        If scope_unit_ids provided -> restrict to these unit_ids.
        """
        if scope_unit_ids is None:
            sql = text(
                f"""
                SELECT unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
                FROM {self._schema}.{self._org_units_table}
                WHERE COALESCE(is_active, true) = true
                ORDER BY unit_id
            """
            )
            params: Dict[str, Any] = {}
        else:
            sql = (
                text(
                    f"""
                    SELECT unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
                    FROM {self._schema}.{self._org_units_table}
                    WHERE COALESCE(is_active, true) = true
                      AND unit_id IN :ids
                    ORDER BY unit_id
                """
                )
                .bindparams(bindparam("ids", expanding=True))
            )
            params = {"ids": [int(x) for x in scope_unit_ids]}

        with self._engine.begin() as c:
            rows = c.execute(sql, params).mappings().all()

        out: List[OrgUnit] = []
        for r in rows:
            out.append(
                OrgUnit(
                    unit_id=int(r["unit_id"]),
                    parent_unit_id=int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
                    name=str(r["name"]) if r["name"] is not None else "",
                    code=str(r["code"]) if r["code"] is not None else None,
                    is_active=bool(r["is_active"]),
                )
            )
        return out

    @staticmethod
    def build_tree(units: List[OrgUnit]) -> List[Dict[str, Any]]:
        """
        Returns forest of roots.

        Public API node schema (aligned with employee.org_unit):
          {
            "unit_id": int,
            "parent_unit_id": Optional[int],
            "name": str,
            "code": Optional[str],
            "is_active": bool,
            "children": [...]
          }
        """
        nodes: Dict[int, Dict[str, Any]] = {}
        for u in units:
            nodes[u.unit_id] = {
                "unit_id": u.unit_id,
                "parent_unit_id": u.parent_unit_id,
                "name": u.name,
                "code": u.code,
                "is_active": bool(u.is_active),
                "children": [],
            }

        roots: List[Dict[str, Any]] = []
        for node in nodes.values():
            pid = node["parent_unit_id"]
            if pid is not None and pid in nodes:
                nodes[pid]["children"].append(node)
            else:
                roots.append(node)

        def sort_rec(n: Dict[str, Any]) -> None:
            n["children"].sort(key=lambda x: (x.get("name") or "", x["unit_id"]))
            for ch in n["children"]:
                sort_rec(ch)

        roots.sort(key=lambda x: (x.get("name") or "", x["unit_id"]))
        for r in roots:
            sort_rec(r)

        return roots

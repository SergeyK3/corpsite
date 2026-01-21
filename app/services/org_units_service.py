# FILE: app/services/org_units_service.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import bindparam, text
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
        org_unit_groups_table: str = "org_unit_groups",
        org_unit_group_units_table: str = "org_unit_group_units",
    ) -> None:
        self._engine = engine
        self._schema = schema
        self._org_units_table = org_units_table
        self._users_table = users_table
        self._org_unit_groups_table = org_unit_groups_table
        self._org_unit_group_units_table = org_unit_group_units_table

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
            row = c.execute(sql, {"uid": int(user_id)}).mappings().first()

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
        # off | dept | groups
        v = (os.getenv("DIRECTORY_RBAC_MODE") or "dept").strip().lower()
        return v if v in ("off", "dept", "groups") else "dept"

    def _fallback_dept_scope_or_raise(self, *, user_id: int, unit_id: Optional[int], include_inactive: bool) -> Set[int]:
        """
        MVP fallback for groups-RBAC:
        If deputy has no group assignments, fall back to dept scope using users.unit_id (+ descendants).
        """
        if unit_id is None:
            raise PermissionError(
                f"RBAC(dept): cannot determine department scope for user_id={user_id}: unit_id is null"
            )
        return self.get_scope_unit_ids(int(unit_id), include_inactive=include_inactive)

    # ---------------------------
    # Org units load (ids only)
    # ---------------------------
    def _load_unit_edges(self, include_inactive: bool = False) -> List[Tuple[int, Optional[int]]]:
        where = ""
        if not include_inactive:
            where = "WHERE COALESCE(is_active, true) = true"

        sql = text(
            f"""
            SELECT unit_id, parent_unit_id
            FROM {self._schema}.{self._org_units_table}
            {where}
            """
        )
        with self._engine.begin() as c:
            rows = c.execute(sql).mappings().all()

        return [
            (int(r["unit_id"]), int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None)
            for r in rows
        ]

    def get_scope_unit_ids(self, root_unit_id: int, include_inactive: bool = False) -> Set[int]:
        edges = self._load_unit_edges(include_inactive=include_inactive)

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

    def get_scope_unit_ids_many(self, root_unit_ids: List[int], include_inactive: bool = False) -> Set[int]:
        out: Set[int] = set()
        for rid in root_unit_ids:
            out |= self.get_scope_unit_ids(int(rid), include_inactive=include_inactive)
        return out

    # ---------------------------
    # RBAC (groups): deputy -> group -> units
    # ---------------------------
    def list_group_unit_ids_for_deputy(self, deputy_user_id: int, include_inactive: bool = False) -> List[int]:
        """
        Returns direct unit_ids assigned to deputy's groups (org_unit_group_units).
        Note: descendants are NOT included here.
        """
        where_active_g = "AND COALESCE(g.is_active, true) = true"
        where_active_u = "" if include_inactive else "AND COALESCE(u.is_active, true) = true"

        sql = text(
            f"""
            SELECT DISTINCT u.unit_id
            FROM {self._schema}.{self._org_unit_groups_table} g
            JOIN {self._schema}.{self._org_unit_group_units_table} gu
              ON gu.group_id = g.group_id
            JOIN {self._schema}.{self._org_units_table} u
              ON u.unit_id = gu.unit_id
            WHERE g.deputy_user_id = :uid
              {where_active_g}
              {where_active_u}
            ORDER BY u.unit_id
            """
        )
        with self._engine.begin() as c:
            rows = c.execute(sql, {"uid": int(deputy_user_id)}).mappings().all()

        return [int(r["unit_id"]) for r in rows]

    def compute_user_scope_unit_ids(
        self,
        user_id: int,
        include_inactive: bool = False,
    ) -> Optional[Set[int]]:
        """
        Returns:
          - None: no restrictions (rbac off or privileged)
          - Set[int]: allowed unit_ids
             * dept  : user's unit + descendants
             * groups: union(assigned group unit + its descendants)
                      (MVP fallback: if no assignments -> dept scope)
        """
        mode = self._rbac_mode()
        if mode == "off":
            return None

        privileged_users = self._parse_int_set_env("DIRECTORY_PRIVILEGED_USER_IDS")
        privileged_roles = self._parse_int_set_env("DIRECTORY_PRIVILEGED_ROLE_IDS")

        unit_id, role_id, is_active = self.get_user_unit_and_role(int(user_id))

        if not is_active:
            raise PermissionError(f"user_id={user_id} inactive or not found")

        if int(user_id) in privileged_users:
            return None

        if role_id is not None and int(role_id) in privileged_roles:
            return None

        if mode == "dept":
            return self._fallback_dept_scope_or_raise(user_id=int(user_id), unit_id=unit_id, include_inactive=include_inactive)

        # mode == "groups"
        assigned = self.list_group_unit_ids_for_deputy(int(user_id), include_inactive=include_inactive)
        if not assigned:
            # MVP fallback: allow dept-scope if deputy is not configured in groups tables yet
            return self._fallback_dept_scope_or_raise(user_id=int(user_id), unit_id=unit_id, include_inactive=include_inactive)

        return self.get_scope_unit_ids_many(assigned, include_inactive=include_inactive)

    # ---------------------------
    # Org units (full rows)
    # ---------------------------
    def list_org_units(
        self,
        scope_unit_ids: Optional[List[int]] = None,
        include_inactive: bool = True,
    ) -> List[OrgUnit]:
        """
        Flat list of org units.
        If scope_unit_ids provided -> restrict to these unit_ids.
        include_inactive=True -> includes inactive units.
        """
        where_active = "" if include_inactive else "AND COALESCE(is_active, true) = true"

        if scope_unit_ids is None:
            sql = text(
                f"""
                SELECT unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
                FROM {self._schema}.{self._org_units_table}
                WHERE 1=1
                  {where_active}
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
                    WHERE unit_id IN :ids
                      {where_active}
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

    # ---------------------------
    # Convenience: scoped reads for endpoints
    # ---------------------------
    def list_org_units_for_user(
        self,
        *,
        user_id: int,
        include_inactive: bool,
    ) -> List[OrgUnit]:
        """
        Read-only helper for endpoints:
        - applies RBAC scope if enabled (dept/groups)
        - returns flat list of OrgUnit rows
        """
        scope = self.compute_user_scope_unit_ids(int(user_id), include_inactive=include_inactive)
        scope_ids = None if scope is None else sorted(scope)
        return self.list_org_units(scope_unit_ids=scope_ids, include_inactive=include_inactive)

    def get_org_units_tree_for_user(
        self,
        *,
        user_id: int,
        include_inactive: bool,
    ) -> List[Dict[str, Any]]:
        units = self.list_org_units_for_user(user_id=int(user_id), include_inactive=include_inactive)
        return self.build_tree(units)

    def get_org_units_ui_tree_for_user(
        self,
        *,
        user_id: int,
        include_inactive: bool,
    ) -> Tuple[List[Dict[str, Any]], List[str], int]:
        units = self.list_org_units_for_user(user_id=int(user_id), include_inactive=include_inactive)
        return self.build_ui_tree(units)

    # ---------------------------
    # Tree builders (cycle/orphan safe)
    # ---------------------------
    @staticmethod
    def _creates_cycle(child_id: int, parent_id: int, parent_map: Dict[int, Optional[int]]) -> bool:
        """
        Detects whether linking child -> parent would create a cycle.
        Walk up from parent_id to roots; if we meet child_id => cycle.
        """
        cur = parent_id
        seen: Set[int] = set()
        while cur is not None:
            if cur == child_id:
                return True
            if cur in seen:
                # defensive: existing cycle already present upstream
                return True
            seen.add(cur)
            cur = parent_map.get(cur)
        return False

    @staticmethod
    def build_tree(units: List[OrgUnit]) -> List[Dict[str, Any]]:
        """
        Legacy tree schema (kept stable for callers):
          {
            "unit_id": int,
            "parent_unit_id": Optional[int],
            "name": str,
            "code": Optional[str],
            "is_active": bool,
            "children": [...]
          }

        Safety:
          - Orphans (parent not found) become roots.
          - Cycles are broken: the offending node becomes a root (no infinite recursion).
        """
        nodes: Dict[int, Dict[str, Any]] = {}
        parent_map: Dict[int, Optional[int]] = {}

        for u in units:
            parent_map[u.unit_id] = u.parent_unit_id
            nodes[u.unit_id] = {
                "unit_id": u.unit_id,
                "parent_unit_id": u.parent_unit_id,
                "name": u.name,
                "code": u.code,
                "is_active": bool(u.is_active),
                "children": [],
            }

        roots: List[Dict[str, Any]] = []
        for uid, node in nodes.items():
            pid = node["parent_unit_id"]
            if pid is None:
                roots.append(node)
                continue

            if pid not in nodes:
                # orphan -> root
                roots.append(node)
                continue

            # cycle check
            if OrgUnitsService._creates_cycle(int(uid), int(pid), parent_map):
                roots.append(node)
                continue

            nodes[int(pid)]["children"].append(node)

        def sort_rec(n: Dict[str, Any]) -> None:
            n["children"].sort(key=lambda x: ((x.get("name") or "").lower(), int(x["unit_id"])))
            for ch in n["children"]:
                sort_rec(ch)

        roots.sort(key=lambda x: ((x.get("name") or "").lower(), int(x["unit_id"])))
        for r in roots:
            sort_rec(r)

        return roots

    @staticmethod
    def build_ui_tree(units: List[OrgUnit]) -> Tuple[List[Dict[str, Any]], List[str], int]:
        """
        UI tree schema:
          {
            "id": str,
            "title": str,
            "type": "unit",
            "is_active": bool,
            "children": [...]
          }
        Returns: (items, inactive_ids, total)

        Safety:
          - Orphans become roots.
          - Cycles are broken: offending node becomes a root (no infinite recursion).
        """
        inactive_ids: List[str] = [str(u.unit_id) for u in units if not u.is_active]

        nodes: Dict[int, Dict[str, Any]] = {}
        parent_map: Dict[int, Optional[int]] = {}

        for u in units:
            parent_map[u.unit_id] = u.parent_unit_id
            nodes[u.unit_id] = {
                "id": str(u.unit_id),
                "title": u.name,
                "type": "unit",
                "is_active": bool(u.is_active),
                "children": [],
            }

        roots: List[Dict[str, Any]] = []
        for u in units:
            uid = int(u.unit_id)
            pid = u.parent_unit_id
            node = nodes[uid]

            if pid is None:
                roots.append(node)
                continue

            if int(pid) not in nodes:
                roots.append(node)
                continue

            if OrgUnitsService._creates_cycle(uid, int(pid), parent_map):
                roots.append(node)
                continue

            nodes[int(pid)]["children"].append(node)

        def sort_rec(n: Dict[str, Any]) -> None:
            n["children"].sort(key=lambda x: ((x.get("title") or "").lower(), str(x.get("id") or "")))
            for ch in n["children"]:
                sort_rec(ch)

        roots.sort(key=lambda x: ((x.get("title") or "").lower(), str(x.get("id") or "")))
        for r in roots:
            sort_rec(r)

        return roots, inactive_ids, len(units)

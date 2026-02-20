# FILE: app/services/org_units_service.py

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
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
    def _trim_opt(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None

    @staticmethod
    @lru_cache(maxsize=64)
    def _parse_int_set_env_cached(name: str) -> Set[int]:
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

    # Backward-friendly wrapper (keeps call sites simple)
    def _parse_int_set_env(self, name: str) -> Set[int]:
        return set(self._parse_int_set_env_cached(name))

    @staticmethod
    @lru_cache(maxsize=8)
    def _rbac_mode_cached() -> str:
        v = (os.getenv("DIRECTORY_RBAC_MODE") or "dept").strip().lower()
        return v if v in ("off", "dept", "groups") else "dept"

    def _fallback_dept_scope_or_raise(self, *, user_id: int, unit_id: Optional[int], include_inactive: bool) -> Set[int]:
        if unit_id is None:
            raise PermissionError(
                f"RBAC(dept): cannot determine department scope for user_id={user_id}: unit_id is null"
            )
        return self.get_scope_unit_ids(int(unit_id), include_inactive=include_inactive)

    # ---------------------------
    # Roots invariants (single root)
    # ---------------------------
    def _list_root_ids(self, include_inactive: bool = True) -> List[int]:
        where_active = "" if include_inactive else "AND COALESCE(is_active, true) = true"
        sql = text(
            f"""
            SELECT unit_id
            FROM {self._schema}.{self._org_units_table}
            WHERE parent_unit_id IS NULL
              {where_active}
            ORDER BY unit_id
            """
        )
        with self._engine.begin() as c:
            rows = c.execute(sql).mappings().all()
        return [int(r["unit_id"]) for r in rows]

    def _ensure_single_root_on_create(self, *, include_inactive: bool = True) -> None:
        roots = self._list_root_ids(include_inactive=include_inactive)
        if roots:
            raise ValueError("single-root invariant: root already exists")

    def _ensure_single_root_on_move_to_null(self, *, unit_id: int) -> None:
        src = self.get_org_unit(unit_id=int(unit_id), include_inactive=True)
        if src is None:
            raise LookupError(f"org unit not found: unit_id={unit_id}")
        if src.parent_unit_id is None:
            return
        raise ValueError("single-root invariant: moving a non-root unit to root is forbidden")

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

    @staticmethod
    def _children_map(edges: List[Tuple[int, Optional[int]]]) -> Dict[int, List[int]]:
        children: Dict[int, List[int]] = {}
        for uid, pid in edges:
            if pid is not None:
                children.setdefault(pid, []).append(uid)
        return children

    def get_scope_unit_ids(self, root_unit_id: int, include_inactive: bool = False) -> Set[int]:
        edges = self._load_unit_edges(include_inactive=include_inactive)
        return self._get_scope_unit_ids_from_edges([int(root_unit_id)], edges)

    def get_scope_unit_ids_many(self, root_unit_ids: List[int], include_inactive: bool = False) -> Set[int]:
        if not root_unit_ids:
            return set()
        edges = self._load_unit_edges(include_inactive=include_inactive)
        return self._get_scope_unit_ids_from_edges([int(x) for x in root_unit_ids], edges)

    def _get_scope_unit_ids_from_edges(self, roots: List[int], edges: List[Tuple[int, Optional[int]]]) -> Set[int]:
        children = self._children_map(edges)

        result: Set[int] = set()
        stack: List[int] = []

        for r in roots:
            rr = int(r)
            if rr not in result:
                result.add(rr)
                stack.append(rr)

        while stack:
            cur = stack.pop()
            for ch in children.get(cur, []):
                if ch not in result:
                    result.add(ch)
                    stack.append(ch)

        return result

    # ---------------------------
    # RBAC (groups): deputy -> group -> units
    # ---------------------------
    def list_group_unit_ids_for_deputy(self, deputy_user_id: int, include_inactive: bool = False) -> List[int]:
        # ВАЖНО: include_inactive теперь влияет и на активность групп, и на активность подразделений
        where_active_g = "" if include_inactive else "AND COALESCE(g.is_active, true) = true"
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
        mode = self._rbac_mode_cached()
        if mode == "off":
            return None

        privileged_users = self._parse_int_set_env_cached("DIRECTORY_PRIVILEGED_USER_IDS")
        privileged_roles = self._parse_int_set_env_cached("DIRECTORY_PRIVILEGED_ROLE_IDS")

        unit_id, role_id, is_active = self.get_user_unit_and_role(int(user_id))

        if not is_active:
            raise PermissionError(f"user_id={user_id} inactive or not found")

        if int(user_id) in privileged_users:
            return None

        if role_id is not None and int(role_id) in privileged_roles:
            return None

        if mode == "dept":
            return self._fallback_dept_scope_or_raise(
                user_id=int(user_id),
                unit_id=unit_id,
                include_inactive=include_inactive,
            )

        assigned = self.list_group_unit_ids_for_deputy(int(user_id), include_inactive=include_inactive)
        if not assigned:
            return self._fallback_dept_scope_or_raise(
                user_id=int(user_id),
                unit_id=unit_id,
                include_inactive=include_inactive,
            )

        return self.get_scope_unit_ids_many(assigned, include_inactive=include_inactive)

    # ---------------------------
    # ROLE-SCOPE for tasks (2-level policy)
    # ---------------------------
    def _list_child_unit_ids(self, parent_unit_id: int, *, include_inactive_units: bool) -> List[int]:
        where_active = "" if include_inactive_units else "AND COALESCE(is_active, true) = true"
        sql = text(
            f"""
            SELECT unit_id
            FROM {self._schema}.{self._org_units_table}
            WHERE parent_unit_id = :pid
              {where_active}
            ORDER BY unit_id
            """
        )
        with self._engine.begin() as c:
            rows = c.execute(sql, {"pid": int(parent_unit_id)}).mappings().all()
        return [int(r["unit_id"]) for r in rows]

    def _list_user_role_ids_by_unit_ids(
        self,
        unit_ids: List[int],
        *,
        role_ids_filter: Optional[Set[int]] = None,
        include_inactive_users: bool = False,
    ) -> List[int]:
        if not unit_ids:
            return []

        where_user_active = "" if include_inactive_users else "AND COALESCE(u.is_active, true) = true"

        if role_ids_filter is not None:
            sql = (
                text(
                    f"""
                    SELECT DISTINCT u.role_id
                    FROM {self._schema}.{self._users_table} u
                    WHERE u.unit_id IN :unit_ids
                      AND u.role_id IN :role_ids
                      {where_user_active}
                    ORDER BY u.role_id
                    """
                )
                .bindparams(bindparam("unit_ids", expanding=True))
                .bindparams(bindparam("role_ids", expanding=True))
            )
            params: Dict[str, Any] = {
                "unit_ids": [int(x) for x in unit_ids],
                "role_ids": [int(x) for x in role_ids_filter],
            }
        else:
            sql = (
                text(
                    f"""
                    SELECT DISTINCT u.role_id
                    FROM {self._schema}.{self._users_table} u
                    WHERE u.unit_id IN :unit_ids
                      {where_user_active}
                    ORDER BY u.role_id
                    """
                ).bindparams(bindparam("unit_ids", expanding=True))
            )
            params = {"unit_ids": [int(x) for x in unit_ids]}

        with self._engine.begin() as c:
            rows = c.execute(sql, params).mappings().all()

        out: List[int] = []
        for r in rows:
            if r.get("role_id") is None:
                continue
            out.append(int(r["role_id"]))
        return out

    def compute_visible_executor_role_ids_for_tasks(
        self,
        *,
        user_id: int,
        include_inactive_units: bool = False,
        include_inactive_users: bool = False,
    ) -> Set[int]:
        """
        STRICT role-scope for tasks (two levels):
          - Director: own role + deputy roles (ONLY deputies)
          - Deputy: own role + supervisor roles assigned to deputy via groups (ONLY supervisors)
          - Supervisor: own role + roles of direct subordinates (ANY roles in direct child units)
          - Others: own role only

        Env sets:
          DIRECTOR_ROLE_IDS, DEPUTY_ROLE_IDS, SUPERVISOR_ROLE_IDS
        """
        uid = int(user_id)

        director_role_ids = self._parse_int_set_env("DIRECTOR_ROLE_IDS")
        deputy_role_ids = self._parse_int_set_env("DEPUTY_ROLE_IDS")
        supervisor_role_ids = self._parse_int_set_env("SUPERVISOR_ROLE_IDS")

        unit_id, role_id, is_active = self.get_user_unit_and_role(uid)
        if not is_active or role_id is None:
            raise PermissionError(f"user_id={uid} inactive or not found")

        my_role_id = int(role_id)
        out: Set[int] = {my_role_id}

        # Director -> deputies (only deputy roles in direct child units)
        if my_role_id in director_role_ids:
            if unit_id is None:
                return out
            child_units = self._list_child_unit_ids(int(unit_id), include_inactive_units=include_inactive_units)
            dep_roles = self._list_user_role_ids_by_unit_ids(
                child_units,
                role_ids_filter=deputy_role_ids,
                include_inactive_users=include_inactive_users,
            )
            out |= set(dep_roles)
            return out

        # Deputy -> supervisors assigned to deputy via groups (only supervisor roles)
        if my_role_id in deputy_role_ids:
            assigned_units = self.list_group_unit_ids_for_deputy(uid, include_inactive=include_inactive_units)
            head_roles = self._list_user_role_ids_by_unit_ids(
                assigned_units,
                role_ids_filter=supervisor_role_ids,
                include_inactive_users=include_inactive_users,
            )
            out |= set(head_roles)
            return out

        # Supervisor -> direct subordinates (any roles in direct child units)
        if my_role_id in supervisor_role_ids:
            if unit_id is None:
                return out
            child_units = self._list_child_unit_ids(int(unit_id), include_inactive_units=include_inactive_units)
            sub_roles = self._list_user_role_ids_by_unit_ids(
                child_units,
                role_ids_filter=None,
                include_inactive_users=include_inactive_users,
            )
            out |= set(sub_roles)
            return out

        return out

    # ---------------------------
    # Org units (full rows)
    # ---------------------------
    def list_org_units(
        self,
        scope_unit_ids: Optional[List[int]] = None,
        include_inactive: bool = True,
    ) -> List[OrgUnit]:
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
                ).bindparams(bindparam("ids", expanding=True))
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

    def get_org_unit(self, *, unit_id: int, include_inactive: bool = True) -> Optional[OrgUnit]:
        where_active = "" if include_inactive else "AND COALESCE(is_active, true) = true"
        sql = text(
            f"""
            SELECT unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
            FROM {self._schema}.{self._org_units_table}
            WHERE unit_id = :unit_id
              {where_active}
            LIMIT 1
            """
        )
        with self._engine.begin() as c:
            r = c.execute(sql, {"unit_id": int(unit_id)}).mappings().first()

        if not r:
            return None

        return OrgUnit(
            unit_id=int(r["unit_id"]),
            parent_unit_id=int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            name=str(r["name"]) if r["name"] is not None else "",
            code=str(r["code"]) if r["code"] is not None else None,
            is_active=bool(r["is_active"]),
        )

    # ---------------------------
    # Convenience: scoped reads for endpoints
    # ---------------------------
    def list_org_units_for_user(
        self,
        *,
        user_id: int,
        include_inactive: bool,
    ) -> List[OrgUnit]:
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
        cur = parent_id
        seen: Set[int] = set()
        while cur is not None:
            if cur == child_id:
                return True
            if cur in seen:
                return True
            seen.add(cur)
            cur = parent_map.get(cur)
        return False

    @staticmethod
    def build_tree(units: List[OrgUnit]) -> List[Dict[str, Any]]:
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
                roots.append(node)
                continue

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

    # ---------------------------
    # B3.1 Rename (write)
    # ---------------------------
    def rename_org_unit(
        self,
        *,
        unit_id: int,
        new_name: str,
    ) -> OrgUnit:
        name = (new_name or "").strip()
        if not name:
            raise ValueError("name must not be empty")

        sql = text(
            f"""
            UPDATE {self._schema}.{self._org_units_table}
            SET name = :name
            WHERE unit_id = :unit_id
            RETURNING unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
            """
        )

        with self._engine.begin() as c:
            r = c.execute(
                sql,
                {
                    "unit_id": int(unit_id),
                    "name": name,
                },
            ).mappings().first()

        if not r:
            raise LookupError(f"org unit not found: unit_id={unit_id}")

        return OrgUnit(
            unit_id=int(r["unit_id"]),
            parent_unit_id=int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            name=str(r["name"]) if r["name"] is not None else "",
            code=str(r["code"]) if r["code"] is not None else None,
            is_active=bool(r["is_active"]),
        )

    # ---------------------------
    # B3.2 Move (write)
    # ---------------------------
    def move_org_unit(
        self,
        *,
        unit_id: int,
        parent_unit_id: Optional[int],
    ) -> OrgUnit:
        uid = int(unit_id)
        pid = int(parent_unit_id) if parent_unit_id is not None else None

        if pid is not None and pid == uid:
            raise ValueError("parent_unit_id cannot equal unit_id")

        if pid is None:
            self._ensure_single_root_on_move_to_null(unit_id=uid)

        src = self.get_org_unit(unit_id=uid, include_inactive=True)
        if src is None:
            raise LookupError(f"org unit not found: unit_id={uid}")

        if pid is not None:
            parent = self.get_org_unit(unit_id=pid, include_inactive=True)
            if parent is None:
                raise LookupError(f"parent org unit not found: parent_unit_id={pid}")

        if pid is not None:
            edges = self._load_unit_edges(include_inactive=True)
            parent_map: Dict[int, Optional[int]] = {u: p for (u, p) in edges}
            if self._creates_cycle(uid, pid, parent_map):
                raise ValueError("cycle detected: parent_unit_id is inside unit subtree")

        sql = text(
            f"""
            UPDATE {self._schema}.{self._org_units_table}
            SET parent_unit_id = :parent_unit_id
            WHERE unit_id = :unit_id
            RETURNING unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
            """
        )

        with self._engine.begin() as c:
            r = c.execute(
                sql,
                {
                    "unit_id": uid,
                    "parent_unit_id": pid,
                },
            ).mappings().first()

        if not r:
            raise LookupError(f"org unit not found: unit_id={uid}")

        return OrgUnit(
            unit_id=int(r["unit_id"]),
            parent_unit_id=int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            name=str(r["name"]) if r["name"] is not None else "",
            code=str(r["code"]) if r["code"] is not None else None,
            is_active=bool(r["is_active"]),
        )

    # ---------------------------
    # B3.3 Deactivate / Activate (write)
    # ---------------------------
    def set_org_unit_active(
        self,
        *,
        unit_id: int,
        is_active: bool,
    ) -> OrgUnit:
        uid = int(unit_id)

        sql = text(
            f"""
            UPDATE {self._schema}.{self._org_units_table}
            SET is_active = :is_active
            WHERE unit_id = :unit_id
            RETURNING unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
            """
        )

        with self._engine.begin() as c:
            r = c.execute(
                sql,
                {
                    "unit_id": uid,
                    "is_active": bool(is_active),
                },
            ).mappings().first()

        if not r:
            raise LookupError(f"org unit not found: unit_id={uid}")

        return OrgUnit(
            unit_id=int(r["unit_id"]),
            parent_unit_id=int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            name=str(r["name"]) if r["name"] is not None else "",
            code=str(r["code"]) if r["code"] is not None else None,
            is_active=bool(r["is_active"]),
        )

    def deactivate_org_unit(self, *, unit_id: int) -> OrgUnit:
        return self.set_org_unit_active(unit_id=int(unit_id), is_active=False)

    def activate_org_unit(self, *, unit_id: int) -> OrgUnit:
        return self.set_org_unit_active(unit_id=int(unit_id), is_active=True)

    # ---------------------------
    # B4 Add org unit (create flow)
    # ---------------------------
    def create_org_unit(
        self,
        *,
        name: str,
        parent_unit_id: Optional[int] = None,
        code: Optional[str] = None,
        is_active: bool = True,
    ) -> OrgUnit:
        nm = (name or "").strip()
        if not nm:
            raise ValueError("name must not be empty")

        pid = int(parent_unit_id) if parent_unit_id is not None else None

        if pid is None:
            self._ensure_single_root_on_create(include_inactive=True)
        else:
            parent = self.get_org_unit(unit_id=pid, include_inactive=True)
            if parent is None:
                raise LookupError(f"parent org unit not found: parent_unit_id={pid}")

        cd = self._trim_opt(code)

        sql = text(
            f"""
            INSERT INTO {self._schema}.{self._org_units_table} (parent_unit_id, name, code, is_active)
            VALUES (:parent_unit_id, :name, :code, :is_active)
            RETURNING unit_id, parent_unit_id, name, code, COALESCE(is_active, true) AS is_active
            """
        )

        with self._engine.begin() as c:
            r = c.execute(
                sql,
                {
                    "parent_unit_id": pid,
                    "name": nm,
                    "code": cd,
                    "is_active": bool(is_active),
                },
            ).mappings().first()

        if not r:
            raise RuntimeError("create org unit failed")

        return OrgUnit(
            unit_id=int(r["unit_id"]),
            parent_unit_id=int(r["parent_unit_id"]) if r["parent_unit_id"] is not None else None,
            name=str(r["name"]) if r["name"] is not None else "",
            code=str(r["code"]) if r["code"] is not None else None,
            is_active=bool(r["is_active"]),
        )

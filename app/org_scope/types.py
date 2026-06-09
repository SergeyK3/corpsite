# FILE: app/org_scope/types.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

ORG_GROUP_PARAM = "org_scope_group_id"
ORG_UNIT_PARAM = "org_scope_unit_id"
SUBTREE_CTE_NAME = "org_scope_subtree"


class OrgScopeStrategy(str, Enum):
    TASK_OWNER_UNIT = "task_owner_unit"
    OWNER_UNIT = "owner_unit"


@dataclass(frozen=True)
class OrgScopeParams:
    org_group_id: Optional[int] = None
    org_unit_id: Optional[int] = None
    include_inactive_units: bool = False


@dataclass(frozen=True)
class OrgScopeSql:
    cte_sql: str
    where_sql: str
    params: Dict[str, Any]


@dataclass(frozen=True)
class DepartmentGroup:
    group_id: int
    group_name: str

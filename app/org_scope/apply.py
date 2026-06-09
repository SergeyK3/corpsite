# FILE: app/org_scope/apply.py
from __future__ import annotations

from typing import List

from app.org_scope.resolver import task_effective_owner_unit_sql
from app.org_scope.types import (
    ORG_GROUP_PARAM,
    ORG_UNIT_PARAM,
    SUBTREE_CTE_NAME,
    OrgScopeParams,
    OrgScopeSql,
    OrgScopeStrategy,
)


def build_subtree_cte_sql(
    *,
    root_param_name: str = ORG_UNIT_PARAM,
    cte_name: str = SUBTREE_CTE_NAME,
    include_inactive: bool = False,
) -> str:
    active_filter = "" if include_inactive else "AND COALESCE(child.is_active, TRUE) = TRUE"
    return f"""
WITH RECURSIVE {cte_name} AS (
    SELECT ou.unit_id
    FROM public.org_units ou
    WHERE ou.unit_id = :{root_param_name}

    UNION ALL

    SELECT child.unit_id
    FROM public.org_units child
    JOIN {cte_name} s ON s.unit_id = child.parent_unit_id
    WHERE TRUE
      {active_filter}
)
""".strip()


def _group_filter_exists_sql(*, unit_expr: str) -> str:
    return f"""
EXISTS (
    SELECT 1
    FROM public.org_units ou_scope
    WHERE ou_scope.unit_id = ({unit_expr})
      AND ou_scope.group_id = :{ORG_GROUP_PARAM}
)
""".strip()


def _unit_subtree_filter_sql(*, unit_expr: str) -> str:
    return f"({unit_expr}) IN (SELECT unit_id FROM {SUBTREE_CTE_NAME})"


def _unit_expr_for_strategy(
    *,
    strategy: OrgScopeStrategy,
    task_alias: str,
    regular_task_alias: str,
    owner_unit_column: str,
) -> str:
    if strategy == OrgScopeStrategy.TASK_OWNER_UNIT:
        return task_effective_owner_unit_sql(
            task_alias=task_alias,
            regular_task_alias=regular_task_alias,
        )
    if strategy == OrgScopeStrategy.OWNER_UNIT:
        return f"{regular_task_alias}.{owner_unit_column}"
    raise ValueError(f"unsupported org scope strategy: {strategy}")


def apply_org_scope(
    *,
    strategy: OrgScopeStrategy,
    params: OrgScopeParams,
    task_alias: str = "t",
    regular_task_alias: str = "rt",
    owner_unit_column: str = "owner_unit_id",
) -> OrgScopeSql:
    if params.org_group_id is None and params.org_unit_id is None:
        return OrgScopeSql(cte_sql="", where_sql="TRUE", params={})

    unit_expr = _unit_expr_for_strategy(
        strategy=strategy,
        task_alias=task_alias,
        regular_task_alias=regular_task_alias,
        owner_unit_column=owner_unit_column,
    )

    sql_params: dict = {}
    where_parts: List[str] = []
    cte_sql = ""

    if params.org_unit_id is not None:
        sql_params[ORG_UNIT_PARAM] = int(params.org_unit_id)
        cte_sql = build_subtree_cte_sql(
            include_inactive=params.include_inactive_units,
        )

    if params.org_group_id is not None:
        sql_params[ORG_GROUP_PARAM] = int(params.org_group_id)
        where_parts.append(_group_filter_exists_sql(unit_expr=unit_expr))

    if params.org_unit_id is not None:
        where_parts.append(_unit_subtree_filter_sql(unit_expr=unit_expr))

    where_sql = " AND ".join(where_parts) if where_parts else "TRUE"
    return OrgScopeSql(cte_sql=cte_sql, where_sql=where_sql, params=sql_params)


def apply_org_group_filter(
    *,
    strategy: OrgScopeStrategy,
    org_group_id: int,
    task_alias: str = "t",
    regular_task_alias: str = "rt",
    owner_unit_column: str = "owner_unit_id",
) -> OrgScopeSql:
    return apply_org_scope(
        strategy=strategy,
        params=OrgScopeParams(org_group_id=int(org_group_id)),
        task_alias=task_alias,
        regular_task_alias=regular_task_alias,
        owner_unit_column=owner_unit_column,
    )


def apply_org_unit_filter(
    *,
    strategy: OrgScopeStrategy,
    org_unit_id: int,
    include_inactive_units: bool = False,
    task_alias: str = "t",
    regular_task_alias: str = "rt",
    owner_unit_column: str = "owner_unit_id",
) -> OrgScopeSql:
    return apply_org_scope(
        strategy=strategy,
        params=OrgScopeParams(
            org_unit_id=int(org_unit_id),
            include_inactive_units=include_inactive_units,
        ),
        task_alias=task_alias,
        regular_task_alias=regular_task_alias,
        owner_unit_column=owner_unit_column,
    )


def merge_org_scope_sql(parts: List[OrgScopeSql]) -> OrgScopeSql:
    cte_chunks: List[str] = []
    where_parts: List[str] = []
    params: dict = {}

    for part in parts:
        if part.cte_sql:
            body = part.cte_sql.strip()
            if body.upper().startswith("WITH RECURSIVE"):
                body = body[len("WITH RECURSIVE") :].strip()
            cte_chunks.append(body)
        if part.where_sql and part.where_sql != "TRUE":
            where_parts.append(f"({part.where_sql})")
        params.update(part.params)

    cte_sql = ""
    if cte_chunks:
        cte_sql = "WITH RECURSIVE\n" + ",\n".join(cte_chunks)

    if not where_parts:
        where_sql = "TRUE"
    else:
        where_sql = " AND ".join(where_parts)

    return OrgScopeSql(cte_sql=cte_sql, where_sql=where_sql, params=params)

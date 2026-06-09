# tests/test_org_scope_apply.py
from __future__ import annotations

from app.org_scope.apply import apply_org_scope, build_subtree_cte_sql, merge_org_scope_sql
from app.org_scope.resolver import task_effective_owner_unit_sql
from app.org_scope.types import ORG_GROUP_PARAM, ORG_UNIT_PARAM, OrgScopeParams, OrgScopeStrategy


def test_apply_org_scope_empty_params_returns_true():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.TASK_OWNER_UNIT,
        params=OrgScopeParams(),
    )
    assert result.cte_sql == ""
    assert result.where_sql == "TRUE"
    assert result.params == {}


def test_apply_org_group_only_task_owner_unit_sql():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.TASK_OWNER_UNIT,
        params=OrgScopeParams(org_group_id=3),
    )
    assert result.cte_sql == ""
    assert "ou_scope.group_id = :org_scope_group_id" in result.where_sql
    assert "to_jsonb(t)" in result.where_sql
    assert "to_jsonb(rt)" in result.where_sql
    assert result.params == {ORG_GROUP_PARAM: 3}


def test_apply_org_unit_only_task_owner_unit_subtree_sql():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.TASK_OWNER_UNIT,
        params=OrgScopeParams(org_unit_id=44),
    )
    assert "WITH RECURSIVE org_scope_subtree" in result.cte_sql
    assert "IN (SELECT unit_id FROM org_scope_subtree)" in result.where_sql
    assert "executor_role_id" not in result.where_sql.lower()
    assert "public.users" not in result.where_sql.lower()
    assert result.params == {ORG_UNIT_PARAM: 44}


def test_apply_both_group_and_unit_combined_with_and():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.TASK_OWNER_UNIT,
        params=OrgScopeParams(org_group_id=1, org_unit_id=44),
    )
    assert result.cte_sql
    assert " AND " in result.where_sql
    assert "ou_scope.group_id = :org_scope_group_id" in result.where_sql
    assert "IN (SELECT unit_id FROM org_scope_subtree)" in result.where_sql
    assert result.params == {ORG_GROUP_PARAM: 1, ORG_UNIT_PARAM: 44}


def test_apply_owner_unit_strategy_group_sql_shape():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.OWNER_UNIT,
        params=OrgScopeParams(org_group_id=2),
        regular_task_alias="rt",
        owner_unit_column="owner_unit_id",
    )
    assert "rt.owner_unit_id" in result.where_sql
    assert "to_jsonb" not in result.where_sql
    assert result.params == {ORG_GROUP_PARAM: 2}


def test_apply_owner_unit_strategy_unit_sql_shape():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.OWNER_UNIT,
        params=OrgScopeParams(org_unit_id=10),
        regular_task_alias="rt",
    )
    assert "(rt.owner_unit_id) IN (SELECT unit_id FROM org_scope_subtree)" in result.where_sql
    assert result.params == {ORG_UNIT_PARAM: 10}


def test_task_owner_unit_does_not_reference_executor_role_or_users():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.TASK_OWNER_UNIT,
        params=OrgScopeParams(org_group_id=3, org_unit_id=44),
    )
    combined = f"{result.cte_sql} {result.where_sql}".lower()
    assert "executor_role_id" not in combined
    assert "public.users" not in combined


def test_param_names_stable():
    result = apply_org_scope(
        strategy=OrgScopeStrategy.TASK_OWNER_UNIT,
        params=OrgScopeParams(org_group_id=1, org_unit_id=2),
    )
    assert ORG_GROUP_PARAM in result.params
    assert ORG_UNIT_PARAM in result.params
    assert "org_unit_id" not in result.params
    assert "org_group_id" not in result.params


def test_build_subtree_cte_sql_uses_configured_param_name():
    sql = build_subtree_cte_sql()
    assert ":org_scope_unit_id" in sql
    assert "org_scope_subtree" in sql


def test_task_effective_owner_unit_sql_is_used_by_task_owner_unit_strategy():
    expected = task_effective_owner_unit_sql(task_alias="t", regular_task_alias="rt")
    result = apply_org_scope(
        strategy=OrgScopeStrategy.TASK_OWNER_UNIT,
        params=OrgScopeParams(org_unit_id=5),
    )
    assert expected in result.where_sql


def test_merge_org_scope_sql_combines_parts():
    left = apply_org_scope(
        strategy=OrgScopeStrategy.OWNER_UNIT,
        params=OrgScopeParams(org_group_id=1),
    )
    right = apply_org_scope(
        strategy=OrgScopeStrategy.OWNER_UNIT,
        params=OrgScopeParams(org_unit_id=2),
    )
    merged = merge_org_scope_sql([left, right])
    assert "org_scope_group_id" in merged.params
    assert "org_scope_unit_id" in merged.params
    assert merged.where_sql != "TRUE"

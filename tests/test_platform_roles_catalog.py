from __future__ import annotations

import pytest

from app.services.platform_roles_catalog import is_pytest_test_role, pytest_role_exclusion_sql


def test_is_pytest_test_role_by_code_or_name():
    assert is_pytest_test_role(role_code="pytest_executor")
    assert is_pytest_test_role(role_code="pytest_initiator_ab12cd34")
    assert is_pytest_test_role(role_name="pytest_manager_1")
    assert not is_pytest_test_role(role_code="QM_HEAD", role_name="QM Head")


def test_pytest_role_exclusion_sql_fragment():
    sql = pytest_role_exclusion_sql(code_expr="role_code", name_expr="role_name")
    assert "pytest\\_%" in sql
    assert "role_code" in sql
    assert "role_name" in sql

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from scripts.provision_employee_accounts import AccountSpec, parse_account_spec, parse_account_specs, provision
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


def test_parse_account_spec_accepts_explicit_classic_login() -> None:
    assert parse_account_spec("13:akiltaeva.bs") == AccountSpec(13, "akiltaeva.bs")


@pytest.mark.parametrize("value", ("", "0:valid", "x:valid", "13:", "13:Upper", "13:has space", "13:two:colons"))
def test_parse_account_spec_rejects_unsafe_or_ambiguous_input(value: str) -> None:
    with pytest.raises(ValueError):
        parse_account_spec(value)


def test_parse_account_specs_rejects_duplicate_employee_or_login() -> None:
    with pytest.raises(ValueError, match="employee_id"):
        parse_account_specs(("13:first.a", "13:second.b"))
    with pytest.raises(ValueError, match="login"):
        parse_account_specs(("13:same.a", "15:same.a"))


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_dry_run_preflights_postgres_without_creating_users_or_audit(seed) -> None:
    """The real provisioning preflight must remain completely write-free."""
    require_ppr_schema()
    with engine.begin() as conn:
        required = {"roles", "users", "audit_log", "security_audit_log", "access_grants", "access_roles"}
        if any(not table_exists(conn, name) for name in required):
            pytest.skip("provisioning schema is incomplete")
        suffix = uuid4().hex[:10]
        person_id = insert_person(conn, full_name=f"Provision Dry Run {suffix}")
        employee_id = insert_employee(
            conn,
            full_name=f"Provision Dry Run Employee {suffix}",
            person_id=person_id,
            operational_status="active",
        )
        conn.execute(
            text("UPDATE public.employees SET org_unit_id = :unit_id WHERE employee_id = :employee_id"),
            {"unit_id": int(seed["unit_id"]), "employee_id": employee_id},
        )
    login = f"provision_dry_{suffix}"
    try:
        result = provision(
            specs=(AccountSpec(employee_id=employee_id, login=login),),
            password=None,
            dry_run=True,
        )
        assert result == {
            "status": "dry_run_ok",
            "role_code": "EMPLOYEE",
            "accounts": [{"employee_id": employee_id, "login": login}],
        }
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT COUNT(*) FROM public.users WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            ).scalar_one() == 0
            assert conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.audit_log
                    WHERE after_data->>'source' = 'explicit_local_employee_provisioning'
                      AND after_data->>'employee_id' = :employee_id
                    """
                ),
                {"employee_id": str(employee_id)},
            ).scalar_one() == 0
            assert conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM public.security_audit_log
                    WHERE target_employee_id = :employee_id
                      AND metadata->>'link_source' = 'explicit_local_employee_provisioning'
                    """
                ),
                {"employee_id": employee_id},
            ).scalar_one() == 0
    finally:
        with engine.begin() as conn:
            cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])

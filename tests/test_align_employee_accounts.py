"""PostgreSQL contract for locked, non-mutating account-alignment preflight."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from scripts.align_employee_accounts import (
    FUTURE_QM_RENAMES,
    CheckedRenameSpec,
    CheckedRoleChangeSpec,
    PersonCreateSpec,
    PersonLinkSpec,
    RenameSpec,
    align,
    parse_checked_rename,
    parse_checked_role_change,
    parse_create,
    parse_person_create,
    parse_person_link,
    parse_rename,
    parse_role_change,
)
from tests.conftest import create_non_privileged_role, create_user, table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema
from tests.personnel_lk.conftest import unique_iin


def test_parser_accepts_only_explicit_alignment_actions() -> None:
    assert parse_rename("10014:10009:saparbaeva.zs") == RenameSpec(10014, 10009, "saparbaeva.zs")
    assert parse_person_link("10044:10391") == PersonLinkSpec(10044, 10391)
    assert parse_role_change("10020:DEP_ADMIN:DEP_OUTPATIENT_AUDIT").new_role_code == "DEP_OUTPATIENT_AUDIT"
    assert parse_person_create("10440:00000000-0000-4000-8000-000000010440") == PersonCreateSpec(10440, "00000000-0000-4000-8000-000000010440")
    assert parse_create("10440:orazbekov.bs:DEP_MED").role_code == "DEP_MED"
    assert parse_checked_rename("10002:10001:qm_head@corp.local:masimov.ab") == CheckedRenameSpec(10002, 10001, "qm_head@corp.local", "masimov.ab")
    assert parse_checked_role_change("10020:10045:kozgambaeva.lt:DEP_ADMIN:DEP_OUTPATIENT_AUDIT") == CheckedRoleChangeSpec(10020, 10045, "kozgambaeva.lt", "DEP_ADMIN", "DEP_OUTPATIENT_AUDIT")
    assert FUTURE_QM_RENAMES == (
        ("qm_head@corp.local", "masimov.ab"),
        ("qm_hosp@corp.local", "seytkazina.gt"),
        ("qm_amb@corp.local", "akiltaeva.bs"),
        ("qm_complaint_reg@corp.local", "abdina.ak"),
        ("qm_complaint_pat@corp.local", "musabekov.ka"),
        ("qm_intern_educat@corp.local", "saparbaeva.zs"),
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_checked_qm_renames_dry_run_returns_all_six_without_writes_or_sequences(seed) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    role_id = None
    employee_ids: list[int] = []
    user_ids: list[int] = []
    mappings = [(f"checked_qm_old_{index}_{suffix}", f"checked_qm_new_{index}_{suffix}") for index in range(1, 7)]
    try:
        with engine.begin() as conn:
            required = {"users", "roles", "audit_log", "security_audit_log"}
            if any(not table_exists(conn, name) for name in required):
                pytest.skip("alignment schema is incomplete")
            role_id = create_non_privileged_role(conn, f"pytest_checked_qm_{suffix}")
            for index, (old_login, _new_login) in enumerate(mappings, start=1):
                employee_id = insert_employee(conn, full_name=f"Checked QM {index} {suffix}", person_id=None, operational_status="active")
                conn.execute(text("UPDATE public.employees SET org_unit_id=:unit_id WHERE employee_id=:employee_id"), {"unit_id": int(seed["unit_id"]), "employee_id": employee_id})
                user_id = create_user(conn, full_name=f"Checked QM {index} {suffix}", role_id=role_id, unit_id=int(seed["unit_id"]))
                conn.execute(text("UPDATE public.users SET employee_id=:employee_id, login=:login, password_hash='test-hash' WHERE user_id=:user_id"), {"employee_id": employee_id, "login": old_login, "user_id": user_id})
                employee_ids.append(employee_id)
                user_ids.append(user_id)
            before_audit = conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one()
            before_security_audit = conn.execute(text("SELECT COUNT(*) FROM public.security_audit_log WHERE metadata->>'source'='approved_account_alignment'" )).scalar_one()
            before_sequence = conn.execute(text("SELECT pg_sequence_last_value(pg_get_serial_sequence('public.users', 'user_id')::regclass)" )).scalar_one()

        checked = tuple(
            CheckedRenameSpec(user_id, employee_id, old_login, new_login)
            for user_id, employee_id, (old_login, new_login) in zip(user_ids, employee_ids, mappings, strict=True)
        )
        result = align(checked_renames=checked)
        assert result["status"] == "dry_run_ok"
        assert result["checked_renames"] == [
            {"user_id": item.user_id, "employee_id": item.employee_id, "old_login": item.old_login, "login": item.login}
            for item in checked
        ]

        with engine.connect() as conn:
            assert conn.execute(text("SELECT array_agg(login ORDER BY user_id) FROM public.users WHERE user_id = ANY(:user_ids)"), {"user_ids": user_ids}).scalar_one() == [item.old_login for item in checked]
            assert conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one() == before_audit
            assert conn.execute(text("SELECT COUNT(*) FROM public.security_audit_log WHERE metadata->>'source'='approved_account_alignment'" )).scalar_one() == before_security_audit
            assert conn.execute(text("SELECT pg_sequence_last_value(pg_get_serial_sequence('public.users', 'user_id')::regclass)" )).scalar_one() == before_sequence
    finally:
        if user_ids:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id = ANY(:user_ids)"), {"user_ids": user_ids})
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = ANY(:employee_ids)"), {"employee_ids": employee_ids})
                conn.execute(text("DELETE FROM public.roles WHERE role_id=:role_id"), {"role_id": role_id})


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("mismatch", ["login", "employee"], ids=["old-login", "employee-id"])
def test_checked_rename_mismatch_blocks_entire_package_before_writes(seed, mismatch: str) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    role_id = first_employee = second_employee = first_user = second_user = None
    try:
        with engine.begin() as conn:
            role_id = create_non_privileged_role(conn, f"pytest_checked_block_{suffix}")
            first_employee = insert_employee(conn, full_name=f"Checked Block One {suffix}", person_id=None, operational_status="active")
            second_employee = insert_employee(conn, full_name=f"Checked Block Two {suffix}", person_id=None, operational_status="active")
            for employee_id in (first_employee, second_employee):
                conn.execute(text("UPDATE public.employees SET org_unit_id=:unit_id WHERE employee_id=:employee_id"), {"unit_id": int(seed["unit_id"]), "employee_id": employee_id})
            first_user = create_user(conn, full_name=f"Checked Block One {suffix}", role_id=role_id, unit_id=int(seed["unit_id"]))
            second_user = create_user(conn, full_name=f"Checked Block Two {suffix}", role_id=role_id, unit_id=int(seed["unit_id"]))
            conn.execute(text("UPDATE public.users SET employee_id=:employee_id, login=:login WHERE user_id=:user_id"), {"employee_id": first_employee, "login": f"checked_one_{suffix}", "user_id": first_user})
            conn.execute(text("UPDATE public.users SET employee_id=:employee_id, login=:login WHERE user_id=:user_id"), {"employee_id": second_employee, "login": f"checked_two_{suffix}", "user_id": second_user})
            before_audit = conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one()

        bad_employee = second_employee if mismatch == "employee" else first_employee
        bad_login = f"not_current_{suffix}" if mismatch == "login" else f"checked_one_{suffix}"
        with pytest.raises(RuntimeError, match="Checked rename"):
            align(checked_renames=(
                CheckedRenameSpec(first_user, first_employee, f"checked_one_{suffix}", f"checked_one_new_{suffix}"),
                CheckedRenameSpec(second_user, bad_employee, bad_login, f"checked_two_new_{suffix}"),
            ))
        with engine.connect() as conn:
            assert conn.execute(text("SELECT array_agg(login ORDER BY user_id) FROM public.users WHERE user_id = ANY(:user_ids)"), {"user_ids": [first_user, second_user]}).scalar_one() == [f"checked_one_{suffix}", f"checked_two_{suffix}"]
            assert conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one() == before_audit
    finally:
        if first_user is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id = ANY(:user_ids)"), {"user_ids": [first_user, second_user]})
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = ANY(:employee_ids)"), {"employee_ids": [first_employee, second_employee]})
                conn.execute(text("DELETE FROM public.roles WHERE role_id=:role_id"), {"role_id": role_id})


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
@pytest.mark.parametrize("mismatch", ["employee", "login", "role"], ids=["employee-id", "current-login", "current-role"])
def test_checked_role_change_mismatch_blocks_entire_package_before_writes(seed, mismatch: str) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    old_role_id = new_role_id = employee_id = other_employee_id = user_id = None
    old_role_code = f"PYTEST_CHECKED_OLD_{suffix.upper()}"
    new_role_code = f"PYTEST_CHECKED_NEW_{suffix.upper()}"
    login = f"checked_role_{suffix}"
    try:
        with engine.begin() as conn:
            old_role_id = create_non_privileged_role(conn, old_role_code)
            new_role_id = create_non_privileged_role(conn, new_role_code)
            employee_id = insert_employee(conn, full_name=f"Checked Role {suffix}", person_id=None, operational_status="active")
            other_employee_id = insert_employee(conn, full_name=f"Checked Role Other {suffix}", person_id=None, operational_status="active")
            for current_employee_id in (employee_id, other_employee_id):
                conn.execute(text("UPDATE public.employees SET org_unit_id=:unit_id WHERE employee_id=:employee_id"), {"unit_id": int(seed["unit_id"]), "employee_id": current_employee_id})
            user_id = create_user(conn, full_name=f"Checked Role {suffix}", role_id=old_role_id, unit_id=int(seed["unit_id"]))
            conn.execute(text("UPDATE public.users SET employee_id=:employee_id, login=:login WHERE user_id=:user_id"), {"employee_id": employee_id, "login": login, "user_id": user_id})
            before_audit = conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one()

        expected_employee_id = other_employee_id if mismatch == "employee" else employee_id
        expected_login = f"not_{login}" if mismatch == "login" else login
        expected_role_code = f"NOT_{old_role_code}" if mismatch == "role" else old_role_code
        with pytest.raises(RuntimeError, match="Checked role change"):
            align(checked_role_changes=(CheckedRoleChangeSpec(user_id, expected_employee_id, expected_login, expected_role_code, new_role_code),))
        with engine.connect() as conn:
            row = conn.execute(text("""SELECT u.employee_id, u.login, r.code AS role_code
                FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
                WHERE u.user_id=:user_id"""), {"user_id": user_id}).mappings().one()
            assert dict(row) == {"employee_id": employee_id, "login": login, "role_code": old_role_code}
            assert conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one() == before_audit
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id=:user_id"), {"user_id": user_id})
                conn.execute(text("DELETE FROM public.employees WHERE employee_id IN (:employee_id,:other_employee_id)"), {"employee_id": employee_id, "other_employee_id": other_employee_id})
                conn.execute(text("DELETE FROM public.roles WHERE role_id IN (:old_role_id,:new_role_id)"), {"old_role_id": old_role_id, "new_role_id": new_role_id})


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_dry_run_locks_and_preflights_without_mutating_person_user_or_audit(seed) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    person_id = employee_id = user_id = role_id = None
    old_login = f"align_old_{suffix}"
    new_login = f"align_new_{suffix}"
    try:
        with engine.begin() as conn:
            required = {"users", "roles", "audit_log", "security_audit_log"}
            if any(not table_exists(conn, name) for name in required):
                pytest.skip("alignment schema is incomplete")
            role_id = create_non_privileged_role(conn, f"pytest_align_{suffix}")
            person_id = insert_person(conn, full_name=f"Alignment Person {suffix}")
            employee_id = insert_employee(conn, full_name=f"Alignment Person {suffix}", person_id=None, operational_status="active")
            conn.execute(text("UPDATE public.employees SET org_unit_id=:unit_id WHERE employee_id=:employee_id"), {"unit_id": int(seed["unit_id"]), "employee_id": employee_id})
            user_id = create_user(conn, full_name=f"Alignment Person {suffix}", role_id=role_id, unit_id=int(seed["unit_id"]))
            conn.execute(text("UPDATE public.users SET employee_id=:employee_id, login=:login, password_hash='test-hash' WHERE user_id=:user_id"), {"employee_id": employee_id, "login": old_login, "user_id": user_id})
            before_audit = conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one()
            before_security_audit = conn.execute(text("SELECT COUNT(*) FROM public.security_audit_log WHERE metadata->>'source'='approved_account_alignment'" )).scalar_one()
            before_sequences = conn.execute(text("""SELECT
                pg_sequence_last_value(pg_get_serial_sequence('public.persons', 'person_id')::regclass) AS person_sequence,
                pg_sequence_last_value(pg_get_serial_sequence('public.users', 'user_id')::regclass) AS user_sequence""")).mappings().one()

        result = align(
            renames=(RenameSpec(user_id=user_id, employee_id=employee_id, login=new_login),),
            links=(PersonLinkSpec(employee_id=employee_id, person_id=person_id),),
        )
        assert result["status"] == "dry_run_ok"

        with engine.connect() as conn:
            assert conn.execute(text("SELECT person_id FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": employee_id}).scalar_one() is None
            assert conn.execute(text("SELECT login FROM public.users WHERE user_id=:user_id"), {"user_id": user_id}).scalar_one() == old_login
            assert conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment'" )).scalar_one() == before_audit
            assert conn.execute(text("SELECT COUNT(*) FROM public.security_audit_log WHERE metadata->>'source'='approved_account_alignment'" )).scalar_one() == before_security_audit
            after_sequences = conn.execute(text("""SELECT
                pg_sequence_last_value(pg_get_serial_sequence('public.persons', 'person_id')::regclass) AS person_sequence,
                pg_sequence_last_value(pg_get_serial_sequence('public.users', 'user_id')::regclass) AS user_sequence""")).mappings().one()
            assert dict(after_sequences) == dict(before_sequences)
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM public.users WHERE user_id=:user_id"), {"user_id": user_id})
                cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])
                conn.execute(text("DELETE FROM public.roles WHERE role_id=:role_id"), {"role_id": role_id})


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_apply_renames_and_links_without_replacing_existing_user_fields(seed) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    person_id = employee_id = user_id = role_id = None
    old_login = f"align_apply_old_{suffix}"
    new_login = f"align_apply_new_{suffix}"
    try:
        with engine.begin() as conn:
            role_id = create_non_privileged_role(conn, f"pytest_align_apply_{suffix}")
            person_id = insert_person(conn, full_name=f"Alignment Apply {suffix}")
            employee_id = insert_employee(conn, full_name=f"Alignment Apply {suffix}", person_id=None, operational_status="active")
            conn.execute(text("UPDATE public.employees SET org_unit_id=:unit_id WHERE employee_id=:employee_id"), {"unit_id": int(seed["unit_id"]), "employee_id": employee_id})
            user_id = create_user(conn, full_name=f"Alignment Apply {suffix}", role_id=role_id, unit_id=int(seed["unit_id"]))
            conn.execute(text("""UPDATE public.users SET employee_id=:employee_id, login=:login,
                         password_hash='test-hash', google_login='preserve-google' WHERE user_id=:user_id"""), {"employee_id": employee_id, "login": old_login, "user_id": user_id})

        assert align(
            renames=(RenameSpec(user_id=user_id, employee_id=employee_id, login=new_login),),
            links=(PersonLinkSpec(employee_id=employee_id, person_id=person_id),),
            execute=True,
        ) == {"status": "committed"}

        with engine.connect() as conn:
            row = conn.execute(text("SELECT employee_id, login, password_hash, google_login FROM public.users WHERE user_id=:user_id"), {"user_id": user_id}).mappings().one()
            assert dict(row) == {"employee_id": employee_id, "login": new_login, "password_hash": "test-hash", "google_login": "preserve-google"}
            assert conn.execute(text("SELECT person_id FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": employee_id}).scalar_one() == person_id
            assert conn.execute(text("SELECT COUNT(*) FROM public.audit_log WHERE entity_id=:user_id AND action='USER_LOGIN_RENAMED'"), {"user_id": user_id}).scalar_one() == 1
    finally:
        if user_id is not None:
            with engine.begin() as conn:
                conn.execute(text("""DELETE FROM public.security_audit_log
                    WHERE (target_user_id=:user_id OR target_employee_id=:employee_id)
                      AND metadata->>'source'='approved_account_alignment'"""), {"user_id": user_id, "employee_id": employee_id})
                conn.execute(text("DELETE FROM public.audit_log WHERE entity_id=:user_id AND after_data->>'source'='approved_account_alignment'"), {"user_id": user_id})
                conn.execute(text("DELETE FROM public.audit_log WHERE entity_id=:employee_id AND after_data->>'source'='approved_account_alignment'"), {"employee_id": employee_id})
                conn.execute(text("DELETE FROM public.users WHERE user_id=:user_id"), {"user_id": user_id})
                cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[employee_id])
                conn.execute(text("DELETE FROM public.roles WHERE role_id=:role_id"), {"role_id": role_id})


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_governance_person_create_user_create_rollback_and_repeat_are_fail_closed(seed) -> None:
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    actor = int(seed["initiator_user_id"])
    role_id = person_employee = legacy_employee = legacy_user = blocked_employee = None
    created_person_id = created_user_id = None
    request_id = f"00000000-0000-4000-8000-{int(uuid4().int % 10**12):012d}"
    try:
        with engine.begin() as conn:
            required = {"employee_identities", "personnel_identity_link_operations", "security_audit_log"}
            if any(not table_exists(conn, name) for name in required):
                pytest.skip("active employee governance schema is incomplete")
            role_code = f"PYTEST_ALIGN_GOVERNANCE_{suffix.upper()}"
            role_id = create_non_privileged_role(conn, role_code)
            person_employee = insert_employee(conn, full_name=f"Governance Person {suffix}", person_id=None, operational_status="active")
            legacy_employee = insert_employee(conn, full_name=f"Governance Legacy {suffix}", person_id=None, operational_status="active")
            blocked_employee = insert_employee(conn, full_name=f"Governance Rollback {suffix}", person_id=None, operational_status="active")
            position_id = conn.execute(text("SELECT position_id FROM public.positions ORDER BY position_id LIMIT 1")).scalar_one()
            for employee_id in (person_employee, legacy_employee, blocked_employee):
                conn.execute(text("UPDATE public.employees SET org_unit_id=:unit_id, position_id=:position_id, is_active=TRUE, operational_status='active' WHERE employee_id=:employee_id"), {"unit_id": int(seed["unit_id"]), "position_id": position_id, "employee_id": employee_id})
            for employee_id in (person_employee, blocked_employee):
                conn.execute(text("INSERT INTO public.employee_identities(employee_id,identity_type,identity_value,is_primary,created_by) VALUES (:employee_id,'IIN',:iin,TRUE,:actor)"), {"employee_id": employee_id, "iin": unique_iin("7"), "actor": actor})
            legacy_user = create_user(conn, full_name=f"Governance Legacy {suffix}", role_id=role_id, unit_id=int(seed["unit_id"]))
            conn.execute(text("UPDATE public.users SET employee_id=:employee_id, login=:login, password_hash='legacy-hash' WHERE user_id=:user_id"), {"employee_id": legacy_employee, "login": f"governance_old_{suffix}", "user_id": legacy_user})

        result = align(
            person_creates=(PersonCreateSpec(person_employee, request_id),),
            creates=(parse_create(f"{person_employee}:governance_new_{suffix}:{role_code}"),),
            renames=(RenameSpec(legacy_user, legacy_employee, f"governance_renamed_{suffix}"),),
            actor_user_id=actor,
            execute=True,
            password="temporary-password",
        )
        assert result == {"status": "committed"}
        with engine.connect() as conn:
            created_person_id = conn.execute(text("SELECT person_id FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": person_employee}).scalar_one()
            created_user_id = conn.execute(text("SELECT user_id FROM public.users WHERE employee_id=:employee_id"), {"employee_id": person_employee}).scalar_one()
            assert created_person_id is not None and created_user_id is not None
            assert conn.execute(text("SELECT login FROM public.users WHERE user_id=:user_id"), {"user_id": legacy_user}).scalar_one() == f"governance_renamed_{suffix}"

        with pytest.raises(RuntimeError, match="already has a Person link"):
            align(person_creates=(PersonCreateSpec(person_employee, request_id),), actor_user_id=actor)
        with pytest.raises(RuntimeError, match="Role MISSING_ROLE is missing"):
            align(person_creates=(PersonCreateSpec(blocked_employee, f"00000000-0000-4000-8000-{int(uuid4().int % 10**12):012d}"),), creates=(parse_create(f"{blocked_employee}:blocked_{suffix}:MISSING_ROLE"),), actor_user_id=actor)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT person_id FROM public.employees WHERE employee_id=:employee_id"), {"employee_id": blocked_employee}).scalar_one() is None
    finally:
        with engine.begin() as conn:
            if created_user_id is not None:
                conn.execute(text("DELETE FROM public.security_audit_log WHERE (target_user_id IN (:created_user_id,:legacy_user) OR target_employee_id IN (:person_employee,:legacy_employee)) AND metadata->>'source'='approved_account_alignment'"), {"created_user_id": created_user_id, "legacy_user": legacy_user, "person_employee": person_employee, "legacy_employee": legacy_employee})
                conn.execute(text("DELETE FROM public.audit_log WHERE after_data->>'source'='approved_account_alignment' AND entity_id IN (:created_user_id,:legacy_user,:person_employee,:legacy_employee)"), {"created_user_id": created_user_id, "legacy_user": legacy_user, "person_employee": person_employee, "legacy_employee": legacy_employee})
                conn.execute(text("DELETE FROM public.users WHERE user_id IN (:created_user_id,:legacy_user)"), {"created_user_id": created_user_id, "legacy_user": legacy_user})
            if created_person_id is not None:
                conn.execute(text("SET LOCAL session_replication_role = replica"))
                try:
                    conn.execute(text("DELETE FROM public.personnel_identity_link_operations WHERE request_id=:request_id"), {"request_id": request_id})
                finally:
                    conn.execute(text("SET LOCAL session_replication_role = origin"))
                conn.execute(text("UPDATE public.employees SET person_id=NULL WHERE employee_id=:employee_id"), {"employee_id": person_employee})
                cleanup_person_graph(conn, person_ids=[created_person_id], employee_ids=[])
            if person_employee is not None:
                conn.execute(text("DELETE FROM public.employee_identities WHERE employee_id IN (:person_employee,:blocked_employee)"), {"person_employee": person_employee, "blocked_employee": blocked_employee})
                conn.execute(text("DELETE FROM public.employees WHERE employee_id IN (:person_employee,:legacy_employee,:blocked_employee)"), {"person_employee": person_employee, "legacy_employee": legacy_employee, "blocked_employee": blocked_employee})
            if role_id is not None:
                conn.execute(text("DELETE FROM public.roles WHERE role_id=:role_id"), {"role_id": role_id})

"""Real PostgreSQL coverage for ADR-065 atomic Person linking."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from app.db.engine import engine
from app.services.adr065_person_link_service import (
    PersonLinkError,
    build_precondition,
    link_person_tx,
)
from tests.personnel_applications.conftest import insert_person_with_iin
from tests.ppr.conftest import insert_employee
from tests.conftest import auth_headers
from app.main import app


@pytest.fixture
def pg_case():
    with engine.begin() as conn:
        actor = conn.execute(text("SELECT user_id FROM users WHERE login='adr065-test-operator' LIMIT 1")).scalar_one()
        unit = conn.execute(text("SELECT unit_id FROM org_units WHERE code='DISP' LIMIT 1")).scalar_one()
        iin = str(700000000000 + (uuid4().int % 999999)).zfill(12)
        employee_id = insert_employee(conn, full_name="Нурбеков Бахдат Байтлевич")
        conn.execute(text("UPDATE employees SET org_unit_id=:u WHERE employee_id=:e"), {"u": unit, "e": employee_id})
        conn.execute(text("INSERT INTO employee_identities(employee_id,identity_type,identity_value,is_primary,created_by) VALUES (:e,'IIN',:i,TRUE,:a)"), {"e": employee_id, "i": iin, "a": actor})
        import_code = f"ADR065-{uuid4().hex}"
        batch = conn.execute(text("INSERT INTO hr_import_batches(source_type,file_name,import_code,imported_by,status) VALUES ('HR_CONTROL_LIST','adr065.json',:code,:a,'PARSED') RETURNING batch_id"), {"code": import_code, "a": actor}).scalar_one()
        payload = json.dumps({"iin": iin, "full_name": "Нурбеков Багдат Байтлевич"})
        row = conn.execute(text("INSERT INTO hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,match_status,employee_id) VALUES (:b,'control',1,CAST(:p AS jsonb),CAST(:p AS jsonb),'AUTO_MATCH',:e) RETURNING row_id"), {"b": batch, "e": employee_id, "p": payload}).scalar_one()
        rec = conn.execute(text("INSERT INTO hr_import_normalized_records(batch_id,row_id,employee_id,source_field,source_text,source_record_key,record_kind,review_status) VALUES (:b,:r,:e,'education','x',:k,'education','approved') RETURNING normalized_record_id"), {"b": batch, "r": row, "e": employee_id, "k": str(uuid4())}).scalar_one()
    return {"actor": int(actor), "unit": int(unit), "iin": iin, "employee": int(employee_id), "record": int(rec)}


def _apply(case, **kw):
    with engine.begin() as conn:
        emp = conn.execute(text("SELECT full_name FROM employees WHERE employee_id=:e"), {"e": case["employee"]}).scalar_one()
        pre = _current_precondition(conn, case["employee"], emp, [case["record"]])
        args = dict(employee_id=case["employee"], normalized_record_ids=[case["record"]], expected_precondition=pre, request_id=str(uuid4()), actor_user_id=case["actor"], confirm_name_correction=True, scope_unit_ids={case["unit"]})
        args.update(kw)
        return link_person_tx(conn, **args)


def _current_precondition(conn, employee_id, full_name, record_ids):
    records = list(conn.execute(text("SELECT nr.normalized_record_id,nr.row_id,nr.batch_id,nr.employee_id,nr.review_status,ir.normalized_payload FROM hr_import_normalized_records nr JOIN hr_import_rows ir ON ir.row_id=nr.row_id AND ir.batch_id=nr.batch_id WHERE nr.normalized_record_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": record_ids}).mappings())
    return build_precondition(employee_id, full_name, records)


def test_create_replay_and_audit_without_iin(pg_case):
    with engine.begin() as conn:
        original_precondition = build_precondition(pg_case["employee"], "Нурбеков Бахдат Байтлевич", list(conn.execute(text("SELECT nr.normalized_record_id,nr.row_id,nr.batch_id,nr.employee_id,nr.review_status,ir.normalized_payload FROM hr_import_normalized_records nr JOIN hr_import_rows ir ON ir.row_id=nr.row_id AND ir.batch_id=nr.batch_id WHERE nr.normalized_record_id=:id"), {"id": pg_case["record"]}).mappings()))
    result = _apply(pg_case, request_id="adr065-create-replay", expected_precondition=original_precondition)
    assert result["decision"] == "CREATE"
    replay = _apply(pg_case, request_id="adr065-create-replay", expected_precondition=original_precondition)
    assert replay["decision"] == "REPLAY" and replay["person_id"] == result["person_id"]
    with engine.begin() as conn:
        audit = conn.execute(text("SELECT old_full_name,new_full_name,normalized_record_ids::text FROM personnel_identity_link_operations WHERE request_id='adr065-create-replay'" )).one()
        assert pg_case["iin"] not in "|".join(map(str, audit))


@pytest.mark.parametrize("change", ["records", "precondition", "confirmation", "actor"])
def test_request_id_reuse_with_changed_payload_is_conflict(pg_case, change):
    with engine.begin() as conn:
        original_precondition = build_precondition(pg_case["employee"], "Нурбеков Бахдат Байтлевич", list(conn.execute(text("SELECT nr.normalized_record_id,nr.row_id,nr.batch_id,nr.employee_id,nr.review_status,ir.normalized_payload FROM hr_import_normalized_records nr JOIN hr_import_rows ir ON ir.row_id=nr.row_id AND ir.batch_id=nr.batch_id WHERE nr.normalized_record_id=:id"), {"id": pg_case["record"]}).mappings()))
    request_id = f"adr065-fingerprint-{change}"
    first = _apply(pg_case, request_id=request_id, expected_precondition=original_precondition)
    with engine.begin() as conn:
        before_audit = conn.execute(text("SELECT count(*) FROM personnel_identity_link_operations")).scalar_one()
        before_people = conn.execute(text("SELECT count(*) FROM persons WHERE iin=:i"), {"i": pg_case["iin"]}).scalar_one()
    overrides = {}
    if change == "records": overrides["normalized_record_ids"] = [pg_case["record"], pg_case["record"] + 999]
    if change == "precondition": overrides["expected_precondition"] = "changed-precondition"
    if change == "confirmation": overrides["confirm_name_correction"] = False
    if change == "actor": overrides["actor_user_id"] = pg_case["actor"] + 999
    with pytest.raises(PersonLinkError) as exc:
        _apply(pg_case, request_id=request_id, **overrides)
    assert exc.value.code == "REQUEST_ID_REUSE_CONFLICT"
    with engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM personnel_identity_link_operations")).scalar_one() == before_audit
        assert conn.execute(text("SELECT count(*) FROM persons WHERE iin=:i"), {"i": pg_case["iin"]}).scalar_one() == before_people
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() == first["person_id"]


def test_stale_precondition_and_name_confirmation(pg_case):
    with pytest.raises(PersonLinkError) as exc:
        _apply(pg_case, expected_precondition="stale", request_id="adr065-stale")
    assert exc.value.code == "STALE_PRECONDITION"
    with pytest.raises(PersonLinkError) as exc:
        _apply(pg_case, confirm_name_correction=False, request_id="adr065-no-name-confirm")
    assert exc.value.code == "NAME_CORRECTION_CONFIRMATION_REQUIRED"


def test_payload_change_after_preflight_is_stale_without_mutation(pg_case):
    with engine.begin() as conn:
        old_name = conn.execute(text("SELECT full_name FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one()
        expected = _current_precondition(conn, pg_case["employee"], old_name, [pg_case["record"]])
        conn.execute(text("UPDATE hr_import_rows SET normalized_payload=CAST(:payload AS jsonb) WHERE row_id=(SELECT row_id FROM hr_import_normalized_records WHERE normalized_record_id=:record)"), {"record": pg_case["record"], "payload": json.dumps({"iin": pg_case["iin"], "full_name": "Changed source name"})})
    with pytest.raises(PersonLinkError) as exc:
        _apply(pg_case, expected_precondition=expected, request_id="adr065-payload-stale")
    assert exc.value.code == "STALE_PRECONDITION"
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() is None
        assert conn.execute(text("SELECT count(*) FROM personnel_identity_link_operations WHERE request_id='adr065-payload-stale'")).scalar_one() == 0


def test_rollback_leaves_no_link(pg_case):
    request_id = "adr065-rollback"
    with pytest.raises(RuntimeError):
        with engine.begin() as conn:
            result = link_person_tx(conn, employee_id=pg_case["employee"], normalized_record_ids=[pg_case["record"]], expected_precondition=build_precondition(pg_case["employee"], "Нурбеков Бахдат Байтлевич", [pg_case["record"]]), request_id=request_id, actor_user_id=pg_case["actor"], confirm_name_correction=True, scope_unit_ids={pg_case["unit"]})
            assert result["person_id"]
            raise RuntimeError("forced rollback")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() is None


def test_adopt_existing_person(pg_case):
    with engine.begin() as conn:
        person_id = insert_person_with_iin(conn, full_name="Нурбеков Багдат Байтлевич", iin=pg_case["iin"], prefix="adr065-adopt")
    result = _apply(pg_case, request_id="adr065-adopt")
    assert result["decision"] == "ADOPT" and result["person_id"] == person_id
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() == person_id
        assert conn.execute(text("SELECT decision,person_id FROM personnel_identity_link_operations WHERE request_id='adr065-adopt'" )).one() == ("ADOPT", person_id)
        assert conn.execute(text("SELECT count(*) FROM persons WHERE iin=:i"), {"i": pg_case["iin"]}).scalar_one() == 1


def test_multiple_person_candidates_block(pg_case):
    with engine.begin() as conn:
        first = insert_person_with_iin(conn, full_name="Candidate one", iin=pg_case["iin"], prefix="adr065-c1")
        conn.execute(text("UPDATE persons SET person_status='inactive' WHERE person_id=:p"), {"p": first})
        insert_person_with_iin(conn, full_name="Candidate two", iin=pg_case["iin"], prefix="adr065-c2")
    with pytest.raises(PersonLinkError) as exc:
        _apply(pg_case, request_id="adr065-person-conflict")
    assert exc.value.code == "PERSON_IIN_AMBIGUOUS"
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() is None


def test_multiple_employee_iin_conflict_is_rejected_by_schema(pg_case):
    with engine.begin() as conn:
        other = insert_employee(conn, full_name="ADR065 conflicting Employee")
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO employee_identities(employee_id,identity_type,identity_value,is_primary,created_by) VALUES (:e,'IIN',:i,TRUE,:a)"), {"e": other, "i": pg_case["iin"], "a": pg_case["actor"]})
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() is None


def test_apply_api_denies_user_without_permission(pg_case):
    response = TestClient(app).post(
        "/directory/personnel/lk/control-list-repair/apply",
        headers=auth_headers(pg_case["actor"]),
        json={"employee_id": pg_case["employee"], "normalized_record_ids": [pg_case["record"]], "expected_precondition": "x", "request_id": "adr065-api-deny"},
    )
    assert response.status_code == 403
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() is None
        assert conn.execute(text("SELECT count(*) FROM personnel_identity_link_operations WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() == 0


def test_apply_api_hr_enrollment_manager_has_organization_wide_access(pg_case):
    with engine.begin() as conn:
        access_role = conn.execute(text("SELECT access_role_id FROM access_roles WHERE code='HR_ENROLLMENT_MANAGER' AND is_active=TRUE LIMIT 1")).scalar_one()
        conn.execute(text("INSERT INTO access_grants(access_role_id,target_type,target_id,scope_type,granted_by_user_id,reason) VALUES (:ar,'USER',:u,'GLOBAL',:g,'ADR065 organization-wide policy test')"), {"ar": access_role, "u": pg_case["actor"], "g": pg_case["actor"]})
        other_unit = conn.execute(text("SELECT unit_id FROM org_units WHERE code='ADR065_ROOT' LIMIT 1")).scalar_one()
        conn.execute(text("UPDATE employees SET org_unit_id=:u WHERE employee_id=:e"), {"u": other_unit, "e": pg_case["employee"]})
        name = conn.execute(text("SELECT full_name FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one()
        expected_precondition = _current_precondition(conn, pg_case["employee"], name, [pg_case["record"]])
    response = TestClient(app).post(
        "/directory/personnel/lk/control-list-repair/apply",
        headers=auth_headers(pg_case["actor"]),
        json={"employee_id": pg_case["employee"], "normalized_record_ids": [pg_case["record"]], "expected_precondition": expected_precondition, "request_id": "adr065-api-org-wide", "confirm_name_correction": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] in {"CREATE", "ADOPT"}
    with engine.begin() as conn:
        assert conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": pg_case["employee"]}).scalar_one() == payload["person_id"]
        assert conn.execute(text("SELECT count(*) FROM personnel_identity_link_operations WHERE request_id='adr065-api-org-wide'" )).scalar_one() == 1

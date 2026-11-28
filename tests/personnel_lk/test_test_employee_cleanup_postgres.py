"""Physical cleanup contract on an isolated PostgreSQL database only."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from app.services import test_employee_cleanup_service as cleanup
from app.person_photos.infrastructure.photo_storage import canonical_photo_absolute_path


@pytest.fixture
def sample():
    with engine.begin() as conn:
        admin = conn.execute(text("""INSERT INTO users(full_name,role_id,is_active,login)
            VALUES ('Isolated system administrator',2,true,:login)
            RETURNING user_id,role_id"""), {"login": f"cleanup_admin_{uuid4().hex[:12]}"}).mappings().one()
        admin = {**dict(admin), "role_code": "TEMPLATE_TEST_SYSADMIN"}
        other = conn.execute(text("""SELECT u.user_id,u.role_id,r.code FROM users u
            JOIN roles r ON r.role_id=u.role_id WHERE u.role_id<>2 AND u.is_active=true
            ORDER BY u.user_id LIMIT 1""")).mappings().one()
        name = f"Cleanup fixture {uuid4().hex[:12]}"
        person_id = conn.execute(text("""INSERT INTO persons(full_name,match_key,person_status,source)
            VALUES (:name,:key,'active','manual') RETURNING person_id"""),
            {"name": name, "key": f"cleanup:{uuid4().hex}"}).scalar_one()
        employee_id = conn.execute(text("""INSERT INTO employees(full_name,person_id,is_active,operational_status)
            VALUES (:name,:person,true,'active') RETURNING employee_id"""),
            {"name": name, "person": person_id}).scalar_one()
        neighbour = conn.execute(text("""INSERT INTO employees(full_name,is_active,operational_status)
            VALUES (:name,true,'active') RETURNING employee_id"""),
            {"name": f"Neighbour {uuid4().hex[:12]}"}).scalar_one()
    return {"admin": dict(admin), "other": dict(other), "name": name,
            "person_id": int(person_id), "employee_id": int(employee_id), "neighbour": int(neighbour)}


def test_unmarked_and_non_sysadmin_are_rejected(sample):
    eid = sample["employee_id"]
    with pytest.raises(cleanup.TestEmployeeCleanupError) as error:
        cleanup.preview(employee_id=eid, actor_user_id=sample["other"]["user_id"])
    assert error.value.status_code == 403
    plan = cleanup.preview(employee_id=eid, actor_user_id=sample["admin"]["user_id"])
    assert plan["can_delete"] is False
    assert plan["is_test_marked"] is False


def test_mark_preview_delete_and_audit(sample):
    eid = sample["employee_id"]
    actor = sample["admin"]["user_id"]
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Created by isolated pytest fixture for cleanup")
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    assert plan["is_test_marked"] is True
    assert plan["counts"]["employees"] == 1
    assert plan["counts"]["persons"] == 1
    assert plan["can_delete"], plan["blockers"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": eid}).scalar_one() == 1
    with pytest.raises(cleanup.TestEmployeeCleanupError):
        cleanup.execute(employee_id=eid, actor_user_id=actor, confirmation="NO",
                        expected_snapshot_hash=plan["snapshot_hash"])
    result = cleanup.execute(employee_id=eid, actor_user_id=actor, confirmation="УДАЛИТЬ",
                             expected_snapshot_hash=plan["snapshot_hash"])
    assert result["deleted_counts"]["employees"] == 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": eid}).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM persons WHERE person_id=:id"), {"id": sample["person_id"]}).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": sample["neighbour"]}).scalar_one() == 1
        audit = conn.execute(text("""SELECT deleted_by_user_id,deleted_counts FROM test_employee_deletion_audit
            WHERE deletion_id=CAST(:id AS uuid)"""), {"id": result["deletion_id"]}).mappings().one()
        assert audit["deleted_by_user_id"] == actor
        assert audit["deleted_counts"]["employees"] == 1


def test_same_name_employee_remains_after_target_id_is_deleted(sample):
    with engine.begin() as conn:
        other_person = conn.scalar(text("""INSERT INTO persons(full_name,match_key,person_status,source)
            VALUES (:name,:key,'active','manual') RETURNING person_id"""),
            {"name": sample["name"], "key": f"cleanup:{uuid4().hex}"})
        other_employee = conn.scalar(text("""INSERT INTO employees(full_name,person_id,is_active,operational_status)
            VALUES (:name,:person,true,'active') RETURNING employee_id"""),
            {"name": sample["name"], "person": other_person})
    actor = sample["admin"]["user_id"]
    cleanup.mark_employee(employee_id=sample["employee_id"], actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="тестовая запись")
    plan = cleanup.preview(employee_id=sample["employee_id"], actor_user_id=actor)
    assert plan["can_delete"], plan["blockers"]
    result = cleanup.execute(employee_id=sample["employee_id"], actor_user_id=actor,
                             confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    assert result["employee_id"] == sample["employee_id"]
    assert result["full_name"] == sample["name"]
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": other_employee}) == 1
        assert conn.scalar(text("SELECT count(*) FROM persons WHERE person_id=:id"), {"id": other_person}) == 1
        assert conn.scalar(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": sample["employee_id"]}) == 0


def test_independent_event_ids_do_not_block_or_delete_other_person_history(sample):
    event_id = 9_000_000 + sample["employee_id"]
    actor = sample["admin"]["user_id"]
    with engine.begin() as conn:
        other_person = conn.scalar(text("""INSERT INTO persons(full_name,match_key,person_status,source)
            VALUES ('Unrelated event owner',:key,'active','manual') RETURNING person_id"""),
            {"key": f"cleanup:{uuid4().hex}"})
        domain = conn.scalar(text("SELECT domain_code FROM personnel_migration_domains ORDER BY domain_code LIMIT 1"))
        conn.execute(text("""INSERT INTO personnel_record_events
            (event_id,person_id,employee_context_id,domain_code,record_table_name,record_id,event_type)
            OVERRIDING SYSTEM VALUE VALUES
            (:event,:person,:employee,:domain,'employees',:employee,'test')"""),
            {"event": event_id, "person": sample["person_id"],
             "employee": sample["employee_id"], "domain": domain})
        conn.execute(text("""INSERT INTO personnel_file_events
            (event_id,person_id,actor_id,action,request_id)
            OVERRIDING SYSTEM VALUE VALUES (:event,:person,:actor,'test',CAST(:request AS uuid))"""),
            {"event": event_id, "person": other_person, "actor": actor,
             "request": str(uuid4())})
    cleanup.mark_employee(employee_id=sample["employee_id"], actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="тестовая запись")
    plan = cleanup.preview(employee_id=sample["employee_id"], actor_user_id=actor)
    assert plan["can_delete"], plan["blockers"]
    assert plan["counts"]["personnel_record_events"] == 1
    result = cleanup.execute(employee_id=sample["employee_id"], actor_user_id=actor,
                             confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    assert result["deleted_counts"]["personnel_record_events"] == 1
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM personnel_file_events WHERE event_id=:event AND person_id=:person"),
                           {"event": event_id, "person": other_person}) == 1


def test_route_rejects_other_role(sample):
    for role_id, role_code in ((1, "HR_HEAD"), (4, "ADMIN"), (99, "SYSADMIN_ASSISTANT")):
        actor = {"user_id": sample["other"]["user_id"], "role_id": role_id,
                 "role_code": role_code, "is_sysadmin_assistant": role_code == "SYSADMIN_ASSISTANT"}
        app.dependency_overrides[get_current_user] = lambda actor=actor: actor
        try:
            client = TestClient(app)
            path = f"/directory/personnel/lk/test-employees/{sample['employee_id']}"
            assert client.get(f"{path}/preview").status_code == 403
            assert client.post(f"{path}/mark", json={"evidence": "A sufficiently long explanation", "confirmed_name": sample["name"]}).status_code == 403
            assert client.post(f"{path}/orders/1/mark", json={
                "evidence": "A sufficiently long explanation", "confirmed_number": "X",
                "expected_snapshot_hash": "a"*64, "confirmed_test_origin": True,
            }).status_code == 403
            assert client.post(f"{path}/delete", json={"confirmation": "УДАЛИТЬ", "expected_snapshot_hash": "a"*64}).status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)


def _technical_order(conn, employee_ids: list[int], actor: int) -> int:
    order_id = conn.execute(text("""INSERT INTO personnel_orders
        (order_number,order_date,order_type_code,status,source_mode,storage_json,created_by)
        VALUES (:number,CURRENT_DATE,'HIRE','DRAFT','DIGITAL',
                CAST(:storage AS jsonb),:actor)
        RETURNING order_id"""), {
            "number": f"CLEANUP-{uuid4().hex[:12]}", "actor": actor,
            "storage": json.dumps({"technical_record": True, "record_quality": "TECHNICAL_RECORD"}),
        }).scalar_one()
    for index, employee_id in enumerate(employee_ids, 1):
        conn.execute(text("""INSERT INTO personnel_order_items
            (order_id,item_number,item_type_code,employee_id,item_status,payload)
            VALUES (:order,:number,'HIRE',:employee,'ACTIVE','{}'::jsonb)"""),
            {"order": order_id, "number": index, "employee": employee_id})
    return int(order_id)


def test_mixed_order_blocks_without_touching_other_employee(sample):
    eid, actor = sample["employee_id"], sample["admin"]["user_id"]
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    with engine.begin() as conn:
        order_id = _technical_order(conn, [eid, sample["neighbour"]], actor)
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    assert not plan["can_delete"]
    assert any("других сотрудников" in blocker for blocker in plan["blockers"])
    with pytest.raises(cleanup.TestEmployeeCleanupError):
        cleanup.execute(employee_id=eid, actor_user_id=actor,
                        confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM personnel_orders WHERE order_id=:id"), {"id": order_id}).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": sample["neighbour"]}).scalar_one() == 1


def test_own_account_and_changed_snapshot_are_rejected(sample):
    eid, actor = sample["employee_id"], sample["admin"]["user_id"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET employee_id=:employee WHERE user_id=:actor"),
                     {"employee": eid, "actor": actor})
    with pytest.raises(cleanup.TestEmployeeCleanupError) as own:
        cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                              confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    assert own.value.code == "OWN_ACCOUNT"
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET employee_id=NULL WHERE user_id=:actor"), {"actor": actor})
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    with engine.begin() as conn:
        conn.execute(text("UPDATE employees SET is_active=false WHERE employee_id=:id"),
                     {"id": eid})
    with pytest.raises(cleanup.TestEmployeeCleanupError) as stale:
        cleanup.execute(employee_id=eid, actor_user_id=actor,
                        confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    assert stale.value.code == "SNAPSHOT_CHANGED"
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": eid}).scalar_one() == 1


def test_unknown_composite_fk_blocks_preview(sample):
    eid, actor = sample["employee_id"], sample["admin"]["user_id"]
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE public.cleanup_test_composite_fk (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            employee_id BIGINT NOT NULL, person_id BIGINT NOT NULL,
            FOREIGN KEY(employee_id,person_id)
                REFERENCES public.employees(employee_id,person_id))"""))
        conn.execute(text("""INSERT INTO public.cleanup_test_composite_fk(employee_id,person_id)
            VALUES (:employee,:person)"""),
            {"employee": eid, "person": sample["person_id"]})
    try:
        plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
        assert not plan["can_delete"]
        assert any("Составная внешняя зависимость" in item for item in plan["blockers"])
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": eid}).scalar_one() == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE public.cleanup_test_composite_fk"))


def test_unrelated_uuid_document_id_does_not_break_preview(sample):
    eid, actor = sample["employee_id"], sample["admin"]["user_id"]
    with engine.begin() as conn:
        document_type_id = conn.execute(text("SELECT document_type_id FROM document_types LIMIT 1")).scalar_one()
        conn.execute(text("""INSERT INTO employee_documents
            (employee_id,document_type_id,title,created_by)
            VALUES (:employee,:type,'Cleanup fixture',:actor)"""),
            {"employee": eid, "type": document_type_id, "actor": actor})
        conn.execute(text("CREATE TABLE public.cleanup_test_uuid_document (document_id uuid PRIMARY KEY)"))
        conn.execute(text("INSERT INTO public.cleanup_test_uuid_document(document_id) VALUES (CAST(:id AS uuid))"),
                     {"id": str(uuid4())})
    try:
        cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                              confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
        plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
        assert plan["counts"]["employee_documents"] == 1
        assert plan["can_delete"], plan["blockers"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE public.cleanup_test_uuid_document"))


def test_user_and_single_test_order_are_physically_removed(sample):
    eid, actor = sample["employee_id"], sample["admin"]["user_id"]
    with engine.begin() as conn:
        user_id = conn.execute(text("""INSERT INTO users(full_name,role_id,is_active,login,employee_id)
            VALUES (:name,1,true,:login,:employee) RETURNING user_id"""),
            {"name": sample["name"], "login": f"cleanup_user_{uuid4().hex[:12]}",
             "employee": eid}).scalar_one()
        order_id = _technical_order(conn, [eid], actor)
        unit_id = conn.execute(text("SELECT unit_id FROM org_units ORDER BY unit_id LIMIT 1")).scalar_one()
        position_id = conn.execute(text("SELECT position_id FROM positions ORDER BY position_id LIMIT 1")).scalar_one()
        assignment_id = conn.execute(text("""INSERT INTO person_assignments
            (person_id,org_unit_id,position_id,rate,start_date,assignment_key,active_flag,is_primary)
            VALUES (:person,:unit,:position,1,CURRENT_DATE,:key,true,true)
            RETURNING assignment_id"""), {"person": sample["person_id"], "unit": unit_id,
                "position": position_id, "key": f"cleanup:{uuid4().hex}"}).scalar_one()
        conn.execute(text("""INSERT INTO employee_assignment_links
            (employee_id,assignment_id,enrolled_by_user_id)
            VALUES (:employee,:assignment,:actor)"""),
            {"employee": eid, "assignment": assignment_id, "actor": actor})
        application_id = conn.execute(text("""INSERT INTO personnel_applications
            (person_id,application_received_at,registered_by_user_id)
            VALUES (:person,CURRENT_DATE,:actor) RETURNING application_id"""),
            {"person": sample["person_id"], "actor": actor}).scalar_one()
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    order_preview = cleanup.preview(employee_id=eid, actor_user_id=actor)["personnel_orders"][0]
    mark_args = dict(employee_id=eid, order_id=order_id, actor_user_id=actor,
                     confirmed_number=order_preview["order_number"],
                     expected_snapshot_hash=order_preview["snapshot_hash"])
    with pytest.raises(cleanup.TestEmployeeCleanupError) as error:
        cleanup.mark_personnel_order(**mark_args, confirmed_test_origin=False,
            evidence="Isolated fixture order created only for the cleanup contract")
    assert error.value.code == "ORDER_CONFIRMATION_REQUIRED"
    with pytest.raises(cleanup.TestEmployeeCleanupError) as error:
        cleanup.mark_personnel_order(**{**mark_args, "expected_snapshot_hash": "a"*64},
            confirmed_test_origin=True,
            evidence="Isolated fixture order created only for the cleanup contract")
    assert error.value.code == "ORDER_SNAPSHOT_CHANGED"
    marked = cleanup.mark_personnel_order(**mark_args, confirmed_test_origin=True,
        evidence="Isolated fixture order created only for the cleanup contract")
    assert cleanup.mark_personnel_order(**mark_args, confirmed_test_origin=True,
        evidence=None) == marked
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    assert plan["can_delete"], plan["blockers"]
    assert plan["counts"]["person_assignments"] == 1
    assert plan["counts"]["personnel_applications"] == 1
    result = cleanup.execute(employee_id=eid, actor_user_id=actor,
                             confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    assert result["deleted_counts"]["personnel_orders"] == 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users WHERE user_id=:id"), {"id": user_id}).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM personnel_orders WHERE order_id=:id"), {"id": order_id}).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM person_assignments WHERE assignment_id=:id"), {"id": assignment_id}).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM personnel_applications WHERE application_id=:id"), {"id": application_id}).scalar_one() == 0


def test_reviewer_history_of_another_employee_is_preserved(sample):
    with engine.begin() as conn:
        if conn.scalar(text("SELECT to_regclass('public.person_relative_change_events')")) is None:
            pytest.skip("Self-card review schema is not present in this isolated database")
        employee_role_id = conn.scalar(text("SELECT role_id FROM roles WHERE code='EMPLOYEE'"))
        assert employee_role_id is not None
        target = sample["employee_id"]
        reviewer = conn.scalar(text("""INSERT INTO users(full_name,role_id,is_active,login,employee_id)
            VALUES (:name,:role,true,:login,:employee) RETURNING user_id"""),
            {"name": sample["name"], "role": employee_role_id,
             "login": f"reviewer_{uuid4().hex[:12]}", "employee": target})
        other_person = conn.scalar(text("""INSERT INTO persons(full_name,match_key,person_status,source)
            VALUES (:name,:key,'active','manual') RETURNING person_id"""),
            {"name": f"Other owner {uuid4().hex[:8]}", "key": f"review-owner:{uuid4().hex}"})
        other_employee = conn.scalar(text("""INSERT INTO employees(full_name,person_id,is_active,operational_status)
            VALUES (:name,:person,true,'active') RETURNING employee_id"""),
            {"name": f"Other owner {uuid4().hex[:8]}", "person": other_person})
        owner = conn.scalar(text("""INSERT INTO users(full_name,role_id,is_active,login,employee_id)
            VALUES (:name,:role,true,:login,:employee) RETURNING user_id"""),
            {"name": "Other owner", "role": employee_role_id,
             "login": f"owner_{uuid4().hex[:12]}", "employee": other_employee})
        conn.execute(text("""INSERT INTO person_contacts
            (person_id,source_kind,created_by_user_id,updated_by_user_id)
            VALUES (:person,'HR_MANUAL',:reviewer,:reviewer)"""),
            {"person": other_person, "reviewer": reviewer})
        conn.execute(text("""INSERT INTO employee_identities
            (employee_id,identity_type,identity_value,created_by)
            VALUES (:employee,'TEST_REVIEW',:value,:reviewer)"""),
            {"employee": other_employee, "value": uuid4().hex, "reviewer": reviewer})
        card_request = uuid4()
        relative_request = uuid4()
        conn.execute(text("""INSERT INTO person_card_change_requests
            (request_id,person_id,employee_context_id,section,request_kind,current,proposed,
             status,revision,submitted_by,decided_by,reason)
            VALUES (:id,:person,:employee,'contacts','addition','{}'::jsonb,'{}'::jsonb,
                    'approved',1,:owner,:reviewer,'Approved by reviewer')"""),
            {"id": card_request, "person": other_person, "employee": other_employee,
             "owner": owner, "reviewer": reviewer})
        conn.execute(text("""INSERT INTO person_card_change_events
            (request_id,actor_id,action,detail) VALUES (:id,:reviewer,'approved','{}'::jsonb)"""),
            {"id": card_request, "reviewer": reviewer})
        conn.execute(text("""INSERT INTO person_relative_change_requests
            (request_id,person_id,request_kind,proposed,status,revision,submitted_by,decided_by,reason)
            VALUES (:id,:person,'addition','{}'::jsonb,'approved',1,:owner,:reviewer,'Approved by reviewer')"""),
            {"id": relative_request, "person": other_person, "owner": owner, "reviewer": reviewer})
        conn.execute(text("""INSERT INTO person_relative_change_events
            (request_id,actor_id,action,detail) VALUES (:id,:reviewer,'approved','{}'::jsonb)"""),
            {"id": relative_request, "reviewer": reviewer})
    cleanup.mark_employee(employee_id=target, actor_user_id=sample["admin"]["user_id"],
                          confirmed_name=sample["name"], evidence="Isolated reviewer with unrelated employee history")
    plan = cleanup.preview(employee_id=target, actor_user_id=sample["admin"]["user_id"])
    assert plan["can_delete"], plan["blockers"]
    assert plan["retained_counts"]["person_contacts"] == 1
    assert plan["retained_counts"]["person_card_change_events"] == 1
    result = cleanup.execute(employee_id=target, actor_user_id=sample["admin"]["user_id"],
                             confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": target}) == 0
        assert conn.scalar(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": other_employee}) == 1
        for table, request_id in (("person_card_change_requests", card_request),
                                  ("person_relative_change_requests", relative_request)):
            row = conn.execute(text(f"SELECT status,reason,submitted_by,decided_by FROM {table} WHERE request_id=:id"),
                               {"id": request_id}).one()
            assert row == ("approved", "Approved by reviewer", owner, None)
        for table, request_id in (("person_card_change_events", card_request),
                                  ("person_relative_change_events", relative_request)):
            row = conn.execute(text(f"SELECT action,actor_id FROM {table} WHERE request_id=:id"),
                               {"id": request_id}).one()
            assert row == ("approved", None)
        contact = conn.execute(text("""SELECT created_by_user_id,updated_by_user_id
            FROM person_contacts WHERE person_id=:person"""), {"person": other_person}).one()
        assert contact == (None, None)
        assert conn.scalar(text("SELECT count(*) FROM employee_identities WHERE employee_id=:id AND created_by IS NULL"),
                           {"id": other_employee}) == 1
        assert conn.scalar(text("""SELECT count(*) FROM test_employee_history_snapshots
            WHERE deletion_id=CAST(:id AS uuid) AND source_table IN
              ('person_card_change_requests','person_card_change_events',
               'person_relative_change_requests','person_relative_change_events',
               'person_contacts','employee_identities')"""), {"id": result["deletion_id"]}) == 6


def test_photo_file_is_removed_after_commit(sample, tmp_path, monkeypatch):
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path))
    eid, person, actor = sample["employee_id"], sample["person_id"], sample["admin"]["user_id"]
    file_id = uuid4().hex
    relative_path = f"person/{person}/{file_id}.jpg"
    path = canonical_photo_absolute_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic photo")
    with engine.begin() as conn:
        photo_id = conn.execute(text("""INSERT INTO person_photos
            (person_id,file_id,storage_rel_path,mime_type,byte_size,checksum_sha256,is_active,uploaded_by_user_id)
            VALUES (:person,:file,:path,'image/jpeg',15,:checksum,true,:actor) RETURNING person_photo_id"""),
            {"person": person, "file": file_id, "path": relative_path,
             "checksum": "a"*64, "actor": actor}).scalar_one()
        conn.execute(text("""INSERT INTO person_photo_sources
            (person_photo_id,person_id,source_kind,canonicalization_mode,command_id)
            VALUES (:photo,:person,'manual_upload','backfill',:command)"""),
            {"photo": photo_id, "person": person, "command": f"cleanup:{uuid4().hex}"})
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    assert plan["can_delete"], plan["blockers"]
    assert plan["file_count"] == 1
    result = cleanup.execute(employee_id=eid, actor_user_id=actor,
                             confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    assert result["file_cleanup"] == {"completed": 1, "pending": 0, "deleted_files": 1}
    assert not path.exists()


def test_personnel_files_and_historical_attribution(sample, tmp_path, monkeypatch):
    monkeypatch.setenv("PERSONNEL_FILE_STORAGE_ROOT", str(tmp_path))
    eid, person, actor = sample["employee_id"], sample["person_id"], sample["admin"]["user_id"]
    own_key, outside_key = str(uuid4()), str(uuid4())
    own_bundle = tmp_path / own_key
    own_bundle.mkdir()
    (own_bundle / "original").write_bytes(b"owned test document")
    (own_bundle / "page-1.png").write_bytes(b"owned preview")
    with engine.begin() as conn:
        user_id = conn.execute(text("""INSERT INTO users(full_name,role_id,is_active,login,employee_id)
            VALUES (:name,1,true,:login,:employee) RETURNING user_id"""),
            {"name": sample["name"], "login": f"cleanup_user_{uuid4().hex[:12]}",
             "employee": eid}).scalar_one()
        other_person = conn.execute(text("""INSERT INTO persons(full_name,match_key,person_status,source)
            VALUES ('Other person',:key,'active','manual') RETURNING person_id"""),
            {"key": f"cleanup:{uuid4().hex}"}).scalar_one()
        document_type_id = conn.execute(text("SELECT document_type_id FROM document_types LIMIT 1")).scalar_one()
        document_id = conn.execute(text("""INSERT INTO employee_documents
            (employee_id,document_type_id,title,created_by) VALUES (:employee,:type,'Owned document',:actor)
            RETURNING document_id"""),
            {"employee": eid, "type": document_type_id, "actor": actor}).scalar_one()
        own_set, other_set = str(uuid4()), str(uuid4())
        for set_id, owner in ((own_set, person), (other_set, other_person)):
            conn.execute(text("""INSERT INTO personnel_file_sets(set_id,person_id,kind,title)
                VALUES (CAST(:set AS uuid),:person,'photo','Test file')"""),
                {"set": set_id, "person": owner})
        own_version, outside_version = str(uuid4()), str(uuid4())
        for version, set_id, key, linked_document in (
            (own_version, own_set, own_key, document_id),
            (outside_version, other_set, outside_key, None),
        ):
            conn.execute(text("""INSERT INTO personnel_file_versions
                (version_id,set_id,version_no,state,storage_key,original_name,mime_type,
                 byte_size,checksum_sha256,page_count,uploaded_by,preview_checksums,employee_document_id)
                VALUES (CAST(:version AS uuid),CAST(:set AS uuid),1,'pending',:key,'scan.pdf',
                        'application/pdf',12,:digest,1,:user,'[]'::jsonb,:document)"""),
                {"version": version, "set": set_id, "key": key, "digest": "a"*64,
                 "user": user_id, "document": linked_document})
        for owner, version in ((person, own_version), (other_person, outside_version)):
            event_id = conn.scalar(text("""INSERT INTO personnel_file_events(person_id,version_id,actor_id,action,request_id)
                VALUES (:person,CAST(:version AS uuid),:actor,'uploaded',CAST(:request AS uuid))
                RETURNING event_id"""),
                {"person": owner, "version": version, "actor": user_id, "request": str(uuid4())})
            if owner == person:
                own_event_id = event_id
                conn.execute(text("CREATE TABLE IF NOT EXISTS cleanup_unrelated_event_stream (event_id bigint PRIMARY KEY)"))
                conn.execute(text("INSERT INTO cleanup_unrelated_event_stream(event_id) VALUES (:id)"),
                             {"id": event_id})
        security_id = conn.execute(text("""INSERT INTO security_audit_log
            (event_type,actor_user_id,target_user_id,success)
            VALUES ('LOGIN_SUCCESS',:user,:user,true) RETURNING audit_id"""),
            {"user": user_id}).scalar_one()
    before_mark = cleanup.preview(employee_id=eid, actor_user_id=actor)
    assert not before_mark["can_delete"]
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"],
                          evidence="Isolated synthetic personnel files and security history")
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    assert plan["can_delete"], plan["blockers"]
    assert plan["counts"]["personnel_file_sets"] == 1
    assert plan["counts"]["personnel_file_versions"] == 1
    assert plan["counts"]["personnel_file_events"] == 1
    assert plan["retained_counts"]["personnel_file_events"] == 1
    assert plan["retained_counts"]["personnel_file_versions"] == 1
    assert plan["retained_counts"]["security_audit_log"] == 1
    assert plan["file_count"] == 1
    result = cleanup.execute(employee_id=eid, actor_user_id=actor, confirmation="УДАЛИТЬ",
                             expected_snapshot_hash=plan["snapshot_hash"])
    assert result["file_cleanup"] == {"completed": 1, "pending": 0, "deleted_files": 2}
    assert not own_bundle.exists()
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM personnel_file_sets WHERE person_id=:id"), {"id": person}) == 0
        assert conn.scalar(text("SELECT count(*) FROM employee_documents WHERE document_id=:id"), {"id": document_id}) == 0
        assert conn.scalar(text("SELECT count(*) FROM personnel_file_events WHERE person_id=:id"), {"id": person}) == 0
        assert conn.scalar(text("SELECT count(*) FROM cleanup_unrelated_event_stream WHERE event_id=:id"),
                           {"id": own_event_id}) == 1
        assert conn.scalar(text("SELECT actor_id FROM personnel_file_events WHERE person_id=:id"), {"id": other_person}) is None
        assert conn.scalar(text("SELECT uploaded_by FROM personnel_file_versions WHERE version_id=CAST(:id AS uuid)"), {"id": outside_version}) is None
        audit = conn.execute(text("SELECT actor_user_id,target_user_id FROM security_audit_log WHERE audit_id=:id"),
                             {"id": security_id}).one()
        assert audit == (None, None)
        refs = conn.execute(text("""SELECT source_table,source_column,deleted_entity_id
            FROM test_employee_retained_history_refs WHERE deletion_id=CAST(:id AS uuid)"""),
            {"id": result["deletion_id"]}).all()
        assert len(refs) == 4
        assert all(row.deleted_entity_id == user_id for row in refs)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE cleanup_unrelated_event_stream"))


def test_failed_file_removal_is_queued_for_retry(sample, tmp_path, monkeypatch):
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path))
    eid, person, actor = sample["employee_id"], sample["person_id"], sample["admin"]["user_id"]
    relative_path = f"person/{person}/{uuid4().hex}.jpg"
    path = canonical_photo_absolute_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic photo")
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO person_photos
            (person_id,file_id,storage_rel_path,mime_type,byte_size,checksum_sha256,is_active,uploaded_by_user_id)
            VALUES (:person,:file,:path,'image/jpeg',15,:checksum,true,:actor)"""),
            {"person": person, "file": uuid4().hex, "path": relative_path,
             "checksum": "a"*64, "actor": actor})
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    real_delete = cleanup.delete_canonical_photo_file
    def fail_once(_: str) -> None:
        raise OSError("injected file failure")
    monkeypatch.setattr(cleanup, "delete_canonical_photo_file", fail_once)
    result = cleanup.execute(employee_id=eid, actor_user_id=actor,
                             confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
    assert result["file_cleanup"] == {"completed": 0, "pending": 1, "deleted_files": 0}
    assert path.exists()
    monkeypatch.setattr(cleanup, "delete_canonical_photo_file", real_delete)
    retried = cleanup.retry_file_cleanup(deletion_id=result["deletion_id"], actor_user_id=actor)
    assert retried == {"completed": 1, "pending": 0, "deleted_files": 1}
    assert not path.exists()


def test_delete_failure_rolls_back_every_postgres_row(sample):
    eid, person, actor = sample["employee_id"], sample["person_id"], sample["admin"]["user_id"]
    cleanup.mark_employee(employee_id=eid, actor_user_id=actor,
                          confirmed_name=sample["name"], evidence="Isolated synthetic employee from a test fixture")
    plan = cleanup.preview(employee_id=eid, actor_user_id=actor)
    with engine.begin() as conn:
        conn.execute(text("""CREATE FUNCTION cleanup_injected_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'injected cleanup failure'; END $$"""))
        conn.execute(text("""CREATE TRIGGER cleanup_injected_failure_trigger BEFORE DELETE ON persons
            FOR EACH ROW EXECUTE FUNCTION cleanup_injected_failure()"""))
    try:
        with pytest.raises(Exception, match="injected cleanup failure"):
            cleanup.execute(employee_id=eid, actor_user_id=actor,
                            confirmation="УДАЛИТЬ", expected_snapshot_hash=plan["snapshot_hash"])
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM employees WHERE employee_id=:id"), {"id": eid}).scalar_one() == 1
            assert conn.execute(text("SELECT count(*) FROM persons WHERE person_id=:id"), {"id": person}).scalar_one() == 1
            assert conn.execute(text("SELECT count(*) FROM test_employee_deletion_audit WHERE employee_id=:id"), {"id": eid}).scalar_one() == 0
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP TRIGGER cleanup_injected_failure_trigger ON persons"))
            conn.execute(text("DROP FUNCTION cleanup_injected_failure()"))

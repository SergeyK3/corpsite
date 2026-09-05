"""WP-TD-005 stage 5 transactional applicant-only execution regressions."""
from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from starlette.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from app.security import admin_permissions
from app.services import access_resolver_service
from app.services import test_personnel_deletion_execution_service as execution
from app.services import test_personnel_deletion_fingerprint_service as fingerprints
from app.services import test_personnel_deletion_service as approval
from tests.test_wp_td_005_manifest_v2 import _alembic_config, _ephemeral_database


PREVIOUS_REVISION = "td005audit401"
REVISION = "td005exec501"


@pytest.fixture(scope="module")
def execution_engine():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        command.upgrade(_alembic_config(url), REVISION)
        yield clone_engine


@pytest.fixture(autouse=True)
def bind_engines(execution_engine, monkeypatch):
    monkeypatch.setattr(approval, "engine", execution_engine)
    monkeypatch.setattr(execution, "engine", execution_engine)
    monkeypatch.setattr(admin_permissions, "engine", execution_engine)
    monkeypatch.setattr(access_resolver_service, "engine", execution_engine)


@pytest.fixture
def actors(execution_engine):
    with execution_engine.connect() as connection:
        rows = connection.execute(text("""SELECT DISTINCT ON (role.code)
                role.code,users.user_id,users.role_id
            FROM public.users users JOIN public.roles role ON role.role_id=users.role_id
            WHERE role.code IN ('ADMIN','HR_HEAD') AND users.is_active=TRUE
            ORDER BY role.code,users.user_id""")).mappings().all()
    result = {str(row["code"]): dict(row) for row in rows}
    assert set(result) == {"ADMIN", "HR_HEAD"}
    return result


def _execution_snapshot(detail):
    decision = next(item for item in reversed(detail["decisions"]) if item["decision"] == "APPROVE")
    expires_at = detail["approval_expires_at"]
    return {
        "request_version": int(detail["version"]),
        "approval_decision_id": int(decision["decision_id"]),
        "approval_request_version": int(decision["request_version"]),
        "target_set_hash": detail["target_set_hash"],
        "relationship_fingerprint": detail["relationship_fingerprint"],
        "fingerprint_version": detail["fingerprint_version"],
        "relationship_policy_version": detail["relationship_policy_version"],
        "catalog_version": detail["catalog_version"],
        "catalog_fingerprint": detail["catalog_fingerprint"],
        "approval_expires_at": expires_at.isoformat(),
        "target_person_count": len(detail["manifest_targets"]),
    }


def _approved_synthetic(
    execution_engine, actors, *, with_journals=True, basis="PROVENANCE",
    command_id: str | None = None, before_draft=None, after_approval=None,
):
    suffix = uuid.uuid4().hex[:12]
    admin_id = int(actors["ADMIN"]["user_id"])
    hr_id = int(actors["HR_HEAD"]["user_id"])
    with execution_engine.begin() as connection:
        person_id = int(connection.execute(text("""INSERT INTO public.persons(
                full_name,match_key,source)
            VALUES(:name,:key,'manual') RETURNING person_id"""), {
            "name": f"Stage 5 synthetic {suffix}", "key": f"td005-exec-{suffix}",
        }).scalar_one())
        application_id = int(connection.execute(text("""INSERT INTO public.personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key)
            VALUES(:person_id,'intake_pending',CURRENT_DATE,:actor,:key)
            RETURNING application_id"""), {
            "person_id": person_id, "actor": admin_id, "key": f"td005-app-{suffix}",
        }).scalar_one())
        connection.execute(text("""INSERT INTO public.test_personnel_provenance(
                target_type,target_id,environment,test_run_id,creation_source,purpose,
                created_by_user_id,source_artifact_hash,provenance_version,provenance_state)
            VALUES('PERSON',:person_id,'dev',:run,'pytest','stage-5 synthetic',
                :actor,:artifact,1,'ACTIVE')"""), {
            "person_id": person_id, "run": f"td005-run-{suffix}", "actor": admin_id,
            "artifact": "a" * 64,
        })
        connection.execute(text(
            "INSERT INTO public.personnel_record_metadata(person_id) VALUES(:person_id)"
        ), {"person_id": person_id})
        if with_journals:
            link_id = int(connection.execute(text("""INSERT INTO public.personnel_intake_links(
                    application_id,token_hash,status,issued_by_user_id,expires_at)
                VALUES(:application_id,:token_hash,'issued',:actor,
                    statement_timestamp()+interval '1 hour') RETURNING link_id"""), {
                "application_id": application_id, "token_hash": (suffix * 6)[:64], "actor": admin_id,
            }).scalar_one())
            connection.execute(text("""INSERT INTO public.personnel_intake_drafts(
                    application_id,link_id,status,payload)
                VALUES(:application_id,:link_id,'editable',CAST(:payload AS jsonb))"""), {
                "application_id": application_id, "link_id": link_id,
                "payload": '{"email":"raw@example.test"}',
            })
            connection.execute(text("""INSERT INTO public.personnel_record_events(
                    person_id,domain_code,record_table_name,record_id,event_type,actor_id,event_payload)
                VALUES(:person_id,NULL,'persons',:person_id,'PPR_CREATED',:actor,
                    CAST(:payload AS jsonb))"""), {
                "person_id": person_id, "actor": str(admin_id),
                "payload": '{"full_name":"must only survive as digest"}',
            })
            connection.execute(text("""INSERT INTO public.ppr_command_executions(
                    command_id,command_type,person_id,request_fingerprint,status,result_payload)
                VALUES(:command,'MaterializePPR',:person_id,'raw-request','completed',
                    CAST(:result AS jsonb))"""), {
                "command": command_id or f"td005-command-{suffix}", "person_id": person_id,
                "result": '{"iin":"000000000000"}',
            })
            connection.execute(text("""INSERT INTO public.personnel_application_lifecycle_audit(
                    application_id,action,new_status,actor_user_id,metadata,comment)
                VALUES(:application_id,'registered','intake_pending',:actor,
                    CAST(:metadata AS jsonb),'raw comment')"""), {
                "application_id": application_id, "actor": admin_id,
                "metadata": '{"phone":"+70000000000"}',
            })
        if before_draft is not None:
            before_draft(connection, person_id, application_id, admin_id)
    draft = approval.create_draft(
        actor_user_id=admin_id, basis=basis,
        reason_code="PROVENANCE_TEST_RUN_CLEANUP",
        preview_criteria={"field": "full_name", "selection": "EXACT_MANIFEST"},
        original_mask=None,
        targets=[{"person_id": person_id, "application_id": application_id}],
        idempotency_key=f"td005-create-{uuid.uuid4().hex}",
    )
    submitted, conflict = approval.submit_request(
        request_id=draft["request_id"], actor_user_id=admin_id,
        expected_version=draft["version"], idempotency_key=f"td005-submit-{uuid.uuid4().hex}",
    )
    assert conflict is None
    approved, conflict = approval.decide_request(
        request_id=draft["request_id"], actor_user_id=hr_id,
        expected_version=submitted["version"], decision="APPROVE",
        idempotency_key=f"td005-approve-{uuid.uuid4().hex}", comment=None,
        submitted_synthetic_confirmed=False,
    )
    assert conflict is None
    expected_snapshot = _execution_snapshot(approval.get_request(draft["request_id"]))
    if after_approval is not None:
        with execution_engine.begin() as connection:
            after_approval(connection, person_id, application_id, admin_id)
    return {
        "request_id": uuid.UUID(approved["request_id"]),
        "request_number": approved["request_number"],
        "person_id": person_id, "application_id": application_id,
        "expected_snapshot": expected_snapshot,
    }


def _execute(target, actors, *, key=None, phrase=None, fault=None):
    return execution.execute_request(
        request_id=target["request_id"],
        executor_user_id=int(actors["ADMIN"]["user_id"]),
        idempotency_key=key or uuid.uuid4(),
        confirmation=phrase or execution.confirmation_phrase(target["request_number"], 1),
        expected_snapshot=target["expected_snapshot"],
        fault_after_step=fault,
    )


def test_alembic_has_one_stage5_head():
    assert ScriptDirectory.from_config(_alembic_config()).get_heads() == [REVISION]


def test_stage5_upgrade_downgrade_upgrade():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            status_check = connection.execute(text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='ck_tpdr_status'"
            )).scalar_one()
            assert "COMPLETED" in status_check
        command.downgrade(config, PREVIOUS_REVISION)
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION


def test_stage5_downgrade_preflight_rejects_nonempty_attempt_state():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        with clone_engine.begin() as connection:
            users = connection.execute(text("""SELECT role.code,users.user_id
                FROM public.users users JOIN public.roles role USING(role_id)
                WHERE role.code IN ('ADMIN','HR_HEAD') ORDER BY role.code""")).mappings().all()
            actor_ids = {row["code"]: int(row["user_id"]) for row in users}
            request_id = uuid.uuid4()
            connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
                    request_id,request_number,status,basis,reason_code,target_set_hash,
                    relationship_fingerprint,version,initiated_by_user_id,manifest_version,
                    process_type,fingerprint_version,relationship_policy_version,catalog_version,
                    catalog_fingerprint,approved_at,approval_expires_at)
                VALUES(:id,:number,'APPROVED','PROVENANCE','PROVENANCE_TEST_RUN_CLEANUP',
                    :hash,:hash,3,:admin,2,:process,:fingerprint,:policy,:catalog,:hash,
                    statement_timestamp(),statement_timestamp()+interval '1 hour')"""), {
                "id": request_id, "number": f"TD-DOWN-{request_id.hex[:12].upper()}",
                "hash": "a" * 64, "admin": actor_ids["ADMIN"],
                "process": approval.APPLICANT_PROCESS_TYPE,
                "fingerprint": fingerprints.FINGERPRINT_VERSION,
                "policy": fingerprints.POLICY_VERSION, "catalog": fingerprints.CATALOG_VERSION,
            })
            connection.execute(text("""INSERT INTO public.test_personnel_deletion_execution_attempts(
                    request_id,executor_user_id,idempotency_key,command_payload_hash,event_type)
                VALUES(:request_id,:executor,:key,:hash,'INTENT')"""), {
                "request_id": request_id, "executor": actor_ids["ADMIN"],
                "key": str(uuid.uuid4()), "hash": "b" * 64,
            })
        with pytest.raises(Exception, match="WP_TD_005_EXECUTION_STATE_PREVENTS_DOWNGRADE"):
            command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION


def test_stage5_downgrade_preflight_rejects_completed_status():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        request_id = uuid.uuid4()
        with clone_engine.begin() as connection:
            admin_id = int(connection.execute(text("""SELECT users.user_id
                FROM public.users users JOIN public.roles role USING(role_id)
                WHERE role.code='ADMIN' ORDER BY users.user_id LIMIT 1""")).scalar_one())
            connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
                    request_id,request_number,status,basis,reason_code,target_set_hash,
                    relationship_fingerprint,version,initiated_by_user_id,manifest_version,
                    process_type,fingerprint_version,relationship_policy_version,catalog_version,
                    catalog_fingerprint)
                VALUES(:id,:number,'COMPLETED','PROVENANCE','PROVENANCE_TEST_RUN_CLEANUP',
                    repeat('a',64),repeat('b',64),4,:admin,2,:process,:fingerprint,
                    :policy,:catalog,repeat('c',64))"""), {
                "id": request_id, "number": f"TD-COMPLETED-{request_id.hex[:12].upper()}",
                "admin": admin_id, "process": approval.APPLICANT_PROCESS_TYPE,
                "fingerprint": fingerprints.FINGERPRINT_VERSION,
                "policy": fingerprints.POLICY_VERSION, "catalog": fingerprints.CATALOG_VERSION,
            })

        with pytest.raises(Exception, match="WP_TD_005_EXECUTION_STATE_PREVENTS_DOWNGRADE"):
            command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == REVISION
            assert connection.execute(text("""SELECT status
                FROM test_personnel_deletion_requests WHERE request_id=:id"""), {
                "id": request_id,
            }).scalar_one() == "COMPLETED"


def test_catalog_revision_is_reviewed_and_compatible(execution_engine):
    with execution_engine.connect() as connection:
        state = fingerprints.catalog_state(connection, approval.RELATIONSHIP_MATRIX)
    assert state["compatible"] is True
    assert state["fingerprint"] == fingerprints.EXPECTED_CATALOG_FINGERPRINTS[REVISION]


def test_feature_flag_defaults_off_and_api_makes_no_change(execution_engine, actors, monkeypatch):
    monkeypatch.delenv(execution.FEATURE_FLAG, raising=False)
    before = None
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    with execution_engine.connect() as connection:
        before = connection.execute(text(
            "SELECT status,version FROM test_personnel_deletion_requests WHERE request_id=:id"
        ), {"id": target["request_id"]}).one()
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": int(actors["ADMIN"]["user_id"]), "role_code": "ADMIN",
    }
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/directory/test-personnel-deletion/requests/{target['request_id']}/execute",
                json={"idempotency_key": str(uuid.uuid4()),
                      "confirmation_phrase": execution.confirmation_phrase(target["request_number"], 1),
                      "expected_snapshot": target["expected_snapshot"]},
            )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "TD_EXECUTION_DISABLED"
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous
    with execution_engine.connect() as connection:
        assert connection.execute(text(
            "SELECT status,version FROM test_personnel_deletion_requests WHERE request_id=:id"
        ), {"id": target["request_id"]}).one() == before
        assert connection.execute(text(
            "SELECT COUNT(*) FROM test_personnel_deletion_history WHERE request_id=:id AND action='EXECUTE'"
        ), {"id": target["request_id"]}).scalar_one() == 0


def test_success_is_atomic_tombstoned_and_idempotent(execution_engine, actors, monkeypatch):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors)
    key = uuid.uuid4()
    first = _execute(target, actors, key=key)
    second = _execute(target, actors, key=key)
    with pytest.raises(approval.TestPersonnelDeletionError) as completed:
        _execute(target, actors, key=uuid.uuid4())
    assert first["status"] == "COMPLETED" and first["replayed"] is False
    assert second["result"] == first["result"] and second["replayed"] is True
    assert completed.value.code == "TD_EXECUTE_ALREADY_COMPLETED"
    with execution_engine.connect() as connection:
        assert connection.execute(text(
            "SELECT COUNT(*) FROM persons WHERE person_id=:id"
        ), {"id": target["person_id"]}).scalar_one() == 0
        assert connection.execute(text(
            "SELECT COUNT(*) FROM personnel_applications WHERE application_id=:id"
        ), {"id": target["application_id"]}).scalar_one() == 0
        assert connection.execute(text("""SELECT status FROM test_personnel_deletion_requests
            WHERE request_id=:id"""), {"id": target["request_id"]}).scalar_one() == "COMPLETED"
        assert connection.execute(text("""SELECT COUNT(*) FROM test_personnel_provenance
            WHERE target_type='PERSON' AND target_id=:id"""), {"id": target["person_id"]}).scalar_one() == 1
        assert connection.execute(text("""SELECT COUNT(*)
            FROM test_personnel_deletion_manifest_v2_targets WHERE request_id=:id"""), {
            "id": target["request_id"],
        }).scalar_one() == 1
        assert connection.execute(text("""SELECT COUNT(*)
            FROM test_personnel_deletion_targets WHERE request_id=:id"""), {
            "id": target["request_id"],
        }).scalar_one() == 1
        assert connection.execute(text("""SELECT COUNT(*)
            FROM test_personnel_deletion_decisions
            WHERE request_id=:id AND decision='APPROVE'"""), {
            "id": target["request_id"],
        }).scalar_one() == 1
        assert connection.execute(text("""SELECT COUNT(*) FROM test_personnel_deletion_history
            WHERE request_id=:id AND action='EXECUTE'"""), {"id": target["request_id"]}).scalar_one() == 1
        assert connection.execute(text(
            "SELECT COUNT(*) FROM test_personnel_deletion_record_event_tombstones WHERE request_id=:id"
        ), {"id": target["request_id"]}).scalar_one() == 1
        attempts = connection.execute(text("""SELECT event_type,result_code,error_code
            FROM test_personnel_deletion_execution_attempts WHERE request_id=:id
            ORDER BY attempt_event_id"""), {"id": target["request_id"]}).all()
        assert attempts[:2] == [("INTENT", None, None), ("RESULT", "TD_EXECUTION_COMPLETED", None)]
        assert attempts[2][0:2] == ("INTENT", None)
        assert attempts[3][0:2] == ("RESULT", "TD_EXECUTION_FAILED")
        assert connection.execute(text(
            "SELECT COUNT(*) FROM test_personnel_deletion_command_tombstones WHERE request_id=:id"
        ), {"id": target["request_id"]}).scalar_one() == 1
        assert connection.execute(text(
            "SELECT COUNT(*) FROM test_personnel_deletion_lifecycle_tombstones WHERE request_id=:id"
        ), {"id": target["request_id"]}).scalar_one() == 1
        raw_projection = connection.execute(text("""SELECT result_projection::text
            FROM test_personnel_deletion_history WHERE request_id=:id AND action='EXECUTE'"""), {
            "id": target["request_id"],
        }).scalar_one().lower()
        assert all(value not in raw_projection for value in ("full_name", "iin", "phone", "raw-request"))


def test_returning_count_mismatch_rolls_back_all_domain_changes(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors)
    original = execution._technical_ids

    def hide_expected_draft(connection, sql, params):
        values = original(connection, sql, params)
        return [] if "SELECT draft_id" in sql else values

    monkeypatch.setattr(execution, "_technical_ids", hide_expected_draft)
    with pytest.raises(approval.TestPersonnelDeletionError) as mismatch:
        _execute(target, actors)
    assert mismatch.value.code == "TD_EXECUTION_COUNT_HASH_MISMATCH"
    with execution_engine.connect() as connection:
        assert connection.execute(text(
            "SELECT COUNT(*) FROM persons WHERE person_id=:id"
        ), {"id": target["person_id"]}).scalar_one() == 1
        assert connection.execute(text("""SELECT COUNT(*) FROM personnel_intake_drafts
            WHERE application_id=:id"""), {"id": target["application_id"]}).scalar_one() == 1
        assert connection.execute(text("""SELECT COUNT(*) FROM test_personnel_deletion_record_event_tombstones
            WHERE request_id=:id"""), {"id": target["request_id"]}).scalar_one() == 0


@pytest.mark.parametrize("step", ["R0", "D1", "D2", "TOMBSTONES", "JOURNALS", "D3", "D4", "D5", "AUDIT"])
def test_fault_after_every_step_rolls_back(execution_engine, actors, monkeypatch, step):
    monkeypatch.setenv(execution.FEATURE_FLAG, "1")
    target = _approved_synthetic(execution_engine, actors)
    with pytest.raises(approval.TestPersonnelDeletionError) as error:
        _execute(target, actors, fault=step)
    assert error.value.code == "TD_EXECUTION_FAULT_INJECTED"
    with execution_engine.connect() as connection:
        assert connection.execute(text(
            "SELECT COUNT(*) FROM persons WHERE person_id=:id"
        ), {"id": target["person_id"]}).scalar_one() == 1
        assert connection.execute(text(
            "SELECT COUNT(*) FROM personnel_applications WHERE application_id=:id"
        ), {"id": target["application_id"]}).scalar_one() == 1
        assert connection.execute(text("""SELECT COUNT(*) FROM test_personnel_deletion_record_event_tombstones
            WHERE request_id=:id"""), {"id": target["request_id"]}).scalar_one() == 0
        failed = connection.execute(text("""SELECT result_code,error_projection.result
            FROM test_personnel_deletion_history h
            CROSS JOIN LATERAL (SELECT h.result_projection->>'result' result) error_projection
            WHERE request_id=:id AND action='EXECUTE'"""), {"id": target["request_id"]}).one()
        assert failed[0] == failed[1] == "TD_EXECUTION_FAILED"
        attempt_events = connection.execute(text("""SELECT event_type,result_code,error_code
            FROM test_personnel_deletion_execution_attempts
            WHERE request_id=:id ORDER BY attempt_event_id"""), {
            "id": target["request_id"],
        }).all()
        assert attempt_events == [
            ("INTENT", None, None),
            ("RESULT", "TD_EXECUTION_FAILED", "TD_EXECUTION_FAULT_INJECTED"),
        ]


def test_confirmation_permission_employee_and_drift_fail_closed(execution_engine, actors, monkeypatch):
    monkeypatch.setenv(execution.FEATURE_FLAG, "on")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    with pytest.raises(approval.TestPersonnelDeletionError) as confirmation_error:
        _execute(target, actors, phrase="DELETE")
    assert confirmation_error.value.code == "TD_EXECUTION_CONFIRMATION_MISMATCH"
    with pytest.raises(approval.TestPersonnelDeletionError) as role_error:
        execution.execute_request(
            request_id=target["request_id"], executor_user_id=int(actors["HR_HEAD"]["user_id"]),
            idempotency_key=uuid.uuid4(),
            confirmation=execution.confirmation_phrase(target["request_number"], 1),
            expected_snapshot=target["expected_snapshot"],
        )
    assert role_error.value.code == "TD_EXECUTE_PERMISSION_REQUIRED"
    with execution_engine.begin() as connection:
        connection.execute(text("""UPDATE public.persons SET full_name=full_name || ' drift'
            WHERE person_id=:id"""), {"id": target["person_id"]})
    drifted = _execute(target, actors)
    assert drifted["status"] == "REAPPROVAL_REQUIRED"
    with execution_engine.connect() as connection:
        assert connection.execute(text(
            "SELECT COUNT(*) FROM persons WHERE person_id=:id"
        ), {"id": target["person_id"]}).scalar_one() == 1
        assert connection.execute(text("""SELECT status FROM test_personnel_deletion_requests
            WHERE request_id=:id"""), {"id": target["request_id"]}).scalar_one() == "REAPPROVAL_REQUIRED"


def test_expected_operator_snapshot_mismatch_returns_409_without_delete(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "on")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    stale_snapshot = {**target["expected_snapshot"], "request_version": 1}
    with pytest.raises(approval.TestPersonnelDeletionError) as error:
        execution.execute_request(
            request_id=target["request_id"],
            executor_user_id=int(actors["ADMIN"]["user_id"]),
            idempotency_key=uuid.uuid4(),
            confirmation=execution.confirmation_phrase(target["request_number"], 1),
            expected_snapshot=stale_snapshot,
        )
    assert error.value.status_code == 409
    assert error.value.code == "TD_EXECUTION_SNAPSHOT_CHANGED"
    with execution_engine.connect() as connection:
        assert connection.execute(text(
            "SELECT EXISTS(SELECT 1 FROM public.persons WHERE person_id=:id)"
        ), {"id": target["person_id"]}).scalar_one()
        assert connection.execute(text(
            "SELECT EXISTS(SELECT 1 FROM public.personnel_applications WHERE application_id=:id)"
        ), {"id": target["application_id"]}).scalar_one()


def test_same_key_different_payload_conflicts(execution_engine, actors, monkeypatch):
    monkeypatch.setenv(execution.FEATURE_FLAG, "yes")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    key = uuid.uuid4()
    _execute(target, actors, key=key)
    with pytest.raises(approval.TestPersonnelDeletionError) as conflict:
        _execute(target, actors, key=key, phrase="different")
    assert conflict.value.code == "TD_EXECUTE_IDEMPOTENCY_CONFLICT"


def test_expired_legacy_v1_and_employee_are_never_deleted(execution_engine, actors, monkeypatch):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")

    expired = _approved_synthetic(execution_engine, actors, with_journals=False)
    with execution_engine.begin() as connection:
        connection.execute(text("""UPDATE public.test_personnel_deletion_requests
            SET approved_at=statement_timestamp()-interval '2 hours',
                approval_expires_at=statement_timestamp()-interval '1 hour'
            WHERE request_id=:id"""), {"id": expired["request_id"]})
    expired_key = uuid.uuid4()
    with pytest.raises(approval.TestPersonnelDeletionError) as expired_error:
        _execute(expired, actors, key=expired_key)
    assert expired_error.value.code == "TD_EXECUTION_SNAPSHOT_CHANGED"
    with execution_engine.connect() as connection:
        assert connection.execute(text("""SELECT result_code,result_projection->>'error_code'
            FROM public.test_personnel_deletion_history
            WHERE request_id=:request_id AND action='EXECUTE'
              AND idempotency_key=:idempotency_key"""), {
            "request_id": expired["request_id"],
            "idempotency_key": str(expired_key),
        }).one() == ("TD_EXECUTION_FAILED", "TD_EXECUTION_SNAPSHOT_CHANGED")

    legacy = _approved_synthetic(
        execution_engine, actors, with_journals=False, basis="LEGACY_MANIFEST",
    )
    with pytest.raises(approval.TestPersonnelDeletionError) as legacy_error:
        _execute(legacy, actors)
    assert legacy_error.value.code == "TD_LEGACY_MANIFEST_NOT_EXECUTABLE"

    employee = _approved_synthetic(execution_engine, actors, with_journals=False)
    with execution_engine.begin() as connection:
        connection.execute(text("""INSERT INTO public.employees(full_name,person_id)
            VALUES('forbidden employee',:person_id)"""), {"person_id": employee["person_id"]})
    assert _execute(employee, actors)["status"] == "REAPPROVAL_REQUIRED"

    request_id = uuid.uuid4()
    digest = "d" * 64
    with execution_engine.begin() as connection:
        connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
                request_id,request_number,status,basis,reason_code,target_set_hash,
                relationship_fingerprint,version,initiated_by_user_id,manifest_version,
                process_type,fingerprint_version,relationship_policy_version,
                catalog_version,catalog_fingerprint,approved_at,approval_expires_at)
            VALUES(:id,:number,'APPROVED','PROVENANCE','PROVENANCE_TEST_RUN_CLEANUP',
                :digest,:digest,3,:admin,1,'APPLICANT_ONLY','WP-TD-RELATIONSHIP/v1',
                :policy,:catalog,:catalog_hash,statement_timestamp(),
                statement_timestamp()+interval '1 hour')"""), {
            "id": request_id, "number": f"TD-V1-{request_id.hex[:12].upper()}",
            "digest": digest, "admin": int(actors["ADMIN"]["user_id"]),
            "policy": fingerprints.POLICY_VERSION, "catalog": fingerprints.CATALOG_VERSION,
            "catalog_hash": fingerprints.EXPECTED_CATALOG_FINGERPRINTS[REVISION],
        })
    with pytest.raises(approval.TestPersonnelDeletionError) as v1_error:
        execution.execute_request(
            request_id=request_id, executor_user_id=int(actors["ADMIN"]["user_id"]),
            idempotency_key=uuid.uuid4(), confirmation="irrelevant", expected_snapshot={},
        )
    assert v1_error.value.code == "TD_MANIFEST_V1_READ_ONLY"

    with execution_engine.connect() as connection:
        for target in (expired, legacy, employee):
            assert connection.execute(text(
                "SELECT COUNT(*) FROM persons WHERE person_id=:id"
            ), {"id": target["person_id"]}).scalar_one() == 1


def test_every_matrix_rule_has_fail_closed_execution_action():
    actions = {
        rule.code: (
            "DELETE" if rule.code in fingerprints.DELETE_RULES
            else "PRESERVE" if rule.code in fingerprints.PRESERVE_RULES else "BLOCK"
        )
        for rule in approval.RELATIONSHIP_MATRIX
    }
    assert set(actions) == fingerprints.EXPECTED_RULE_CODES
    assert all(action in {"DELETE", "BLOCK", "PRESERVE"} for action in actions.values())
    assert "EMPLOYEE_PRESENT" not in fingerprints.DELETE_RULES
    assert actions["EMPLOYEE_PRESENT"] == "BLOCK"


def test_parallel_execute_deletes_once(execution_engine, actors, monkeypatch):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_execute, target, actors, key=uuid.uuid4()) for _ in range(2)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=20))
            except approval.TestPersonnelDeletionError as error:
                outcomes.append(error)
    completed = [item for item in outcomes if isinstance(item, dict)]
    rejected = [item for item in outcomes if isinstance(item, approval.TestPersonnelDeletionError)]
    assert len(completed) == 1 and completed[0]["status"] == "COMPLETED"
    assert len(rejected) == 1 and rejected[0].code == "TD_EXECUTE_ALREADY_COMPLETED"
    with execution_engine.connect() as connection:
        assert connection.execute(text("""SELECT COUNT(*) FROM test_personnel_deletion_history
            WHERE request_id=:id AND action='EXECUTE' AND result_code='TD_EXECUTION_COMPLETED'"""), {
            "id": target["request_id"],
        }).scalar_one() == 1


def test_concurrent_legacy_logical_insert_blocks_then_fails_closed(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    reached_r0 = Event()
    release = Event()

    def hook(step):
        assert step == "R0"
        reached_r0.set()
        assert release.wait(timeout=10)

    def run_execution():
        return execution.execute_request(
            request_id=target["request_id"],
            executor_user_id=int(actors["ADMIN"]["user_id"]),
            idempotency_key=uuid.uuid4(),
            confirmation=execution.confirmation_phrase(target["request_number"], 1),
            expected_snapshot=target["expected_snapshot"],
            _test_step_hook=hook,
        )

    def insert_legacy_contact():
        with execution_engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout='10s'"))
            connection.execute(text("""INSERT INTO public.contacts(person_id,full_name)
                VALUES(:person_id,'concurrent logical child')"""), {
                "person_id": target["person_id"],
            })

    with ThreadPoolExecutor(max_workers=2) as pool:
        execution_future = pool.submit(run_execution)
        assert reached_r0.wait(timeout=10)
        insert_future = pool.submit(insert_legacy_contact)
        sleep(0.2)
        assert not insert_future.done()
        release.set()
        assert execution_future.result(timeout=20)["status"] == "COMPLETED"
        with pytest.raises(Exception, match="WP_TD_005_LOGICAL_PERSON_TARGET_MISSING"):
            insert_future.result(timeout=20)
    with execution_engine.connect() as connection:
        assert connection.execute(text("""SELECT COUNT(*) FROM public.contacts
            WHERE person_id=:person_id"""), {"person_id": target["person_id"]}).scalar_one() == 0


def test_concurrent_fk_child_insert_blocks_then_fails_closed(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    reached_r0 = Event()
    release = Event()

    def hook(step):
        assert step == "R0"
        reached_r0.set()
        assert release.wait(timeout=10)

    def run_execution():
        return execution.execute_request(
            request_id=target["request_id"],
            executor_user_id=int(actors["ADMIN"]["user_id"]),
            idempotency_key=uuid.uuid4(),
            confirmation=execution.confirmation_phrase(target["request_number"], 1),
            expected_snapshot=target["expected_snapshot"],
            _test_step_hook=hook,
        )

    def insert_fk_child():
        with execution_engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout='10s'"))
            connection.execute(text("""INSERT INTO public.personnel_application_blockers(
                    application_id,blocker_code)
                VALUES(:application_id,'INTAKE_PHOTO_UNAVAILABLE')"""), {
                "application_id": target["application_id"],
            })

    with ThreadPoolExecutor(max_workers=2) as pool:
        execution_future = pool.submit(run_execution)
        assert reached_r0.wait(timeout=10)
        insert_future = pool.submit(insert_fk_child)
        sleep(0.2)
        assert not insert_future.done()
        release.set()
        assert execution_future.result(timeout=20)["status"] == "COMPLETED"
        with pytest.raises(Exception):
            insert_future.result(timeout=20)


def test_unknown_inbound_cascade_is_catalog_drift_before_delete(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors)
    with execution_engine.begin() as connection:
        connection.execute(text("""CREATE TABLE public.test_unknown_draft_child(
            child_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            draft_id BIGINT NOT NULL REFERENCES public.personnel_intake_drafts(draft_id)
                ON DELETE CASCADE)"""))
        connection.execute(text("""INSERT INTO public.test_unknown_draft_child(draft_id)
            SELECT draft_id FROM public.personnel_intake_drafts
            WHERE application_id=:application_id"""), {"application_id": target["application_id"]})
    try:
        result = _execute(target, actors)
        assert result["status"] == "REAPPROVAL_REQUIRED"
        with execution_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT COUNT(*) FROM public.persons WHERE person_id=:person_id"
            ), {"person_id": target["person_id"]}).scalar_one() == 1
            assert connection.execute(text(
                "SELECT COUNT(*) FROM public.test_unknown_draft_child"
            )).scalar_one() == 1
    finally:
        with execution_engine.begin() as connection:
            connection.execute(text("DROP TABLE public.test_unknown_draft_child"))


def test_approval_fingerprint_drift_commits_reapproval_and_audit(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    original = execution.execute_audit.assert_approver_executor_separation

    def drifted_approval(connection, **kwargs):
        approval_row = original(connection, **kwargs)
        approval_row["target_set_hash"] = "f" * 64
        return approval_row

    monkeypatch.setattr(
        execution.execute_audit, "assert_approver_executor_separation", drifted_approval,
    )
    result = _execute(target, actors)
    assert result["status"] == "REAPPROVAL_REQUIRED"
    with execution_engine.connect() as connection:
        request = connection.execute(text("""SELECT status,approved_at,approval_expires_at
            FROM public.test_personnel_deletion_requests WHERE request_id=:id"""), {
            "id": target["request_id"],
        }).one()
        assert tuple(request) == ("REAPPROVAL_REQUIRED", None, None)
        audit = connection.execute(text("""SELECT new_status,result_code
            FROM public.test_personnel_deletion_history
            WHERE request_id=:id AND action='EXECUTE'"""), {"id": target["request_id"]}).one()
        assert tuple(audit) == ("REAPPROVAL_REQUIRED", "TD_REAPPROVAL_REQUIRED")
        assert connection.execute(text(
            "SELECT COUNT(*) FROM public.persons WHERE person_id=:person_id"
        ), {"person_id": target["person_id"]}).scalar_one() == 1


@pytest.mark.parametrize("raw_command_id", [
    "person@example.test", "900101123456", "+77001234567",
])
def test_command_tombstone_contains_only_technical_id_and_digest(
    execution_engine, actors, monkeypatch, raw_command_id,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    source_command_id = f"{raw_command_id}-{uuid.uuid4().hex[:6]}"
    target = _approved_synthetic(
        execution_engine, actors, command_id=source_command_id,
    )
    _execute(target, actors)
    with execution_engine.connect() as connection:
        columns = connection.execute(text("""SELECT column_name FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='test_personnel_deletion_command_tombstones'""")).scalars().all()
        assert "source_command_id" not in columns
        stored = connection.execute(text("""SELECT to_jsonb(t)::text
            FROM public.test_personnel_deletion_command_tombstones t
            WHERE request_id=:id"""), {"id": target["request_id"]}).scalar_one()
        assert raw_command_id not in stored
        assert "source_command_execution_id" in stored
        assert "source_reference_digest" in stored
        assert connection.execute(text("""SELECT source_reference_digest
            FROM public.test_personnel_deletion_command_tombstones
            WHERE request_id=:id"""), {"id": target["request_id"]}).scalar_one() == hashlib.sha256(
                source_command_id.encode("utf-8")
            ).hexdigest()


def test_command_tombstone_source_reference_digest_is_db_constrained(
    execution_engine, actors,
):
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    with execution_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(DBAPIError, match="ck_tpd_ct_source_reference_digest"):
                connection.execute(text("""INSERT INTO public.test_personnel_deletion_command_tombstones(
                        request_id,source_command_execution_id,source_reference_digest,
                        command_type,command_status,source_created_at,request_digest,
                        result_digest,canonical_digest)
                    VALUES(:request_id,999999,'person@example.test','MaterializePPR','completed',
                        statement_timestamp(),repeat('a',64),repeat('b',64),repeat('c',64))"""), {
                    "request_id": target["request_id"],
                })
        finally:
            transaction.rollback()


def test_uuid_v7_is_accepted(execution_engine, actors, monkeypatch):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    uuid_v7 = uuid.UUID("01890f3e-3b2a-7cc2-98c4-dc0c0c07398f")
    assert _execute(target, actors, key=uuid_v7)["status"] == "COMPLETED"


def test_preserve_and_set_null_rows_are_verified_and_audited(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    retained = {}

    def seed_preserved(connection, person_id, _application_id, admin_id):
        retained["security"] = int(connection.execute(text("""INSERT INTO public.security_audit_log(
                event_type,actor_user_id,target_person_id,metadata)
            VALUES('ACCESS_CHANGED',:actor,:person_id,CAST(:metadata AS jsonb))
            RETURNING audit_id"""), {
            "actor": admin_id, "person_id": person_id, "metadata": '{"synthetic":true}',
        }).scalar_one())
        retained["override"] = int(connection.execute(text("""INSERT INTO public.hr_review_overrides(
                scope_type,scope_key,person_id,field_path,override_value,tier,owner_domain,
                status,persistence_policy,created_by_user_id,creation_channel)
            VALUES('PERSON',:scope,:person_id,'note.text','"synthetic"'::jsonb,0,'HR',
                'active','until_incoming_matches',:actor,'review_ui') RETURNING override_id"""), {
            "scope": f"PERSON:{person_id}", "person_id": person_id, "actor": admin_id,
        }).scalar_one())

    target = _approved_synthetic(
        execution_engine, actors, with_journals=False, before_draft=seed_preserved,
    )
    result = _execute(target, actors)
    assert result["status"] == "COMPLETED"
    counts = result["result"]["table_counts"]
    assert counts["preserved_security_audit_log"] == 1
    assert counts["preserved_hr_review_overrides"] == 1
    with execution_engine.connect() as connection:
        assert tuple(connection.execute(text(
            "SELECT audit_id,target_person_id FROM public.security_audit_log WHERE audit_id=:id"
        ), {"id": retained["security"]}).one()) == (retained["security"], None)
        assert tuple(connection.execute(text(
            "SELECT override_id,person_id FROM public.hr_review_overrides WHERE override_id=:id"
        ), {"id": retained["override"]}).one()) == (retained["override"], None)


def test_durable_intent_survives_execution_crash_for_recovery(
    execution_engine, actors, monkeypatch,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")
    target = _approved_synthetic(execution_engine, actors, with_journals=False)
    key = uuid.uuid4()
    # Commit the intent exactly as execute_request does, then simulate a crash
    # by never entering the domain transaction.
    request_id = target["request_id"]
    payload_hash = execution._payload_hash(
        request_id, key, execution.confirmation_phrase(target["request_number"], 1),
        target["expected_snapshot"],
    )
    execution._prepare_attempt(
        request_id=request_id, executor_user_id=int(actors["ADMIN"]["user_id"]),
        idempotency_key=key, payload_hash=payload_hash,
    )
    with execution_engine.connect() as connection:
        assert connection.execute(text("""SELECT event_type FROM
            public.test_personnel_deletion_execution_attempts WHERE idempotency_key=:key"""), {
            "key": str(key),
        }).scalar_one() == "INTENT"


@pytest.mark.parametrize("block_kind", [
    "user_onboarding", "photo", "incoming_document", "personnel_order",
    "operational_order", "verification", "telegram", "security_grant",
])
def test_real_block_relationships_force_reapproval_without_delete(
    execution_engine, actors, monkeypatch, block_kind,
):
    monkeypatch.setenv(execution.FEATURE_FLAG, "true")

    def seed_block(connection, person_id, application_id, admin_id):
        if block_kind == "user_onboarding":
            employee_id = int(connection.execute(text("""INSERT INTO public.employees(full_name,person_id)
                VALUES('Synthetic blocked employee',:person_id) RETURNING employee_id"""), {
                "person_id": person_id,
            }).scalar_one())
            admin_role = connection.execute(text(
                "SELECT role_id FROM public.roles WHERE code='ADMIN'"
            )).scalar_one()
            connection.execute(text("""INSERT INTO public.users(
                    full_name,role_id,is_active,login,employee_id)
                VALUES('Synthetic linked user',:role,TRUE,:login,:employee)"""), {
                "role": admin_role, "login": f"test.linked.{person_id}", "employee": employee_id,
            })
            connection.execute(text("""INSERT INTO public.employee_onboardings(
                    employee_id,application_id,responsible_hr_id)
                VALUES(:employee,:application,:actor)"""), {
                "employee": employee_id, "application": application_id, "actor": admin_id,
            })
        elif block_kind == "photo":
            connection.execute(text("""INSERT INTO public.person_photos(
                    person_id,file_id,storage_rel_path,mime_type,byte_size,checksum_sha256,
                    is_active,uploaded_by_user_id)
                VALUES(:person_id,:file_id,:path,'image/jpeg',10,:checksum,TRUE,:actor)"""), {
                "person_id": person_id, "file_id": f"{person_id:032x}",
                "path": f"test/{person_id}.jpg", "checksum": "a" * 64, "actor": admin_id,
            })
        elif block_kind == "incoming_document":
            unit_id = int(connection.execute(text("""INSERT INTO public.org_units(name,code)
                VALUES('Synthetic incoming unit',:code) RETURNING unit_id"""), {
                "code": f"TEST-IN-{person_id}",
            }).scalar_one())
            refs = connection.execute(text("""SELECT
                (SELECT document_type_id FROM incoming_document_types ORDER BY document_type_id LIMIT 1),
                (SELECT receipt_channel_id FROM incoming_receipt_channels ORDER BY receipt_channel_id LIMIT 1),
                (SELECT status_id FROM incoming_document_statuses ORDER BY status_id LIMIT 1)""")).one()
            incoming_document_id = int(connection.execute(text("""INSERT INTO public.incoming_documents(
                    registration_number,registration_year,registration_seq,received_at,
                    document_type_id,receipt_channel_id,status_id,summary,sender_kind,
                    sender_person_id,addressee_kind,addressee_text,registration_org_unit_id,
                    responsible_org_unit_id,created_by_user_id)
                VALUES(:number,2099,:seq,CURRENT_DATE,:type,:channel,:status,'Synthetic document',
                    'PERSON',:person_id,'TEXT','Synthetic addressee',:unit,:unit,:actor)
                RETURNING incoming_document_id"""), {
                "number": f"TEST-IN-{person_id}", "seq": person_id, "type": refs[0],
                "channel": refs[1], "status": refs[2], "person_id": person_id,
                "unit": unit_id, "actor": admin_id,
            }).scalar_one())
            connection.execute(text("""INSERT INTO public.incoming_document_attachments(
                    incoming_document_id,file_id,original_filename,content_type,size_bytes,
                    uploaded_by_user_id)
                VALUES(:document_id,:file_id,'synthetic.txt','text/plain',10,:actor)"""), {
                "document_id": incoming_document_id, "file_id": f"{person_id:032x}",
                "actor": admin_id,
            })
        elif block_kind == "personnel_order":
            order_id = int(connection.execute(text("""INSERT INTO public.personnel_orders(
                    order_number,order_date,order_type_code,status,source_mode,created_by)
                VALUES(:number,CURRENT_DATE,'HIRE','DRAFT','PAPER',:actor) RETURNING order_id"""), {
                "number": f"TEST-PO-{person_id}", "actor": admin_id,
            }).scalar_one())
            connection.execute(text("""UPDATE public.personnel_applications
                SET personnel_order_id=:order_id WHERE application_id=:application_id"""), {
                "order_id": order_id, "application_id": application_id,
            })
        elif block_kind == "operational_order":
            employee_id = int(connection.execute(text("""INSERT INTO public.employees(full_name,person_id)
                VALUES('Synthetic operational signer',:person_id) RETURNING employee_id"""), {
                "person_id": person_id,
            }).scalar_one())
            unit_id = int(connection.execute(text(
                "SELECT unit_id FROM public.org_units WHERE code='TEST_ROOT'"
            )).scalar_one())
            workspace_id = int(connection.execute(text("""INSERT INTO public.operational_order_draft_workspaces(
                    organization_id,stage,initiator_type,initiator_reference,content_author_type,
                    content_author_reference,submitting_org_unit_id,record_creator_user_id)
                VALUES(:unit,'DOCUMENT_PROMOTED','PERSON','synthetic-initiator','PERSON',
                    'synthetic-author',:unit,:actor) RETURNING workspace_id"""), {
                "unit": unit_id, "actor": admin_id,
            }).scalar_one())
            promotion_id = int(connection.execute(text("""INSERT INTO public.operational_order_promotions(
                    workspace_id,status,workspace_version,workspace_fingerprint,promoted_by_user_id)
                VALUES(:workspace,'COMPLETED',1,:fingerprint,:actor) RETURNING id"""), {
                "workspace": workspace_id, "fingerprint": f"synthetic-{person_id}", "actor": admin_id,
            }).scalar_one())
            document_id = int(connection.execute(text("""INSERT INTO public.operational_order_documents(
                    workspace_id,status,created_from_workspace_version,
                    created_from_workspace_fingerprint,promotion_id,created_by_user_id)
                VALUES(:workspace,'CREATED',1,:fingerprint,:promotion,:actor) RETURNING id"""), {
                "workspace": workspace_id, "fingerprint": f"synthetic-doc-{person_id}",
                "promotion": promotion_id, "actor": admin_id,
            }).scalar_one())
            version_id = int(connection.execute(text("""INSERT INTO public.operational_order_document_versions(
                    document_id,version_number,workspace_version,snapshot_fingerprint,created_by_user_id)
                VALUES(:document,1,1,:fingerprint,:actor) RETURNING id"""), {
                "document": document_id, "fingerprint": f"synthetic-version-{person_id}",
                "actor": admin_id,
            }).scalar_one())
            authority_id = int(connection.execute(text("""INSERT INTO public.operational_order_signing_authority(
                    document_id,document_version_id,authority_party_type,authority_party_reference,
                    assigned_by_user_id)
                VALUES(:document,:version,'PERSON','synthetic-authority',:actor) RETURNING id"""), {
                "document": document_id, "version": version_id, "actor": admin_id,
            }).scalar_one())
            connection.execute(text("""INSERT INTO public.operational_order_signing_attestations(
                    document_id,signing_authority_id,document_version_id,actor_user_id,
                    actor_employee_id,assigned_authority_party_type,
                    assigned_authority_party_reference,signed_at)
                VALUES(:document,:authority,:version,:actor,:employee,'PERSON',
                    'synthetic-authority',statement_timestamp())"""), {
                "document": document_id, "authority": authority_id, "version": version_id,
                "actor": admin_id, "employee": employee_id,
            })
        elif block_kind == "verification":
            employment_id = int(connection.execute(text("""INSERT INTO public.person_external_employment(
                    person_id,record_kind,employer_name,position_title,started_at)
                VALUES(:person_id,'episode','Synthetic employer','Synthetic role',CURRENT_DATE)
                RETURNING employment_id"""), {"person_id": person_id}).scalar_one())
            policy_id = int(connection.execute(text("""INSERT INTO public.verification_policies(
                    control_point,policy_version,status,effective_from,decision_basis,
                    created_by_user_id,published_by_user_id,published_at)
                VALUES('employment_episode',99,'active',CURRENT_DATE,'Synthetic policy',
                    :actor,:actor,statement_timestamp()) RETURNING policy_id"""), {
                "actor": admin_id,
            }).scalar_one())
            connection.execute(text("""INSERT INTO public.verification_tasks(
                    person_id,control_point,object_type,object_id,object_version_id,
                    policy_id,policy_version,status)
                VALUES(:person_id,'employment_episode','person_external_employment',
                    :object_id,:object_id,:policy,99,'pending')"""), {
                "person_id": person_id, "object_id": employment_id, "policy": policy_id,
            })
        elif block_kind == "telegram":
            connection.execute(text("""INSERT INTO public.person_telegram_bindings(
                    person_id,telegram_user_id,telegram_username)
                VALUES(:person_id,:telegram_id,'synthetic_test')"""), {
                "person_id": person_id, "telegram_id": 900000000000 + person_id,
            })
        elif block_kind == "security_grant":
            connection.execute(text("""INSERT INTO public.access_grants(
                    access_role_id,target_type,target_id,granted_by_user_id,reason)
                SELECT access_role_id,'PERSON',:person_id,:actor,'Synthetic person grant'
                FROM public.access_roles WHERE code='TEST_PERSONNEL_DELETION_AUDIT_READ'"""), {
                "person_id": person_id, "actor": admin_id,
            })

    target = _approved_synthetic(
        execution_engine, actors, with_journals=False, after_approval=seed_block,
    )
    result = _execute(target, actors)
    assert result["status"] == "REAPPROVAL_REQUIRED"
    with execution_engine.connect() as connection:
        assert connection.execute(text(
            "SELECT COUNT(*) FROM public.persons WHERE person_id=:person_id"
        ), {"person_id": target["person_id"]}).scalar_one() == 1

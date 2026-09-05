"""WP-TD-005 stage 4 permission and append-only EXECUTE audit tests."""
from __future__ import annotations

import json
import uuid

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from starlette.testclient import TestClient

from app import auth
from app.auth import get_current_user
from app.main import app
from app.security import admin_permissions
from app.services import access_resolver_service
from app.services import test_personnel_deletion_execute_audit_service as execute_audit
from app.services import test_personnel_deletion_fingerprint_service as fingerprints
from app.services import test_personnel_deletion_service as deletion_service
from tests.test_wp_td_005_manifest_v2 import _alembic_config, _ephemeral_database


PREVIOUS_REVISION = "td005fp3v101"
REVISION = "td005audit401"


@pytest.fixture(scope="module")
def audit_engine():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        command.upgrade(_alembic_config(url), REVISION)
        yield clone_engine


@pytest.fixture(autouse=True)
def bind_engines(audit_engine, monkeypatch):
    monkeypatch.setattr(admin_permissions, "engine", audit_engine)
    monkeypatch.setattr(access_resolver_service, "engine", audit_engine)
    monkeypatch.setattr(deletion_service, "engine", audit_engine)


@pytest.fixture
def actors(audit_engine):
    with audit_engine.connect() as connection:
        rows = connection.execute(text("""SELECT DISTINCT ON (role.code)
                role.code,users.user_id,users.role_id
            FROM public.users users JOIN public.roles role ON role.role_id=users.role_id
            WHERE role.code IN ('ADMIN','HR_HEAD') AND users.is_active=TRUE
            ORDER BY role.code,users.user_id""")).mappings().all()
    result = {str(row["code"]): dict(row) for row in rows}
    assert set(result) == {"ADMIN", "HR_HEAD"}
    return result


def _seed_approved_request(connection, actors):
    request_id = uuid.uuid4()
    digest = "a" * 64
    catalog_hash = fingerprints.EXPECTED_CATALOG_FINGERPRINTS[REVISION]
    connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
            request_id,request_number,status,basis,reason_code,target_set_hash,
            relationship_fingerprint,version,initiated_by_user_id,manifest_version,
            process_type,fingerprint_version,relationship_policy_version,
            catalog_version,catalog_fingerprint,approved_at,approval_expires_at)
        VALUES(:request_id,:number,'APPROVED','PROVENANCE',
            'PROVENANCE_TEST_RUN_CLEANUP',:digest,:digest,3,:admin,2,
            'APPLICANT_ONLY',:fingerprint_version,:policy_version,:catalog_version,
            :catalog_hash,statement_timestamp(),statement_timestamp()+interval '1 hour')"""), {
            "request_id": request_id,
            "number": f"TD-AUDIT-{request_id.hex[:14].upper()}",
            "digest": digest,
            "admin": int(actors["ADMIN"]["user_id"]),
            "fingerprint_version": fingerprints.FINGERPRINT_VERSION,
            "policy_version": fingerprints.POLICY_VERSION,
            "catalog_version": fingerprints.CATALOG_VERSION,
            "catalog_hash": catalog_hash,
        })
    connection.execute(text("""INSERT INTO public.test_personnel_deletion_decisions(
            request_id,decision,actor_user_id,actor_role_code,permission_code,
            request_version,target_set_hash,submitted_synthetic_confirmed,
            relationship_fingerprint,fingerprint_version,catalog_fingerprint)
        VALUES(:request_id,'APPROVE',:hr,'HR_HEAD',
            'TEST_PERSONNEL_DELETION_APPROVE',3,:digest,FALSE,
            :digest,:fingerprint_version,:catalog_hash)"""), {
            "request_id": request_id,
            "hr": int(actors["HR_HEAD"]["user_id"]),
            "digest": digest,
            "fingerprint_version": fingerprints.FINGERPRINT_VERSION,
            "catalog_hash": catalog_hash,
        })
    return request_id


def _write(connection, request_id, actors, *, key="10000000-0000-4000-8000-000000000001", counts=None):
    return execute_audit.record_execute_audit(
        connection,
        request_id=request_id,
        executor_user_id=int(actors["ADMIN"]["user_id"]),
        table_counts=counts or {"persons": 1, "personnel_applications": 2},
        before_hash="b" * 64,
        after_hash="c" * 64,
        idempotency_key=key,
        result="TD_EXECUTE_SIMULATED",
        error_code=None,
    )


def test_alembic_has_one_stage4_head():
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert len(heads) == 1
    assert REVISION in {
        migration.revision for migration in script.iterate_revisions(heads[0], "base")
    }


def test_stage4_upgrade_downgrade_upgrade():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            actions = connection.execute(text("""SELECT pg_get_constraintdef(oid)
                FROM pg_constraint WHERE conname='ck_tpdh_action'""")).scalar_one()
            assert "EXECUTE" in actions
        command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS_REVISION
            actions = connection.execute(text("""SELECT pg_get_constraintdef(oid)
                FROM pg_constraint WHERE conname='ck_tpdh_action'""")).scalar_one()
            assert "EXECUTE" not in actions
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION


def test_execute_permission_default_is_admin_only(audit_engine, actors):
    admin_id = int(actors["ADMIN"]["user_id"])
    hr_id = int(actors["HR_HEAD"]["user_id"])
    assert admin_permissions.has_admin_permission(
        admin_id, admin_permissions.TEST_PERSONNEL_DELETION_EXECUTE,
    )
    assert not admin_permissions.has_admin_permission(
        hr_id, admin_permissions.TEST_PERSONNEL_DELETION_EXECUTE,
    )
    with audit_engine.connect() as connection:
        role_grants = connection.execute(text("""SELECT target_role.code
            FROM public.access_grants grant_def
            JOIN public.access_roles access_role
              ON access_role.access_role_id=grant_def.access_role_id
            JOIN public.roles target_role
              ON grant_def.target_type='ROLE' AND target_role.role_id=grant_def.target_id
            WHERE access_role.code='TEST_PERSONNEL_DELETION_EXECUTE'
              AND grant_def.active_flag=TRUE ORDER BY target_role.code""")).scalars().all()
    assert role_grants == ["ADMIN"]


def test_auth_me_exposes_execute_capability(audit_engine, actors):
    admin_caps = admin_permissions.get_test_personnel_deletion_capabilities(
        int(actors["ADMIN"]["user_id"]), primary_role_code="ADMIN",
    )
    hr_caps = admin_permissions.get_test_personnel_deletion_capabilities(
        int(actors["HR_HEAD"]["user_id"]), primary_role_code="HR_HEAD",
    )
    assert admin_caps["can_execute_test_personnel_deletion"] is True
    assert hr_caps["can_execute_test_personnel_deletion"] is False
    previous = app.dependency_overrides.get(get_current_user)
    try:
        app.dependency_overrides[get_current_user] = lambda: {**actors["ADMIN"], **admin_caps}
        with TestClient(app) as client:
            response = client.get("/auth/me")
        assert response.status_code == 200
        assert response.json()["can_execute_test_personnel_deletion"] is True
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous


def test_approver_executor_separation_and_permission(audit_engine, actors):
    with audit_engine.connect() as connection:
        transaction = connection.begin()
        try:
            request_id = _seed_approved_request(connection, actors)
            approval = execute_audit.assert_approver_executor_separation(
                connection, request_id=request_id,
                executor_user_id=int(actors["ADMIN"]["user_id"]),
            )
            assert int(approval["actor_user_id"]) == int(actors["HR_HEAD"]["user_id"])
            with pytest.raises(execute_audit.ExecuteAuditContractError) as conflict:
                execute_audit.assert_approver_executor_separation(
                    connection, request_id=request_id,
                    executor_user_id=int(actors["HR_HEAD"]["user_id"]),
                )
            assert conflict.value.code == "TD_EXECUTE_APPROVER_CONFLICT"
            with pytest.raises(execute_audit.ExecuteAuditContractError) as denied:
                execute_audit.assert_executor_permission(
                    connection, executor_user_id=int(actors["HR_HEAD"]["user_id"]),
                )
            assert denied.value.code == "TD_EXECUTE_PERMISSION_REQUIRED"
        finally:
            transaction.rollback()


def test_execute_audit_is_idempotent_and_projection_is_exact(audit_engine, actors):
    with audit_engine.connect() as connection:
        transaction = connection.begin()
        try:
            request_id = _seed_approved_request(connection, actors)
            first = _write(connection, request_id, actors)
            second = _write(connection, request_id, actors)
            assert second == first
            assert set(first) == {
                "request_id", "executor_user_id", "manifest_version",
                "fingerprint_version", "target_set_hash", "relationship_fingerprint",
                "policy_version", "catalog_version", "catalog_fingerprint",
                "table_counts", "before_hash", "after_hash", "idempotency_key",
                "timestamp", "result", "error_code",
            }
            assert first["table_counts"] == {
                "personnel_applications": 2, "persons": 1,
            }
            count = connection.execute(text("""SELECT COUNT(*)
                FROM public.test_personnel_deletion_history
                WHERE request_id=:request_id AND action='EXECUTE'"""), {
                    "request_id": request_id,
                }).scalar_one()
            assert count == 1
            with pytest.raises(execute_audit.ExecuteAuditContractError) as conflict:
                _write(connection, request_id, actors, counts={"persons": 2})
            assert conflict.value.code == "TD_EXECUTE_IDEMPOTENCY_CONFLICT"
            second_admin_id = int(connection.execute(text("""INSERT INTO public.users(
                    user_id,full_name,role_id,is_active,login)
                SELECT (SELECT max(user_id)+1 FROM public.users),'Stage 4 second admin',
                    role_id,TRUE,:login FROM public.roles WHERE code='ADMIN'
                RETURNING user_id"""), {
                    "login": f"stage4-second-admin-{uuid.uuid4().hex[:10]}",
                }).scalar_one())
            second_actors = {**actors, "ADMIN": {**actors["ADMIN"], "user_id": second_admin_id}}
            with pytest.raises(execute_audit.ExecuteAuditContractError) as actor_conflict:
                _write(connection, request_id, second_actors)
            assert actor_conflict.value.code == "TD_EXECUTE_IDEMPOTENCY_CONFLICT"
        finally:
            transaction.rollback()


def test_execute_audit_is_append_only_and_rejects_pii_raw_payload(audit_engine, actors):
    with audit_engine.connect() as connection:
        transaction = connection.begin()
        try:
            request_id = _seed_approved_request(connection, actors)
            projection = _write(
                connection, request_id, actors,
                key="10000000-0000-4000-8000-000000000002",
            )
            for statement in (
                "UPDATE public.test_personnel_deletion_history SET result_code='TD_CHANGED' WHERE action='EXECUTE'",
                "DELETE FROM public.test_personnel_deletion_history WHERE action='EXECUTE'",
                "TRUNCATE public.test_personnel_deletion_history",
            ):
                savepoint = connection.begin_nested()
                try:
                    with pytest.raises(Exception, match="WP_TD_002_APPEND_ONLY"):
                        connection.execute(text(statement))
                finally:
                    savepoint.rollback()

            unsafe = {**projection, "raw_payload": {"full_name": "Forbidden Person"}}
            savepoint = connection.begin_nested()
            try:
                with pytest.raises(Exception):
                    connection.execute(text("""INSERT INTO public.test_personnel_deletion_history(
                            request_id,actor_user_id,actor_role_code,permission_code,action,
                            old_status,new_status,old_version,new_version,target_set_hash,
                            idempotency_key,command_payload_hash,occurred_at,result_code,result_projection)
                        SELECT request_id,actor_user_id,actor_role_code,permission_code,action,
                            old_status,new_status,old_version,new_version,target_set_hash,
                            'stage4-unsafe',repeat('d',64),occurred_at,result_code,CAST(:projection AS jsonb)
                        FROM public.test_personnel_deletion_history WHERE action='EXECUTE' LIMIT 1"""), {
                        "projection": json.dumps(unsafe),
                    })
            finally:
                savepoint.rollback()
        finally:
            transaction.rollback()


def test_old_request_remains_readable(audit_engine, actors):
    request_id = uuid.uuid4()
    with audit_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
                    request_id,request_number,basis,reason_code,target_set_hash,
                    relationship_fingerprint,manifest_version,process_type,initiated_by_user_id)
                VALUES(:request_id,:number,'LEGACY_MANIFEST','LEGACY_SYNTHETIC_TEST_DATA',
                    repeat('e',64),repeat('f',64),1,'APPLICANT_ONLY',:admin)"""), {
                    "request_id": request_id,
                    "number": f"TD-OLD-{request_id.hex[:16].upper()}",
                    "admin": int(actors["ADMIN"]["user_id"]),
                })
            detail = deletion_service._request_detail(connection, request_id)
            assert detail["manifest_read_only"] is True
            assert detail["execution_eligible"] is False
        finally:
            transaction.rollback()

"""WP-TD-005 stage 1: PERSON-root manifest v2."""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import date

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import dotenv_values
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.directory.test_personnel_deletion_schemas import (
    TestPersonnelDraftCreateIn as PersonnelDraftCreateIn,
)
from app.services import test_personnel_deletion_service as service
from tests.db_guard import assert_connected_test_database, validate_test_database_url


PREVIOUS_REVISION = "b1c2d3e4f5a6"
REVISION = "td005m1v2a01"


def _canonical_hash(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _alembic_config(url: str | None = None) -> Config:
    config = Config("alembic.ini")
    if url:
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@contextmanager
def _ephemeral_database(*, upgrade: bool = True):
    source_url = str(dotenv_values(".env")["DATABASE_URL"])
    source = make_url(source_url)
    name = f"corpsite_td005_manifest_{uuid.uuid4().hex[:10]}_test"
    admin_url = source.set(database="postgres").render_as_string(hide_password=False)
    target_url = source.set(database=name).render_as_string(hide_password=False)
    expected = validate_test_database_url(
        test_database_url=target_url,
        app_database_url=source_url,
    )
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    clone_engine = create_engine(target_url)
    template_name = str(source.database)
    assert template_name.replace("_", "").isalnum()
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{template_name}"'))
    try:
        with clone_engine.connect() as connection:
            assert_connected_test_database(connection, expected)
        if upgrade:
            command.upgrade(_alembic_config(target_url), REVISION)
        yield target_url, clone_engine
    finally:
        clone_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=:name AND pid<>pg_backend_pid()"
            ), {"name": name})
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin_engine.dispose()


@pytest.fixture(scope="module")
def manifest_engine():
    with _ephemeral_database() as (_url, clone_engine):
        yield clone_engine


@pytest.fixture(autouse=True)
def bind_service_engine(manifest_engine, monkeypatch):
    monkeypatch.setattr(service, "engine", manifest_engine)


@pytest.fixture
def actors(manifest_engine) -> dict[str, int]:
    with manifest_engine.connect() as connection:
        rows = connection.execute(text("""SELECT DISTINCT ON (r.code) r.code,u.user_id
            FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
            WHERE r.code IN ('ADMIN','HR_HEAD') AND u.is_active=TRUE
            ORDER BY r.code,u.user_id""")).mappings().all()
    result = {str(row["code"]): int(row["user_id"]) for row in rows}
    assert set(result) == {"ADMIN", "HR_HEAD"}
    return result


@pytest.fixture
def person_with_applications(actors, manifest_engine):
    suffix = uuid.uuid4().hex[:12]
    with manifest_engine.begin() as connection:
        person_id = int(connection.execute(text("""INSERT INTO public.persons(
                full_name,match_key,source
            ) VALUES(:name,:key,'manual') RETURNING person_id"""), {
                "name": f"WP TD 005 Applicant {suffix}",
                "key": f"wp-td-005-{suffix}",
            }).scalar_one())
        application_ids = [int(connection.execute(text("""INSERT INTO public.personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key
            ) VALUES(:person_id,'intake_pending',:received,:actor,:key)
            RETURNING application_id"""), {
                "person_id": person_id,
                "received": date.today(),
                "actor": actors["ADMIN"],
                "key": f"wp-td-005-{suffix}-active",
            }).scalar_one())]
    yield person_id, application_ids, suffix
    with manifest_engine.begin() as connection:
        connection.execute(text(
            "DELETE FROM public.personnel_applications WHERE application_id=ANY(:ids)"
        ), {"ids": application_ids})
        connection.execute(text(
            "DELETE FROM public.persons WHERE person_id=:person_id"
        ), {"person_id": person_id})


def _draft(actors, person_with_applications):
    person_id, application_ids, suffix = person_with_applications
    return service.create_draft(
        actor_user_id=actors["ADMIN"],
        basis="LEGACY_MANIFEST",
        reason_code="LEGACY_SYNTHETIC_TEST_DATA",
        preview_criteria={"field": "full_name", "selection": "EXACT_MANIFEST"},
        original_mask=None,
        targets=[
            {"person_id": person_id, "application_id": application_id}
            for application_id in reversed(application_ids)
        ],
        idempotency_key=f"wp-td-005-create-{suffix}-{uuid.uuid4().hex[:6]}",
    )


def test_alembic_has_single_manifest_v2_head():
    assert ScriptDirectory.from_config(_alembic_config()).get_heads() == [REVISION]


def test_manifest_v2_migration_upgrade_downgrade_upgrade():
    legacy_request_id = uuid.uuid4()
    digest = "b" * 64
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        with clone_engine.begin() as connection:
            connection.execute(text("""INSERT INTO test_personnel_deletion_requests(
                    request_id,request_number,basis,reason_code,target_set_hash,
                    relationship_fingerprint,initiated_by_user_id
                ) VALUES(:id,:number,'LEGACY_MANIFEST','LEGACY_SYNTHETIC_TEST_DATA',
                    :digest,:digest,1)"""), {
                    "id": legacy_request_id,
                    "number": f"TD-PRE-V2-{legacy_request_id.hex[:12]}",
                    "digest": digest,
                })
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            legacy = connection.execute(text("""SELECT manifest_version,process_type
                FROM test_personnel_deletion_requests WHERE request_id=:id"""), {
                    "id": legacy_request_id,
                }).one()
            assert tuple(legacy) == (1, "APPLICANT_ONLY")
            assert connection.execute(text(
                "SELECT to_regclass('public.test_personnel_deletion_manifest_v2_targets')"
            )).scalar_one() is not None

        command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS_REVISION
            assert connection.execute(text(
                "SELECT to_regclass('public.test_personnel_deletion_manifest_v2_targets')"
            )).scalar_one() is None
            assert not connection.execute(text("""SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='test_personnel_deletion_requests'
                  AND column_name='manifest_version'
            )""")).scalar_one()
            assert connection.execute(text("""SELECT COUNT(*)
                FROM test_personnel_deletion_requests WHERE request_id=:id"""), {
                    "id": legacy_request_id,
                }).scalar_one() == 1

        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert connection.execute(text(
                "SELECT to_regclass('public.test_personnel_deletion_manifest_v2_targets')"
            )).scalar_one() is not None


def test_manifest_v2_hash_is_person_rooted_sorted_and_complete():
    targets = [
        {"person_id": 20, "application_id": 202},
        {"person_id": 10, "application_id": 102},
        {"person_id": 10, "application_id": 101},
    ]
    expected = {
        "schema": "WP-TD-MANIFEST/v2",
        "manifest_version": 2,
        "process_type": "APPLICANT_ONLY",
        "targets": [
            {"root_type": "PERSON", "person_id": 10, "application_ids": [101, 102]},
            {"root_type": "PERSON", "person_id": 20, "application_ids": [202]},
        ],
    }
    assert service._manifest_v2_roots(targets) == expected["targets"]
    assert service._target_set_hash(targets) == _canonical_hash(expected)
    assert service._target_set_hash(reversed(targets)) == _canonical_hash(expected)
    assert service._target_set_hash(targets[:-1]) != _canonical_hash(expected)


def test_manifest_v2_create_submit_and_approval_workflow(actors, person_with_applications):
    person_id, application_ids, _suffix = person_with_applications
    preview = service.preview_candidates(
        mask=None,
        field="full_name",
        person_ids=[person_id],
        application_ids=[],
    )
    assert [item["application_id"] for item in preview["items"]] == application_ids

    draft = _draft(actors, person_with_applications)
    assert draft["manifest_version"] == 2
    assert draft["process_type"] == "APPLICANT_ONLY"
    assert draft["manifest_read_only"] is False
    assert draft["approval_eligible"] is True
    assert draft["execution_eligible"] is False
    assert draft["execution_block_code"] == "TD_EXECUTION_NOT_IMPLEMENTED"
    assert draft["target_set_hash"] == service._target_set_hash([
        {"person_id": person_id, "application_id": application_id}
        for application_id in application_ids
    ])
    assert draft["manifest_targets"] == [{
        "root_type": "PERSON",
        "person_id": person_id,
        "application_ids": application_ids,
        "manifest_order": 0,
    }]

    submitted, conflict = service.submit_request(
        request_id=draft["request_id"],
        actor_user_id=actors["ADMIN"],
        expected_version=draft["version"],
        idempotency_key=f"wp-td-005-submit-{uuid.uuid4().hex}",
    )
    assert conflict is None
    assert submitted["status"] == "PENDING_HR_APPROVAL"

    approved, conflict = service.decide_request(
        request_id=draft["request_id"],
        actor_user_id=actors["HR_HEAD"],
        expected_version=submitted["version"],
        decision="APPROVE",
        idempotency_key=f"wp-td-005-approve-{uuid.uuid4().hex}",
        comment=None,
        submitted_synthetic_confirmed=False,
    )
    assert conflict is None
    assert approved["status"] == "APPROVED"
    assert approved["manifest_version"] == 2


def test_incomplete_application_set_and_employee_process_are_rejected(
    actors, person_with_applications, manifest_engine,
):
    person_id, application_ids, suffix = person_with_applications
    with manifest_engine.begin() as connection:
        historical_application_id = int(connection.execute(text("""INSERT INTO public.personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key
            ) VALUES(:person_id,'withdrawn',:received,:actor,:key)
            RETURNING application_id"""), {
                "person_id": person_id,
                "received": date.today(),
                "actor": actors["ADMIN"],
                "key": f"wp-td-005-{suffix}-historical",
            }).scalar_one())
    application_ids.append(historical_application_id)
    application_ids.sort()
    with pytest.raises(service.TestPersonnelDeletionError) as incomplete:
        service.create_draft(
            actor_user_id=actors["ADMIN"],
            basis="LEGACY_MANIFEST",
            reason_code="LEGACY_SYNTHETIC_TEST_DATA",
            preview_criteria={"selection": "EXACT_MANIFEST"},
            original_mask=None,
            targets=[{"person_id": person_id, "application_id": application_ids[0]}],
            idempotency_key=f"wp-td-005-incomplete-{suffix}",
        )
    assert incomplete.value.code == "TD_MANIFEST_APPLICATION_SET_INCOMPLETE"

    with pytest.raises(service.TestPersonnelDeletionError) as employee:
        service.create_draft(
            actor_user_id=actors["ADMIN"],
            basis="LEGACY_MANIFEST",
            reason_code="LEGACY_SYNTHETIC_TEST_DATA",
            preview_criteria={"selection": "EXACT_MANIFEST"},
            original_mask=None,
            targets=[
                {"person_id": person_id, "application_id": application_id}
                for application_id in application_ids
            ],
            idempotency_key=f"wp-td-005-employee-{suffix}",
            process_type="EMPLOYEE",
        )
    assert employee.value.code == "TD_PROCESS_TYPE_INVALID"

    with pytest.raises(ValidationError):
        PersonnelDraftCreateIn.model_validate({
            "basis": "LEGACY_MANIFEST",
            "process_type": "EMPLOYEE",
            "reason_code": "LEGACY_SYNTHETIC_TEST_DATA",
            "targets": [
                {"person_id": person_id, "application_id": application_id}
                for application_id in application_ids
            ],
            "idempotency_key": f"wp-td-005-schema-{suffix}",
        })


def test_manifest_v2_roots_and_request_identity_are_immutable(
    actors, person_with_applications, manifest_engine,
):
    draft = _draft(actors, person_with_applications)
    with manifest_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(Exception, match="WP_TD_005_MANIFEST_V2_TARGET_IMMUTABLE"):
                connection.execute(text("""UPDATE test_personnel_deletion_manifest_v2_targets
                    SET application_ids=application_ids || 999999
                    WHERE request_id=:request_id"""), {"request_id": draft["request_id"]})
        finally:
            transaction.rollback()

    with manifest_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(Exception, match="ck_tpd_v2_application_ids"):
                connection.execute(text("""INSERT INTO test_personnel_deletion_manifest_v2_targets(
                        request_id,root_type,person_id,application_ids,manifest_order
                    ) VALUES(:request_id,'PERSON',999999,ARRAY[2,1]::bigint[],99)"""), {
                        "request_id": draft["request_id"],
                    })
        finally:
            transaction.rollback()

    with manifest_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(Exception, match="WP_TD_002_REQUEST_MANIFEST_IMMUTABLE"):
                connection.execute(text("""UPDATE test_personnel_deletion_requests
                    SET manifest_version=1 WHERE request_id=:request_id"""), {
                        "request_id": draft["request_id"],
                    })
        finally:
            transaction.rollback()


def test_manifest_v1_is_read_only_and_cannot_receive_new_approval(actors, manifest_engine):
    digest = "a" * 64
    draft_id = uuid.uuid4()
    pending_id = uuid.uuid4()
    with manifest_engine.begin() as connection:
        for request_id, status in ((draft_id, "DRAFT"), (pending_id, "PENDING_HR_APPROVAL")):
            connection.execute(text("""INSERT INTO test_personnel_deletion_requests(
                    request_id,request_number,status,basis,reason_code,target_set_hash,
                    relationship_fingerprint,initiated_by_user_id,submitted_at,expires_at
                ) VALUES(:id,:number,:status,'LEGACY_MANIFEST','LEGACY_SYNTHETIC_TEST_DATA',
                    :digest,:digest,:actor,
                    CASE WHEN :status='PENDING_HR_APPROVAL' THEN statement_timestamp() END,
                    CASE WHEN :status='PENDING_HR_APPROVAL' THEN statement_timestamp()+interval '1 hour' END
                )"""), {
                    "id": request_id,
                    "number": f"TD-V1-{request_id.hex[:16].upper()}",
                    "status": status,
                    "digest": digest,
                    "actor": actors["ADMIN"],
                })

    detail = service.get_request(draft_id)
    assert detail["manifest_version"] == 1
    assert detail["manifest_read_only"] is True
    assert detail["approval_eligible"] is False
    assert detail["execution_eligible"] is False
    assert detail["execution_block_code"] == "TD_MANIFEST_V1_READ_ONLY"

    with manifest_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(Exception, match="WP_TD_005_MANIFEST_V2_REQUEST_REQUIRED"):
                connection.execute(text("""INSERT INTO test_personnel_deletion_manifest_v2_targets(
                        request_id,root_type,person_id,application_ids,manifest_order
                    ) VALUES(:request_id,'PERSON',999999,ARRAY[1]::bigint[],0)"""), {
                        "request_id": draft_id,
                    })
        finally:
            transaction.rollback()

    with pytest.raises(service.TestPersonnelDeletionError) as submit_error:
        service.submit_request(
            request_id=draft_id,
            actor_user_id=actors["ADMIN"],
            expected_version=1,
            idempotency_key=f"wp-td-005-v1-submit-{uuid.uuid4().hex}",
        )
    assert submit_error.value.code == "TD_MANIFEST_V1_READ_ONLY"

    with pytest.raises(service.TestPersonnelDeletionError) as approval_error:
        service.decide_request(
            request_id=pending_id,
            actor_user_id=actors["HR_HEAD"],
            expected_version=1,
            decision="APPROVE",
            idempotency_key=f"wp-td-005-v1-approve-{uuid.uuid4().hex}",
            comment=None,
            submitted_synthetic_confirmed=False,
        )
    assert approval_error.value.code == "TD_MANIFEST_V1_READ_ONLY"
    with manifest_engine.connect() as connection:
        assert connection.execute(text("""SELECT COUNT(*)
            FROM test_personnel_deletion_decisions
            WHERE request_id=:request_id"""), {"request_id": pending_id}).scalar_one() == 0

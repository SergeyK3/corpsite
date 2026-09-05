"""WP-TD-005 stage 2 PostgreSQL tests for PII-free tombstones."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.services import test_personnel_deletion_tombstone_service as tombstones
from app.services.test_personnel_deletion_service import (
    TestPersonnelDeletionError as _TestPersonnelDeletionError,
)
from tests.test_wp_td_005_manifest_v2 import _alembic_config, _ephemeral_database


PREVIOUS_REVISION = "td005m1v2a01"
REVISION = "td005tomb201"
TOMBSTONE_TABLES = (
    "test_personnel_deletion_record_event_tombstones",
    "test_personnel_deletion_command_tombstones",
    "test_personnel_deletion_lifecycle_tombstones",
)


@pytest.fixture(scope="module")
def tombstone_engine():
    with _ephemeral_database() as (url, clone_engine):
        command.upgrade(_alembic_config(url), REVISION)
        yield clone_engine


@pytest.fixture
def tombstone_sources(tombstone_engine):
    suffix = uuid.uuid4().hex[:12]
    with tombstone_engine.begin() as connection:
        admin_id = int(connection.execute(text("""SELECT u.user_id
            FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
            WHERE r.code='ADMIN' AND u.is_active=TRUE
            ORDER BY u.user_id LIMIT 1""")).scalar_one())
        domain_code = str(connection.execute(text("""SELECT domain_code
            FROM public.personnel_migration_domains ORDER BY domain_code LIMIT 1""")).scalar_one())
        person_id = int(connection.execute(text("""INSERT INTO public.persons(
                full_name,match_key,source
            ) VALUES(:name,:key,'manual') RETURNING person_id"""), {
                "name": f"WP TD 005 Tombstone {suffix}",
                "key": f"wp-td-005-tombstone-{suffix}",
            }).scalar_one())
        application_id = int(connection.execute(text("""INSERT INTO public.personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key
            ) VALUES(:person_id,'intake_pending',CURRENT_DATE,:actor,:key)
            RETURNING application_id"""), {
                "person_id": person_id,
                "actor": admin_id,
                "key": f"wp-td-005-tombstone-app-{suffix}",
            }).scalar_one())
        request_id = uuid.uuid4()
        digest = "a" * 64
        connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
                request_id,request_number,basis,reason_code,target_set_hash,
                relationship_fingerprint,manifest_version,process_type,initiated_by_user_id
            ) VALUES(:id,:number,'LEGACY_MANIFEST','LEGACY_SYNTHETIC_TEST_DATA',
                :digest,:digest,2,'APPLICANT_ONLY',:actor)"""), {
                "id": request_id,
                "number": f"TD-TOMB-{request_id.hex[:16].upper()}",
                "digest": digest,
                "actor": admin_id,
            })
        connection.execute(text("""INSERT INTO public.test_personnel_deletion_manifest_v2_targets(
                request_id,root_type,person_id,application_ids,manifest_order
            ) VALUES(:request_id,'PERSON',:person_id,ARRAY[:application_id]::bigint[],0)"""), {
                "request_id": request_id,
                "person_id": person_id,
                "application_id": application_id,
            })
        event_id = int(connection.execute(text("""INSERT INTO public.personnel_record_events(
                person_id,domain_code,record_table_name,record_id,event_type,actor_id,event_payload
            ) VALUES(:person_id,:domain,'personnel_record_metadata',:person_id,
                'PPR_CREATED',:actor,CAST(:payload AS jsonb)) RETURNING event_id"""), {
                "person_id": person_id,
                "domain": domain_code,
                "actor": str(admin_id),
                "payload": json.dumps({"iin": "991231123456", "name": "Secret Person"}),
            }).scalar_one())
        command_id = f"td005-command-{suffix}"
        connection.execute(text("""INSERT INTO public.ppr_command_executions(
                command_id,command_type,person_id,request_fingerprint,status,
                result_payload,completed_at
            ) VALUES(:command_id,'MaterializePPR',:person_id,:request,'completed',
                CAST(:result AS jsonb),statement_timestamp())"""), {
                "command_id": command_id,
                "person_id": person_id,
                "request": "raw-request-person@example.org",
                "result": json.dumps({"phone": "+7 777 123 45 67", "result": "secret"}),
            })
        lifecycle_id = int(connection.execute(text("""INSERT INTO public.personnel_application_lifecycle_audit(
                application_id,action,previous_status,new_status,comment,actor_user_id,metadata
            ) VALUES(:application_id,'registered',NULL,'intake_pending',:comment,:actor,
                CAST(:metadata AS jsonb)) RETURNING audit_id"""), {
                "application_id": application_id,
                "comment": "Secret Applicant comment",
                "actor": admin_id,
                "metadata": json.dumps({"email": "person@example.org", "iin": "991231123456"}),
            }).scalar_one())
    return {
        "request_id": request_id,
        "person_id": person_id,
        "application_id": application_id,
        "event_id": event_id,
        "command_id": command_id,
        "lifecycle_id": lifecycle_id,
        "admin_id": admin_id,
    }


def _capture_all(connection, source):
    return tombstones.capture_tombstones(
        connection,
        request_id=source["request_id"],
        record_event_ids=[source["event_id"]],
        command_ids=[source["command_id"]],
        lifecycle_audit_ids=[source["lifecycle_id"]],
    )


def test_alembic_has_single_tombstone_head():
    assert ScriptDirectory.from_config(_alembic_config()).get_heads() == [REVISION]


def test_tombstone_migration_upgrade_downgrade_upgrade():
    with _ephemeral_database() as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert all(connection.execute(text("SELECT to_regclass(:name)"), {
                "name": f"public.{table}",
            }).scalar_one() is not None for table in TOMBSTONE_TABLES)

        command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS_REVISION
            assert all(connection.execute(text("SELECT to_regclass(:name)"), {
                "name": f"public.{table}",
            }).scalar_one() is None for table in TOMBSTONE_TABLES)

        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert all(connection.execute(text("SELECT to_regclass(:name)"), {
                "name": f"public.{table}",
            }).scalar_one() is not None for table in TOMBSTONE_TABLES)


def test_downgrade_refuses_to_drop_retained_tombstones():
    with _ephemeral_database() as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        request_id = uuid.uuid4()
        with clone_engine.begin() as connection:
            admin_id = int(connection.execute(text(
                "SELECT user_id FROM public.users ORDER BY user_id LIMIT 1"
            )).scalar_one())
            connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
                    request_id,request_number,basis,reason_code,target_set_hash,
                    relationship_fingerprint,manifest_version,process_type,initiated_by_user_id
                ) VALUES(:id,:number,'LEGACY_MANIFEST','LEGACY_SYNTHETIC_TEST_DATA',
                    :digest,:digest,2,'APPLICANT_ONLY',:actor)"""), {
                    "id": request_id,
                    "number": f"TD-TOMB-DOWN-{request_id.hex[:12].upper()}",
                    "digest": "b" * 64,
                    "actor": admin_id,
                })
            connection.execute(text("""INSERT INTO public.test_personnel_deletion_record_event_tombstones(
                    request_id,source_event_id,event_type,source_occurred_at,
                    event_payload_digest,canonical_digest
                ) VALUES(:request_id,1,'PPR_CREATED',statement_timestamp(),:digest,:digest)"""), {
                    "request_id": request_id,
                    "digest": "c" * 64,
                })

        with pytest.raises(Exception, match="WP_TD_005_TOMBSTONES_PREVENT_DOWNGRADE"):
            command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == REVISION
            assert connection.execute(text("""SELECT COUNT(*)
                FROM public.test_personnel_deletion_record_event_tombstones
                WHERE request_id=:request_id"""), {
                    "request_id": request_id,
                }).scalar_one() == 1


def test_canonical_digest_is_deterministic_and_order_independent():
    first = {
        "event": {"b": [2, 1], "a": "значение"},
        "at": datetime(2026, 9, 5, 12, 30, tzinfo=timezone.utc),
    }
    second = {
        "at": datetime(
            2026, 9, 5, 18, 30, tzinfo=timezone(timedelta(hours=6))
        ),
        "event": {"a": "значение", "b": [2, 1]},
    }
    assert tombstones.canonical_digest(first) == (
        "364c965c94933b35a92ef5105ba276355efbfad36d4689d46286adbffd1d7942"
    )
    assert tombstones.canonical_digest(first) == tombstones.canonical_digest(second)
    assert tombstones.canonical_digest(first) != tombstones.canonical_digest({
        **first, "event": {"a": "другое", "b": [2, 1]},
    })


def test_capture_is_idempotent_pii_free_and_keeps_sources(tombstone_engine, tombstone_sources):
    with tombstone_engine.begin() as connection:
        first = _capture_all(connection, tombstone_sources)
        second = _capture_all(connection, tombstone_sources)
        assert {
            key: [row["canonical_digest"] for row in rows]
            for key, rows in first.items()
        } == {
            key: [row["canonical_digest"] for row in rows]
            for key, rows in second.items()
        }

    with tombstone_engine.connect() as connection:
        for table in TOMBSTONE_TABLES:
            assert connection.execute(text(f"SELECT COUNT(*) FROM public.{table} WHERE request_id=:id"), {
                "id": tombstone_sources["request_id"],
            }).scalar_one() == 1
        serialized = " ".join(
            str(connection.execute(text(f"SELECT row_to_json(t)::text FROM public.{table} t WHERE request_id=:id"), {
                "id": tombstone_sources["request_id"],
            }).scalar_one())
            for table in TOMBSTONE_TABLES
        ).lower()
        for forbidden in (
            "secret person", "secret applicant", "991231123456",
            "person@example.org", "+7 777 123 45 67", "raw-request",
        ):
            assert forbidden not in serialized
        assert connection.execute(text(
            "SELECT COUNT(*) FROM public.personnel_record_events WHERE event_id=:id"
        ), {"id": tombstone_sources["event_id"]}).scalar_one() == 1
        assert connection.execute(text(
            "SELECT COUNT(*) FROM public.ppr_command_executions WHERE command_id=:id"
        ), {"id": tombstone_sources["command_id"]}).scalar_one() == 1
        assert connection.execute(text(
            "SELECT COUNT(*) FROM public.personnel_application_lifecycle_audit WHERE audit_id=:id"
        ), {"id": tombstone_sources["lifecycle_id"]}).scalar_one() == 1


def test_tombstone_schema_has_only_request_foreign_keys_and_no_raw_columns(tombstone_engine):
    forbidden_columns = {
        "person_id", "application_id", "person_name", "full_name", "iin",
        "phone", "email", "contact", "event_payload", "request_payload",
        "result_payload", "comment", "metadata",
    }
    with tombstone_engine.connect() as connection:
        for table in TOMBSTONE_TABLES:
            columns = connection.execute(text("""SELECT column_name,data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:table
                ORDER BY ordinal_position"""), {"table": table}).all()
            assert columns
            assert all(str(name).lower() not in forbidden_columns for name, _data_type in columns)
            assert all(data_type not in {"json", "jsonb", "bytea"} for _name, data_type in columns)
            foreign_keys = connection.execute(text("""SELECT source.attname,target.relname
                FROM pg_constraint constraint_def
                JOIN pg_class table_def ON table_def.oid=constraint_def.conrelid
                JOIN pg_namespace namespace ON namespace.oid=table_def.relnamespace
                JOIN pg_class target ON target.oid=constraint_def.confrelid
                JOIN pg_attribute source ON source.attrelid=table_def.oid
                    AND source.attnum=constraint_def.conkey[1]
                WHERE namespace.nspname='public' AND table_def.relname=:table
                  AND constraint_def.contype='f'"""), {"table": table}).all()
            assert foreign_keys == [("request_id", "test_personnel_deletion_requests")]


def test_tombstones_are_append_only(tombstone_engine, tombstone_sources):
    with tombstone_engine.begin() as connection:
        _capture_all(connection, tombstone_sources)
    for table in TOMBSTONE_TABLES:
        for statement in (
            f"UPDATE public.{table} SET canonical_digest=canonical_digest WHERE request_id=:id",
            f"DELETE FROM public.{table} WHERE request_id=:id",
        ):
            with tombstone_engine.connect() as connection:
                transaction = connection.begin()
                try:
                    with pytest.raises(Exception, match="WP_TD_005_TOMBSTONE_APPEND_ONLY"):
                        connection.execute(text(statement), {"id": tombstone_sources["request_id"]})
                finally:
                    transaction.rollback()
        with tombstone_engine.connect() as connection:
            transaction = connection.begin()
            try:
                with pytest.raises(Exception, match="WP_TD_005_TOMBSTONE_APPEND_ONLY"):
                    connection.execute(text(f"TRUNCATE TABLE public.{table}"))
            finally:
                transaction.rollback()


def test_capture_rolls_back_as_one_caller_transaction(tombstone_engine, tombstone_sources):
    with tombstone_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(_TestPersonnelDeletionError) as error:
                tombstones.capture_tombstones(
                    connection,
                    request_id=tombstone_sources["request_id"],
                    record_event_ids=[tombstone_sources["event_id"]],
                    lifecycle_audit_ids=[999999999],
                )
            assert error.value.code == "TD_TOMBSTONE_SOURCE_NOT_IN_MANIFEST"
        finally:
            transaction.rollback()
    with tombstone_engine.connect() as connection:
        assert connection.execute(text("""SELECT COUNT(*)
            FROM public.test_personnel_deletion_record_event_tombstones
            WHERE request_id=:id"""), {"id": tombstone_sources["request_id"]}).scalar_one() == 0


def test_official_lifecycle_action_is_not_tombstoned(tombstone_engine, tombstone_sources):
    with tombstone_engine.begin() as connection:
        audit_id = int(connection.execute(text("""INSERT INTO public.personnel_application_lifecycle_audit(
                application_id,action,previous_status,new_status,actor_user_id,metadata
            ) VALUES(:application_id,'review_started','intake_submitted','under_review',
                :actor,'{}'::jsonb) RETURNING audit_id"""), {
                "application_id": tombstone_sources["application_id"],
                "actor": tombstone_sources["admin_id"],
            }).scalar_one())
        with pytest.raises(_TestPersonnelDeletionError) as error:
            tombstones.capture_lifecycle_tombstone(
                connection,
                request_id=tombstone_sources["request_id"],
                source_audit_id=audit_id,
            )
        assert error.value.code == "TD_TOMBSTONE_LIFECYCLE_ACTION_FORBIDDEN"

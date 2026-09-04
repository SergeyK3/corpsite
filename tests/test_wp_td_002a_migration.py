"""Alembic-chain and RBAC ownership tests for WP-TD-002A."""
from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.db.engine import engine
from app.services import test_personnel_deletion_service as deletion_service
from tests.db_guard import (
    PytestDatabaseGuardError,
    assert_connected_test_database,
    normalize_database_url,
    validate_test_database_url,
)

FOUNDATION_PREVIOUS = "x7y8z9a0b1c2"
PREVIOUS = "y8z9a0b1c2d3"
PROJECTION_PREVIOUS = "z9a0b1c2d3e4"
PERFORMANCE_PREVIOUS = "a0b1c2d3e4f5"
REVISION = "b1c2d3e4f5a6"

PERFORMANCE_INDEXES = {
    "ix_td002d_incoming_sender_person": ("incoming_documents", ("sender_person_id",)),
    "ix_td002d_incoming_sender_employee": ("incoming_documents", ("sender_employee_id",)),
    "ix_td002d_incoming_addressee_employee": ("incoming_documents", ("addressee_employee_id",)),
    "ix_td002d_incoming_addressee_user": ("incoming_documents", ("addressee_user_id",)),
    "ix_td002d_incoming_controller_user": ("incoming_documents", ("controller_user_id",)),
    "ix_td002d_incoming_created_by_user": ("incoming_documents", ("created_by_user_id",)),
    "ix_td002d_incoming_updated_by_user": ("incoming_documents", ("updated_by_user_id",)),
    "ix_td002d_incoming_closed_by_user": ("incoming_documents", ("closed_by_user_id",)),
    "ix_td002d_incoming_cancelled_by_user": ("incoming_documents", ("cancelled_by_user_id",)),
    "ix_td002d_incoming_transferred_by_user": ("incoming_documents", ("transferred_by_user_id",)),
    "ix_td002d_incoming_external_recipient_user": ("incoming_documents", ("external_recipient_user_id",)),
    "ix_td002d_employees_import_stage_employee": ("employees_import_stage", ("employee_id",)),
    "ix_td002d_hr_import_rows_employee": ("hr_import_rows", ("employee_id",)),
    "ix_td002d_hr_baseline_entries_employee": ("hr_baseline_entries", ("employee_id",)),
    "ix_td002d_hr_monthly_reference_entries_employee": ("hr_monthly_reference_entries", ("employee_id",)),
    "ix_td002d_personnel_migration_runs_person": ("personnel_migration_runs", ("person_id",)),
    "ix_td002d_personnel_migration_runs_employee_context": ("personnel_migration_runs", ("employee_context_id",)),
    "ix_td002d_persons_merged_into": ("persons", ("merged_into_person_id",)),
    "ix_td002d_personnel_orders_signatory": ("personnel_orders", ("signed_by_employee_id",)),
    "ix_td002d_operational_signing_actor": ("operational_order_signing_attestations", ("actor_employee_id",)),
    "ix_td002d_personnel_order_item_bases_subject": ("personnel_order_item_bases", ("subject_employee_id",)),
    "ix_td002d_onboarding_notifications_onboarding": ("employee_onboarding_notifications", ("onboarding_id",)),
    "ix_td002d_onboarding_task_audit_onboarding": ("employee_onboarding_task_audit", ("onboarding_id",)),
    "ix_td002d_termination_audit_record": ("employee_termination_record_audit", ("termination_record_id",)),
    "ix_td002d_user_linkage_decisions_employee": ("user_linkage_review_decisions", ("proposed_employee_id",)),
    "ix_td002d_access_grants_target_all": ("access_grants", ("target_type", "target_id")),
    "ix_td002d_visibility_target_user_all": ("personnel_visibility_assignments", ("target_user_id",)),
}

PERFORMANCE_INDEX_RULES = {
    "ix_td002d_incoming_sender_person": ("INCOMING_DOCUMENT_PRESENT",),
    "ix_td002d_incoming_sender_employee": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_addressee_employee": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_addressee_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_controller_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_created_by_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_updated_by_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_closed_by_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_cancelled_by_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_transferred_by_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_incoming_external_recipient_user": ("INCOMING_DOCUMENT_PARTICIPATION_PRESENT",),
    "ix_td002d_employees_import_stage_employee": ("LEGACY_IMPORT_STAGE_RETAINED",),
    "ix_td002d_hr_import_rows_employee": ("HR_IMPORT_ROW_RETAINED",),
    "ix_td002d_hr_baseline_entries_employee": ("HR_BASELINE_ENTRY_RETAINED",),
    "ix_td002d_hr_monthly_reference_entries_employee": ("HR_MONTHLY_REFERENCE_ENTRY_RETAINED",),
    "ix_td002d_personnel_migration_runs_person": ("PERSONNEL_MIGRATION_RUN_PRESENT",),
    "ix_td002d_personnel_migration_runs_employee_context": ("PERSONNEL_MIGRATION_RUN_PRESENT",),
    "ix_td002d_persons_merged_into": ("MERGED_PERSON_REFERENCE_PRESENT",),
    "ix_td002d_personnel_orders_signatory": ("PERSONNEL_ORDER_SIGNATORY_PRESENT",),
    "ix_td002d_operational_signing_actor": ("OPERATIONAL_ORDER_SIGNING_PRESENT",),
    "ix_td002d_personnel_order_item_bases_subject": ("PERSONNEL_ORDER_ITEM_BASIS_PRESENT",),
    "ix_td002d_onboarding_notifications_onboarding": ("ONBOARDING_NOTIFICATION_PRESENT",),
    "ix_td002d_onboarding_task_audit_onboarding": ("ONBOARDING_TASK_AUDIT_PRESENT",),
    "ix_td002d_termination_audit_record": ("TERMINATION_AUDIT_RETAINED",),
    "ix_td002d_user_linkage_decisions_employee": ("USER_LINKAGE_REVIEW_DECISION_PRESENT",),
    "ix_td002d_access_grants_target_all": ("ACCESS_GRANT_RETAINED",),
    "ix_td002d_visibility_target_user_all": ("PERSONNEL_VISIBILITY_RETAINED",),
}


def test_performance_index_catalog_contract_matches_matrix_predicates():
    rules = {rule.code: rule for rule in deletion_service.RELATIONSHIP_MATRIX}
    assert PERFORMANCE_INDEX_RULES.keys() == PERFORMANCE_INDEXES.keys()
    for index_name, rule_codes in PERFORMANCE_INDEX_RULES.items():
        _table, columns = PERFORMANCE_INDEXES[index_name]
        rule_sql = "\n".join(rules[code].sql for code in rule_codes)
        assert all(f".{column}" in rule_sql for column in columns)


@contextmanager
def _ephemeral_database():
    name = f"corpsite_td002b_migration_{uuid4().hex[:10]}_test"
    source_url = engine.url.render_as_string(hide_password=False)
    main_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not main_url:
        raise PytestDatabaseGuardError("DATABASE_URL is required for main-target comparison.")
    base_url = make_url(source_url)
    admin_url = base_url.set(database="postgres").render_as_string(hide_password=False)
    url = base_url.set(database=name).render_as_string(hide_password=False)
    target = validate_test_database_url(
        test_database_url=url,
        app_database_url=main_url,
    )
    if target.identity_key() == normalize_database_url(source_url).identity_key():
        raise PytestDatabaseGuardError("Ephemeral target must differ from its template database.")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = create_engine(url)
    template_name = str(base_url.database)
    assert template_name.replace("_", "").isalnum()
    # The pytest guard opened the template once to verify current_database().
    # Dispose that pool before PostgreSQL takes its consistent template copy.
    engine.dispose()
    with admin.connect() as conn:
        assert str(conn.execute(text("SELECT current_database()" )).scalar_one()).lower() == "postgres"
        conn.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{template_name}"'))
    try:
        with test_engine.connect() as conn:
            assert_connected_test_database(conn, target)
        # The shared test template may legitimately lag behind this work
        # package.  Bring only the disposable clone to the revision under test
        # before exercising downgrade/upgrade ownership behavior.
        command.upgrade(_config(url), REVISION)
        yield url, test_engine
    finally:
        test_engine.dispose()
        with admin.connect() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()"), {"name": name})
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


def _config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def test_explicit_alembic_url_wins_over_process_database_url(monkeypatch):
    with _ephemeral_database() as (url, db):
        monkeypatch.setenv("DATABASE_URL", "postgresql://invalid:invalid@203.0.113.1:1/corpsite")
        command.downgrade(_config(url), PREVIOUS)
        with db.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS


def test_explicit_alembic_url_wins_when_process_url_is_main_database(monkeypatch):
    main_url = os.environ["DATABASE_URL"]
    with _ephemeral_database() as (url, db):
        monkeypatch.setenv("DATABASE_URL", main_url)
        command.downgrade(_config(url), PREVIOUS)
        with db.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS


def test_missing_explicit_alembic_url_uses_process_database_url(monkeypatch):
    with _ephemeral_database() as (url, db):
        monkeypatch.setenv("DATABASE_URL", url)
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", "")
        command.downgrade(cfg, PREVIOUS)
        with db.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
        "postgresql://postgres:postgres@db.internal:5432/corpsite_test",
        "postgresql://postgres:postgres@127.0.0.1:5432/corpsite_staging",
    ],
)
def test_ephemeral_url_guard_rejects_unsafe_targets(url):
    with pytest.raises(PytestDatabaseGuardError):
        validate_test_database_url(
            test_database_url=url,
            app_database_url="postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
        )


def test_connected_database_guard_rejects_mismatch():
    class WrongConnection:
        def execute(self, _statement):
            class Result:
                @staticmethod
                def scalar_one():
                    return "corpsite"
            return Result()

    expected = validate_test_database_url(
        test_database_url="postgresql://postgres:postgres@127.0.0.1:5432/corpsite_td002b_test",
        app_database_url="postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
    )
    with pytest.raises(PytestDatabaseGuardError, match="does not match"):
        assert_connected_test_database(WrongConnection(), expected)


def test_real_alembic_chain_and_append_only_guards():
    with _ephemeral_database() as (url, db):
        cfg = _config(url)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, REVISION)
        with db.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert conn.execute(text("SELECT to_regclass('public.test_personnel_deletion_history')")).scalar_one()
        command.downgrade(cfg, PREVIOUS)
        with db.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
            assert conn.execute(text("SELECT to_regclass('public.test_personnel_deletion_history')")).scalar_one()
            assert not conn.execute(text("""SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='test_personnel_deletion_history'
                  AND column_name='result_projection')""")).scalar_one()


def test_wp_td_full_chain_x_y_z_a_b_a_b():
    with _ephemeral_database() as (url, db):
        cfg = _config(url)
        for direction, revision in (
            (command.downgrade, FOUNDATION_PREVIOUS),
            (command.upgrade, PREVIOUS),
            (command.upgrade, PROJECTION_PREVIOUS),
            (command.upgrade, PERFORMANCE_PREVIOUS),
            (command.upgrade, REVISION),
            (command.downgrade, PERFORMANCE_PREVIOUS),
            (command.upgrade, REVISION),
        ):
            direction(cfg, revision)
            with db.connect() as conn:
                assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == revision


def _catalog_index_columns(conn, index_name):
    row = conn.execute(text("""SELECT table_rel.relname AS table_name,
            array_agg(attribute.attname ORDER BY key_column.ordinality) AS columns
        FROM pg_class index_rel
        JOIN pg_index index_def ON index_def.indexrelid=index_rel.oid
        JOIN pg_class table_rel ON table_rel.oid=index_def.indrelid
        JOIN unnest(index_def.indkey) WITH ORDINALITY key_column(attnum, ordinality) ON TRUE
        JOIN pg_attribute attribute
          ON attribute.attrelid=table_rel.oid AND attribute.attnum=key_column.attnum
        JOIN pg_namespace namespace ON namespace.oid=table_rel.relnamespace
        WHERE namespace.nspname='public' AND index_rel.relname=:name
        GROUP BY table_rel.relname"""), {"name": index_name}).one_or_none()
    return None if row is None else (str(row.table_name), tuple(row.columns))


def _catalog_index_is_partial(conn, index_name):
    return conn.execute(text("""SELECT index_def.indpred IS NOT NULL
        FROM pg_index index_def
        JOIN pg_class index_rel ON index_rel.oid=index_def.indexrelid
        JOIN pg_namespace namespace ON namespace.oid=index_rel.relnamespace
        WHERE namespace.nspname='public' AND index_rel.relname=:name"""), {
        "name": index_name,
    }).scalar_one_or_none()


def test_wp_td_002d_index_catalog_upgrade_downgrade_and_column_order():
    with _ephemeral_database() as (url, db):
        cfg = _config(url)
        with db.connect() as conn:
            assert {
                name: _catalog_index_columns(conn, name)
                for name in PERFORMANCE_INDEXES
            } == PERFORMANCE_INDEXES
            # These rules intentionally include inactive retained rows, so the
            # pre-existing active-only partial indexes are not substitutes.
            assert _catalog_index_is_partial(conn, "ix_ag_target") is True
            assert _catalog_index_is_partial(conn, "ix_pva_active_target_user") is True
            assert _catalog_index_is_partial(conn, "ix_td002d_access_grants_target_all") is False
            assert _catalog_index_is_partial(conn, "ix_td002d_visibility_target_user_all") is False

        command.downgrade(cfg, PERFORMANCE_PREVIOUS)
        with db.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PERFORMANCE_PREVIOUS
            assert all(_catalog_index_columns(conn, name) is None for name in PERFORMANCE_INDEXES)

        command.upgrade(cfg, REVISION)
        with db.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert {
                name: _catalog_index_columns(conn, name)
                for name in PERFORMANCE_INDEXES
            } == PERFORMANCE_INDEXES


@pytest.mark.parametrize("projection", [
    {"iin": "990101123456"},
    {"target": {"profile": {"phone": "+7 777 123 45 67"}}},
    {"targets": [{"identity": {"email": "person@example.org"}}]},
    {"history": [{"actor": {"full_name": "Sensitive Name"}}]},
    {"target": {"identity": {"mobile_phone": "+7 777 123 45 67"}}},
    {"target": {"identity": {"date_of_birth": "1990-01-01"}}},
    {"target": {"identity": {"masked_iin": "********3456"}}},
])
def test_result_projection_rejects_forbidden_keys_at_any_depth(projection):
    import json

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            request_id = _seed_projection_history(conn)
            with pytest.raises(Exception, match="ck_tpdh_result_projection"):
                conn.execute(text("""INSERT INTO test_personnel_deletion_history(
                    request_id,actor_user_id,actor_role_code,permission_code,action,
                    old_status,new_status,old_version,new_version,target_set_hash,
                    idempotency_key,command_payload_hash,result_code,result_projection)
                    SELECT request_id,actor_user_id,actor_role_code,permission_code,'CANCEL',
                           new_status,'CANCELLED',new_version,new_version+1,target_set_hash,
                           :key,command_payload_hash,'TD_CANCELLED',CAST(:projection AS jsonb)
                    FROM test_personnel_deletion_history WHERE request_id=:request_id
                    ORDER BY history_id LIMIT 1"""), {
                    "request_id": request_id, "key": f"nested-pii-{uuid4()}", "projection": json.dumps(projection),
                })
        finally:
            transaction.rollback()


def test_result_projection_accepts_safe_nested_projection():
    import json

    safe = {"targets": [{"person_id": 1, "codes": ["BLOCK"]}], "result_code": "TD_TEST"}
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            request_id = _seed_projection_history(conn)
            inserted = conn.execute(text("""INSERT INTO test_personnel_deletion_history(
                request_id,actor_user_id,actor_role_code,permission_code,action,
                old_status,new_status,old_version,new_version,target_set_hash,
                idempotency_key,command_payload_hash,result_code,result_projection)
                SELECT request_id,actor_user_id,actor_role_code,permission_code,'CANCEL',
                       new_status,'CANCELLED',new_version,new_version+1,target_set_hash,
                       :key,command_payload_hash,'TD_CANCELLED',CAST(:projection AS jsonb)
                FROM test_personnel_deletion_history WHERE request_id=:request_id
                ORDER BY history_id LIMIT 1
                RETURNING history_id"""), {
                "request_id": request_id, "key": f"safe-projection-{uuid4()}", "projection": json.dumps(safe),
            }).scalar_one()
            assert inserted > 0
        finally:
            transaction.rollback()


def _seed_projection_history(conn):
    request_id = uuid4()
    digest = "a" * 64
    conn.execute(text("""INSERT INTO test_personnel_deletion_requests(
        request_id,request_number,basis,reason_code,target_set_hash,
        relationship_fingerprint,initiated_by_user_id)
        VALUES(:id,:number,'LEGACY_MANIFEST','LEGACY_SYNTHETIC_TEST_DATA',:digest,:digest,1)"""), {
        "id": request_id, "number": f"TD-PROJECTION-{request_id.hex[:12]}", "digest": digest,
    })
    conn.execute(text("""INSERT INTO test_personnel_deletion_history(
        request_id,actor_user_id,actor_role_code,permission_code,action,new_status,
        new_version,target_set_hash,idempotency_key,command_payload_hash,result_code,result_projection)
        VALUES(:id,1,'ADMIN','TEST_PERSONNEL_DELETION_REQUEST','CREATE','DRAFT',1,
               :digest,:key,:digest,'TD_DRAFT_CREATED',CAST(:projection AS jsonb))"""), {
        "id": request_id, "digest": digest, "key": f"seed-{request_id}",
        "projection": '{"request_id":"safe","status":"DRAFT"}',
    })
    return request_id


def test_upgrade_fails_closed_without_claiming_preexisting_permission():
    with _ephemeral_database() as (url, db):
        cfg = _config(url)
        command.downgrade(cfg, FOUNDATION_PREVIOUS)
        with db.begin() as conn:
            conn.execute(text("""INSERT INTO access_roles(code,name,description,access_level,level_rank,is_system)
                VALUES('TEST_PERSONNEL_DELETION_REQUEST','preexisting','owned elsewhere','MANAGER',20,TRUE)"""))
        with pytest.raises(Exception, match="WP_TD_002_PERMISSION_CODE_CONFLICT"):
            command.upgrade(cfg, PREVIOUS)
        with db.connect() as conn:
            row = conn.execute(text("SELECT name,description FROM access_roles WHERE code='TEST_PERSONNEL_DELETION_REQUEST'")).one()
            assert tuple(row) == ("preexisting", "owned elsewhere")
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == FOUNDATION_PREVIOUS


def test_downgrade_fails_closed_when_external_grant_exists():
    with _ephemeral_database() as (url, db):
        cfg = _config(url)
        with db.begin() as conn:
            admin_user = conn.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
            grant_id = conn.execute(text("""INSERT INTO access_grants(access_role_id,target_type,target_id,granted_by_user_id,reason)
                SELECT access_role_id,'USER',:user_id,:user_id,'external grant' FROM access_roles
                WHERE code='TEST_PERSONNEL_DELETION_REQUEST' RETURNING grant_id"""), {"user_id": admin_user}).scalar_one()
        with pytest.raises(Exception, match="WP_TD_002_EXTERNAL_GRANTS_PRESENT"):
            command.downgrade(cfg, FOUNDATION_PREVIOUS)
        with db.begin() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert conn.execute(text("SELECT EXISTS(SELECT 1 FROM access_grants WHERE grant_id=:id)"), {"id": grant_id}).scalar_one()
            conn.execute(text("DELETE FROM access_grants WHERE grant_id=:id"), {"id": grant_id})
        command.downgrade(cfg, FOUNDATION_PREVIOUS)


def test_downgrade_fails_closed_for_external_grant_copying_owner_reason():
    with _ephemeral_database() as (url, db):
        cfg = _config(url)
        with db.begin() as conn:
            admin_user = conn.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
            grant_id = conn.execute(text("""INSERT INTO access_grants(
                    access_role_id,target_type,target_id,granted_by_user_id,reason)
                SELECT access_role_id,'USER',:user_id,:user_id,
                       'WP-TD-002A:y8z9a0b1c2d3:TEST_PERSONNEL_DELETION_REQUEST:ADMIN'
                FROM access_roles WHERE code='TEST_PERSONNEL_DELETION_REQUEST'
                RETURNING grant_id"""), {"user_id": admin_user}).scalar_one()
        with pytest.raises(Exception, match="WP_TD_002_EXTERNAL_GRANTS_PRESENT"):
            command.downgrade(cfg, FOUNDATION_PREVIOUS)
        with db.begin() as conn:
            assert conn.execute(text("SELECT EXISTS(SELECT 1 FROM access_grants WHERE grant_id=:id)"), {"id": grant_id}).scalar_one()
            conn.execute(text("DELETE FROM access_grants WHERE grant_id=:id"), {"id": grant_id})
        command.downgrade(cfg, FOUNDATION_PREVIOUS)

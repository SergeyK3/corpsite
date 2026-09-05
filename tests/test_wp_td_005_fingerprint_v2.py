"""WP-TD-005 stage 3 PostgreSQL tests for provenance/catalog fingerprints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.services import test_personnel_deletion_fingerprint_service as fingerprints
from app.services import test_personnel_deletion_service as service
from tests.test_wp_td_005_manifest_v2 import _alembic_config, _ephemeral_database


PREVIOUS_REVISION = "td005tomb201"
REVISION = "td005fp3v101"


@pytest.fixture(scope="module")
def fingerprint_engine():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        command.upgrade(_alembic_config(url), REVISION)
        yield clone_engine


@pytest.fixture(autouse=True)
def bind_service_engine(fingerprint_engine, monkeypatch):
    monkeypatch.setattr(service, "engine", fingerprint_engine)


@pytest.fixture
def applicant(fingerprint_engine):
    suffix = uuid.uuid4().hex[:12]
    with fingerprint_engine.begin() as connection:
        actors = {
            str(row["code"]): int(row["user_id"])
            for row in connection.execute(text("""SELECT DISTINCT ON (role.code)
                    role.code,users.user_id
                FROM public.users users JOIN public.roles role ON role.role_id=users.role_id
                WHERE role.code IN ('ADMIN','HR_HEAD') AND users.is_active=TRUE
                ORDER BY role.code,users.user_id""")).mappings()
        }
        assert set(actors) == {"ADMIN", "HR_HEAD"}
        person_id = int(connection.execute(text("""INSERT INTO public.persons(
                full_name,match_key,source
            ) VALUES(:name,:key,'manual') RETURNING person_id"""), {
                "name": f"WP TD 005 Fingerprint {suffix}",
                "key": f"wp-td-005-fingerprint-{suffix}",
            }).scalar_one())
        application_id = int(connection.execute(text("""INSERT INTO public.personnel_applications(
                person_id,status,application_received_at,registered_by_user_id,idempotency_key
            ) VALUES(:person_id,'intake_pending',CURRENT_DATE,:actor,:key)
            RETURNING application_id"""), {
                "person_id": person_id,
                "actor": actors["ADMIN"],
                "key": f"wp-td-005-fingerprint-app-{suffix}",
            }).scalar_one())
    return {
        "suffix": suffix,
        "person_id": person_id,
        "application_id": application_id,
        "actors": actors,
    }


def _candidates(connection, applicant):
    return service._evaluate_candidates(connection, [
        (applicant["person_id"], applicant["application_id"]),
    ])


def _append_provenance(connection, applicant, *, version, state="ACTIVE", artifact="a"):
    return int(connection.execute(text("""INSERT INTO public.test_personnel_provenance(
            target_type,target_id,environment,test_run_id,creation_source,purpose,
            created_by_user_id,source_artifact_hash,provenance_version,provenance_state
        ) VALUES('PERSON',:person_id,'dev',:run,'pytest','stage-3 regression',
            :actor,:artifact,:version,:state) RETURNING provenance_id"""), {
            "person_id": applicant["person_id"],
            "run": f"wp-td-005-stage3-{applicant['suffix']}-{version}",
            "actor": applicant["actors"]["ADMIN"],
            "artifact": artifact * 64,
            "version": version,
            "state": state,
        }).scalar_one())


def test_alembic_has_single_fingerprint_head():
    assert ScriptDirectory.from_config(_alembic_config()).get_heads() == [REVISION]


def test_fingerprint_migration_upgrade_downgrade_upgrade():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == REVISION
            assert connection.execute(text("""SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema='public' AND table_name='test_personnel_provenance'
                  AND column_name='provenance_state'""")).scalar_one() == 1
            assert connection.execute(text("""SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema='public' AND table_name='test_personnel_deletion_requests'
                  AND column_name='fingerprint_version'""")).scalar_one() == 1
        command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == PREVIOUS_REVISION
            assert connection.execute(text("""SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema='public' AND table_name='test_personnel_provenance'
                  AND column_name='provenance_state'""")).scalar_one() == 0
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == REVISION


def test_canonical_fingerprint_vector_is_deterministic():
    first = {
        "z": [2, 1],
        "at": datetime(2026, 9, 5, 12, 30, tzinfo=timezone.utc),
        "nested": {"b": False, "a": "значение"},
    }
    second = {
        "nested": {"a": "значение", "b": False},
        "at": datetime(2026, 9, 5, 18, 30, tzinfo=timezone(timedelta(hours=6))),
        "z": [2, 1],
    }
    assert fingerprints.canonical_hash(first) == fingerprints.canonical_hash(second)
    assert fingerprints.canonical_hash(first) == (
        "825bb19a77bbcc50d5e1b3157b11aebcd2fb4b278fa34c52602f87973ceb695c"
    )


def test_catalog_is_deterministic_and_compatible(fingerprint_engine):
    with fingerprint_engine.connect() as connection:
        first = fingerprints.catalog_state(connection, service.RELATIONSHIP_MATRIX)
        second = fingerprints.catalog_state(connection, service.RELATIONSHIP_MATRIX)
    assert first == second
    assert first == {
        "version": fingerprints.CATALOG_VERSION,
        "fingerprint": fingerprints.EXPECTED_CATALOG_FINGERPRINT,
        "compatible": True,
        "revision_compatible": True,
        "missing_tables": [],
    }


@pytest.mark.parametrize("drift_sql", [
    "ALTER TABLE public.persons ADD COLUMN wp_td_005_unknown TEXT",
    "CREATE TABLE public.wp_td_005_unknown_satellite(person_id BIGINT)",
    "DROP TRIGGER trg_test_personnel_provenance_truncate_guard ON public.test_personnel_provenance",
])
def test_catalog_schema_drift_fails_closed(fingerprint_engine, drift_sql):
    with fingerprint_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(drift_sql))
            with pytest.raises(fingerprints.FingerprintGateError) as error:
                fingerprints.catalog_state(connection, service.RELATIONSHIP_MATRIX)
            assert error.value.code == "TD_CATALOG_MISMATCH"
        finally:
            transaction.rollback()


def test_catalog_fk_and_trigger_function_drift_fail_closed(fingerprint_engine):
    with fingerprint_engine.connect() as connection:
        transaction = connection.begin()
        try:
            constraint_name = connection.execute(text("""SELECT constraint_def.conname
                FROM pg_catalog.pg_constraint constraint_def
                JOIN pg_catalog.pg_class source ON source.oid=constraint_def.conrelid
                JOIN pg_catalog.pg_class target ON target.oid=constraint_def.confrelid
                WHERE constraint_def.contype='f'
                  AND source.relname='personnel_applications'
                  AND target.relname='persons'""")).scalar_one()
            connection.execute(text(
                f'ALTER TABLE public.personnel_applications DROP CONSTRAINT "{constraint_name}"'
            ))
            with pytest.raises(fingerprints.FingerprintGateError, match="allowlisted"):
                fingerprints.catalog_state(connection, service.RELATIONSHIP_MATRIX)
        finally:
            transaction.rollback()

    with fingerprint_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("""CREATE OR REPLACE FUNCTION public.td002_reject_mutation()
                RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END; $$"""))
            with pytest.raises(fingerprints.FingerprintGateError, match="allowlisted"):
                fingerprints.catalog_state(connection, service.RELATIONSHIP_MATRIX)
        finally:
            transaction.rollback()


def test_unknown_alembic_revision_fails_closed(fingerprint_engine):
    with fingerprint_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(
                "UPDATE public.alembic_version SET version_num='unknownschema'"
            ))
            state = fingerprints.catalog_state(
                connection, service.RELATIONSHIP_MATRIX, enforce=False,
            )
            assert state["revision_compatible"] is False
            assert state["compatible"] is False
            with pytest.raises(fingerprints.FingerprintGateError) as error:
                fingerprints.catalog_state(connection, service.RELATIONSHIP_MATRIX)
            assert error.value.code == "TD_CATALOG_MISMATCH"
        finally:
            transaction.rollback()


def test_unknown_or_missing_relationship_rule_fails_closed(fingerprint_engine):
    with fingerprint_engine.connect() as connection:
        with pytest.raises(fingerprints.FingerprintGateError) as error:
            fingerprints.catalog_state(connection, service.RELATIONSHIP_MATRIX[:-1])
    assert error.value.code == "TD_RELATIONSHIP_REGISTRY_MISMATCH"


def test_person_provenance_missing_revoked_and_changed_changes_fingerprint(
    fingerprint_engine, applicant,
):
    with fingerprint_engine.begin() as connection:
        missing = fingerprints.build_fingerprint(
            connection, candidates=_candidates(connection, applicant), basis="PROVENANCE",
            rules=service.RELATIONSHIP_MATRIX,
        )
        assert "ACTIVE_PERSON_PROVENANCE_REQUIRED" in missing["blockers"]
        _append_provenance(connection, applicant, version=1, artifact="a")
        active = fingerprints.build_fingerprint(
            connection, candidates=_candidates(connection, applicant), basis="PROVENANCE",
            rules=service.RELATIONSHIP_MATRIX,
        )
        assert "ACTIVE_PERSON_PROVENANCE_REQUIRED" not in active["blockers"]
        _append_provenance(connection, applicant, version=2, state="REVOKED", artifact="a")
        revoked = fingerprints.build_fingerprint(
            connection, candidates=_candidates(connection, applicant), basis="PROVENANCE",
            rules=service.RELATIONSHIP_MATRIX,
        )
        assert "ACTIVE_PERSON_PROVENANCE_REQUIRED" in revoked["blockers"]
        _append_provenance(connection, applicant, version=3, artifact="b")
        changed = fingerprints.build_fingerprint(
            connection, candidates=_candidates(connection, applicant), basis="PROVENANCE",
            rules=service.RELATIONSHIP_MATRIX,
        )
    assert len({missing["fingerprint"], active["fingerprint"], revoked["fingerprint"], changed["fingerprint"]}) == 4
    assert changed["provenance"][0]["source_artifact_hash"] == "b" * 64


def test_provenance_is_append_only_and_version_monotonic(fingerprint_engine, applicant):
    with fingerprint_engine.begin() as connection:
        provenance_id = _append_provenance(connection, applicant, version=1)
    statements = (
        ("UPDATE public.test_personnel_provenance SET purpose='changed' WHERE provenance_id=:id", {"id": provenance_id}, "WP_TD_002_APPEND_ONLY"),
        ("DELETE FROM public.test_personnel_provenance WHERE provenance_id=:id", {"id": provenance_id}, "WP_TD_002_APPEND_ONLY"),
        ("TRUNCATE public.test_personnel_provenance", {}, "WP_TD_002_APPEND_ONLY"),
        ("""INSERT INTO public.test_personnel_provenance(target_type,target_id,environment,
                test_run_id,creation_source,purpose,created_by_user_id,source_artifact_hash,
                provenance_version,provenance_state)
            SELECT target_type,target_id,environment,'duplicate','pytest','duplicate',
                created_by_user_id,source_artifact_hash,provenance_version,'ACTIVE'
            FROM public.test_personnel_provenance WHERE provenance_id=:id""", {"id": provenance_id}, "WP_TD_005_PROVENANCE_VERSION_NOT_MONOTONIC"),
    )
    for statement, params, marker in statements:
        with fingerprint_engine.connect() as connection:
            transaction = connection.begin()
            try:
                with pytest.raises(Exception, match=marker):
                    connection.execute(text(statement), params)
            finally:
                transaction.rollback()


def test_legacy_manifest_and_old_fingerprint_are_analysis_only(fingerprint_engine, applicant):
    request_id = uuid.uuid4()
    with fingerprint_engine.begin() as connection:
        connection.execute(text("""INSERT INTO public.test_personnel_deletion_requests(
                request_id,request_number,basis,reason_code,target_set_hash,
                relationship_fingerprint,manifest_version,process_type,initiated_by_user_id
            ) VALUES(:id,:number,'LEGACY_MANIFEST','LEGACY_SYNTHETIC_TEST_DATA',
                :digest,:digest,2,'APPLICANT_ONLY',:actor)"""), {
                "id": request_id,
                "number": f"TD-FP-OLD-{request_id.hex[:12].upper()}",
                "digest": "d" * 64,
                "actor": applicant["actors"]["ADMIN"],
            })
        row = service._effective(service._request_row(connection, request_id))
    assert row["manifest_read_only"] is False
    assert row["fingerprint_read_only"] is True
    assert row["execution_eligible"] is False
    assert row["execution_block_code"] == "TD_FINGERPRINT_VERSION_OBSOLETE"


def test_satellite_security_and_legacy_rules_are_explicit_and_fail_closed():
    contract = {rule.code: rule for rule in service.RELATIONSHIP_MATRIX}
    expected = {
        "PERSONNEL_ORDER_ITEM_EDITORIAL_BLOCK_PRESENT",
        "ONBOARDING_NOTIFICATION_RECIPIENT_PRESENT",
        "ONBOARDING_NOTIFICATION_DELIVERY_PRESENT",
        "PERSONNEL_MIGRATION_ITEM_PRESENT",
        "SECURITY_AUDIT_EMPLOYEE_RETAINED",
        "TASK_USER_SATELLITE_PRESENT",
        "TASK_REPORT_USER_SATELLITE_PRESENT",
        "TASK_EVENT_RECIPIENT_USER_SATELLITE_PRESENT",
        "USER_SUPERVISOR_RELATION_PRESENT",
        "PERSON_ROOT_NOT_ELIGIBLE",
        "LEGACY_PERSONNEL_PRESENT", "CONTACT_PRESENT", "KEY_CONTACT_PRESENT",
        "ACCESS_GRANT_RETAINED",
    }
    assert expected <= set(contract)
    assert contract["ACCESS_GRANT_RETAINED"].category == service.BLOCK
    registry = fingerprints._rule_registry(service.RELATIONSHIP_MATRIX)
    actions = {item["code"]: item["action"] for item in registry}
    assert actions["ACCESS_GRANT_RETAINED"] == "BLOCK"
    assert actions["SECURITY_AUDIT_EMPLOYEE_RETAINED"] == "PRESERVE"
    assert actions["INTAKE_DRAFT_PRESENT"] == "DELETE"


def test_data_or_provenance_change_after_approval_requires_reapproval(
    fingerprint_engine, applicant, monkeypatch,
):
    with fingerprint_engine.begin() as connection:
        _append_provenance(connection, applicant, version=1)
    draft = service.create_draft(
        actor_user_id=applicant["actors"]["ADMIN"], basis="PROVENANCE",
        reason_code="PROVENANCE_TEST_RUN_CLEANUP",
        preview_criteria={"selection": "EXACT_MANIFEST"}, original_mask=None,
        targets=[{
            "person_id": applicant["person_id"],
            "application_id": applicant["application_id"],
        }],
        idempotency_key=f"stage3-create-{applicant['suffix']}",
    )
    submitted, conflict = service.submit_request(
        request_id=draft["request_id"], actor_user_id=applicant["actors"]["ADMIN"],
        expected_version=1, idempotency_key=f"stage3-submit-{applicant['suffix']}",
    )
    assert conflict is None
    approved, conflict = service.decide_request(
        request_id=draft["request_id"], actor_user_id=applicant["actors"]["HR_HEAD"],
        expected_version=submitted["version"], decision="APPROVE",
        idempotency_key=f"stage3-approve-{applicant['suffix']}", comment=None,
        submitted_synthetic_confirmed=False,
    )
    assert conflict is None
    with fingerprint_engine.begin() as connection:
        before = service._assess_future_execution_readiness(connection, draft["request_id"])
        _append_provenance(connection, applicant, version=2, artifact="b")
        after_provenance = service._assess_future_execution_readiness(connection, draft["request_id"])
        connection.execute(text("""UPDATE public.personnel_applications
            SET updated_at=updated_at+interval '1 second' WHERE application_id=:id"""), {
                "id": applicant["application_id"],
            })
        after_data = service._assess_future_execution_readiness(connection, draft["request_id"])
        monkeypatch.setattr(fingerprints, "POLICY_VERSION", "WP-TD-005-APPLICANT/drift")
        after_policy = service._assess_future_execution_readiness(connection, draft["request_id"])
    assert before["approval_revalidation_required"] is False
    assert before["execution_available"] is False
    assert after_provenance["approval_revalidation_required"] is True
    assert "TD_REAPPROVAL_REQUIRED" in after_provenance["blockers"]
    assert after_data["current_fingerprint"] != after_provenance["current_fingerprint"]
    assert "TD_REAPPROVAL_REQUIRED" in after_policy["blockers"]
    assert approved["status"] == "APPROVED"

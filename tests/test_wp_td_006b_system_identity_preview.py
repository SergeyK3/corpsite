"""PostgreSQL 16 regressions for WP-TD-006B read-only search and preview."""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.main import app
from app.security import admin_permissions
from app.services import access_resolver_service
from app.services import test_system_identity_preview_service as service
from tests.test_wp_td_005_manifest_v2 import _alembic_config, _ephemeral_database


REVISION = "td006afnd601"


@pytest.fixture(scope="module")
def preview_engine():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        command.upgrade(_alembic_config(url), REVISION)
        with clone_engine.connect() as connection:
            version = int(connection.execute(text("SHOW server_version_num")).scalar_one())
            assert 160000 <= version < 170000
        yield clone_engine


@pytest.fixture(autouse=True)
def bind_engines(preview_engine, monkeypatch):
    monkeypatch.setattr(service, "engine", preview_engine)
    monkeypatch.setattr(admin_permissions, "engine", preview_engine)
    monkeypatch.setattr(access_resolver_service, "engine", preview_engine)


@pytest.fixture(scope="module")
def seed(preview_engine):
    with preview_engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE public.roles ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
        ))
        actors = {
            str(row["code"]): int(row["user_id"])
            for row in connection.execute(text("""SELECT DISTINCT ON (role.code)
                    role.code,users.user_id
                FROM public.users users JOIN public.roles role USING(role_id)
                WHERE role.code IN ('ADMIN','HR_HEAD') AND users.is_active=TRUE
                ORDER BY role.code,users.user_id""")).mappings()
        }
        roles = {}
        for code, is_active in (
            ("TD006B_UNUSED", False),
            ("TD006B_SHARED", False),
            ("TD006B_ACTIVE", True),
        ):
            roles[code] = int(connection.execute(text("""INSERT INTO public.roles(
                    role_id,name,code,is_active) VALUES(
                    (SELECT coalesce(max(role_id),0)+1 FROM public.roles),:name,:code,:is_active)
                    RETURNING role_id"""), {
                    "name": f"WP TD 006B {code}", "code": code, "is_active": is_active,
                }).scalar_one())
        ready_user = int(connection.execute(text("""INSERT INTO public.users(
                user_id,full_name,role_id,is_active,login)
            VALUES((SELECT max(user_id)+1 FROM public.users),
                'WP TD 006B Ready User',:role_id,FALSE,'td006b.ready')
            RETURNING user_id"""), {"role_id": roles["TD006B_SHARED"]}).scalar_one())
        shared_user = int(connection.execute(text("""INSERT INTO public.users(
                user_id,full_name,role_id,is_active,login)
            VALUES((SELECT max(user_id)+1 FROM public.users),
                'WP TD 006B Shared User',:role_id,FALSE,'td006b.shared')
            RETURNING user_id"""), {"role_id": roles["TD006B_SHARED"]}).scalar_one())
        person_id = int(connection.execute(text("""INSERT INTO public.persons(
                full_name,match_key,source)
            VALUES('WP TD 006B Employee Person','td006b-employee-person','manual')
            RETURNING person_id""")).scalar_one())
        employee_id = int(connection.execute(text("""INSERT INTO public.employees(
                full_name,person_id,is_active)
            VALUES('WP TD 006B Employee',:person_id,TRUE) RETURNING employee_id"""), {
                "person_id": person_id,
            }).scalar_one())
        employee_user = int(connection.execute(text("""INSERT INTO public.users(
                user_id,full_name,role_id,is_active,login,employee_id)
            VALUES((SELECT max(user_id)+1 FROM public.users),
                'WP TD 006B Employee User',:role_id,FALSE,'td006b.employee',:employee_id)
            RETURNING user_id"""), {
                "role_id": roles["TD006B_SHARED"], "employee_id": employee_id,
            }).scalar_one())
        admin_role_id = int(connection.execute(text(
            "SELECT role_id FROM public.roles WHERE code='ADMIN'"
        )).scalar_one())
        provenance = (
            ("USER", ready_user, ready_user, "a"),
            ("USER", shared_user, actors["ADMIN"], "b"),
            ("USER", employee_user, actors["ADMIN"], "c"),
            ("ROLE", roles["TD006B_UNUSED"], actors["ADMIN"], "d"),
            ("ROLE", roles["TD006B_SHARED"], actors["ADMIN"], "e"),
            ("ROLE", admin_role_id, actors["ADMIN"], "f"),
            ("ROLE", roles["TD006B_ACTIVE"], actors["ADMIN"], "1"),
        )
        for object_type, object_id, creator, marker in provenance:
            connection.execute(text("""INSERT INTO public.test_system_identity_provenance(
                    object_type,object_id,source,artifact_hash,created_by_user_id)
                VALUES(:object_type,:object_id,'wp-td-006b-pytest',:digest,:creator)"""), {
                    "object_type": object_type, "object_id": object_id,
                    "digest": marker * 64, "creator": creator,
                })
        historical_id = int(connection.execute(text("""SELECT user_id FROM public.users
            WHERE is_system_identity=TRUE
              AND system_identity_purpose='HISTORICAL_AUTHORSHIP'""")).scalar_one())
    return {
        "actors": actors,
        "roles": roles,
        "ready_user": ready_user,
        "shared_user": shared_user,
        "employee_user": employee_user,
        "person_id": person_id,
        "employee_id": employee_id,
        "admin_role_id": admin_role_id,
        "historical_id": historical_id,
    }


@contextmanager
def api_client(user_id: int, role_code: str):
    previous = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": user_id, "role_code": role_code,
    }
    try:
        with TestClient(app) as client:
            yield client
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous


def _target(object_type: str, object_id: int) -> dict:
    return {"object_type": object_type, "object_id": object_id}


def _item(preview: dict, object_type: str, object_id: int) -> dict:
    return next(
        item for item in preview["items"]
        if item["object_type"] == object_type and item["object_id"] == object_id
    )


def test_catalog_contract_is_exact_and_revision_specific(preview_engine):
    with preview_engine.connect() as connection:
        state = service.catalog_state(connection)
    assert service.SUPPORTED_ALEMBIC_REVISIONS == frozenset({REVISION})
    assert state == {
        "version": "WP-TD-SYSTEM-CATALOG/v2",
        "fingerprint": "516e9c2db97527314e44434c8d090b4c91e89109018cf4d60ca2320922ed62f8",
        "compatible": True,
        "revision_compatible": True,
    }


def test_search_uses_safe_masks_exact_ids_and_only_allowlisted_fields(seed):
    by_mask = service.search_candidates(
        object_type="USER", field="full_name", mask="WP TD 006B Ready U?er",
        object_ids=[],
    )
    assert by_mask["typed_ids"] == [_target("USER", seed["ready_user"])]
    assert by_mask["normalized_mask"] == "WP TD 006B Ready U?er"
    by_id = service.search_candidates(
        object_type="ROLE", field="code", mask=None,
        object_ids=[seed["roles"]["TD006B_UNUSED"]],
    )
    assert by_id["typed_ids"] == [
        _target("ROLE", seed["roles"]["TD006B_UNUSED"]),
    ]
    with pytest.raises(service.SystemIdentityPreviewError) as forbidden:
        service.search_candidates(
            object_type="USER", field="password_hash", mask="secret*", object_ids=[],
        )
    assert forbidden.value.code == "TD_SYSTEM_SEARCH_FIELD_FORBIDDEN"
    with pytest.raises(service.SystemIdentityPreviewError) as broad:
        service.search_candidates(
            object_type="USER", field="full_name", mask="***", object_ids=[],
        )
    assert broad.value.code == "TD_SYSTEM_MASK_TOO_BROAD"


def test_provenance_is_required_and_historical_authorship_is_always_excluded(seed):
    historical_search = service.search_candidates(
        object_type="USER", field="full_name", mask=None,
        object_ids=[seed["historical_id"]],
    )
    assert historical_search["items"] == []
    preview = service.preview_targets(targets=[
        _target("USER", seed["historical_id"]),
        _target("USER", seed["actors"]["HR_HEAD"]),
    ])
    historical = _item(preview, "USER", seed["historical_id"])
    ordinary = _item(preview, "USER", seed["actors"]["HR_HEAD"])
    assert "HISTORICAL_AUTHORSHIP_PROTECTED" in historical["blocking_codes"]
    assert historical["ready_for_deletion"] is False
    assert ordinary["has_test_provenance"] is False
    assert "TEST_SYSTEM_IDENTITY_PROVENANCE_REQUIRED" in ordinary["blocking_codes"]


def test_user_employee_and_person_links_block(seed):
    preview = service.preview_targets(targets=[
        _target("USER", seed["employee_user"]),
    ])
    item = preview["items"][0]
    assert item["has_test_provenance"] is True
    assert {"EMPLOYEE_LINK_PRESENT", "PERSON_LINK_PRESENT"} <= set(item["blocking_codes"])
    assert item["ready_for_deletion"] is False


def test_canonical_and_shared_roles_block_while_unused_provenance_role_is_ready(seed):
    preview = service.preview_targets(targets=[
        _target("ROLE", seed["roles"]["TD006B_UNUSED"]),
        _target("ROLE", seed["roles"]["TD006B_SHARED"]),
        _target("ROLE", seed["admin_role_id"]),
    ])
    unused = _item(preview, "ROLE", seed["roles"]["TD006B_UNUSED"])
    shared = _item(preview, "ROLE", seed["roles"]["TD006B_SHARED"])
    canonical = _item(preview, "ROLE", seed["admin_role_id"])
    assert unused["ready_for_deletion"] is True
    assert "ROLE_USED_BY_USERS" in shared["blocking_codes"]
    assert "CANONICAL_ROLE_PROTECTED" in canonical["blocking_codes"]
    assert shared["ready_for_deletion"] is False
    assert canonical["ready_for_deletion"] is False


def test_relationships_have_all_four_explicit_classifications(seed, preview_engine):
    before = service.preview_targets(targets=[_target("USER", seed["ready_user"])])
    assert before["items"][0]["ready_for_deletion"] is True
    with preview_engine.begin() as connection:
        connection.execute(text("""INSERT INTO public.audit_log(
                actor_user_id,entity,action)
            VALUES(:user_id,'wp-td-006b','preview')"""), {"user_id": seed["ready_user"]})
        connection.execute(text("""INSERT INTO public.notifications(
                channel,recipient_user_id,payload,status)
            VALUES('IN_APP',:user_id,'{}'::jsonb,'PENDING')"""), {
                "user_id": seed["ready_user"],
            })
        connection.execute(text("""INSERT INTO public.access_grants(
                access_role_id,target_type,target_id,granted_by_user_id,reason)
            SELECT access_role_id,'USER',:target,:actor,'WP-TD-006B preview blocker'
            FROM public.access_roles WHERE code='TEST_SYSTEM_IDENTITY_DELETION_REQUEST'"""), {
                "target": seed["ready_user"], "actor": seed["actors"]["ADMIN"],
            })
    preview = service.preview_targets(targets=[_target("USER", seed["ready_user"])])
    item = preview["items"][0]
    assert preview["target_list_hash"] == before["target_list_hash"]
    assert preview["relationship_fingerprint"] != before["relationship_fingerprint"]
    classifications = {relation["classification"] for relation in item["relationships"]}
    assert {service.BLOCKING, service.PRESERVE, service.REBIND, service.DELETE_ALLOWLIST} <= classifications
    assert item["ready_for_deletion"] is False


@pytest.mark.parametrize("drift_sql", [
    "CREATE TABLE public.td006b_unknown_fk(user_id BIGINT REFERENCES public.users(user_id))",
    "CREATE TABLE public.td006b_unknown_logical(user_id BIGINT)",
    "ALTER TABLE public.users ADD COLUMN td006b_unknown_identity_state TEXT",
])
def test_unknown_identity_fk_column_and_logical_relation_fail_closed(preview_engine, drift_sql):
    with preview_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(drift_sql))
            with pytest.raises(service.SystemIdentityPreviewError) as error:
                service.catalog_state(connection)
            assert error.value.code == "TD_SYSTEM_CATALOG_MISMATCH"
        finally:
            transaction.rollback()


def test_unrelated_public_objects_do_not_change_identity_catalog(preview_engine):
    with preview_engine.connect() as connection:
        transaction = connection.begin()
        try:
            before = service.catalog_state(connection)
            connection.execute(text("""CREATE TABLE public.td006b_unrelated_stage(
                value TEXT, imported_at TIMESTAMPTZ)
            """))
            connection.execute(text("""CREATE FUNCTION public.td006b_unrelated_touch()
                RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$
            """))
            connection.execute(text("""CREATE TRIGGER trg_td006b_unrelated_touch
                BEFORE INSERT ON public.td006b_unrelated_stage
                FOR EACH ROW EXECUTE FUNCTION public.td006b_unrelated_touch()
            """))
            after = service.catalog_state(connection)
            assert after == before
        finally:
            transaction.rollback()


def test_trigger_on_identity_table_fails_closed(preview_engine):
    with preview_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("""CREATE FUNCTION public.td006b_unknown_users_guard()
                RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$
            """))
            connection.execute(text("""CREATE TRIGGER trg_td006b_unknown_users_guard
                BEFORE UPDATE ON public.users FOR EACH ROW
                EXECUTE FUNCTION public.td006b_unknown_users_guard()
            """))
            with pytest.raises(service.SystemIdentityPreviewError) as error:
                service.catalog_state(connection)
            assert error.value.code == "TD_SYSTEM_CATALOG_MISMATCH"
        finally:
            transaction.rollback()


def test_registered_logical_links_block_only_exact_selected_target(seed, preview_engine):
    with preview_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("""CREATE TABLE public.regular_tasks_stg(
                created_by_user_id BIGINT, executorrolecode TEXT, payload TEXT)
            """))
            connection.execute(text("""INSERT INTO public.regular_tasks_stg(
                    created_by_user_id,executorrolecode,payload)
                VALUES(:user_id,:role_code,'matching'),
                      (999999999,'not-a-selected-role','unrelated')
            """), {
                "user_id": seed["ready_user"],
                "role_code": "TD006B_UNUSED",
            })
            assert service.catalog_state(connection)["compatible"] is True
            logical = service._logical_relationships(connection, [
                _target("USER", seed["ready_user"]),
                _target("USER", seed["shared_user"]),
                _target("ROLE", seed["roles"]["TD006B_UNUSED"]),
                _target("ROLE", seed["roles"]["TD006B_SHARED"]),
            ])
            codes = lambda key: {
                item["relation_code"] for item in logical.get(key, [])
                if item["relation_code"].startswith("LOGICAL:regular_tasks_stg.")
            }
            assert codes(("USER", seed["ready_user"])) == {
                "LOGICAL:regular_tasks_stg.created_by_user_id",
            }
            assert codes(("USER", seed["shared_user"])) == set()
            assert codes(("ROLE", seed["roles"]["TD006B_UNUSED"])) == {
                "LOGICAL:regular_tasks_stg.executorrolecode",
            }
            assert codes(("ROLE", seed["roles"]["TD006B_SHARED"])) == set()
        finally:
            transaction.rollback()


def test_active_role_is_blocking_when_optional_state_column_exists(seed, preview_engine):
    with preview_engine.connect() as connection:
        assert service.catalog_state(connection)["compatible"] is True
    item = service.preview_targets(targets=[
        _target("ROLE", seed["roles"]["TD006B_ACTIVE"]),
    ])["items"][0]
    assert item["has_test_provenance"] is True
    assert item["blocking_codes"] == ["ACTIVE_ROLE_PROTECTED"]
    assert item["ready_for_deletion"] is False


def test_unsupported_revision_fails_closed(preview_engine):
    with preview_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(
                "UPDATE public.alembic_version SET version_num='td006b_future'"
            ))
            state = service.catalog_state(connection, enforce=False)
            assert state["revision_compatible"] is False
            assert state["compatible"] is False
            with pytest.raises(service.SystemIdentityPreviewError) as error:
                service.catalog_state(connection)
            assert error.value.code == "TD_SYSTEM_CATALOG_MISMATCH"
        finally:
            transaction.rollback()


def test_typed_list_hash_and_relationship_fingerprint_are_sorted_and_stable(seed):
    targets = [
        _target("USER", seed["ready_user"]),
        _target("ROLE", seed["roles"]["TD006B_UNUSED"]),
    ]
    first = service.preview_targets(targets=targets)
    second = service.preview_targets(targets=list(reversed(targets)) + [targets[0]])
    assert first["typed_ids"] == [
        _target("ROLE", seed["roles"]["TD006B_UNUSED"]),
        _target("USER", seed["ready_user"]),
    ]
    assert first["target_list_hash"] == second["target_list_hash"]
    assert first["relationship_fingerprint"] == second["relationship_fingerprint"]
    assert len(first["target_list_hash"]) == 64
    assert len(first["relationship_fingerprint"]) == 64


def test_admin_endpoint_is_read_only_and_hr_head_is_denied(seed, preview_engine):
    tables = ("users", "roles", "employees", "persons", "test_system_identity_provenance")
    with preview_engine.connect() as connection:
        before = {
            table: int(connection.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one())
            for table in tables
        }
    with api_client(seed["actors"]["ADMIN"], "ADMIN") as admin:
        response = admin.post("/directory/test-system-identity-deletion/preview", json={
            "targets": [_target("ROLE", seed["roles"]["TD006B_UNUSED"])],
        })
        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert admin.post("/directory/test-system-identity-deletion/preview", json={
            "targets": [_target("ROLE", seed["roles"]["TD006B_UNUSED"])],
            "mask": "forbidden*",
        }).status_code == 422
        assert admin.post(
            "/directory/test-system-identity-deletion/requests", json={},
        ).status_code == 404
        assert admin.post(
            "/directory/test-system-identity-deletion/execute", json={},
        ).status_code == 404
    with api_client(seed["actors"]["HR_HEAD"], "HR_HEAD") as hr:
        response = hr.post("/directory/test-system-identity-deletion/search", json={
            "object_type": "ROLE", "field": "code", "object_ids": [
                seed["roles"]["TD006B_UNUSED"],
            ],
        })
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "TD_SYSTEM_PERMISSION_REQUIRED"
    with preview_engine.connect() as connection:
        after = {
            table: int(connection.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one())
            for table in tables
        }
    assert after == before

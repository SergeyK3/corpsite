"""PostgreSQL regressions for WP-TD-006A foundation."""
from __future__ import annotations

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.test_wp_td_005_manifest_v2 import _alembic_config, _ephemeral_database


PREVIOUS_REVISION = "td005exec501"
REVISION = "td006afnd601"
PERMISSION_CODES = (
    "TEST_SYSTEM_IDENTITY_DELETION_REQUEST",
    "TEST_SYSTEM_IDENTITY_DELETION_APPROVE",
    "TEST_SYSTEM_IDENTITY_DELETION_EXECUTE",
    "TEST_SYSTEM_IDENTITY_DELETION_AUDIT_READ",
)


def _assert_postgresql_16(connection) -> None:
    version = int(connection.execute(text("SHOW server_version_num")).scalar_one())
    assert 160000 <= version < 170000


def _business_snapshot(connection) -> dict:
    has_system_flag = bool(connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='users'
              AND column_name='is_system_identity'
        )
    """)).scalar_one())
    user_filter = "WHERE is_system_identity=FALSE" if has_system_flag else ""
    has_role_active = bool(connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='roles'
              AND column_name='is_active'
        )
    """)).scalar_one())
    role_active = ",is_active" if has_role_active else ""
    return {
        "users": connection.execute(text(f"""
            SELECT user_id,full_name,google_login,phone,telegram_id,role_id,
                   unit_id,is_active,created_at,telegram_username,
                   telegram_bound_at,login,password_hash,employee_id,
                   must_change_password,password_changed_at,
                   temp_password_expires_at,failed_login_count,locked_at,
                   locked_until,locked_reason,last_login_at,
                   last_failed_login_at,token_version
            FROM public.users {user_filter} ORDER BY user_id
        """)).tuples().all(),
        "roles": connection.execute(text(
            f"SELECT role_id,name,code{role_active} FROM public.roles ORDER BY role_id"
        )).tuples().all(),
        "employees": connection.execute(text(
            "SELECT * FROM public.employees ORDER BY employee_id"
        )).tuples().all(),
        "persons": connection.execute(text(
            "SELECT * FROM public.persons ORDER BY person_id"
        )).tuples().all(),
    }


def _technical_identity(connection):
    return connection.execute(text("""
        SELECT users.*,roles.code AS role_code
        FROM public.users users
        JOIN public.roles roles ON roles.role_id=users.role_id
        WHERE users.is_system_identity=TRUE
          AND users.system_identity_purpose='HISTORICAL_AUTHORSHIP'
    """)).mappings().one()


def test_alembic_has_one_wp_td_006a_head():
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_heads() == [REVISION]


def test_upgrade_downgrade_upgrade_is_idempotent_and_preserves_business_rows():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            _assert_postgresql_16(connection)
            before = _business_snapshot(connection)

        command.upgrade(config, REVISION)
        # Reapplying the same Alembic target is a no-op and must not duplicate
        # the protected identity, permissions, or grants.
        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == REVISION
            account = _technical_identity(connection)
            assert account["user_id"] not in {1, 25}
            assert account["employee_id"] is None
            assert account["role_code"] == "ADMIN"
            assert account["is_active"] is False
            assert account["locked_at"] is not None
            assert account["locked_reason"] == "policy"
            assert account["login"] is None
            assert account["google_login"] is None
            assert account["password_hash"] is None
            assert account["telegram_id"] is None
            assert account["telegram_username"] is None
            assert connection.execute(text("""
                SELECT count(*) FROM public.users
                WHERE is_system_identity=TRUE
                  AND system_identity_purpose='HISTORICAL_AUTHORSHIP'
            """)).scalar_one() == 1
            assert connection.execute(text("""
                SELECT count(*) FROM public.access_roles
                WHERE code=ANY(:codes)
                  AND description='WP-TD-006A:td006afnd601'
            """), {"codes": list(PERMISSION_CODES)}).scalar_one() == 4
            grants = connection.execute(text("""
                SELECT access_role.code,target_role.code
                FROM public.access_grants grant_def
                JOIN public.access_roles access_role
                  ON access_role.access_role_id=grant_def.access_role_id
                JOIN public.roles target_role
                  ON grant_def.target_type='ROLE'
                 AND target_role.role_id=grant_def.target_id
                WHERE access_role.code=ANY(:codes)
                  AND grant_def.active_flag=TRUE
                ORDER BY access_role.code
            """), {"codes": list(PERMISSION_CODES)}).tuples().all()
            assert grants == sorted((code, "ADMIN") for code in PERMISSION_CODES)
            after = _business_snapshot(connection)
            assert after["roles"] == before["roles"]
            assert after["employees"] == before["employees"]
            assert after["persons"] == before["persons"]
            assert [row for row in after["users"]] == before["users"]

        command.downgrade(config, PREVIOUS_REVISION)
        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == PREVIOUS_REVISION
            assert connection.execute(text("""
                SELECT to_regclass('public.test_system_identity_provenance')
            """)).scalar_one() is None
            assert connection.execute(text("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_schema='public' AND table_name='users'
                  AND column_name IN ('is_system_identity','system_identity_purpose')
            """)).scalar_one() == 0
            assert _business_snapshot(connection) == before

        command.upgrade(config, REVISION)
        with clone_engine.connect() as connection:
            assert _technical_identity(connection)["system_identity_purpose"] == (
                "HISTORICAL_AUTHORSHIP"
            )
            assert connection.execute(text("""
                SELECT count(*) FROM public.users
                WHERE is_system_identity=TRUE
                  AND system_identity_purpose='HISTORICAL_AUTHORSHIP'
            """)).scalar_one() == 1


@pytest.fixture(scope="module")
def foundation_engine():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        command.upgrade(_alembic_config(url), REVISION)
        with clone_engine.connect() as connection:
            _assert_postgresql_16(connection)
        yield clone_engine


def test_provenance_uses_real_user_and_role_foreign_keys(foundation_engine):
    with foundation_engine.connect() as connection:
        transaction = connection.begin()
        try:
            admin_user_id = connection.execute(text("""
                SELECT users.user_id FROM public.users users
                JOIN public.roles roles ON roles.role_id=users.role_id
                WHERE roles.code='ADMIN' AND users.is_active=TRUE
                ORDER BY users.user_id LIMIT 1
            """)).scalar_one()
            admin_role_id = connection.execute(text(
                "SELECT role_id FROM public.roles WHERE code='ADMIN'"
            )).scalar_one()
            connection.execute(text("""
                INSERT INTO public.test_system_identity_provenance(
                    object_type,object_id,source,artifact_hash,created_by_user_id
                ) VALUES('USER',:object_id,'migration-regression',:digest,:actor)
            """), {"object_id": admin_user_id, "digest": "a" * 64,
                    "actor": admin_user_id})
            connection.execute(text("""
                INSERT INTO public.test_system_identity_provenance(
                    object_type,object_id,source,artifact_hash,created_by_user_id
                ) VALUES('ROLE',:object_id,'migration-regression',:digest,:actor)
            """), {"object_id": admin_role_id, "digest": "b" * 64,
                    "actor": admin_user_id})
            typed = connection.execute(text("""
                SELECT object_type,user_id,role_id
                FROM public.test_system_identity_provenance
                ORDER BY object_type
            """)).tuples().all()
            assert typed == [("ROLE", None, admin_role_id),
                             ("USER", admin_user_id, None)]

            for object_type in ("USER", "ROLE"):
                with pytest.raises(DBAPIError):
                    with connection.begin_nested():
                        connection.execute(text("""
                            INSERT INTO public.test_system_identity_provenance(
                                object_type,object_id,source,artifact_hash,
                                created_by_user_id
                            ) VALUES(:object_type,9223372036854775000,
                                'missing-target',:digest,:actor)
                        """), {"object_type": object_type,
                                "digest": "c" * 64, "actor": admin_user_id})
        finally:
            transaction.rollback()


def test_provenance_is_append_only_unique_and_truncate_protected(foundation_engine):
    with foundation_engine.connect() as connection:
        transaction = connection.begin()
        try:
            actor = connection.execute(text("""
                SELECT user_id FROM public.users
                WHERE is_active=TRUE ORDER BY user_id LIMIT 1
            """)).scalar_one()
            role_id = connection.execute(text(
                "SELECT role_id FROM public.roles WHERE code='ADMIN'"
            )).scalar_one()
            params = {"role_id": role_id, "actor": actor, "digest": "d" * 64}
            provenance_id = connection.execute(text("""
                INSERT INTO public.test_system_identity_provenance(
                    object_type,object_id,source,artifact_hash,created_by_user_id
                ) VALUES('ROLE',:role_id,'append-only-test',:digest,:actor)
                RETURNING provenance_id
            """), params).scalar_one()
            statements = (
                ("UPDATE public.test_system_identity_provenance "
                 "SET source='changed' WHERE provenance_id=:id", {"id": provenance_id}),
                ("DELETE FROM public.test_system_identity_provenance "
                 "WHERE provenance_id=:id", {"id": provenance_id}),
                ("TRUNCATE public.test_system_identity_provenance", {}),
                ("""INSERT INTO public.test_system_identity_provenance(
                    object_type,object_id,source,artifact_hash,created_by_user_id)
                    VALUES('ROLE',:role_id,'append-only-test',:digest,:actor)""", params),
            )
            for statement, values in statements:
                with pytest.raises(DBAPIError):
                    with connection.begin_nested():
                        connection.execute(text(statement), values)
            assert connection.execute(text("""
                SELECT count(*) FROM public.test_system_identity_provenance
                WHERE provenance_id=:id
            """), {"id": provenance_id}).scalar_one() == 1
        finally:
            transaction.rollback()


def test_historical_identity_is_immutable_and_cannot_get_provenance(foundation_engine):
    with foundation_engine.connect() as connection:
        transaction = connection.begin()
        try:
            account = _technical_identity(connection)
            actor = connection.execute(text("""
                SELECT user_id FROM public.users
                WHERE is_active=TRUE ORDER BY user_id LIMIT 1
            """)).scalar_one()
            assert account["login"] is None
            assert account["password_hash"] is None
            assert account["is_active"] is False
            assert account["locked_at"] is not None

            for statement in (
                "UPDATE public.users SET is_active=TRUE WHERE user_id=:id",
                "DELETE FROM public.users WHERE user_id=:id",
            ):
                with pytest.raises(DBAPIError):
                    with connection.begin_nested():
                        connection.execute(text(statement), {"id": account["user_id"]})
            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(text("TRUNCATE public.users CASCADE"))
            with pytest.raises(DBAPIError):
                with connection.begin_nested():
                    connection.execute(text("""
                        INSERT INTO public.test_system_identity_provenance(
                            object_type,object_id,source,artifact_hash,
                            created_by_user_id
                        ) VALUES('USER',:id,'forbidden',:digest,:actor)
                    """), {"id": account["user_id"], "digest": "e" * 64,
                            "actor": actor})
        finally:
            transaction.rollback()


def test_system_identity_trigger_does_not_block_normal_user_updates(foundation_engine):
    with foundation_engine.connect() as connection:
        transaction = connection.begin()
        try:
            ordinary_user_id = connection.execute(text("""
                SELECT user_id FROM public.users
                WHERE is_system_identity=FALSE
                ORDER BY user_id LIMIT 1
            """)).scalar_one()
            before = connection.execute(text("""
                SELECT failed_login_count FROM public.users WHERE user_id=:id
            """), {"id": ordinary_user_id}).scalar_one()
            assert connection.execute(text("""
                UPDATE public.users
                SET failed_login_count=failed_login_count + 1
                WHERE user_id=:id AND is_system_identity=FALSE
                RETURNING failed_login_count
            """), {"id": ordinary_user_id}).scalar_one() == before + 1
        finally:
            transaction.rollback()


def test_downgrade_fails_closed_when_non_seed_provenance_exists():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        with clone_engine.begin() as connection:
            actor = connection.execute(text("""
                SELECT user_id FROM public.users
                WHERE is_active=TRUE ORDER BY user_id LIMIT 1
            """)).scalar_one()
            role_id = connection.execute(text(
                "SELECT role_id FROM public.roles WHERE code='ADMIN'"
            )).scalar_one()
            connection.execute(text("""
                INSERT INTO public.test_system_identity_provenance(
                    object_type,object_id,source,artifact_hash,created_by_user_id
                ) VALUES('ROLE',:role_id,'downgrade-preflight',:digest,:actor)
            """), {"role_id": role_id, "digest": "f" * 64, "actor": actor})

        with pytest.raises(DBAPIError, match="WP_TD_006A_PROVENANCE_PREVENTS_DOWNGRADE"):
            command.downgrade(config, PREVIOUS_REVISION)

        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == REVISION
            assert connection.execute(text(
                "SELECT count(*) FROM public.test_system_identity_provenance"
            )).scalar_one() == 1
            assert _technical_identity(connection)["system_identity_purpose"] == (
                "HISTORICAL_AUTHORSHIP"
            )


def test_downgrade_fails_closed_before_external_history_can_cascade():
    with _ephemeral_database(upgrade=False) as (url, clone_engine):
        config = _alembic_config(url)
        command.upgrade(config, REVISION)
        with clone_engine.begin() as connection:
            technical_user_id = _technical_identity(connection)["user_id"]
            connection.execute(text("""
                CREATE TABLE public.td006a_external_history (
                    history_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    author_user_id BIGINT NOT NULL
                        REFERENCES public.users(user_id) ON DELETE CASCADE,
                    event_code TEXT NOT NULL
                )
            """))
            connection.execute(text("""
                INSERT INTO public.td006a_external_history(author_user_id,event_code)
                VALUES(:user_id,'HISTORY_MUST_SURVIVE')
            """), {"user_id": technical_user_id})

        with pytest.raises(DBAPIError, match="WP_TD_006A_TECHNICAL_USER_REFERENCED"):
            command.downgrade(config, PREVIOUS_REVISION)

        with clone_engine.connect() as connection:
            assert connection.execute(text(
                "SELECT version_num FROM alembic_version"
            )).scalar_one() == REVISION
            assert connection.execute(text("""
                SELECT event_code FROM public.td006a_external_history
            """)).scalar_one() == "HISTORY_MUST_SURVIVE"
            assert _technical_identity(connection)["system_identity_purpose"] == (
                "HISTORICAL_AUTHORSHIP"
            )

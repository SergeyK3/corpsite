from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.db.engine import engine


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "v5w6x7y8z9a"
PERMISSION_REVISION = "w6x7y8z9a0b1"
HEAD_REVISION = "x7y8z9a0b1c2"
HR_HEAD_PREREQUISITE_REVISION = "g4b5c6d7e8f9"
ORG_UNIT_PREREQUISITE_REVISION = "r1s2t3u4v5w6"


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


@contextmanager
def _database_url(value: str):
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@contextmanager
def _database_at_previous_revision():
    database_name = f"corpsite_wpcl_hotfix_{uuid4().hex[:12]}_test"
    admin_url = engine.url.set(database="postgres")
    database_url = engine.url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    test_engine = create_engine(database_url)

    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{database_name}"'))

    rendered_url = database_url.render_as_string(hide_password=False)
    try:
        with _database_url(rendered_url):
            command.upgrade(_alembic_config(), HR_HEAD_PREREQUISITE_REVISION)
        with test_engine.begin() as conn:
            _seed_hr_head(conn)
        with _database_url(rendered_url):
            command.upgrade(_alembic_config(), ORG_UNIT_PREREQUISITE_REVISION)
        with test_engine.begin() as conn:
            _seed_org_unit_prerequisite(conn)
        with _database_url(rendered_url):
            command.upgrade(_alembic_config(), PREVIOUS_REVISION)
            yield test_engine
    finally:
        test_engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": database_name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()


def _seed_role_and_user(
    conn,
    *,
    role_id: int,
    role_code: str,
    user_id: int,
    login: str,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.roles (role_id, name, code)
            VALUES (:role_id, :name, :code)
            """
        ),
        {"role_id": role_id, "name": role_code, "code": role_code},
    )
    conn.execute(
        text(
            """
            INSERT INTO public.users (user_id, full_name, role_id, is_active, login)
            VALUES (:user_id, :full_name, :role_id, TRUE, :login)
            """
        ),
        {
            "user_id": user_id,
            "full_name": f"Migration test {role_code}",
            "role_id": role_id,
            "login": login,
        },
    )


def _seed_hr_head(conn) -> None:
    _seed_role_and_user(
        conn,
        role_id=17,
        role_code="HR_HEAD",
        user_id=1701,
        login="wpcl_migration_hr_head",
    )


def _seed_user_for_existing_role(
    conn,
    *,
    role_code: str,
    user_id: int,
    login: str,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.users (user_id, full_name, role_id, is_active, login)
            SELECT :user_id, :full_name, role_id, TRUE, :login
            FROM public.roles
            WHERE code = :role_code
            """
        ),
        {
            "user_id": user_id,
            "full_name": f"Migration test {role_code}",
            "role_code": role_code,
            "login": login,
        },
    )


def _seed_org_unit_prerequisite(conn) -> None:
    parent_id = conn.execute(
        text(
            """
            INSERT INTO public.org_units (name, code, group_id, is_active)
            VALUES ('Migration test parent', 'MIGRATION_TEST_PARENT', 3, TRUE)
            RETURNING unit_id
            """
        )
    ).scalar_one()
    conn.execute(
        text(
            """
            INSERT INTO public.org_units
                (name, code, parent_unit_id, group_id, is_active)
            VALUES ('Migration test DISP', 'DISP', :parent_id, 2, TRUE)
            """
        ),
        {"parent_id": parent_id},
    )


def _revision(conn) -> str:
    return str(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def test_real_postgresql_full_chain_v5_to_head_and_back() -> None:
    with _database_at_previous_revision() as test_engine:
        with test_engine.begin() as conn:
            role_columns = {
                str(value)
                for value in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'roles'
                        """
                    )
                ).scalars()
            }
            assert role_columns == {"role_id", "name", "code"}
            assert "is_active" not in role_columns
        with _database_url(test_engine.url.render_as_string(hide_password=False)):
            command.upgrade(_alembic_config(), "head")

        with test_engine.connect() as conn:
            assert _revision(conn) == HEAD_REVISION
            permission = conn.execute(
                text(
                    """
                    SELECT code, access_level, level_rank, is_system, is_active
                    FROM public.access_roles
                    WHERE code = 'CONTROL_LIST_EXPORT'
                    """
                )
            ).one()
            assert tuple(permission) == (
                "CONTROL_LIST_EXPORT", "MANAGER", 20, True, True
            )
            grants = conn.execute(
                text(
                    """
                    SELECT r.code, g.resource_key, g.scope_type, g.active_flag
                    FROM public.access_grants g
                    JOIN public.access_roles ar USING (access_role_id)
                    JOIN public.roles r
                      ON g.target_type = 'ROLE' AND g.target_id = r.role_id
                    WHERE ar.code = 'CONTROL_LIST_EXPORT'
                    """
                )
            ).all()
            assert [tuple(row) for row in grants] == [
                ("HR_HEAD", "*", "GLOBAL", True)
            ]
            audit_constraint = conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(oid)
                    FROM pg_constraint
                    WHERE conrelid = 'public.security_audit_log'::regclass
                      AND conname = 'chk_sal_event_type'
                    """
                )
            ).scalar_one()
            assert "CONTROL_LIST_EXPORT" in str(audit_constraint)

        with _database_url(test_engine.url.render_as_string(hide_password=False)):
            command.downgrade(_alembic_config(), PREVIOUS_REVISION)

        with test_engine.connect() as conn:
            assert _revision(conn) == PREVIOUS_REVISION
            assert conn.execute(
                text(
                    "SELECT count(*) FROM public.access_roles "
                    "WHERE code = 'CONTROL_LIST_EXPORT'"
                )
            ).scalar_one() == 0
            audit_constraint = conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(oid)
                    FROM pg_constraint
                    WHERE conrelid = 'public.security_audit_log'::regclass
                      AND conname = 'chk_sal_event_type'
                    """
                )
            ).scalar_one()
            assert "CONTROL_LIST_EXPORT" not in str(audit_constraint)


def test_real_postgresql_upgrade_rejects_preexisting_permission_atomically() -> None:
    with _database_at_previous_revision() as test_engine:
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_roles
                        (code, name, description, access_level, level_rank, is_system)
                    VALUES
                        ('CONTROL_LIST_EXPORT', 'Preexisting', 'Must remain untouched',
                         'OBSERVER', 10, FALSE)
                    """
                )
            )

        with _database_url(test_engine.url.render_as_string(hide_password=False)):
            with pytest.raises(Exception, match="code already exists"):
                command.upgrade(_alembic_config(), PERMISSION_REVISION)

        with test_engine.connect() as conn:
            assert _revision(conn) == PREVIOUS_REVISION
            row = conn.execute(
                text(
                    "SELECT name, description, access_level FROM public.access_roles "
                    "WHERE code = 'CONTROL_LIST_EXPORT'"
                )
            ).one()
            assert tuple(row) == ("Preexisting", "Must remain untouched", "OBSERVER")
            assert conn.execute(
                text(
                    """
                    SELECT count(*) FROM public.access_grants g
                    JOIN public.access_roles ar USING (access_role_id)
                    WHERE ar.code = 'CONTROL_LIST_EXPORT'
                    """
                )
            ).scalar_one() == 0


def test_real_postgresql_upgrade_requires_exactly_one_hr_head_atomically() -> None:
    with _database_at_previous_revision() as test_engine:
        with test_engine.begin() as conn:
            conn.execute(
                text("UPDATE public.roles SET code = 'HR_HEAD_MISSING' WHERE role_id = 17")
            )

        with _database_url(test_engine.url.render_as_string(hide_password=False)):
            with pytest.raises(Exception, match="requires exactly one role HR_HEAD, found 0"):
                command.upgrade(_alembic_config(), PERMISSION_REVISION)

        with test_engine.connect() as conn:
            assert _revision(conn) == PREVIOUS_REVISION
            assert conn.execute(
                text(
                    "SELECT count(*) FROM public.access_roles "
                    "WHERE code = 'CONTROL_LIST_EXPORT'"
                )
            ).scalar_one() == 0


def test_real_postgresql_downgrade_preserves_later_personal_grant() -> None:
    with _database_at_previous_revision() as test_engine:
        rendered_url = test_engine.url.render_as_string(hide_password=False)
        with _database_url(rendered_url):
            command.upgrade(_alembic_config(), "head")

        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants
                        (access_role_id, target_type, target_id, granted_by_user_id, reason)
                    SELECT ar.access_role_id, 'USER', u.user_id, u.user_id,
                           'later personal grant'
                    FROM public.access_roles ar
                    CROSS JOIN public.users u
                    WHERE ar.code = 'CONTROL_LIST_EXPORT'
                      AND u.login = 'wpcl_migration_hr_head'
                    """
                )
            )

        with _database_url(rendered_url):
            command.downgrade(_alembic_config(), PREVIOUS_REVISION)

        with test_engine.connect() as conn:
            assert _revision(conn) == PREVIOUS_REVISION
            assert conn.execute(
                text(
                    "SELECT count(*) FROM public.access_roles "
                    "WHERE code = 'CONTROL_LIST_EXPORT'"
                )
            ).scalar_one() == 1
            grants = conn.execute(
                text(
                    """
                    SELECT target_type, reason FROM public.access_grants g
                    JOIN public.access_roles ar USING (access_role_id)
                    WHERE ar.code = 'CONTROL_LIST_EXPORT'
                    ORDER BY g.grant_id
                    """
                )
            ).all()
            assert [tuple(row) for row in grants] == [
                ("USER", "later personal grant")
            ]


def test_real_postgresql_rbac_matrix_has_no_role_or_admin_bypass(monkeypatch) -> None:
    import app.services.access_resolver_service as resolver
    from app.security.admin_permissions import (
        CONTROL_LIST_EXPORT_PERMISSION,
        has_admin_permission,
    )

    with _database_at_previous_revision() as test_engine:
        with test_engine.begin() as conn:
            _seed_user_for_existing_role(
                conn,
                role_code="HR_reg",
                user_id=1801,
                login="wpcl_migration_hr_reg",
            )
            _seed_role_and_user(
                conn,
                role_id=190,
                role_code="WPCL_ENROLLMENT_ONLY",
                user_id=1901,
                login="wpcl_migration_enrollment",
            )
            _seed_role_and_user(
                conn,
                role_code="ADMIN",
                role_id=2,
                user_id=2001,
                login="wpcl_migration_admin",
            )

        with _database_url(test_engine.url.render_as_string(hide_password=False)):
            command.upgrade(_alembic_config(), "head")

        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants
                        (access_role_id, target_type, target_id, granted_by_user_id, reason)
                    SELECT ar.access_role_id, 'ROLE', target.role_id, grantor.user_id,
                           'enrollment only'
                    FROM public.access_roles ar
                    JOIN public.roles target ON target.code = 'WPCL_ENROLLMENT_ONLY'
                    JOIN public.users grantor
                      ON grantor.login = 'wpcl_migration_hr_head'
                    WHERE ar.code = 'HR_ENROLLMENT_MANAGER'
                    """
                )
            )

        monkeypatch.setattr(resolver, "engine", test_engine)

        def allowed(login: str) -> bool:
            with test_engine.connect() as conn:
                user_id = conn.execute(
                    text("SELECT user_id FROM public.users WHERE login = :login"),
                    {"login": login},
                ).scalar_one()
            return has_admin_permission(user_id, CONTROL_LIST_EXPORT_PERMISSION)

        assert allowed("wpcl_migration_hr_head") is True
        assert allowed("wpcl_migration_hr_reg") is False
        assert allowed("wpcl_migration_enrollment") is False
        assert allowed("wpcl_migration_admin") is False

        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.access_grants
                        (access_role_id, target_type, target_id, granted_by_user_id, reason)
                    SELECT ar.access_role_id, 'USER', target.user_id, grantor.user_id,
                           'personal export'
                    FROM public.access_roles ar
                    JOIN public.users target
                      ON target.login = 'wpcl_migration_hr_reg'
                    JOIN public.users grantor
                      ON grantor.login = 'wpcl_migration_hr_head'
                    WHERE ar.code = 'CONTROL_LIST_EXPORT'
                    """
                )
            )

        assert allowed("wpcl_migration_hr_reg") is True

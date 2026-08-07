"""PostgreSQL tests for the ADR-046 F2 audit CHECK migration."""
from __future__ import annotations

import re
from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import exc, text

from app.db.engine import engine
from tests.alembic_test_helpers import exclusive_migration_cycle

REVISION_F2 = "j7k8l9m0n1o2"
REVISION_PRE_F2 = "i6j7k8l9m0n1"
RUN_MARKER = uuid4().hex
UNKNOWN_EVENT_TYPE = "ADR046_F2_UNKNOWN_EVENT_TYPE"

F2_EVENT_TYPES = (
    "ORG_UNIT_ALLOWED_POSITION_CREATED",
    "ORG_UNIT_ALLOWED_POSITION_REACTIVATED",
    "ORG_UNIT_ALLOWED_POSITION_UPDATED",
    "ORG_UNIT_ALLOWED_POSITION_DEACTIVATED",
)

PRE_F2_EVENT_TYPES = (
    "LOGIN_SUCCESS",
    "LOGIN_FAILED",
    "LOGOUT",
    "PASSWORD_RESET_REQUESTED",
    "PASSWORD_RESET_COMPLETED",
    "PASSWORD_CHANGED",
    "TEMP_PASSWORD_ISSUED",
    "USER_LOCKED",
    "USER_UNLOCKED",
    "ACCESS_GRANTED",
    "ACCESS_REVOKED",
    "ACCESS_CHANGED",
    "ENROLLMENT_APPROVED",
    "ENROLLMENT_REJECTED",
    "ENROLLMENT_COMPLETED",
    "USER_BLOCKED",
    "USER_UNBLOCKED",
    "PERSON_IIN_RECONCILED",
    "VISIBILITY_GRANTED",
    "VISIBILITY_REVOKED",
    "USER_EMPLOYEE_LINKED",
    "USER_EMPLOYEE_UNLINKED",
    "USER_EMPLOYEE_LINK_ROLLED_BACK",
    "EMPLOYEE_ENROLLED_FROM_IMPORT",
    "HR_IMPORT_REVIEW_COMPLETED",
    "EDITORIAL_GENERATED",
    "EDITORIAL_REGENERATED",
    "EDITORIAL_OVERRIDE_UPDATED",
    "EDITORIAL_OVERRIDE_CLEARED",
    "EDITORIAL_MARKED_STALE",
    "READY_GATE_REJECTED",
    "ORG_UNIT_CREATED",
    "ORG_UNIT_UPDATED",
    "ORG_UNIT_ACTIVATED",
    "ORG_UNIT_DEACTIVATED",
    "ORG_UNIT_DELETED",
    "ORG_UNIT_DELETE_REJECTED",
    "EMPLOYEE_HARD_DELETED",
)


def _migration_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "j7k8l9m0n1o2_adr046_f2_allowed_position_audit_events.py"
    )
    spec = spec_from_file_location("adr046_f2_allowed_position_audit_migration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def _constraint_definition(conn) -> str:
    return str(
        conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid)
                FROM pg_constraint AS c
                JOIN pg_class AS t ON t.oid = c.conrelid
                JOIN pg_namespace AS n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = 'security_audit_log'
                  AND c.conname = 'chk_sal_event_type'
                """
            )
        ).scalar_one()
    )


def _constraint_event_types(conn) -> tuple[str, ...]:
    return tuple(re.findall(r"'([^']+)'::text", _constraint_definition(conn)))


def _insert_event(conn, event_type: str, marker: str) -> int:
    return int(
        conn.execute(
            text(
                """
                INSERT INTO public.security_audit_log (event_type, metadata)
                VALUES (
                    :event_type,
                    jsonb_build_object(
                        'adr046_f2_test_run', :run_marker,
                        'adr046_f2_test', :marker
                    )
                )
                RETURNING audit_id
                """
            ),
            {"event_type": event_type, "run_marker": RUN_MARKER, "marker": marker},
        ).scalar_one()
    )


def _insert_allowed_event_types(
    conn,
    event_types: tuple[str, ...],
    marker_prefix: str,
) -> list[int]:
    return [
        _insert_event(conn, event_type, f"{marker_prefix}-{index}-{event_type}")
        for index, event_type in enumerate(event_types)
    ]


def _all_audit_rows(conn) -> list[str]:
    return list(
        conn.execute(
            text(
                """
                SELECT to_jsonb(sal)::text
                FROM public.security_audit_log AS sal
                ORDER BY sal.audit_id
                """
            )
        ).scalars()
    )


def _assert_event_rejected(conn, event_type: str, marker: str) -> None:
    with pytest.raises(exc.IntegrityError) as exc_info:
        with conn.begin_nested():
            _insert_event(conn, event_type, marker)
    original = exc_info.value.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    assert sqlstate == "23514"
    assert original.diag.constraint_name == "chk_sal_event_type"


def _assert_database_consistent(conn) -> None:
    assert conn.execute(text("SELECT 1")).scalar_one() == 1
    assert conn.execute(
        text(
            """
            SELECT convalidated
            FROM pg_constraint AS c
            JOIN pg_class AS t ON t.oid = c.conrelid
            JOIN pg_namespace AS n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'security_audit_log'
              AND c.conname = 'chk_sal_event_type'
            """
        )
    ).scalar_one() is True


@pytest.fixture(scope="module", autouse=True)
def _remove_stage1_test_artifacts():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM public.security_audit_log
                WHERE metadata ->> 'adr046_f2_test_run' = :run_marker
                """
            ),
            {"run_marker": RUN_MARKER},
        )
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM public.security_audit_log
                WHERE metadata ->> 'adr046_f2_test_run' = :run_marker
                """
            ),
            {"run_marker": RUN_MARKER},
        )


@contextmanager
def _rolled_back_migration_connection():
    with exclusive_migration_cycle() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def test_revision_is_the_single_head_and_has_exact_parent() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    assert script.get_heads() == [REVISION_F2]
    revision = script.get_revision(REVISION_F2)
    assert revision is not None
    assert revision.down_revision == REVISION_PRE_F2


def test_upgrade_accepts_all_four_f2_event_types() -> None:
    module = _migration_module()
    marker = f"upgrade-{uuid4().hex}"

    with _rolled_back_migration_connection() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        assert _constraint_event_types(conn) == PRE_F2_EVENT_TYPES + F2_EVENT_TYPES
        _insert_allowed_event_types(conn, PRE_F2_EVENT_TYPES, f"{marker}-pre-f2")
        _insert_allowed_event_types(conn, F2_EVENT_TYPES, f"{marker}-f2")
        assert conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.security_audit_log
                WHERE metadata ->> 'adr046_f2_test_run' = :run_marker
                """
            ),
            {"run_marker": RUN_MARKER},
        ).scalar_one() == len(PRE_F2_EVENT_TYPES) + len(F2_EVENT_TYPES)
        _assert_event_rejected(conn, UNKNOWN_EVENT_TYPE, f"{marker}-unknown")


@pytest.mark.parametrize("blocking_event_type", F2_EVENT_TYPES)
def test_guarded_downgrade_refuses_each_f2_type_before_check_ddl(
    blocking_event_type: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _migration_module()
    marker = f"blocked-{uuid4().hex}"

    with _rolled_back_migration_connection() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        _insert_event(conn, "LOGIN_SUCCESS", marker)
        _insert_event(conn, blocking_event_type, marker)
        rows_before = _all_audit_rows(conn)
        check_before = _constraint_definition(conn)
        ddl_calls: list[tuple[str, ...]] = []
        original_replace = module._replace_event_type_check

        def tracked_replace(event_types: tuple[str, ...]) -> None:
            ddl_calls.append(event_types)
            original_replace(event_types)

        monkeypatch.setattr(module, "_replace_event_type_check", tracked_replace)
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match=f"{blocking_event_type}=1"):
                module.downgrade()

        assert ddl_calls == []
        assert _all_audit_rows(conn) == rows_before
        assert _constraint_definition(conn) == check_before
        assert _constraint_event_types(conn) == PRE_F2_EVENT_TYPES + F2_EVENT_TYPES
        _assert_database_consistent(conn)

        after_refusal_marker = f"{marker}-after-refusal"
        _insert_allowed_event_types(
            conn,
            PRE_F2_EVENT_TYPES,
            f"{after_refusal_marker}-pre-f2",
        )
        _insert_allowed_event_types(conn, F2_EVENT_TYPES, f"{after_refusal_marker}-f2")
        assert conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.security_audit_log
                WHERE metadata ->> 'adr046_f2_test' LIKE :marker_prefix
                """
            ),
            {"marker_prefix": f"{after_refusal_marker}-%"},
        ).scalar_one() == len(PRE_F2_EVENT_TYPES) + len(F2_EVENT_TYPES)
        _assert_event_rejected(conn, UNKNOWN_EVENT_TYPE, f"{after_refusal_marker}-unknown")
        _assert_database_consistent(conn)


def test_empty_f2_downgrade_restores_exact_pre_f2_check_and_reupgrade() -> None:
    module = _migration_module()
    marker = f"success-{uuid4().hex}"

    with _rolled_back_migration_connection() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        baseline_audit_id = _insert_event(conn, "LOGIN_SUCCESS", marker)
        baseline_row = conn.execute(
            text(
                """
                SELECT to_jsonb(sal)::text
                FROM public.security_audit_log AS sal
                WHERE sal.audit_id = :audit_id
                """
            ),
            {"audit_id": baseline_audit_id},
        ).scalar_one()

        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()

        assert _constraint_event_types(conn) == PRE_F2_EVENT_TYPES
        assert conn.execute(
            text(
                """
                SELECT to_jsonb(sal)::text
                FROM public.security_audit_log AS sal
                WHERE sal.audit_id = :audit_id
                """
            ),
            {"audit_id": baseline_audit_id},
        ).scalar_one() == baseline_row
        for event_type in F2_EVENT_TYPES:
            _assert_event_rejected(conn, event_type, f"{marker}-rejected")
        _assert_event_rejected(conn, UNKNOWN_EVENT_TYPE, f"{marker}-unknown-rejected")
        _assert_database_consistent(conn)

        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        assert _constraint_event_types(conn) == PRE_F2_EVENT_TYPES + F2_EVENT_TYPES
        for event_type in F2_EVENT_TYPES:
            _insert_event(conn, event_type, f"{marker}-reupgrade")
        _assert_database_consistent(conn)

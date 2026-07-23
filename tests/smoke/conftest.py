# tests/smoke/conftest.py
"""Smoke-test guard: allow execution only against corpsite_test."""
from __future__ import annotations

import os
import sys

from tests.db_guard import PytestDatabaseGuardError, normalize_database_url

REQUIRED_DATABASE = "corpsite_test"
_SMOKE_ENGINE_BOUND = False


def _database_name_from_env(var_name: str, *, required: bool) -> str | None:
    raw = os.environ.get(var_name)
    if not raw or not str(raw).strip():
        if required:
            raise PytestDatabaseGuardError(
                f"{var_name} is required for smoke tests and must target {REQUIRED_DATABASE!r}."
            )
        return None
    return normalize_database_url(str(raw)).database


def bind_smoke_engine_to_corpsite_test() -> None:
    """Bind app.db.engine to TEST_DATABASE_URL without dev/prod DATABASE_URL comparison."""
    global _SMOKE_ENGINE_BOUND
    if _SMOKE_ENGINE_BOUND:
        return

    test_db = _database_name_from_env("TEST_DATABASE_URL", required=True)
    if test_db != REQUIRED_DATABASE:
        raise PytestDatabaseGuardError(
            f"TEST_DATABASE_URL must target {REQUIRED_DATABASE!r}, got {test_db!r}."
        )

    from sqlalchemy import create_engine

    import app.db.engine as engine_module

    test_url = os.environ["TEST_DATABASE_URL"].strip()
    if getattr(engine_module.engine, "dispose", None):
        engine_module.engine.dispose()
    engine_module.DATABASE_URL = test_url
    engine_module.engine = create_engine(test_url, pool_pre_ping=True)
    _SMOKE_ENGINE_BOUND = True


def enforce_corpsite_test_smoke_guard() -> None:
    try:
        test_db = _database_name_from_env("TEST_DATABASE_URL", required=True)
    except PytestDatabaseGuardError as exc:
        print(f"SMOKE GUARD: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if test_db != REQUIRED_DATABASE:
        print(
            f"SMOKE GUARD: TEST_DATABASE_URL must target database {REQUIRED_DATABASE!r}, "
            f"got {test_db!r}. Aborting before any test data is touched.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        app_db = _database_name_from_env("DATABASE_URL", required=True)
    except PytestDatabaseGuardError as exc:
        print(f"SMOKE GUARD: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if app_db != REQUIRED_DATABASE:
        print(
            f"SMOKE GUARD: DATABASE_URL must target database {REQUIRED_DATABASE!r}, "
            f"got {app_db!r}. Aborting before any test data is touched.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    bind_smoke_engine_to_corpsite_test()

    from app.db.engine import engine

    bound_db = (engine.url.database or "").strip().lower()
    if bound_db != REQUIRED_DATABASE:
        print(
            f"SMOKE GUARD: SQLAlchemy engine is bound to {bound_db!r}, "
            f"expected {REQUIRED_DATABASE!r}. Aborting.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def pytest_configure(config):  # noqa: ARG001
    enforce_corpsite_test_smoke_guard()

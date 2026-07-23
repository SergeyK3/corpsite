# tests/db_guard.py
"""Pytest database isolation guard — TEST_DATABASE_URL only, no dev/prod fallback."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote

from sqlalchemy.engine.url import URL, make_url

_GUARD_APPLIED = False
_ENGINE_BOUND = False


class PytestDatabaseGuardError(Exception):
    """Raised when TEST_DATABASE_URL fails isolation checks."""


@dataclass(frozen=True)
class NormalizedDatabaseTarget:
    dialect: str
    host: str
    port: int
    database: str

    def identity_key(self) -> tuple[str, str, int, str]:
        return (self.dialect, self.host, self.port, self.database)


def _normalize_host(host: Optional[str]) -> str:
    value = (host or "localhost").strip().lower()
    if value in {"localhost", "::1"}:
        return "127.0.0.1"
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1].lower()
    return value


def _normalize_port(port: Optional[int], *, dialect: str) -> int:
    if port is not None:
        return int(port)
    if dialect.startswith("postgres"):
        return 5432
    return 0


def normalize_database_url(raw_url: str) -> NormalizedDatabaseTarget:
    url: URL = make_url(raw_url.strip())
    dialect = (url.drivername or "postgresql").split("+", 1)[0].lower()
    host = _normalize_host(url.host)
    port = _normalize_port(url.port, dialect=dialect)
    database = unquote((url.database or "").strip()).lower()
    if not database:
        raise PytestDatabaseGuardError(f"Database name is missing in URL: {raw_url!r}")
    return NormalizedDatabaseTarget(
        dialect=dialect,
        host=host,
        port=port,
        database=database,
    )


def is_test_database_name(database: str) -> bool:
    name = database.strip().lower()
    return name.endswith("_test") or name.endswith("-test")


def validate_test_database_url(
    *,
    test_database_url: Optional[str],
    app_database_url: Optional[str] = None,
) -> NormalizedDatabaseTarget:
    if not test_database_url or not str(test_database_url).strip():
        raise PytestDatabaseGuardError(
            "TEST_DATABASE_URL is required for pytest. "
            "Set it to a dedicated test database (for example corpsite_test). "
            "Pytest must not use DATABASE_URL or the dev/prod database."
        )

    test_target = normalize_database_url(str(test_database_url))

    if not is_test_database_name(test_target.database):
        raise PytestDatabaseGuardError(
            "TEST_DATABASE_URL must point to a database whose name ends with "
            "'_test' or '-test'. "
            f"Got database name {test_target.database!r}."
        )

    if app_database_url and str(app_database_url).strip():
        app_target = normalize_database_url(str(app_database_url))
        if test_target.identity_key() == app_target.identity_key():
            raise PytestDatabaseGuardError(
                "TEST_DATABASE_URL must not target the same database as DATABASE_URL "
                f"(host={test_target.host}, port={test_target.port}, "
                f"database={test_target.database}). "
                "Use a separate test database such as corpsite_test."
            )

    return test_target


def _fail_guard(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def enforce_pytest_database_isolation() -> NormalizedDatabaseTarget:
    global _GUARD_APPLIED
    if _GUARD_APPLIED:
        validated = os.environ.get("TEST_DATABASE_URL")
        if not validated:
            _fail_guard("TEST_DATABASE_URL missing after guard was applied.")
        return normalize_database_url(validated)

    try:
        target = validate_test_database_url(
            test_database_url=os.environ.get("TEST_DATABASE_URL"),
            app_database_url=os.environ.get("DATABASE_URL"),
        )
    except PytestDatabaseGuardError as exc:
        _fail_guard(str(exc))

    os.environ["TEST_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"].strip()
    _GUARD_APPLIED = True
    return target


def bind_app_engine_to_test_database() -> str:
    """Point app.db.engine at TEST_DATABASE_URL after guard validation."""
    global _ENGINE_BOUND
    enforce_pytest_database_isolation()
    test_url = os.environ["TEST_DATABASE_URL"].strip()

    if _ENGINE_BOUND:
        return test_url

    from sqlalchemy import create_engine

    import app.db.engine as engine_module

    if getattr(engine_module.engine, "dispose", None):
        engine_module.engine.dispose()

    engine_module.DATABASE_URL = test_url
    engine_module.engine = create_engine(test_url, pool_pre_ping=True)
    _ENGINE_BOUND = True
    return test_url


def get_validated_test_database_url() -> str:
    enforce_pytest_database_isolation()
    return os.environ["TEST_DATABASE_URL"].strip()

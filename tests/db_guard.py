# tests/db_guard.py
"""Pytest database isolation guard — TEST_DATABASE_URL only, no dev/prod fallback."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from dotenv import dotenv_values
from sqlalchemy.engine.url import URL, make_url

_GUARD_APPLIED = False
_ENGINE_BOUND = False
PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
    try:
        url: URL = make_url(raw_url.strip())
    except Exception as exc:
        raise PytestDatabaseGuardError("Database URL is invalid.") from exc
    dialect = (url.drivername or "postgresql").split("+", 1)[0].lower()
    host = _normalize_host(url.host)
    port = _normalize_port(url.port, dialect=dialect)
    database = unquote((url.database or "").strip()).lower()
    if not database:
        raise PytestDatabaseGuardError("Database name is missing in URL.")
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

    if test_target.host != "127.0.0.1":
        raise PytestDatabaseGuardError(
            "TEST_DATABASE_URL must use an explicitly allowed loopback host "
            f"(127.0.0.1, localhost or ::1); got {test_target.host!r}."
        )

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


def resolve_main_database_url(
    *, process_database_url: Optional[str] = None, dotenv_path: Path | None = None,
) -> Optional[str]:
    """Read the application URL without mutating os.environ."""
    process_value = process_database_url if process_database_url is not None else os.environ.get("DATABASE_URL")
    if process_value and str(process_value).strip():
        return str(process_value).strip()
    values = dotenv_values(dotenv_path or (PROJECT_ROOT / ".env"))
    dotenv_value = values.get("DATABASE_URL")
    return str(dotenv_value).strip() if dotenv_value and str(dotenv_value).strip() else None


def assert_connected_test_database(connection, expected: NormalizedDatabaseTarget) -> None:
    """Fail closed unless the connected PostgreSQL database is the validated target."""
    from sqlalchemy import text

    actual = str(connection.execute(text("SELECT current_database()" )).scalar_one()).lower()
    if actual != expected.database:
        raise PytestDatabaseGuardError(
            "Connected database does not match the validated test target: "
            f"expected {expected.database!r}, got {actual!r}."
        )
    if not is_test_database_name(actual):
        raise PytestDatabaseGuardError(
            f"Connected database {actual!r} is not a permitted test database."
        )


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
            app_database_url=resolve_main_database_url(),
        )
    except PytestDatabaseGuardError as exc:
        _fail_guard(str(exc))

    os.environ["TEST_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"].strip()
    _GUARD_APPLIED = True
    return target


def bind_app_engine_to_test_database() -> str:
    """Point app.db.engine at TEST_DATABASE_URL after guard validation."""
    global _ENGINE_BOUND
    target = enforce_pytest_database_isolation()
    test_url = os.environ["TEST_DATABASE_URL"].strip()

    if _ENGINE_BOUND:
        return test_url

    from sqlalchemy import create_engine

    import app.db.engine as engine_module

    if getattr(engine_module.engine, "dispose", None):
        engine_module.engine.dispose()

    engine_module.DATABASE_URL = test_url
    guarded_engine = create_engine(
        test_url,
        pool_pre_ping=True,
        hide_parameters=True,
    )
    # Force a connection and validate the server-reported database before any
    # fixture, migration, or application code can issue DDL/DML.
    with guarded_engine.connect() as connection:
        assert_connected_test_database(connection, target)

    engine_module.engine = guarded_engine
    _ENGINE_BOUND = True
    return test_url


def get_validated_test_database_url() -> str:
    enforce_pytest_database_isolation()
    return os.environ["TEST_DATABASE_URL"].strip()

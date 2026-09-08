"""PostgreSQL integration coverage for the read-only Person/Employee IIN diagnostic."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "ops" / "diagnose_person_identity_iin_integrity.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("diagnose_person_identity_iin_integrity", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            return str(conn.execute(text("SELECT current_database()")).scalar_one()).lower() == "corpsite_test"
    except Exception:
        return False


@pytest.fixture
def diagnostic_schema():
    schema = f"iin_diag_{uuid4().hex[:18]}"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.execute(
            text(
                f"""
                CREATE TABLE {schema}.persons (
                    person_id BIGINT PRIMARY KEY,
                    person_status TEXT NOT NULL,
                    merged_into_person_id BIGINT NULL,
                    iin TEXT NULL
                );
                CREATE TABLE {schema}.employees (
                    employee_id BIGINT PRIMARY KEY,
                    person_id BIGINT NULL
                );
                CREATE TABLE {schema}.employee_identities (
                    identity_id BIGINT PRIMARY KEY,
                    employee_id BIGINT NOT NULL,
                    identity_type TEXT NOT NULL,
                    identity_value TEXT NOT NULL,
                    valid_to DATE NULL
                )
                """
            )
        )
    try:
        yield schema
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))


def _insert_person(conn, *, person_id: int, iin: str | None, status: str = "active", merged_into: int | None = None):
    conn.execute(
        text(
            "INSERT INTO {schema}.persons (person_id, person_status, merged_into_person_id, iin) "
            "VALUES (:person_id, :status, :merged_into, :iin)".replace("{schema}", conn.info["iin_schema"])
        ),
        {"person_id": person_id, "status": status, "merged_into": merged_into, "iin": iin},
    )


def _insert_employee(conn, *, employee_id: int, person_id: int | None):
    conn.execute(
        text(
            "INSERT INTO {schema}.employees (employee_id, person_id) VALUES (:employee_id, :person_id)".replace(
                "{schema}", conn.info["iin_schema"]
            )
        ),
        {"employee_id": employee_id, "person_id": person_id},
    )


def _insert_identity(
    conn,
    *,
    identity_id: int,
    employee_id: int,
    value: str,
    valid_to: str | None = None,
):
    conn.execute(
        text(
            "INSERT INTO {schema}.employee_identities "
            "(identity_id, employee_id, identity_type, identity_value, valid_to) "
            "VALUES (:identity_id, :employee_id, 'IIN', :value, :valid_to)".replace(
                "{schema}", conn.info["iin_schema"]
            )
        ),
        {"identity_id": identity_id, "employee_id": employee_id, "value": value, "valid_to": valid_to},
    )


def _report(schema: str):
    mod = _load_module()
    return mod.run_diagnostics(engine, schema=schema)


@pytest.mark.skipif(not _db_available(), reason="corpsite_test PostgreSQL not available")
def test_clean_schema_has_zero_counts(diagnostic_schema):
    report = _report(diagnostic_schema)
    assert report.database == "corpsite_test"
    assert report.transaction_read_only is True
    assert report.counts == {key: 0 for key in report.violations}
    assert report.violations == {key: [] for key in report.violations}


def test_unknown_cli_argument_is_technical_error_not_mutation(monkeypatch):
    mod = _load_module()
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    assert mod.main(["--apply"]) == mod.EXIT_TECHNICAL_ERROR


@pytest.mark.skipif(not _db_available(), reason="corpsite_test PostgreSQL not available")
def test_detects_each_iin_integrity_violation_class(diagnostic_schema):
    mod = _load_module()
    valid_a = "123456789012"
    valid_b = "210987654321"
    valid_c = "111122223333"
    invalid = "not-an-iin"
    with engine.begin() as conn:
        conn.info["iin_schema"] = diagnostic_schema
        _insert_person(conn, person_id=1, iin=invalid)
        _insert_person(conn, person_id=2, iin=valid_a)
        _insert_person(conn, person_id=3, iin=valid_a)
        _insert_person(conn, person_id=4, iin=valid_b)
        _insert_person(conn, person_id=5, iin=valid_c)
        _insert_person(conn, person_id=6, iin=None)
        _insert_employee(conn, employee_id=40, person_id=4)
        _insert_employee(conn, employee_id=50, person_id=5)
        _insert_employee(conn, employee_id=60, person_id=6)
        _insert_employee(conn, employee_id=70, person_id=None)
        _insert_employee(conn, employee_id=80, person_id=None)
        _insert_identity(conn, identity_id=401, employee_id=40, value=valid_c)
        _insert_identity(conn, identity_id=601, employee_id=60, value=valid_b)
        _insert_identity(conn, identity_id=701, employee_id=70, value=valid_c)
        _insert_identity(conn, identity_id=702, employee_id=70, value=valid_c)
        _insert_identity(conn, identity_id=801, employee_id=80, value=invalid)

    report = mod.run_diagnostics(engine, schema=diagnostic_schema)
    assert report.counts == {
        "invalid_active_person_iin_format": 1,
        "duplicate_active_person_iin": 2,
        "invalid_active_employee_identity_iin_format": 1,
        "duplicate_active_employee_identity_iin": 3,
        "linked_person_employee_iin_mismatch": 1,
        "linked_person_iin_missing_active_employee_identity": 2,
        "linked_employee_identity_person_iin_empty": 1,
        "multiple_active_employee_iin_identities": 2,
    }
    serialized = __import__("json").dumps(report.as_jsonable(), sort_keys=True)
    for raw_iin in (valid_a, valid_b, valid_c, invalid):
        assert raw_iin not in serialized
    assert report.violations["invalid_active_person_iin_format"] == [
        {"person_id": 1, "iin_last4": None}
    ]
    assert report.violations["duplicate_active_person_iin"] == [
        {"person_id": 2, "duplicate_count": 2, "iin_last4": "9012"},
        {"person_id": 3, "duplicate_count": 2, "iin_last4": "9012"},
    ]

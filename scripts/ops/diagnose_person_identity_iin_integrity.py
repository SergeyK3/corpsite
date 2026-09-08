#!/usr/bin/env python3
"""Read-only IIN integrity diagnostics for the approved Person identity backfill gate.

The command intentionally accepts no database argument and reads only
``TEST_DATABASE_URL``.  It refuses every target except loopback PostgreSQL database
``corpsite_test``.  It never writes data, even if unknown extra arguments are supplied.

Exit codes:
  0 - no violations;
  2 - one or more violations found;
  1 - safety or technical failure.

The JSON report never contains a full IIN.  Rows are represented with technical IDs and,
where useful, the last four decimal digits only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.url import URL, make_url


EXPECTED_DATABASE = "corpsite_test"
EXIT_OK = 0
EXIT_TECHNICAL_ERROR = 1
EXIT_VIOLATIONS_FOUND = 2

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_SAFE_SCHEMA_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")

VIOLATION_KEYS = (
    "invalid_active_person_iin_format",
    "duplicate_active_person_iin",
    "invalid_active_employee_identity_iin_format",
    "duplicate_active_employee_identity_iin",
    "linked_person_employee_iin_mismatch",
    "linked_person_iin_missing_active_employee_identity",
    "linked_employee_identity_person_iin_empty",
    "multiple_active_employee_iin_identities",
)


class DiagnosticSafetyError(RuntimeError):
    """Raised when a requested diagnostic target is not the isolated test database."""


@dataclass(frozen=True)
class DiagnosticReport:
    database: str
    transaction_read_only: bool
    counts: dict[str, int]
    violations: dict[str, list[dict[str, Any]]]

    @property
    def has_violations(self) -> bool:
        return any(self.counts.values())

    def as_jsonable(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "transaction_read_only": self.transaction_read_only,
            "counts": self.counts,
            "violations": self.violations,
        }


def _normalize_host(host: str | None) -> str:
    value = (host or "localhost").strip().lower()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return value


def _validated_test_url(raw_url: str | None) -> URL:
    if not raw_url or not raw_url.strip():
        raise DiagnosticSafetyError("TEST_DATABASE_URL is required; DATABASE_URL is never used.")
    try:
        url = make_url(raw_url.strip())
    except Exception as exc:
        raise DiagnosticSafetyError("TEST_DATABASE_URL is invalid.") from exc

    dialect = (url.drivername or "").split("+", 1)[0].lower()
    if dialect != "postgresql":
        raise DiagnosticSafetyError("TEST_DATABASE_URL must use PostgreSQL.")
    if _normalize_host(url.host) not in _LOCAL_HOSTS:
        raise DiagnosticSafetyError("TEST_DATABASE_URL must use a loopback host.")
    if (url.database or "").strip().lower() != EXPECTED_DATABASE:
        raise DiagnosticSafetyError("TEST_DATABASE_URL must target corpsite_test exactly.")
    return url


def _quoted_schema(schema: str) -> str:
    normalized = schema.strip().lower()
    if (
        not normalized
        or normalized[0] not in "abcdefghijklmnopqrstuvwxyz_"
        or any(char not in _SAFE_SCHEMA_CHARS for char in normalized)
    ):
        raise ValueError("Schema name is not a safe PostgreSQL identifier.")
    return normalized


def _last4(value: object) -> str | None:
    digits = "".join(char for char in str(value or "") if char.isdigit())
    return digits[-4:] if digits else None


def _safe_rows(rows: Iterable[Mapping[str, Any]], builder) -> list[dict[str, Any]]:
    """Build and deterministically sort rows without serializing raw identity values."""
    result = [builder(row) for row in rows]
    return sorted(result, key=lambda item: json.dumps(item, ensure_ascii=True, sort_keys=True))


def collect_diagnostics(conn: Connection, *, schema: str = "public") -> dict[str, list[dict[str, Any]]]:
    """Read all diagnostics from an already-open read-only PostgreSQL connection.

    ``schema`` is an internal test seam. CLI callers always use ``public``; PostgreSQL tests use
    a disposable schema with the same three relevant table shapes to exercise every violation
    class without modifying constraints in the real public schema.
    """
    q_schema = _quoted_schema(schema)
    persons = f"{q_schema}.persons"
    employees = f"{q_schema}.employees"
    identities = f"{q_schema}.employee_identities"

    def fetch(sql: str) -> list[Mapping[str, Any]]:
        return list(conn.execute(text(sql)).mappings())

    report: dict[str, list[dict[str, Any]]] = {}

    report["invalid_active_person_iin_format"] = _safe_rows(
        fetch(
            f"""
            SELECT person_id, iin
            FROM {persons}
            WHERE person_status = 'active'
              AND merged_into_person_id IS NULL
              AND NULLIF(BTRIM(iin), '') IS NOT NULL
              AND iin !~ '^[0-9]{{12}}$'
            """
        ),
        lambda row: {"person_id": int(row["person_id"]), "iin_last4": _last4(row["iin"])},
    )

    report["duplicate_active_person_iin"] = _safe_rows(
        fetch(
            f"""
            WITH duplicate_values AS (
                SELECT iin, COUNT(*) AS duplicate_count
                FROM {persons}
                WHERE person_status = 'active'
                  AND merged_into_person_id IS NULL
                  AND NULLIF(BTRIM(iin), '') IS NOT NULL
                GROUP BY iin
                HAVING COUNT(*) > 1
            )
            SELECT p.person_id, p.iin, d.duplicate_count
            FROM {persons} p
            JOIN duplicate_values d ON d.iin = p.iin
            WHERE p.person_status = 'active' AND p.merged_into_person_id IS NULL
            """
        ),
        lambda row: {
            "person_id": int(row["person_id"]),
            "duplicate_count": int(row["duplicate_count"]),
            "iin_last4": _last4(row["iin"]),
        },
    )

    report["invalid_active_employee_identity_iin_format"] = _safe_rows(
        fetch(
            f"""
            SELECT identity_id, employee_id, identity_value
            FROM {identities}
            WHERE identity_type = 'IIN'
              AND valid_to IS NULL
              AND identity_value !~ '^[0-9]{{12}}$'
            """
        ),
        lambda row: {
            "identity_id": int(row["identity_id"]),
            "employee_id": int(row["employee_id"]),
            "iin_last4": _last4(row["identity_value"]),
        },
    )

    report["duplicate_active_employee_identity_iin"] = _safe_rows(
        fetch(
            f"""
            WITH duplicate_values AS (
                SELECT identity_value, COUNT(*) AS duplicate_count
                FROM {identities}
                WHERE identity_type = 'IIN' AND valid_to IS NULL
                GROUP BY identity_value
                HAVING COUNT(*) > 1
            )
            SELECT ei.identity_id, ei.employee_id, ei.identity_value, d.duplicate_count
            FROM {identities} ei
            JOIN duplicate_values d ON d.identity_value = ei.identity_value
            WHERE ei.identity_type = 'IIN' AND ei.valid_to IS NULL
            """
        ),
        lambda row: {
            "identity_id": int(row["identity_id"]),
            "employee_id": int(row["employee_id"]),
            "duplicate_count": int(row["duplicate_count"]),
            "iin_last4": _last4(row["identity_value"]),
        },
    )

    report["linked_person_employee_iin_mismatch"] = _safe_rows(
        fetch(
            f"""
            SELECT p.person_id, e.employee_id, ei.identity_id, p.iin AS person_iin,
                   ei.identity_value AS employee_iin
            FROM {employees} e
            JOIN {persons} p ON p.person_id = e.person_id
            JOIN {identities} ei ON ei.employee_id = e.employee_id
            WHERE NULLIF(BTRIM(p.iin), '') IS NOT NULL
              AND ei.identity_type = 'IIN'
              AND ei.valid_to IS NULL
              AND ei.identity_value <> p.iin
            """
        ),
        lambda row: {
            "person_id": int(row["person_id"]),
            "employee_id": int(row["employee_id"]),
            "identity_id": int(row["identity_id"]),
            "person_iin_last4": _last4(row["person_iin"]),
            "employee_iin_last4": _last4(row["employee_iin"]),
        },
    )

    report["linked_person_iin_missing_active_employee_identity"] = _safe_rows(
        fetch(
            f"""
            SELECT p.person_id, e.employee_id, p.iin
            FROM {employees} e
            JOIN {persons} p ON p.person_id = e.person_id
            WHERE NULLIF(BTRIM(p.iin), '') IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM {identities} ei
                  WHERE ei.employee_id = e.employee_id
                    AND ei.identity_type = 'IIN'
                    AND ei.valid_to IS NULL
                    AND ei.identity_value = p.iin
              )
            """
        ),
        lambda row: {
            "person_id": int(row["person_id"]),
            "employee_id": int(row["employee_id"]),
            "person_iin_last4": _last4(row["iin"]),
        },
    )

    report["linked_employee_identity_person_iin_empty"] = _safe_rows(
        fetch(
            f"""
            SELECT p.person_id, e.employee_id, ei.identity_id, ei.identity_value
            FROM {employees} e
            JOIN {persons} p ON p.person_id = e.person_id
            JOIN {identities} ei ON ei.employee_id = e.employee_id
            WHERE NULLIF(BTRIM(p.iin), '') IS NULL
              AND ei.identity_type = 'IIN'
              AND ei.valid_to IS NULL
            """
        ),
        lambda row: {
            "person_id": int(row["person_id"]),
            "employee_id": int(row["employee_id"]),
            "identity_id": int(row["identity_id"]),
            "employee_iin_last4": _last4(row["identity_value"]),
        },
    )

    report["multiple_active_employee_iin_identities"] = _safe_rows(
        fetch(
            f"""
            WITH duplicate_employee_identities AS (
                SELECT employee_id, COUNT(*) AS active_iin_count
                FROM {identities}
                WHERE identity_type = 'IIN' AND valid_to IS NULL
                GROUP BY employee_id
                HAVING COUNT(*) > 1
            )
            SELECT ei.identity_id, ei.employee_id, ei.identity_value, d.active_iin_count
            FROM {identities} ei
            JOIN duplicate_employee_identities d ON d.employee_id = ei.employee_id
            WHERE ei.identity_type = 'IIN' AND ei.valid_to IS NULL
            """
        ),
        lambda row: {
            "identity_id": int(row["identity_id"]),
            "employee_id": int(row["employee_id"]),
            "active_iin_count": int(row["active_iin_count"]),
            "iin_last4": _last4(row["identity_value"]),
        },
    )

    return {key: report[key] for key in VIOLATION_KEYS}


def run_diagnostics(db_engine: Engine, *, schema: str = "public") -> DiagnosticReport:
    """Run the diagnostic in an explicit PostgreSQL read-only transaction."""
    with db_engine.connect() as conn:
        try:
            conn.execute(text("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY DEFERRABLE"))
            database, read_only = conn.execute(
                text("SELECT current_database(), current_setting('transaction_read_only')")
            ).one()
            if str(database).lower() != EXPECTED_DATABASE or read_only != "on":
                raise DiagnosticSafetyError("Read-only test-database verification failed.")
            violations = collect_diagnostics(conn, schema=schema)
            counts = {key: len(violations[key]) for key in VIOLATION_KEYS}
            return DiagnosticReport(
                database=EXPECTED_DATABASE,
                transaction_read_only=True,
                counts=counts,
                violations=violations,
            )
        finally:
            conn.rollback()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only IIN integrity diagnostics against corpsite_test only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    db_engine: Engine | None = None
    try:
        try:
            _parse_args(argv)
        except SystemExit:
            # argparse's conventional code 2 must never be mistaken for the documented
            # "violations found" result. Unknown options cannot enable a mutation path.
            return EXIT_TECHNICAL_ERROR
        url = _validated_test_url(os.environ.get("TEST_DATABASE_URL"))
        db_engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        report = run_diagnostics(db_engine)
        print(json.dumps(report.as_jsonable(), ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_VIOLATIONS_FOUND if report.has_violations else EXIT_OK
    except DiagnosticSafetyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_TECHNICAL_ERROR
    except Exception:
        # Do not serialize database driver details: values in a failed SQL operation must not
        # become an accidental identity-data disclosure through stderr.
        print("ERROR: IIN integrity diagnostic failed technically.", file=sys.stderr)
        return EXIT_TECHNICAL_ERROR
    finally:
        if db_engine is not None:
            db_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

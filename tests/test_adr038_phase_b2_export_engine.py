"""ADR-038 Phase B.2 — HR sync package export engine tests."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.employee_import_profile_override_service import (
    employee_overrides_available,
    upsert_employee_override,
)
from app.services.sync.export_service import SyncExportError, export_hr_sync_package
from app.services.sync.package_validator import validate_sync_package
from app.services.sync.package_schema import normalize_full_name
from tests.conftest import get_columns, insert_returning_id
from tests.db_sequence_helpers import sync_owned_sequence


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_phase_b2() -> None:
    with engine.connect() as conn:
        if not employee_overrides_available(conn):
            pytest.skip("employee_import_profile_overrides not available — run alembic upgrade head")
        row = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'employee_import_profile_overrides'
                  AND column_name = 'base_batch_id'
                """
            )
        ).first()
        if not row:
            pytest.skip("Phase A.1 columns not available — run alembic upgrade head")


def _create_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    is_active: bool = True,
) -> int:
    cols = get_columns(conn, "employees")
    values = {"full_name": full_name}
    if "org_unit_id" in cols:
        values["org_unit_id"] = org_unit_id
    if "is_active" in cols:
        values["is_active"] = is_active
    return insert_returning_id(conn, table="employees", id_col="employee_id", values=values)


def _attach_iin(conn, *, employee_id: int, iin_value: str, created_by: int) -> None:
    insert_returning_id(
        conn,
        table="employee_identities",
        id_col="identity_id",
        values={
            "employee_id": employee_id,
            "identity_type": "IIN",
            "identity_value": iin_value,
            "is_primary": True,
            "created_by": created_by,
        },
    )


def _export_at_fixed() -> datetime:
    return datetime(2026, 6, 17, 12, 30, 22, tzinfo=timezone.utc)


@pytest.fixture
def export_fixture(seed, tmp_path: Path):
    _require_phase_b2()
    suffix = uuid4().hex[:8]
    iin_value = f"{int(uuid4().int % 10**12):012d}"
    employee_with_iin: int | None = None
    employee_without_iin: int | None = None
    employee_unkeyed: int | None = None
    batch_id: int | None = None
    user_id = int(seed["initiator_user_id"])
    unit_id = int(seed["unit_id"])

    try:
        with engine.begin() as conn:
            employee_with_iin = _create_employee(
                conn,
                full_name=f"Иванов Иван Иванович {suffix}",
                org_unit_id=unit_id,
            )
            _attach_iin(conn, employee_id=employee_with_iin, iin_value=iin_value, created_by=user_id)

            employee_without_iin = _create_employee(
                conn,
                full_name=f"Петров Петр Петрович {suffix}",
                org_unit_id=unit_id,
            )

            employee_unkeyed = _create_employee(conn, full_name="   ", org_unit_id=unit_id)

            batch_id = insert_returning_id(
                conn,
                table="hr_import_batches",
                id_col="batch_id",
                values={
                    "source_type": "HR_CONTROL_LIST",
                    "file_name": f"control_list_{suffix}.xlsx",
                    "imported_by": user_id,
                    "status": "PARSED",
                    "total_rows": 1,
                    "valid_rows": 1,
                    "error_rows": 0,
                },
            )
            row_id = insert_returning_id(
                conn,
                table="hr_import_rows",
                id_col="row_id",
                values={
                    "batch_id": batch_id,
                    "source_sheet": "врачи",
                    "source_row_number": 8,
                    "raw_payload": "{}",
                    "normalized_payload": "{}",
                    "validation_status": "VALID",
                    "employee_id": employee_with_iin,
                },
            )

            upsert_employee_override(
                conn,
                employee_with_iin,
                profile={"notes": f"override with iin {suffix}"},
                updated_by=user_id,
                base_batch_id=batch_id,
                base_row_id=row_id,
                base_imported_at=datetime(2026, 6, 1, 9, 55, tzinfo=timezone.utc),
            )
            upsert_employee_override(
                conn,
                employee_without_iin,
                profile={"notes": f"override without iin {suffix}"},
                updated_by=user_id,
            )
            upsert_employee_override(
                conn,
                employee_unkeyed,
                profile={"notes": "should be skipped"},
                updated_by=user_id,
            )

        yield {
            "tmp_path": tmp_path,
            "suffix": suffix,
            "iin_value": iin_value,
            "employee_with_iin": employee_with_iin,
            "employee_without_iin": employee_without_iin,
            "employee_unkeyed": employee_unkeyed,
            "batch_id": batch_id,
            "user_id": user_id,
        }
    finally:
        with engine.begin() as conn:
            for employee_id in (
                employee_with_iin,
                employee_without_iin,
                employee_unkeyed,
            ):
                if employee_id:
                    conn.execute(
                        text(
                            "DELETE FROM public.employee_import_profile_overrides WHERE employee_id = :id"
                        ),
                        {"id": employee_id},
                    )
                    conn.execute(
                        text("DELETE FROM public.employee_identities WHERE employee_id = :id"),
                        {"id": employee_id},
                    )
                    conn.execute(
                        text("DELETE FROM public.employees WHERE employee_id = :id"),
                        {"id": employee_id},
                    )
            if batch_id:
                conn.execute(
                    text("DELETE FROM public.hr_import_rows WHERE batch_id = :id"),
                    {"id": batch_id},
                )
                conn.execute(
                    text("DELETE FROM public.hr_import_batches WHERE batch_id = :id"),
                    {"id": batch_id},
                )
            sync_owned_sequence(conn, "employees", "employee_id")
            sync_owned_sequence(conn, "employee_identities", "identity_id")
            sync_owned_sequence(conn, "hr_import_batches", "batch_id")
            sync_owned_sequence(conn, "hr_import_rows", "row_id")


def _run_export(tmp_path: Path, *, exported_at: datetime | None = None):
    with engine.connect() as conn:
        return export_hr_sync_package(
            conn,
            output_dir=tmp_path,
            source_instance_id="vps-pilot",
            source_organization={"id": "org-pilot-1", "name": "City Hospital Pilot"},
            environment="local",
            exported_at=exported_at or _export_at_fixed(),
        )


def _read_jsonl_archive(archive: zipfile.ZipFile, member: str) -> list[dict]:
    return [
        json.loads(line)
        for line in archive.read(member).decode("utf-8").splitlines()
        if line.strip()
    ]


def _fixture_export_slice(result, export_fixture) -> tuple[list[dict], list[dict], list[dict]]:
    keyed_employee_ids = {
        export_fixture["employee_with_iin"],
        export_fixture["employee_without_iin"],
    }
    unkeyed_employee_id = export_fixture["employee_unkeyed"]

    with zipfile.ZipFile(result.output_path) as archive:
        employees = _read_jsonl_archive(archive, "employees.jsonl")
        overrides = _read_jsonl_archive(archive, "employee_import_profile_overrides.jsonl")

    fixture_employees = [
        row for row in employees if row.get("source_employee_id") in keyed_employee_ids
    ]
    fixture_overrides = [
        row for row in overrides if row.get("source_employee_id") in keyed_employee_ids
    ]
    unkeyed_overrides = [
        row for row in overrides if row.get("source_employee_id") == unkeyed_employee_id
    ]
    return fixture_employees, fixture_overrides, unkeyed_overrides


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_export_creates_valid_package_from_db_fixtures(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])

    assert result.validation_ok is True
    assert result.output_path.exists()

    fixture_employees, fixture_overrides, unkeyed_overrides = _fixture_export_slice(
        result,
        export_fixture,
    )
    assert len(fixture_employees) == 2
    assert len(fixture_overrides) == 2
    assert unkeyed_overrides == []
    assert any(
        f"employee_id={export_fixture['employee_unkeyed']}" in warning
        for warning in result.warnings
    )

    validation = validate_sync_package(result.output_path)
    assert validation.ok is True


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_employees_exported_with_iin_employee_key(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])
    iin_value = export_fixture["iin_value"]

    with zipfile.ZipFile(result.output_path) as archive:
        employees = [
            json.loads(line)
            for line in archive.read("employees.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]

    iin_records = [row for row in employees if row.get("employee_key") == f"iin:{iin_value}"]
    assert len(iin_records) == 1
    assert iin_records[0]["iin"] == iin_value


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_employee_without_iin_uses_name_fallback(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])
    suffix = export_fixture["suffix"]
    expected_name = normalize_full_name(f"Петров Петр Петрович {suffix}")

    with zipfile.ZipFile(result.output_path) as archive:
        employees = [
            json.loads(line)
            for line in archive.read("employees.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]

    name_records = [row for row in employees if row.get("employee_key") == f"name:{expected_name}"]
    assert len(name_records) == 1
    assert name_records[0]["iin"] is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_overrides_exported_with_provenance(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])
    suffix = export_fixture["suffix"]
    iin_value = export_fixture["iin_value"]

    with zipfile.ZipFile(result.output_path) as archive:
        overrides = [
            json.loads(line)
            for line in archive.read("employee_import_profile_overrides.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]

    iin_override = next(row for row in overrides if row["employee_key"] == f"iin:{iin_value}")
    assert iin_override["profile_override"]["notes"] == f"override with iin {suffix}"
    assert iin_override["base_source_batch_id"] == export_fixture["batch_id"]
    assert iin_override["base_source_row_id"] is not None
    assert iin_override["base_source_file"] == f"control_list_{suffix}.xlsx"
    assert iin_override["base_imported_at"] is not None
    assert iin_override["source_employee_id"] == export_fixture["employee_with_iin"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_override_skipped_if_employee_key_cannot_be_built(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])

    assert result.skipped_override_count == 1
    assert any("cannot build employee_key" in warning for warning in result.warnings)

    with zipfile.ZipFile(result.output_path) as archive:
        overrides = [
            json.loads(line)
            for line in archive.read("employee_import_profile_overrides.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
    assert all(row["employee_key"] != "name:" for row in overrides)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_package_validates_after_export(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])
    validation = validate_sync_package(result.output_path)
    assert validation.ok is True
    assert validation.errors == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_output_file_name_follows_convention(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"], exported_at=_export_at_fixed())
    assert result.output_path.name == "corpsite_sync_vps-pilot_20260617_123022.zip"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_warnings_returned_for_skipped_records(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])
    assert result.skipped_override_count >= 1
    assert len(result.warnings) >= 1


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_export_fails_if_output_file_already_exists(export_fixture) -> None:
    tmp_path = export_fixture["tmp_path"]
    _run_export(tmp_path, exported_at=_export_at_fixed())

    with pytest.raises(SyncExportError, match="already exists"):
        _run_export(tmp_path, exported_at=_export_at_fixed())


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_metadata_includes_b2_extensions(export_fixture) -> None:
    result = _run_export(export_fixture["tmp_path"])

    with zipfile.ZipFile(result.output_path) as archive:
        metadata = json.loads(archive.read("metadata.json").decode("utf-8"))

    assert metadata["generated_by"] == "corpsite"
    assert metadata["environment"] == "local"
    assert "alembic_revision" in metadata
    assert "exported_by_user_login" in metadata

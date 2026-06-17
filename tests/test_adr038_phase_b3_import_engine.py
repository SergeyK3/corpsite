"""ADR-038 Phase B.3 — HR sync package import engine tests."""
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
    load_employee_override,
)
from app.services.sync.import_service import import_hr_sync_package, resolve_employee_key
from app.services.sync.package_schema import (
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    build_employee_key,
    normalize_full_name,
)
from app.services.sync.package_writer import write_sync_package
from tests.conftest import get_columns, insert_returning_id


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _require_phase_b3() -> None:
    with engine.connect() as conn:
        if not employee_overrides_available(conn):
            pytest.skip("employee_import_profile_overrides not available — run alembic upgrade head")


def _create_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
) -> int:
    cols = get_columns(conn, "employees")
    values = {"full_name": full_name}
    if "org_unit_id" in cols:
        values["org_unit_id"] = org_unit_id
    if "is_active" in cols:
        values["is_active"] = True
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


def _write_package(
    tmp_path: Path,
    *,
    employees: list[EmployeeSyncRecord],
    overrides: list[EmployeeImportProfileOverrideSyncRecord],
) -> Path:
    result = write_sync_package(
        tmp_path,
        source_instance_id="vps-pilot",
        source_organization={"id": "org-pilot-1", "name": "City Hospital Pilot"},
        employees=employees,
        overrides=overrides,
        environment="local",
        exported_at=datetime(2026, 6, 17, 15, 0, 0, tzinfo=timezone.utc),
        allow_overwrite=True,
    )
    return Path(result.output_path)


def _override_record(
    *,
    employee_key: str,
    notes: str,
) -> EmployeeImportProfileOverrideSyncRecord:
    return EmployeeImportProfileOverrideSyncRecord(
        employee_key=employee_key,
        profile_override={"notes": notes},
        profile_status="active",
        profile_review_status="pending",
        created_at="2026-06-01T10:00:00+00:00",
        updated_at="2026-06-15T12:30:00+00:00",
        base_imported_at="2026-06-01T09:55:00+00:00",
        base_source_file="control_list_june_2026.xlsx",
        base_source_batch_id=293,
        base_source_row_id=1201,
        source_employee_id=44,
        source_updated_by_user_id=3,
        created_by_login="hr.admin",
        updated_by_login="hr.admin",
    )


@pytest.fixture
def import_targets(seed):
    _require_phase_b3()
    suffix = uuid4().hex[:8]
    iin_value = f"{int(uuid4().int % 10**12):012d}"
    orphan_iin = f"{int(uuid4().int % 10**12):012d}"
    name_full = f"Петров Петр Петрович {suffix}"
    ambiguous_name = f"Дубликат Дубликат Дубликат {suffix}"

    employee_iin_id: int | None = None
    employee_name_id: int | None = None
    ambiguous_ids: list[int] = []
    user_id = int(seed["initiator_user_id"])
    unit_id = int(seed["unit_id"])

    try:
        with engine.begin() as conn:
            employee_iin_id = _create_employee(
                conn,
                full_name=f"Иванов Иван Иванович {suffix}",
                org_unit_id=unit_id,
            )
            _attach_iin(conn, employee_id=employee_iin_id, iin_value=iin_value, created_by=user_id)

            employee_name_id = _create_employee(
                conn,
                full_name=name_full,
                org_unit_id=unit_id,
            )

            ambiguous_ids = [
                _create_employee(conn, full_name=ambiguous_name, org_unit_id=unit_id),
                _create_employee(conn, full_name=ambiguous_name, org_unit_id=unit_id),
            ]

        yield {
            "suffix": suffix,
            "iin_value": iin_value,
            "orphan_iin": orphan_iin,
            "name_full": name_full,
            "ambiguous_name": ambiguous_name,
            "employee_iin_id": employee_iin_id,
            "employee_name_id": employee_name_id,
            "ambiguous_ids": ambiguous_ids,
        }
    finally:
        with engine.begin() as conn:
            for employee_id in [employee_iin_id, employee_name_id, *ambiguous_ids]:
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


def _package_for_targets(tmp_path: Path, targets: dict, *, notes: str = "import test") -> Path:
    iin_key = f"iin:{targets['iin_value']}"
    name_key = build_employee_key(full_name=targets["name_full"])
    ambiguous_key = build_employee_key(full_name=targets["ambiguous_name"])
    orphan_key = f"iin:{targets['orphan_iin']}"

    employees = [
        EmployeeSyncRecord(
            employee_key=iin_key,
            source_employee_id=targets["employee_iin_id"],
            full_name=f"Иванов Иван Иванович {targets['suffix']}",
            iin=targets["iin_value"],
            status="active",
        ),
        EmployeeSyncRecord(
            employee_key=name_key,
            source_employee_id=targets["employee_name_id"],
            full_name=targets["name_full"],
            status="active",
        ),
        EmployeeSyncRecord(
            employee_key=orphan_key,
            source_employee_id=999,
            full_name="Orphan Employee",
            iin=targets["orphan_iin"],
            status="active",
        ),
        EmployeeSyncRecord(
            employee_key=ambiguous_key,
            source_employee_id=999,
            full_name=targets["ambiguous_name"],
            status="active",
        ),
    ]
    overrides = [
        _override_record(employee_key=iin_key, notes=notes),
        _override_record(employee_key=name_key, notes=notes),
        _override_record(employee_key=orphan_key, notes=notes),
        _override_record(employee_key=ambiguous_key, notes=notes),
    ]
    return _write_package(tmp_path, employees=employees, overrides=overrides)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_valid_package_dry_run(import_targets, tmp_path: Path) -> None:
    package_path = _package_for_targets(tmp_path, import_targets)

    with engine.connect() as conn:
        result = import_hr_sync_package(conn, package_path=package_path, apply_changes=False)

    assert result.validation_ok is True
    assert result.dry_run is True
    assert result.override_records == 4
    assert result.resolved_count == 2
    assert result.orphan_count == 1
    assert result.ambiguous_count == 1
    assert result.applied_count == 0
    assert result.skipped_count == 2


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_valid_package_apply(import_targets, tmp_path: Path) -> None:
    package_path = _package_for_targets(tmp_path, import_targets, notes="applied override")

    with engine.begin() as conn:
        result = import_hr_sync_package(conn, package_path=package_path, apply_changes=True)

    assert result.validation_ok is True
    assert result.dry_run is False
    assert result.applied_count == 2

    with engine.connect() as conn:
        loaded = load_employee_override(conn, import_targets["employee_iin_id"])
    assert loaded is not None
    assert loaded["profile_override"]["notes"] == "applied override"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_orphan_employee(import_targets, tmp_path: Path) -> None:
    package_path = _package_for_targets(tmp_path, import_targets)

    with engine.connect() as conn:
        result = import_hr_sync_package(conn, package_path=package_path, apply_changes=False)

    assert result.orphan_count == 1
    assert any("employee_key not found" in warning for warning in result.warnings)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ambiguous_employee(import_targets, tmp_path: Path) -> None:
    package_path = _package_for_targets(tmp_path, import_targets)

    with engine.connect() as conn:
        result = import_hr_sync_package(conn, package_path=package_path, apply_changes=False)

    assert result.ambiguous_count == 1
    assert any("employee_key ambiguous" in warning for warning in result.warnings)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_iin_resolution(import_targets) -> None:
    with engine.connect() as conn:
        resolution = resolve_employee_key(conn, f"iin:{import_targets['iin_value']}")

    assert resolution.status.value == "RESOLVED"
    assert resolution.employee_id == import_targets["employee_iin_id"]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_name_fallback_resolution(import_targets) -> None:
    name_key = build_employee_key(full_name=import_targets["name_full"])
    with engine.connect() as conn:
        resolution = resolve_employee_key(conn, name_key)

    assert resolution.status.value == "RESOLVED"
    assert resolution.employee_id == import_targets["employee_name_id"]
    assert name_key == f"name:{normalize_full_name(import_targets['name_full'])}"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_upsert_existing_override(import_targets, tmp_path: Path) -> None:
    package_path_v1 = _package_for_targets(tmp_path / "v1", import_targets, notes="version 1")
    employees_v2 = [
        EmployeeSyncRecord(
            employee_key=f"iin:{import_targets['iin_value']}",
            full_name="Иванов",
            source_employee_id=import_targets["employee_iin_id"],
            iin=import_targets["iin_value"],
            status="active",
        )
    ]
    overrides_v2 = [
        EmployeeImportProfileOverrideSyncRecord(
            employee_key=f"iin:{import_targets['iin_value']}",
            profile_override={
                "notes": "version 1",
                "certificates": [{"kind": "Cert B", "topic": "topic", "date": "2021-01-01"}],
            },
            created_at="2026-06-01T10:00:00+00:00",
            updated_at="2026-06-15T12:30:00+00:00",
        )
    ]
    package_path_v2 = _write_package(tmp_path / "v2", employees=employees_v2, overrides=overrides_v2)

    with engine.begin() as conn:
        import_hr_sync_package(conn, package_path=package_path_v1, apply_changes=True)
    with engine.begin() as conn:
        import_hr_sync_package(conn, package_path=package_path_v2, apply_changes=True)

    with engine.connect() as conn:
        loaded = load_employee_override(conn, import_targets["employee_iin_id"])
    assert loaded is not None
    assert loaded["profile_override"]["notes"] == "version 1"
    assert loaded["profile_override"]["certificates"][0]["kind"] == "Cert B"


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_invalid_package_rejected(import_targets, tmp_path: Path) -> None:
    package_path = _package_for_targets(tmp_path, import_targets)
    broken_path = tmp_path / "broken.zip"
    with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(broken_path, "w") as dst:
        for item in src.infolist():
            if item.filename != "metadata.json":
                dst.writestr(item, src.read(item.filename))

    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM public.employee_import_profile_overrides")
        ).scalar()
        result = import_hr_sync_package(conn, package_path=broken_path, apply_changes=True)
        after = conn.execute(
            text("SELECT COUNT(*) FROM public.employee_import_profile_overrides")
        ).scalar()

    assert result.validation_ok is False
    assert result.applied_count == 0
    assert any("import aborted" in error for error in result.errors)
    assert before == after


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_dry_run_does_not_modify_db(import_targets, tmp_path: Path) -> None:
    package_path = _package_for_targets(tmp_path, import_targets, notes="dry-run only")

    with engine.connect() as conn:
        before = load_employee_override(conn, import_targets["employee_iin_id"])
    with engine.connect() as conn:
        result = import_hr_sync_package(conn, package_path=package_path, apply_changes=False)
    with engine.connect() as conn:
        after = load_employee_override(conn, import_targets["employee_iin_id"])

    assert result.applied_count == 0
    assert before == after


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_apply_mode_modifies_db(import_targets, tmp_path: Path) -> None:
    package_path = _package_for_targets(tmp_path, import_targets, notes="db modified")

    with engine.connect() as conn:
        before = load_employee_override(conn, import_targets["employee_iin_id"])
    with engine.begin() as conn:
        result = import_hr_sync_package(conn, package_path=package_path, apply_changes=True)
    with engine.connect() as conn:
        after = load_employee_override(conn, import_targets["employee_iin_id"])

    assert result.applied_count == 2
    assert before is None
    assert after is not None
    assert after["profile_override"]["notes"] == "db modified"
    if "_sync_provenance" in after["profile_override"]:
        provenance = after["profile_override"]["_sync_provenance"]
        assert provenance["base_source_file"] == "control_list_june_2026.xlsx"
        assert provenance["base_source_batch_id"] == 293

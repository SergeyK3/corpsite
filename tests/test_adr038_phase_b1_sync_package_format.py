"""ADR-038 Phase B.1 — sync package format tests."""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.services.sync.package_schema import (
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    build_employee_key,
)
from app.services.sync.package_validator import validate_sync_package
from app.services.sync.package_writer import write_sync_package


def _sample_employee(*, iin: str | None = "900101300123") -> EmployeeSyncRecord:
    if iin:
        return EmployeeSyncRecord(
            employee_key=f"iin:{iin}",
            source_employee_id=44,
            full_name="Иванов Иван Иванович",
            iin=iin,
            org_unit_key=None,
            position_key=None,
            status="active",
        )
    return EmployeeSyncRecord(
        employee_key=build_employee_key(full_name="Петров Петр Петрович"),
        source_employee_id=55,
        full_name="Петров Петр Петрович",
        iin=None,
        org_unit_key=None,
        position_key=None,
        status="active",
    )


def _sample_override(*, employee_key: str = "iin:900101300123") -> EmployeeImportProfileOverrideSyncRecord:
    return EmployeeImportProfileOverrideSyncRecord(
        employee_key=employee_key,
        profile_override={"notes": "уточнение HR"},
        profile_status="active",
        profile_review_status="pending",
        created_at="2026-06-01T10:00:00+00:00",
        updated_at="2026-06-15T12:30:00+00:00",
        created_by_login="hr.admin",
        updated_by_login="hr.admin",
        base_imported_at="2026-06-01T09:55:00+00:00",
        base_source_file="control_list_june_2026.xlsx",
        base_source_batch_id=293,
        base_source_row_id=1201,
        source_employee_id=44,
        source_updated_by_user_id=3,
    )


def _write_sample_package(tmp_path: Path) -> Path:
    result = write_sync_package(
        tmp_path,
        source_instance_id="vps-pilot",
        source_organization={"id": "org-pilot-1", "name": "City Hospital Pilot"},
        employees=[_sample_employee()],
        overrides=[_sample_override()],
        environment="local",
        exported_at=datetime(2026, 6, 17, 0, 0, 0, tzinfo=timezone.utc),
    )
    return Path(result.output_path)


def test_valid_package_passes_validator(tmp_path: Path) -> None:
    package_path = _write_sample_package(tmp_path)
    result = validate_sync_package(package_path)

    assert result.ok is True
    assert result.errors == []
    assert result.record_counts == {
        "employees.jsonl": 1,
        "employee_import_profile_overrides.jsonl": 1,
    }


def test_missing_required_file_fails(tmp_path: Path) -> None:
    package_path = _write_sample_package(tmp_path)
    broken_path = tmp_path / "broken_missing_metadata.zip"

    with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(broken_path, "w") as dst:
        for item in src.infolist():
            if item.filename != "metadata.json":
                dst.writestr(item, src.read(item.filename))

    result = validate_sync_package(broken_path)
    assert result.ok is False
    assert any("missing required file: metadata.json" in err for err in result.errors)


def test_checksum_mismatch_fails(tmp_path: Path) -> None:
    package_path = _write_sample_package(tmp_path)
    broken_path = tmp_path / "broken_checksum.zip"

    with zipfile.ZipFile(package_path, "r") as src:
        members = {name: src.read(name) for name in src.namelist()}
    members["employees.jsonl"] = b'{"employee_key":"tampered"}\n'
    with zipfile.ZipFile(broken_path, "w") as dst:
        for name, content in members.items():
            dst.writestr(name, content)

    result = validate_sync_package(broken_path)
    assert result.ok is False
    assert any("checksum mismatch for employees.jsonl" in err for err in result.errors)


def test_invalid_schema_version_major_fails(tmp_path: Path) -> None:
    package_path = _write_sample_package(tmp_path)
    broken_path = tmp_path / "broken_schema_major.zip"

    with zipfile.ZipFile(package_path, "r") as src:
        members = {name: src.read(name) for name in src.namelist()}

    manifest = json.loads(members["manifest.json"].decode("utf-8"))
    manifest["schema_version"] = "2.0"
    members["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    checksums = json.loads(members["checksums.json"].decode("utf-8"))
    checksums["files"]["manifest.json"] = hashlib.sha256(members["manifest.json"]).hexdigest()
    members["checksums.json"] = json.dumps(checksums, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    with zipfile.ZipFile(broken_path, "w") as dst:
        for name, content in members.items():
            dst.writestr(name, content)

    result = validate_sync_package(broken_path)
    assert result.ok is False
    assert any("schema_version major 2 exceeds reader major 1" in err for err in result.errors)


def test_employee_key_fallback_by_name_accepted(tmp_path: Path) -> None:
    employee = _sample_employee(iin=None)
    result = write_sync_package(
        tmp_path,
        source_instance_id="vps-pilot",
        source_organization={"id": "org-pilot-1", "name": "City Hospital Pilot"},
        employees=[employee],
        overrides=[
            _sample_override(employee_key=employee.employee_key),
        ],
        environment="local",
        exported_at=datetime(2026, 6, 17, 0, 0, 0, tzinfo=timezone.utc),
    )
    validation = validate_sync_package(Path(result.output_path))
    assert validation.ok is True
    assert employee.employee_key.startswith("name:")


def test_invalid_employee_key_rejected(tmp_path: Path) -> None:
    package_path = _write_sample_package(tmp_path)
    broken_path = tmp_path / "broken_employee_key.zip"

    with zipfile.ZipFile(package_path, "r") as src:
        members = {name: src.read(name) for name in src.namelist()}

    bad_record = {
        "employee_key": "bad-key",
        "source_employee_id": 44,
        "full_name": "Иванов Иван Иванович",
        "iin": "900101300123",
        "org_unit_key": None,
        "position_key": None,
        "status": "active",
    }
    members["employees.jsonl"] = (json.dumps(bad_record, ensure_ascii=False) + "\n").encode("utf-8")

    manifest = json.loads(members["manifest.json"].decode("utf-8"))
    manifest["record_counts"]["employees.jsonl"] = 1
    members["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    checksums = json.loads(members["checksums.json"].decode("utf-8"))
    for patched_name in ("employees.jsonl", "manifest.json"):
        checksums["files"][patched_name] = hashlib.sha256(members[patched_name]).hexdigest()
    members["checksums.json"] = json.dumps(checksums, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    with zipfile.ZipFile(broken_path, "w") as dst:
        for name, content in members.items():
            dst.writestr(name, content)

    result = validate_sync_package(broken_path)
    assert result.ok is False
    assert any("employee_key must be iin:" in err for err in result.errors)


def test_record_counts_mismatch_fails(tmp_path: Path) -> None:
    package_path = _write_sample_package(tmp_path)
    broken_path = tmp_path / "broken_record_counts.zip"

    with zipfile.ZipFile(package_path, "r") as src:
        members = {name: src.read(name) for name in src.namelist()}

    manifest = json.loads(members["manifest.json"].decode("utf-8"))
    manifest["record_counts"]["employees.jsonl"] = 99
    members["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    checksums = json.loads(members["checksums.json"].decode("utf-8"))
    checksums["files"]["manifest.json"] = hashlib.sha256(members["manifest.json"]).hexdigest()
    members["checksums.json"] = json.dumps(checksums, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    with zipfile.ZipFile(broken_path, "w") as dst:
        for name, content in members.items():
            dst.writestr(name, content)

    result = validate_sync_package(broken_path)
    assert result.ok is False
    assert any("record_counts mismatch for employees.jsonl" in err for err in result.errors)


def test_unknown_optional_file_emits_warning(tmp_path: Path) -> None:
    package_path = _write_sample_package(tmp_path)
    extra_path = tmp_path / "with_unknown_file.zip"

    with zipfile.ZipFile(package_path, "r") as src:
        members = {name: src.read(name) for name in src.namelist()}
    members["unexpected_extra.jsonl"] = b"{}\n"

    with zipfile.ZipFile(extra_path, "w") as dst:
        for name, content in members.items():
            dst.writestr(name, content)

    result = validate_sync_package(extra_path)
    assert result.ok is True
    assert any("unknown file in package (ignored): unexpected_extra.jsonl" in warn for warn in result.warnings)

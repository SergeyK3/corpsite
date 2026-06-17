"""ADR-038 Phase B.1 — sync package writer."""
from __future__ import annotations

import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.services.sync.package_schema import (
    EXPORT_SCOPE_HR_IMPORT_OVERRIDES,
    KNOWN_PACKAGE_FILES,
    MAX_READER_VERSION,
    OPTIONAL_PACKAGE_FILES,
    PACKAGE_VERSION,
    READER_VERSION,
    REQUIRED_PACKAGE_FILES,
    SCHEMA_VERSION,
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    SourceOrganization,
    SyncPackageWriteResult,
    encode_json,
    encode_jsonl,
    utc_now_iso,
)


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _package_filename(source_instance_id: str, exported_at: datetime) -> str:
    stamp = exported_at.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_instance = source_instance_id.strip().replace(" ", "_")
    return f"corpsite_sync_{safe_instance}_{stamp}.zip"


def write_sync_package(
    output_path: Path,
    *,
    source_instance_id: str,
    source_organization: dict[str, str] | SourceOrganization,
    employees: list[EmployeeSyncRecord],
    overrides: list[EmployeeImportProfileOverrideSyncRecord],
    optional_files: Optional[dict[str, list[dict[str, Any]]]] = None,
    environment: str = "local",
    notes: Optional[str] = None,
    exported_at: Optional[datetime] = None,
) -> SyncPackageWriteResult:
    """Build a v1 sync package zip from in-memory records (no DB export)."""
    if isinstance(source_organization, SourceOrganization):
        org = source_organization
    else:
        org = SourceOrganization(
            id=str(source_organization["id"]),
            name=str(source_organization["name"]),
        )

    export_moment = exported_at or datetime.now(timezone.utc)
    if export_moment.tzinfo is None:
        export_moment = export_moment.replace(tzinfo=timezone.utc)
    else:
        export_moment = export_moment.astimezone(timezone.utc)

    optional_files = optional_files or {}
    for filename in optional_files:
        if filename not in OPTIONAL_PACKAGE_FILES:
            raise ValueError(f"unsupported optional file: {filename}")

    file_contents: dict[str, bytes] = {}

    metadata = {
        "generated_by": "corpsite",
        "generated_at": export_moment.replace(microsecond=0).isoformat(),
        "environment": environment,
        "notes": notes,
    }
    file_contents["metadata.json"] = encode_json(metadata)

    employee_records = [record.to_dict() for record in employees]
    override_records = [record.to_dict() for record in overrides]
    file_contents["employees.jsonl"] = encode_jsonl(employee_records)
    file_contents["employee_import_profile_overrides.jsonl"] = encode_jsonl(override_records)

    for filename, records in optional_files.items():
        file_contents[filename] = encode_jsonl(records)

    record_counts = {
        "employees.jsonl": len(employee_records),
        "employee_import_profile_overrides.jsonl": len(override_records),
    }

    manifest = {
        "package_version": PACKAGE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "source_instance_id": source_instance_id.strip(),
        "source_organization": org.to_dict(),
        "exported_at": export_moment.replace(microsecond=0).isoformat(),
        "export_scope": EXPORT_SCOPE_HR_IMPORT_OVERRIDES,
        "required_files": sorted(REQUIRED_PACKAGE_FILES),
        "optional_files": sorted(OPTIONAL_PACKAGE_FILES),
        "record_counts": record_counts,
        "min_reader_version": READER_VERSION,
        "max_reader_version": MAX_READER_VERSION,
    }
    file_contents["manifest.json"] = encode_json(manifest)

    checksum_files = {
        name: _sha256_hex(content)
        for name, content in file_contents.items()
        if name in KNOWN_PACKAGE_FILES and name != "checksums.json"
    }
    checksums = {"algorithm": "sha256", "files": checksum_files}
    file_contents["checksums.json"] = encode_json(checksums)

    package_name = _package_filename(source_instance_id, export_moment)
    target_path = output_path if output_path.suffix == ".zip" else output_path / package_name
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(target_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(file_contents):
            archive.writestr(filename, file_contents[filename])

    return SyncPackageWriteResult(
        output_path=str(target_path),
        package_filename=target_path.name,
        record_counts=record_counts,
        checksums=checksum_files,
    )

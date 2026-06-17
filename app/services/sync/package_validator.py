"""ADR-038 Phase B.1 — sync package validator."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from app.services.sync.package_schema import (
    KNOWN_PACKAGE_FILES,
    OPTIONAL_PACKAGE_FILES,
    REQUIRED_PACKAGE_FILES,
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    SyncPackageValidationResult,
    validate_checksums_dict,
    validate_manifest_dict,
    validate_metadata_dict,
)


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _count_jsonl_records(content: bytes) -> int:
    text = content.decode("utf-8")
    if not text.strip():
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _read_zip_member(archive: zipfile.ZipFile, name: str) -> bytes:
    with archive.open(name) as handle:
        return handle.read()


def _validate_jsonl_file(
    filename: str,
    content: bytes,
    *,
    record_factory: Any,
) -> tuple[list[str], int]:
    errors: list[str] = []
    text = content.decode("utf-8")
    if not text.strip():
        return errors, 0

    count = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{filename}:{line_no}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{filename}:{line_no}: record must be a JSON object")
            continue
        _, record_err = record_factory(payload)
        if record_err:
            errors.append(f"{filename}:{line_no}: {record_err}")
            continue
        count += 1
    return errors, count


def validate_sync_package(package_path: Path) -> SyncPackageValidationResult:
    """Validate a sync package zip (format + checksums + record schemas)."""
    result = SyncPackageValidationResult(ok=True)

    if not package_path.exists():
        result.ok = False
        result.errors.append(f"package not found: {package_path}")
        return result

    try:
        archive = zipfile.ZipFile(package_path, mode="r")
    except zipfile.BadZipFile:
        result.ok = False
        result.errors.append("package is not a valid zip archive")
        return result

    with archive:
        member_names = {info.filename for info in archive.infolist() if not info.is_dir()}

        if "manifest.json" not in member_names:
            result.errors.append("missing required file: manifest.json")

        missing_required = sorted(REQUIRED_PACKAGE_FILES - member_names)
        for filename in missing_required:
            result.errors.append(f"missing required file: {filename}")

        unknown_members = sorted(member_names - KNOWN_PACKAGE_FILES)
        for filename in unknown_members:
            result.warnings.append(f"unknown file in package (ignored): {filename}")

        if missing_required or "manifest.json" not in member_names:
            result.ok = False
            return result

        try:
            manifest = json.loads(_read_zip_member(archive, "manifest.json").decode("utf-8"))
        except json.JSONDecodeError as exc:
            result.ok = False
            result.errors.append(f"manifest.json: invalid JSON: {exc.msg}")
            return result
        if not isinstance(manifest, dict):
            result.ok = False
            result.errors.append("manifest.json must be a JSON object")
            return result

        result.errors.extend(validate_manifest_dict(manifest))

        try:
            metadata = json.loads(_read_zip_member(archive, "metadata.json").decode("utf-8"))
        except json.JSONDecodeError as exc:
            result.errors.append(f"metadata.json: invalid JSON: {exc.msg}")
            metadata = None
        if isinstance(metadata, dict):
            result.errors.extend(validate_metadata_dict(metadata))
        else:
            result.errors.append("metadata.json must be a JSON object")

        try:
            checksums_payload = json.loads(_read_zip_member(archive, "checksums.json").decode("utf-8"))
        except json.JSONDecodeError as exc:
            result.errors.append(f"checksums.json: invalid JSON: {exc.msg}")
            checksums_payload = None
        if isinstance(checksums_payload, dict):
            result.errors.extend(validate_checksums_dict(checksums_payload, present_files=member_names))
        else:
            result.errors.append("checksums.json must be a JSON object")
            checksums_payload = None

        if isinstance(checksums_payload, dict):
            declared = checksums_payload.get("files", {})
            if isinstance(declared, dict):
                for filename, expected_digest in declared.items():
                    if filename not in member_names:
                        result.errors.append(f"checksum declared for missing file: {filename}")
                        continue
                    if not isinstance(expected_digest, str):
                        result.errors.append(f"checksum for {filename} must be a string")
                        continue
                    actual_digest = _sha256_hex(_read_zip_member(archive, filename))
                    if actual_digest != expected_digest:
                        result.errors.append(f"checksum mismatch for {filename}")

        jsonl_validators = {
            "employees.jsonl": EmployeeSyncRecord.from_dict,
            "employee_import_profile_overrides.jsonl": EmployeeImportProfileOverrideSyncRecord.from_dict,
        }
        actual_counts: dict[str, int] = {}
        for filename, factory in jsonl_validators.items():
            if filename not in member_names:
                continue
            file_errors, count = _validate_jsonl_file(
                filename,
                _read_zip_member(archive, filename),
                record_factory=factory,
            )
            result.errors.extend(file_errors)
            actual_counts[filename] = count

        for optional_name in sorted(OPTIONAL_PACKAGE_FILES):
            if optional_name in member_names:
                file_errors, count = _validate_jsonl_file(
                    optional_name,
                    _read_zip_member(archive, optional_name),
                    record_factory=lambda payload: (payload, None),
                )
                for err in file_errors:
                    if "invalid JSON" in err:
                        result.errors.append(err)
                    else:
                        result.warnings.append(err)
                actual_counts[optional_name] = count

        manifest_counts = manifest.get("record_counts", {})
        if isinstance(manifest_counts, dict):
            for filename in ("employees.jsonl", "employee_import_profile_overrides.jsonl"):
                expected = manifest_counts.get(filename)
                actual = actual_counts.get(filename, 0)
                if isinstance(expected, int) and expected != actual:
                    result.errors.append(
                        f"record_counts mismatch for {filename}: manifest={expected}, actual={actual}"
                    )

        result.record_counts = actual_counts

    result.ok = not result.errors
    return result

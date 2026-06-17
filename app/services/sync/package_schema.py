"""ADR-038 Phase B.1 — sync package schemas and validation helpers."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

PACKAGE_VERSION = "corpsite-sync-v1"
SCHEMA_VERSION = "1.0"
READER_VERSION = "1.0"
MAX_READER_VERSION = "1.x"

EXPORT_SCOPE_HR_IMPORT_OVERRIDES = "hr_import_overrides"
KNOWN_EXPORT_SCOPES = frozenset({EXPORT_SCOPE_HR_IMPORT_OVERRIDES})

REQUIRED_PACKAGE_FILES = frozenset(
    {
        "metadata.json",
        "employees.jsonl",
        "employee_import_profile_overrides.jsonl",
        "checksums.json",
    }
)
OPTIONAL_PACKAGE_FILES = frozenset(
    {
        "department_recoding.jsonl",
        "org_units.jsonl",
        "hr_import_batches.jsonl",
        "hr_import_rows.jsonl",
    }
)
KNOWN_PACKAGE_FILES = frozenset({"manifest.json"}) | REQUIRED_PACKAGE_FILES | OPTIONAL_PACKAGE_FILES

RECORD_COUNT_FILES = frozenset(
    {
        "employees.jsonl",
        "employee_import_profile_overrides.jsonl",
    }
)

_IIN_KEY_RE = re.compile(r"^iin:(\d{12})$")
_NAME_KEY_RE = re.compile(r"^name:(.+)$")
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)$")
@dataclass(frozen=True)
class SourceOrganization:
    id: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name}

    @classmethod
    def from_dict(cls, value: Any) -> tuple[Optional[SourceOrganization], Optional[str]]:
        if not isinstance(value, dict):
            return None, "source_organization must be an object with id and name"
        org_id = value.get("id")
        name = value.get("name")
        if not isinstance(org_id, str) or not org_id.strip():
            return None, "source_organization.id is required"
        if not isinstance(name, str) or not name.strip():
            return None, "source_organization.name is required"
        return cls(id=org_id.strip(), name=name.strip()), None


@dataclass(frozen=True)
class EmployeeSyncRecord:
    employee_key: str
    full_name: str
    source_employee_id: Optional[int] = None
    iin: Optional[str] = None
    org_unit_key: Optional[str] = None
    position_key: Optional[str] = None
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_key": self.employee_key,
            "source_employee_id": self.source_employee_id,
            "full_name": self.full_name,
            "iin": self.iin,
            "org_unit_key": self.org_unit_key,
            "position_key": self.position_key,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> tuple[Optional[EmployeeSyncRecord], Optional[str]]:
        employee_key = value.get("employee_key")
        if not isinstance(employee_key, str) or not employee_key.strip():
            return None, "employee_key is required"
        employee_key = employee_key.strip()

        full_name = value.get("full_name")
        if not isinstance(full_name, str) or not full_name.strip():
            return None, "full_name is required"

        iin = value.get("iin")
        if iin is not None and not isinstance(iin, str):
            return None, "iin must be a string or null"

        key_err = validate_employee_key(employee_key, iin=iin, full_name=full_name)
        if key_err:
            return None, key_err

        source_employee_id = value.get("source_employee_id")
        if source_employee_id is not None and not isinstance(source_employee_id, int):
            return None, "source_employee_id must be an integer or null"

        status = value.get("status", "active")
        if not isinstance(status, str) or not status.strip():
            return None, "status must be a non-empty string"

        return (
            cls(
                employee_key=employee_key,
                full_name=full_name.strip(),
                source_employee_id=source_employee_id,
                iin=iin,
                org_unit_key=value.get("org_unit_key"),
                position_key=value.get("position_key"),
                status=status.strip(),
            ),
            None,
        )


@dataclass(frozen=True)
class EmployeeImportProfileOverrideSyncRecord:
    employee_key: str
    profile_override: dict[str, Any]
    profile_status: str = "active"
    profile_review_status: str = "pending"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by_login: Optional[str] = None
    updated_by_login: Optional[str] = None
    base_imported_at: Optional[str] = None
    base_source_file: Optional[str] = None
    base_source_batch_id: Optional[int] = None
    base_source_row_id: Optional[int] = None
    source_employee_id: Optional[int] = None
    source_updated_by_user_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_key": self.employee_key,
            "profile_override": self.profile_override,
            "profile_status": self.profile_status,
            "profile_review_status": self.profile_review_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by_login": self.created_by_login,
            "updated_by_login": self.updated_by_login,
            "base_imported_at": self.base_imported_at,
            "base_source_file": self.base_source_file,
            "base_source_batch_id": self.base_source_batch_id,
            "base_source_row_id": self.base_source_row_id,
            "source_employee_id": self.source_employee_id,
            "source_updated_by_user_id": self.source_updated_by_user_id,
        }

    @classmethod
    def from_dict(
        cls, value: dict[str, Any]
    ) -> tuple[Optional[EmployeeImportProfileOverrideSyncRecord], Optional[str]]:
        employee_key = value.get("employee_key")
        if not isinstance(employee_key, str) or not employee_key.strip():
            return None, "employee_key is required"
        employee_key = employee_key.strip()

        key_err = validate_employee_key(employee_key)
        if key_err:
            return None, key_err

        profile_override = value.get("profile_override")
        if not isinstance(profile_override, dict):
            return None, "profile_override is required and must be an object"

        for int_field in ("base_source_batch_id", "base_source_row_id", "source_employee_id", "source_updated_by_user_id"):
            field_val = value.get(int_field)
            if field_val is not None and not isinstance(field_val, int):
                return None, f"{int_field} must be an integer or null"

        for ts_field in ("created_at", "updated_at", "base_imported_at"):
            ts_val = value.get(ts_field)
            if ts_val is not None:
                ts_err = validate_utc_timestamp(ts_val, field_name=ts_field)
                if ts_err:
                    return None, ts_err

        return (
            cls(
                employee_key=employee_key,
                profile_override=profile_override,
                profile_status=str(value.get("profile_status", "active")),
                profile_review_status=str(value.get("profile_review_status", "pending")),
                created_at=value.get("created_at"),
                updated_at=value.get("updated_at"),
                created_by_login=value.get("created_by_login"),
                updated_by_login=value.get("updated_by_login"),
                base_imported_at=value.get("base_imported_at"),
                base_source_file=value.get("base_source_file"),
                base_source_batch_id=value.get("base_source_batch_id"),
                base_source_row_id=value.get("base_source_row_id"),
                source_employee_id=value.get("source_employee_id"),
                source_updated_by_user_id=value.get("source_updated_by_user_id"),
            ),
            None,
        )


@dataclass(frozen=True)
class SyncPackageWriteResult:
    output_path: str
    package_filename: str
    record_counts: dict[str, int]
    checksums: dict[str, str]


@dataclass
class SyncPackageValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    record_counts: dict[str, int] = field(default_factory=dict)


def normalize_full_name(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def build_employee_key(*, iin: Optional[str] = None, full_name: Optional[str] = None) -> str:
    iin_digits = digits_only(iin or "")
    if len(iin_digits) == 12:
        return f"iin:{iin_digits}"
    normalized = normalize_full_name(full_name or "")
    if not normalized:
        raise ValueError("employee_key requires a valid IIN or full_name")
    return f"name:{normalized}"


def validate_employee_key(
    employee_key: str,
    *,
    iin: Optional[str] = None,
    full_name: Optional[str] = None,
) -> Optional[str]:
    iin_match = _IIN_KEY_RE.match(employee_key)
    if iin_match:
        if iin is not None:
            iin_digits = digits_only(iin)
            if iin_digits and iin_digits != iin_match.group(1):
                return "employee_key iin does not match record iin"
        return None

    name_match = _NAME_KEY_RE.match(employee_key)
    if name_match:
        if iin and digits_only(iin):
            return "employee_key must use iin: prefix when iin is present"
        normalized_key = name_match.group(1)
        if full_name is not None:
            normalized_name = normalize_full_name(full_name)
            if normalized_key != normalized_name:
                return "employee_key name does not match normalized full_name"
        return None

    return "employee_key must be iin:{12digits} or name:{normalized_full_name}"


def validate_utc_timestamp(value: Any, *, field_name: str) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return f"{field_name} must be an ISO-8601 UTC timestamp string"
    text_val = value.strip()
    if text_val.endswith("Z"):
        text_val = text_val[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text_val)
    except ValueError:
        return f"{field_name} must be a valid ISO-8601 timestamp"
    if parsed.tzinfo is None:
        return f"{field_name} must include a UTC timezone offset"
    utc_offset = parsed.utcoffset()
    if utc_offset is None or utc_offset.total_seconds() != 0:
        return f"{field_name} must use UTC (+00:00 or Z)"
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_semver(value: str) -> tuple[Optional[tuple[int, int]], Optional[str]]:
    match = _SEMVER_RE.match((value or "").strip())
    if not match:
        return None, f"invalid semver: {value!r}"
    return (int(match.group(1)), int(match.group(2))), None


def is_schema_version_compatible(schema_version: str) -> tuple[bool, Optional[str]]:
    parsed, err = parse_semver(schema_version)
    if err:
        return False, err
    reader_parsed, reader_err = parse_semver(READER_VERSION)
    if reader_err:
        return False, reader_err
    schema_major, schema_minor = parsed
    reader_major, reader_minor = reader_parsed
    if schema_major > reader_major:
        return False, f"schema_version major {schema_major} exceeds reader major {reader_major}"
    if schema_major == reader_major and schema_minor > reader_minor:
        return False, f"schema_version minor {schema_minor} exceeds reader minor {reader_minor}"
    return True, None


def validate_manifest_dict(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if value.get("package_version") != PACKAGE_VERSION:
        errors.append(f"package_version must be {PACKAGE_VERSION!r}")

    schema_version = value.get("schema_version")
    if not isinstance(schema_version, str):
        errors.append("schema_version is required")
    else:
        ok, err = is_schema_version_compatible(schema_version)
        if not ok and err:
            errors.append(err)

    source_instance_id = value.get("source_instance_id")
    if not isinstance(source_instance_id, str) or not source_instance_id.strip():
        errors.append("source_instance_id is required")

    _, org_err = SourceOrganization.from_dict(value.get("source_organization"))
    if org_err:
        errors.append(org_err)

    exported_at = value.get("exported_at")
    ts_err = validate_utc_timestamp(exported_at, field_name="exported_at")
    if ts_err:
        errors.append(ts_err)

    export_scope = value.get("export_scope")
    if not isinstance(export_scope, str) or export_scope not in KNOWN_EXPORT_SCOPES:
        errors.append(f"export_scope must be one of: {', '.join(sorted(KNOWN_EXPORT_SCOPES))}")

    required_files = value.get("required_files")
    if not isinstance(required_files, list):
        errors.append("required_files must be a list")
    else:
        required_set = set(required_files)
        if required_set != set(REQUIRED_PACKAGE_FILES):
            errors.append(
                "required_files must match the v1 contract: "
                + ", ".join(sorted(REQUIRED_PACKAGE_FILES))
            )

    optional_files = value.get("optional_files")
    if not isinstance(optional_files, list):
        errors.append("optional_files must be a list")
    else:
        optional_set = set(optional_files)
        if optional_set != set(OPTIONAL_PACKAGE_FILES):
            errors.append(
                "optional_files must match the v1 contract: "
                + ", ".join(sorted(OPTIONAL_PACKAGE_FILES))
            )

    for version_field in ("min_reader_version", "max_reader_version"):
        version_val = value.get(version_field)
        if not isinstance(version_val, str) or not version_val.strip():
            errors.append(f"{version_field} is required")

    record_counts = value.get("record_counts")
    if not isinstance(record_counts, dict):
        errors.append("record_counts must be an object")
    else:
        for filename in RECORD_COUNT_FILES:
            count = record_counts.get(filename)
            if not isinstance(count, int) or count < 0:
                errors.append(f"record_counts[{filename!r}] must be a non-negative integer")

    return errors


def validate_metadata_dict(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    generated_by = value.get("generated_by")
    if not isinstance(generated_by, str) or not generated_by.strip():
        errors.append("generated_by is required")

    generated_at = value.get("generated_at")
    ts_err = validate_utc_timestamp(generated_at, field_name="generated_at")
    if ts_err:
        errors.append(ts_err)

    environment = value.get("environment")
    if environment not in {"server", "local", "staging"}:
        errors.append("environment must be one of: server, local, staging")

    notes = value.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append("notes must be a string or null")

    return errors


def validate_checksums_dict(value: dict[str, Any], *, present_files: set[str]) -> list[str]:
    errors: list[str] = []

    if value.get("algorithm") != "sha256":
        errors.append("checksums.algorithm must be 'sha256'")

    files = value.get("files")
    if not isinstance(files, dict):
        errors.append("checksums.files must be an object")
        return errors

    if "checksums.json" in files:
        errors.append("checksums.json must not include a checksum for itself")

    for required_name in sorted((REQUIRED_PACKAGE_FILES - {"checksums.json"}) | {"manifest.json"}):
        if required_name not in files:
            errors.append(f"missing checksum for required file: {required_name}")

    for filename in files:
        if filename not in KNOWN_PACKAGE_FILES:
            errors.append(f"unknown file in checksums: {filename}")

    for optional_name in OPTIONAL_PACKAGE_FILES:
        if optional_name in present_files and optional_name not in files:
            errors.append(f"missing checksum for present optional file: {optional_name}")

    return errors


def encode_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def encode_jsonl(records: list[dict[str, Any]]) -> bytes:
    if not records:
        return b""
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    return ("\n".join(lines) + "\n").encode("utf-8")

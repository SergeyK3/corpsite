"""ADR-038 Phase B.4 / C.1 — HR sync package preview / diff engine."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.engine import Connection

from app.services.employee_import_profile_override_service import (
    employee_overrides_available,
    load_employee_override,
)
from app.services.sync.conflict_policy import (
    STATUS_CONFLICT,
    STATUS_IDENTICAL,
    STATUS_MERGE,
    STATUS_NEW,
    STATUS_UPDATE,
    SyncOverrideClassification,
    classify_sync_override,
    present_sections,
)
from app.services.sync.import_service import (
    EmployeeResolveStatus,
    _load_override_records,
    resolve_employee_key,
)
from app.services.sync.package_schema import EmployeeImportProfileOverrideSyncRecord
from app.services.sync.package_validator import validate_sync_package


@dataclass
class SyncPreviewItem:
    employee_key: str
    target_employee_id: Optional[int]
    status: str
    action: str
    reason: Optional[str]
    incoming_updated_at: Optional[str]
    target_updated_at: Optional[str]
    changed_sections: list[str] = field(default_factory=list)
    incoming_sections: list[str] = field(default_factory=list)
    target_sections: list[str] = field(default_factory=list)
    conflict_type: Optional[str] = None
    conflict_sections: list[str] = field(default_factory=list)
    apply_allowed: bool = False


@dataclass
class SyncPreviewResult:
    package_path: Path
    validation_ok: bool = False
    total_records: int = 0
    new_count: int = 0
    update_count: int = 0
    merge_count: int = 0
    identical_count: int = 0
    orphan_count: int = 0
    ambiguous_count: int = 0
    conflict_count: int = 0
    skipped_count: int = 0
    apply_allowed_count: int = 0
    items: list[SyncPreviewItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def preview_result_to_dict(result: SyncPreviewResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["package_path"] = str(result.package_path)
    return payload


def load_employee_name_map(package_path: Path) -> dict[str, str]:
    """Map employee_key → full_name from package employees.jsonl."""
    from app.services.sync.import_service import _read_jsonl_records

    names: dict[str, str] = {}
    for record in _read_jsonl_records(package_path, "employees.jsonl"):
        key = record.get("employee_key")
        name = record.get("full_name")
        if key and name:
            names[str(key)] = str(name).strip()
    return names


def preview_result_to_api_dict(result: SyncPreviewResult) -> dict[str, Any]:
    """Serialize preview for HTTP API — adds employee_name per item."""
    payload = preview_result_to_dict(result)
    name_map = load_employee_name_map(result.package_path)
    for item in payload.get("items") or []:
        if isinstance(item, dict):
            key = str(item.get("employee_key") or "")
            item["employee_name"] = name_map.get(key)
    return payload


def classification_to_preview_item(
    record: EmployeeImportProfileOverrideSyncRecord,
    *,
    employee_id: Optional[int],
    target_updated_at: Optional[str],
    classification: SyncOverrideClassification,
) -> SyncPreviewItem:
    return SyncPreviewItem(
        employee_key=record.employee_key,
        target_employee_id=employee_id,
        status=classification.status,
        action=classification.action,
        reason=classification.reason,
        incoming_updated_at=record.updated_at,
        target_updated_at=target_updated_at,
        changed_sections=classification.changed_sections,
        incoming_sections=classification.incoming_sections,
        target_sections=classification.target_sections,
        conflict_type=classification.conflict_type,
        conflict_sections=classification.conflict_sections,
        apply_allowed=classification.apply_allowed,
    )


def _increment_counts(result: SyncPreviewResult, item: SyncPreviewItem) -> None:
    if item.status == STATUS_NEW:
        result.new_count += 1
    elif item.status == STATUS_UPDATE:
        result.update_count += 1
    elif item.status == STATUS_MERGE:
        result.merge_count += 1
    elif item.status == STATUS_IDENTICAL:
        result.identical_count += 1
    elif item.status == "orphan":
        result.orphan_count += 1
    elif item.status == "ambiguous":
        result.ambiguous_count += 1
    elif item.status == STATUS_CONFLICT:
        result.conflict_count += 1

    if item.apply_allowed:
        result.apply_allowed_count += 1
    if item.action in {"skip", "review_required"}:
        result.skipped_count += 1


def preview_hr_sync_package(
    conn: Connection,
    *,
    package_path: Path,
) -> SyncPreviewResult:
    """Preview sync package import outcome without writing to the database."""
    result = SyncPreviewResult(package_path=package_path)

    if not employee_overrides_available(conn):
        result.errors.append(
            "employee_import_profile_overrides not available — run alembic upgrade head"
        )
        return result

    validation = validate_sync_package(package_path)
    result.validation_ok = validation.ok
    result.warnings.extend(validation.warnings)
    if not validation.ok:
        result.errors.extend(validation.errors)
        result.errors.append("preview aborted: package validation failed")
        return result

    try:
        override_records = _load_override_records(package_path)
    except Exception as exc:
        result.errors.append(str(exc))
        result.errors.append("preview aborted: failed to parse override records")
        return result

    result.total_records = len(override_records)

    for record in override_records:
        resolution = resolve_employee_key(conn, record.employee_key)
        if resolution.status == EmployeeResolveStatus.ORPHAN:
            incoming_sections = present_sections(record.profile_override)
            item = SyncPreviewItem(
                employee_key=record.employee_key,
                target_employee_id=None,
                status="orphan",
                action="skip",
                reason="employee_key not found",
                incoming_updated_at=record.updated_at,
                target_updated_at=None,
                incoming_sections=incoming_sections,
                changed_sections=incoming_sections,
                apply_allowed=False,
            )
            result.warnings.append(f"employee_key not found: {record.employee_key}")
        elif resolution.status == EmployeeResolveStatus.AMBIGUOUS:
            incoming_sections = present_sections(record.profile_override)
            item = SyncPreviewItem(
                employee_key=record.employee_key,
                target_employee_id=None,
                status="ambiguous",
                action="skip",
                reason=f"employee_key ambiguous candidates={list(resolution.candidate_ids)}",
                incoming_updated_at=record.updated_at,
                target_updated_at=None,
                incoming_sections=incoming_sections,
                changed_sections=incoming_sections,
                apply_allowed=False,
            )
            result.warnings.append(
                f"employee_key ambiguous: {record.employee_key} candidates={list(resolution.candidate_ids)}"
            )
        else:
            assert resolution.employee_id is not None
            target_override = load_employee_override(conn, resolution.employee_id)
            classification = classify_sync_override(record, target_override=target_override)
            item = classification_to_preview_item(
                record,
                employee_id=resolution.employee_id,
                target_updated_at=target_override.get("updated_at") if target_override else None,
                classification=classification,
            )

        result.items.append(item)
        _increment_counts(result, item)

    return result

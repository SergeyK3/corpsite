"""ADR-038 Phase B.4 — HR sync package preview / diff engine."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.engine import Connection

from app.services.employee_import_profile_override_service import (
    employee_overrides_available,
    load_employee_override,
)
from app.services.sync.import_service import (
    EmployeeResolveStatus,
    _load_override_records,
    _parse_iso_datetime,
    resolve_employee_key,
)
from app.services.sync.package_schema import EmployeeImportProfileOverrideSyncRecord
from app.services.sync.package_validator import validate_sync_package

EDITABLE_SECTIONS = (
    "education",
    "training",
    "categories",
    "certificates",
    "degree",
    "awards",
    "notes",
)

_SYNC_PROVENANCE_KEY = "_sync_provenance"


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


@dataclass
class SyncPreviewResult:
    package_path: Path
    validation_ok: bool = False
    total_records: int = 0
    new_count: int = 0
    update_count: int = 0
    identical_count: int = 0
    orphan_count: int = 0
    ambiguous_count: int = 0
    conflict_count: int = 0
    skipped_count: int = 0
    items: list[SyncPreviewItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def preview_result_to_dict(result: SyncPreviewResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["package_path"] = str(result.package_path)
    return payload


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _strip_sync_metadata(override: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in override.items() if key != _SYNC_PROVENANCE_KEY}


def _present_sections(override: dict[str, Any]) -> list[str]:
    return [section for section in EDITABLE_SECTIONS if section in override]


def _sections_differ(incoming: dict[str, Any], target: dict[str, Any], section: str) -> bool:
    incoming_has = section in incoming
    target_has = section in target
    if not incoming_has and not target_has:
        return False
    if incoming_has != target_has:
        return True
    return _stable_json(incoming.get(section)) != _stable_json(target.get(section))


def _diff_sections(
    incoming: dict[str, Any],
    target: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    incoming_clean = _strip_sync_metadata(incoming)
    target_clean = _strip_sync_metadata(target)
    incoming_sections = _present_sections(incoming_clean)
    target_sections = _present_sections(target_clean)
    candidate_sections = sorted(set(incoming_sections) | set(target_sections))
    changed_sections = [
        section for section in candidate_sections if _sections_differ(incoming_clean, target_clean, section)
    ]
    return incoming_sections, target_sections, changed_sections


def _overrides_identical(incoming: dict[str, Any], target: dict[str, Any]) -> bool:
    return _stable_json(_strip_sync_metadata(incoming)) == _stable_json(_strip_sync_metadata(target))


def _classify_resolved_override(
    record: EmployeeImportProfileOverrideSyncRecord,
    *,
    employee_id: int,
    target_override: Optional[dict[str, Any]],
) -> SyncPreviewItem:
    incoming_profile = record.profile_override
    incoming_updated_at = record.updated_at
    target_updated_at = target_override.get("updated_at") if target_override else None

    if not target_override:
        return SyncPreviewItem(
            employee_key=record.employee_key,
            target_employee_id=employee_id,
            status="new",
            action="insert",
            reason="no target override",
            incoming_updated_at=incoming_updated_at,
            target_updated_at=None,
            incoming_sections=_present_sections(incoming_profile),
            target_sections=[],
            changed_sections=_present_sections(incoming_profile),
        )

    target_profile = target_override.get("profile_override") or {}
    incoming_sections, target_sections, changed_sections = _diff_sections(incoming_profile, target_profile)

    if _overrides_identical(incoming_profile, target_profile):
        return SyncPreviewItem(
            employee_key=record.employee_key,
            target_employee_id=employee_id,
            status="identical",
            action="skip",
            reason="profile_override unchanged",
            incoming_updated_at=incoming_updated_at,
            target_updated_at=target_updated_at,
            incoming_sections=incoming_sections,
            target_sections=target_sections,
            changed_sections=[],
        )

    incoming_dt = _parse_iso_datetime(incoming_updated_at)
    target_dt = _parse_iso_datetime(target_updated_at)
    if target_dt and incoming_dt and target_dt > incoming_dt:
        return SyncPreviewItem(
            employee_key=record.employee_key,
            target_employee_id=employee_id,
            status="conflict",
            action="review_required",
            reason="target updated_at is newer than incoming",
            incoming_updated_at=incoming_updated_at,
            target_updated_at=target_updated_at,
            incoming_sections=incoming_sections,
            target_sections=target_sections,
            changed_sections=changed_sections,
        )

    return SyncPreviewItem(
        employee_key=record.employee_key,
        target_employee_id=employee_id,
        status="update",
        action="update",
        reason="incoming override differs from target",
        incoming_updated_at=incoming_updated_at,
        target_updated_at=target_updated_at,
        incoming_sections=incoming_sections,
        target_sections=target_sections,
        changed_sections=changed_sections,
    )


def _increment_counts(result: SyncPreviewResult, item: SyncPreviewItem) -> None:
    status = item.status
    if status == "new":
        result.new_count += 1
    elif status == "update":
        result.update_count += 1
    elif status == "identical":
        result.identical_count += 1
    elif status == "orphan":
        result.orphan_count += 1
    elif status == "ambiguous":
        result.ambiguous_count += 1
    elif status == "conflict":
        result.conflict_count += 1

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
            item = SyncPreviewItem(
                employee_key=record.employee_key,
                target_employee_id=None,
                status="orphan",
                action="skip",
                reason="employee_key not found",
                incoming_updated_at=record.updated_at,
                target_updated_at=None,
                incoming_sections=_present_sections(record.profile_override),
                target_sections=[],
                changed_sections=_present_sections(record.profile_override),
            )
            result.warnings.append(f"employee_key not found: {record.employee_key}")
        elif resolution.status == EmployeeResolveStatus.AMBIGUOUS:
            item = SyncPreviewItem(
                employee_key=record.employee_key,
                target_employee_id=None,
                status="ambiguous",
                action="skip",
                reason=f"employee_key ambiguous candidates={list(resolution.candidate_ids)}",
                incoming_updated_at=record.updated_at,
                target_updated_at=None,
                incoming_sections=_present_sections(record.profile_override),
                target_sections=[],
                changed_sections=_present_sections(record.profile_override),
            )
            result.warnings.append(
                f"employee_key ambiguous: {record.employee_key} candidates={list(resolution.candidate_ids)}"
            )
        else:
            assert resolution.employee_id is not None
            target_override = load_employee_override(conn, resolution.employee_id)
            item = _classify_resolved_override(
                record,
                employee_id=resolution.employee_id,
                target_override=target_override,
            )

        result.items.append(item)
        _increment_counts(result, item)

    return result

"""ADR-038 Phase C.1 — sync conflict policy and apply eligibility."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.sync.package_schema import (
    EmployeeImportProfileOverrideSyncRecord,
    parse_iso_datetime,
)

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

CONFLICT_TYPE_TARGET_NEWER = "TARGET_NEWER"
CONFLICT_TYPE_SECTION_OVERLAP = "SECTION_OVERLAP"

STATUS_NEW = "new"
STATUS_IDENTICAL = "identical"
STATUS_UPDATE = "update"
STATUS_MERGE = "merge"
STATUS_CONFLICT = "conflict"

ACTION_INSERT = "insert"
ACTION_UPDATE = "update"
ACTION_SKIP = "skip"
ACTION_REVIEW_REQUIRED = "review_required"


@dataclass
class SyncOverrideClassification:
    status: str
    action: str
    reason: Optional[str]
    apply_allowed: bool
    incoming_sections: list[str] = field(default_factory=list)
    target_sections: list[str] = field(default_factory=list)
    changed_sections: list[str] = field(default_factory=list)
    conflict_type: Optional[str] = None
    conflict_sections: list[str] = field(default_factory=list)
    merged_profile_override: Optional[dict[str, Any]] = None


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def strip_sync_metadata(override: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in override.items() if key != _SYNC_PROVENANCE_KEY}


def present_sections(override: dict[str, Any]) -> list[str]:
    return [section for section in EDITABLE_SECTIONS if section in override]


def sections_differ(incoming: dict[str, Any], target: dict[str, Any], section: str) -> bool:
    incoming_has = section in incoming
    target_has = section in target
    if not incoming_has and not target_has:
        return False
    if incoming_has != target_has:
        return True
    return _stable_json(incoming.get(section)) != _stable_json(target.get(section))


def diff_sections(
    incoming: dict[str, Any],
    target: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    incoming_clean = strip_sync_metadata(incoming)
    target_clean = strip_sync_metadata(target)
    incoming_sections = present_sections(incoming_clean)
    target_sections = present_sections(target_clean)
    candidate_sections = sorted(set(incoming_sections) | set(target_sections))
    changed_sections = [
        section for section in candidate_sections if sections_differ(incoming_clean, target_clean, section)
    ]
    return incoming_sections, target_sections, changed_sections


def overrides_identical(incoming: dict[str, Any], target: dict[str, Any]) -> bool:
    return _stable_json(strip_sync_metadata(incoming)) == _stable_json(strip_sync_metadata(target))


def overlapping_changed_sections(incoming: dict[str, Any], target: dict[str, Any]) -> list[str]:
    incoming_clean = strip_sync_metadata(incoming)
    target_clean = strip_sync_metadata(target)
    overlap: list[str] = []
    for section in EDITABLE_SECTIONS:
        if section in incoming_clean and section in target_clean:
            if _stable_json(incoming_clean.get(section)) != _stable_json(target_clean.get(section)):
                overlap.append(section)
    return overlap


def merge_profile_overrides(
    target_profile: dict[str, Any],
    incoming_profile: dict[str, Any],
) -> dict[str, Any]:
    """Scenario C — union of disjoint sections; per-section replace from incoming."""
    merged = copy.deepcopy(strip_sync_metadata(target_profile))
    incoming_clean = strip_sync_metadata(incoming_profile)
    for section in EDITABLE_SECTIONS:
        if section in incoming_clean:
            merged[section] = copy.deepcopy(incoming_clean[section])
    return merged


def classify_sync_override(
    record: EmployeeImportProfileOverrideSyncRecord,
    *,
    target_override: Optional[dict[str, Any]],
) -> SyncOverrideClassification:
    incoming_profile = record.profile_override

    if not target_override:
        incoming_sections = present_sections(incoming_profile)
        return SyncOverrideClassification(
            status=STATUS_NEW,
            action=ACTION_INSERT,
            reason="no target override",
            apply_allowed=True,
            incoming_sections=incoming_sections,
            target_sections=[],
            changed_sections=incoming_sections,
        )

    target_profile = target_override.get("profile_override") or {}
    incoming_sections, target_sections, changed_sections = diff_sections(incoming_profile, target_profile)

    if overrides_identical(incoming_profile, target_profile):
        return SyncOverrideClassification(
            status=STATUS_IDENTICAL,
            action=ACTION_SKIP,
            reason="profile_override unchanged",
            apply_allowed=False,
            incoming_sections=incoming_sections,
            target_sections=target_sections,
            changed_sections=[],
        )

    overlap_sections = overlapping_changed_sections(incoming_profile, target_profile)
    if overlap_sections:
        return SyncOverrideClassification(
            status=STATUS_CONFLICT,
            action=ACTION_REVIEW_REQUIRED,
            reason="overlapping sections changed on both sides",
            apply_allowed=False,
            conflict_type=CONFLICT_TYPE_SECTION_OVERLAP,
            conflict_sections=overlap_sections,
            incoming_sections=incoming_sections,
            target_sections=target_sections,
            changed_sections=changed_sections,
        )

    incoming_dt = parse_iso_datetime(record.updated_at)
    target_dt = parse_iso_datetime(target_override.get("updated_at"))
    if target_dt and incoming_dt and target_dt > incoming_dt:
        return SyncOverrideClassification(
            status=STATUS_CONFLICT,
            action=ACTION_REVIEW_REQUIRED,
            reason="target updated_at is newer than incoming",
            apply_allowed=False,
            conflict_type=CONFLICT_TYPE_TARGET_NEWER,
            incoming_sections=incoming_sections,
            target_sections=target_sections,
            changed_sections=changed_sections,
        )

    if changed_sections and (set(incoming_sections) - set(target_sections) or set(target_sections) - set(incoming_sections)):
        return SyncOverrideClassification(
            status=STATUS_MERGE,
            action=ACTION_UPDATE,
            reason="disjoint section changes can be merged",
            apply_allowed=True,
            incoming_sections=incoming_sections,
            target_sections=target_sections,
            changed_sections=changed_sections,
            merged_profile_override=merge_profile_overrides(target_profile, incoming_profile),
        )

    return SyncOverrideClassification(
        status=STATUS_UPDATE,
        action=ACTION_UPDATE,
        reason="incoming override differs from target",
        apply_allowed=True,
        incoming_sections=incoming_sections,
        target_sections=target_sections,
        changed_sections=changed_sections,
    )

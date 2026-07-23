"""Diff helpers for intake draft payloads."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.personnel_intake.domain.models import empty_intake_draft_payload

_DIFF_EXCLUDED_TOP_LEVEL_KEYS = frozenset({"current_step"})


def _normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_dict(template: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, str]:
    source = overlay or {}
    return {key: _normalize_scalar(source.get(key, template.get(key, ""))) for key in template}


def _normalize_list_items(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append({key: _normalize_scalar(value) for key, value in item.items()})
    return normalized


def canonicalize_intake_payload_for_diff(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Merge with empty template and normalize scalars for stable comparison."""
    template = empty_intake_draft_payload()
    source = payload or {}
    result = deepcopy(template)
    result["personal"] = _normalize_dict(template["personal"], source.get("personal"))
    result["contacts"] = _normalize_dict(template["contacts"], source.get("contacts"))
    result["military"] = _normalize_dict(template["military"], source.get("military"))
    result["education"] = _normalize_list_items(source.get("education"))
    result["training"] = _normalize_list_items(source.get("training"))
    result["relatives"] = _normalize_list_items(source.get("relatives"))
    result["employment_biography"] = _normalize_list_items(source.get("employment_biography"))
    additional = source.get("additional") or {}
    template_additional = template["additional"]
    result["additional"] = {
        "foreign_languages": _normalize_list_items(additional.get("foreign_languages")),
        "foreign_languages_none": _normalize_bool(additional.get("foreign_languages_none")),
        "awards": _normalize_list_items(additional.get("awards")),
        "awards_none": _normalize_bool(additional.get("awards_none")),
        "academic_degrees": _normalize_list_items(additional.get("academic_degrees")),
        "academic_degrees_none": _normalize_bool(additional.get("academic_degrees_none")),
        "academic_titles": _normalize_list_items(additional.get("academic_titles")),
        "academic_titles_none": _normalize_bool(additional.get("academic_titles_none")),
    }
    for key in template_additional:
        if key not in result["additional"]:
            result["additional"][key] = template_additional[key]
    result["current_step"] = _normalize_scalar(source.get("current_step", template["current_step"]))
    return result


def compute_intake_payload_field_changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Return sorted dotted paths of fields whose values changed."""
    left = canonicalize_intake_payload_for_diff(before)
    right = canonicalize_intake_payload_for_diff(after)
    for key in _DIFF_EXCLUDED_TOP_LEVEL_KEYS:
        left.pop(key, None)
        right.pop(key, None)

    changes: set[str] = set()

    def walk(path: str, left_value: Any, right_value: Any) -> None:
        if left_value == right_value:
            return
        if isinstance(left_value, dict) and isinstance(right_value, dict):
            keys = set(left_value.keys()) | set(right_value.keys())
            for key in sorted(keys):
                child_path = f"{path}.{key}" if path else str(key)
                walk(child_path, left_value.get(key), right_value.get(key))
            return
        if isinstance(left_value, list) and isinstance(right_value, list):
            if len(left_value) != len(right_value):
                changes.add(path or "payload")
                return
            for index, (left_item, right_item) in enumerate(zip(left_value, right_value)):
                walk(f"{path}[{index}]", left_item, right_item)
            return
        if path:
            changes.add(path)
        else:
            changes.add("payload")

    walk("", left, right)
    return sorted(changes)

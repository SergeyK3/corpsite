"""Programmatic catalog of allowed verification control points (ADR-060)."""
from __future__ import annotations

from dataclasses import dataclass

from app.db.models.personnel_verification import (
    ALLOWED_CONTROL_POINTS,
    CONTROL_POINT_EMPLOYMENT_EPISODE,
    CONTROL_POINT_MEDICAL_CATEGORY,
    OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
)


@dataclass(frozen=True, slots=True)
class ControlPointDefinition:
    control_point: str
    object_type: str | None
    has_canonical_typed_record: bool
    description: str


CONTROL_CATALOG: dict[str, ControlPointDefinition] = {
    CONTROL_POINT_EMPLOYMENT_EPISODE: ControlPointDefinition(
        control_point=CONTROL_POINT_EMPLOYMENT_EPISODE,
        object_type=OBJECT_TYPE_PERSON_EXTERNAL_EMPLOYMENT,
        has_canonical_typed_record=True,
        description="Employment episode in person_external_employment",
    ),
    CONTROL_POINT_MEDICAL_CATEGORY: ControlPointDefinition(
        control_point=CONTROL_POINT_MEDICAL_CATEGORY,
        object_type=None,
        has_canonical_typed_record=False,
        description=(
            "Medical qualification category; typed PPR home arrives in WP-VER-004"
        ),
    ),
}


def is_allowed_control_point(control_point: str) -> bool:
    return control_point in ALLOWED_CONTROL_POINTS


def get_control_point_definition(control_point: str) -> ControlPointDefinition:
    try:
        return CONTROL_CATALOG[control_point]
    except KeyError as exc:
        raise KeyError(f"Unknown control point: {control_point!r}") from exc


def supports_task_creation(control_point: str) -> bool:
    definition = get_control_point_definition(control_point)
    return definition.has_canonical_typed_record and definition.object_type is not None

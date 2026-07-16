"""PPR application command envelope (WP-PR-008 — not HTTP, not domain commands)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Application command type catalog (R5 minimum).
COMMAND_TYPE_MATERIALIZE_PPR = "MaterializePPR"
COMMAND_TYPE_START_COLLECTION = "StartCollection"
COMMAND_TYPE_ACTIVATE_PPR = "ActivatePPR"
COMMAND_TYPE_ADD_EDUCATION = "AddEducationRecord"
COMMAND_TYPE_UPDATE_EDUCATION = "UpdateEducationRecord"
COMMAND_TYPE_VOID_EDUCATION = "VoidEducationRecord"
COMMAND_TYPE_SUPERSEDE_EDUCATION = "SupersedeEducationRecord"
COMMAND_TYPE_ADD_TRAINING = "AddTrainingRecord"
COMMAND_TYPE_UPDATE_TRAINING = "UpdateTrainingRecord"
COMMAND_TYPE_VOID_TRAINING = "VoidTrainingRecord"
COMMAND_TYPE_SUPERSEDE_TRAINING = "SupersedeTrainingRecord"
COMMAND_TYPE_ADD_RELATIVE = "AddRelativeRecord"
COMMAND_TYPE_UPDATE_RELATIVE = "UpdateRelativeRecord"
COMMAND_TYPE_VOID_RELATIVE = "VoidRelativeRecord"
COMMAND_TYPE_SUPERSEDE_RELATIVE = "SupersedeRelativeRecord"
COMMAND_TYPE_ADD_EXTERNAL_EMPLOYMENT = "AddExternalEmploymentRecord"
COMMAND_TYPE_VOID_EXTERNAL_EMPLOYMENT = "VoidExternalEmploymentRecord"
COMMAND_TYPE_SUPERSEDE_EXTERNAL_EMPLOYMENT = "SupersedeExternalEmploymentRecord"
COMMAND_TYPE_CREATE_MILITARY_SERVICE = "CreateMilitaryServiceRecord"
COMMAND_TYPE_VOID_MILITARY_SERVICE = "VoidMilitaryServiceRecord"
COMMAND_TYPE_SUPERSEDE_MILITARY_SERVICE = "SupersedeMilitaryServiceRecord"


@dataclass(frozen=True, slots=True)
class PprCommandEnvelope:
    """Immutable application-level mutation request."""

    command_id: str
    command_type: str
    actor_id: str
    requested_at: datetime
    payload: Any
    person_id: int | None = None
    employee_id: int | None = None
    correlation_id: str | None = None
    source_event_id: str | None = None
    expected_envelope_version: int | None = None
    employee_context_id: int | None = None


@dataclass(frozen=True, slots=True)
class MaterializePprPayload:
    hr_relationship_context: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleCommandPayload:
    pass

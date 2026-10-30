"""Unlinked document subjects are snapshots, never personnel-card commands."""
from typing import Any, Mapping


def manual_subject_payload(subject: Mapping[str, Any]) -> dict[str, Any]:
    from app.services.personnel_orders_query_service import PersonnelOrderValidationError
    if not isinstance(subject, Mapping):
        raise PersonnelOrderValidationError("UNRESOLVED_SUBJECT_FIELDS_REQUIRED")
    values = {}
    for key in ("full_name", "org_unit_name", "position_name", "specialty"):
        value = subject.get(key, "")
        if not isinstance(value, str) or len(value) > 300:
            raise PersonnelOrderValidationError("INVALID_MANUAL_SUBJECT")
        values[key] = value.strip()
    if not values["full_name"]:
        raise PersonnelOrderValidationError("Укажите ФИО, введённое вручную.")
    return {
        "source_employee_name": values["full_name"],
        "source_org_unit_name": values["org_unit_name"],
        "source_position_name": values["position_name"],
        "unresolved_subject": {**values, "needs_employee_link": True, "input_mode": "manual"},
    }


def validate_manual_subject_links(payload: Mapping[str, Any]) -> None:
    from app.services.personnel_orders_query_service import PersonnelOrderValidationError
    recipient = payload.get("allowance_recipient") or {}
    if any(payload.get(key) not in (None, "") for key in ("assignment_id", "person_id")) or recipient.get("assignment_id") is not None:
        raise PersonnelOrderValidationError("Ручное ФИО не может ссылаться на кадровое назначение или карточку человека.")

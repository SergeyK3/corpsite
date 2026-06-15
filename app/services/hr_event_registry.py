# FILE: app/services/hr_event_registry.py
"""HR event type registry (ADR-036 Phase 1A)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional

EVENT_CLASS_EMPLOYMENT = "EMPLOYMENT"
EVENT_CLASS_PERSONNEL = "PERSONNEL"
EVENT_CLASS_CORRECTION = "CORRECTION"

PHASE_1A_CREATABLE: FrozenSet[str] = frozenset({"TRANSFER", "POSITION_CHANGE", "RATE_CHANGE"})


@dataclass(frozen=True)
class HREventDef:
    code: str
    event_class: str
    label_ru: str
    affects_snapshot: bool
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    subgroup: Optional[str] = None


HR_EVENT_REGISTRY: Dict[str, HREventDef] = {
    "HIRE": HREventDef(
        code="HIRE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Приём на работу",
        affects_snapshot=True,
        required_fields=("org_unit_id", "position_id", "effective_date"),
        optional_fields=("employment_rate", "department_id"),
    ),
    "TRANSFER": HREventDef(
        code="TRANSFER",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Перевод",
        affects_snapshot=True,
        required_fields=("to_org_unit_id", "effective_date"),
        optional_fields=("to_position_id", "to_rate", "order_ref", "comment"),
    ),
    "POSITION_CHANGE": HREventDef(
        code="POSITION_CHANGE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Смена должности",
        affects_snapshot=True,
        required_fields=("to_position_id", "effective_date"),
        optional_fields=("to_rate", "order_ref", "comment"),
    ),
    "RATE_CHANGE": HREventDef(
        code="RATE_CHANGE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Изменение ставки",
        affects_snapshot=True,
        required_fields=("to_rate", "effective_date"),
        optional_fields=("order_ref", "comment"),
    ),
    "TERMINATION": HREventDef(
        code="TERMINATION",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Увольнение",
        affects_snapshot=True,
        required_fields=("effective_date",),
        optional_fields=("metadata", "comment"),
    ),
    "REHIRE": HREventDef(
        code="REHIRE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Восстановление",
        affects_snapshot=True,
        required_fields=("org_unit_id", "position_id", "effective_date"),
        optional_fields=("employment_rate", "order_ref", "comment"),
    ),
    "ANNUAL_LEAVE": HREventDef(
        code="ANNUAL_LEAVE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Трудовой отпуск",
        affects_snapshot=True,
        required_fields=("period_start", "period_end", "effective_date"),
        optional_fields=("order_ref", "comment"),
    ),
    "MATERNITY_LEAVE": HREventDef(
        code="MATERNITY_LEAVE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Декретный отпуск",
        affects_snapshot=True,
        required_fields=("period_start", "period_end", "effective_date"),
        optional_fields=("order_ref", "comment"),
    ),
    "UNPAID_LEAVE": HREventDef(
        code="UNPAID_LEAVE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Отпуск без сохранения зарплаты",
        affects_snapshot=True,
        required_fields=("period_start", "period_end", "effective_date"),
        optional_fields=("order_ref", "comment"),
    ),
    "BONUS": HREventDef(
        code="BONUS",
        event_class=EVENT_CLASS_PERSONNEL,
        label_ru="Премия",
        subgroup="REWARD",
        affects_snapshot=False,
        required_fields=("effective_date",),
        optional_fields=("metadata", "order_ref", "comment"),
    ),
    "REMARK": HREventDef(
        code="REMARK",
        event_class=EVENT_CLASS_PERSONNEL,
        label_ru="Замечание",
        subgroup="DISCIPLINARY",
        affects_snapshot=False,
        required_fields=("effective_date", "comment"),
        optional_fields=("order_ref",),
    ),
    "REPRIMAND": HREventDef(
        code="REPRIMAND",
        event_class=EVENT_CLASS_PERSONNEL,
        label_ru="Выговор",
        subgroup="DISCIPLINARY",
        affects_snapshot=False,
        required_fields=("effective_date", "comment"),
        optional_fields=("order_ref",),
    ),
    "SEVERE_REPRIMAND": HREventDef(
        code="SEVERE_REPRIMAND",
        event_class=EVENT_CLASS_PERSONNEL,
        label_ru="Строгий выговор",
        subgroup="DISCIPLINARY",
        affects_snapshot=False,
        required_fields=("effective_date", "comment"),
        optional_fields=("order_ref",),
    ),
    "REPRIMAND_LIFT": HREventDef(
        code="REPRIMAND_LIFT",
        event_class=EVENT_CLASS_PERSONNEL,
        label_ru="Снятие выговора",
        subgroup="DISCIPLINARY",
        affects_snapshot=False,
        required_fields=("comment",),
        optional_fields=("metadata", "order_ref", "effective_date"),
    ),
    "CORRECTION": HREventDef(
        code="CORRECTION",
        event_class=EVENT_CLASS_CORRECTION,
        label_ru="Исправление данных",
        affects_snapshot=True,
        required_fields=("comment", "effective_date"),
        optional_fields=("to_org_unit_id", "to_position_id", "to_rate"),
    ),
}


def get_event_def(event_type: str) -> Optional[HREventDef]:
    return HR_EVENT_REGISTRY.get((event_type or "").strip().upper())


def get_event_class(event_type: str) -> str:
    defn = get_event_def(event_type)
    if defn is None:
        return EVENT_CLASS_EMPLOYMENT
    return defn.event_class


def get_event_label(event_type: str) -> str:
    defn = get_event_def(event_type)
    if defn is None:
        return str(event_type)
    return defn.label_ru


def is_creatable_in_phase_1a(event_type: str) -> bool:
    return (event_type or "").strip().upper() in PHASE_1A_CREATABLE


def list_registry_for_ui() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for code in sorted(HR_EVENT_REGISTRY.keys()):
        defn = HR_EVENT_REGISTRY[code]
        items.append(
            {
                "code": defn.code,
                "label_ru": defn.label_ru,
                "event_class": defn.event_class,
                "subgroup": defn.subgroup,
                "affects_snapshot": defn.affects_snapshot,
                "supported_in_phase_1a": defn.code in PHASE_1A_CREATABLE,
                "required_fields": list(defn.required_fields),
                "optional_fields": list(defn.optional_fields),
            }
        )
    return items

# FILE: app/services/hr_event_registry.py
"""HR event type registry (ADR-036 Phase 1A)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional

EVENT_CLASS_EMPLOYMENT = "EMPLOYMENT"
EVENT_CLASS_PERSONNEL = "PERSONNEL"
EVENT_CLASS_CORRECTION = "CORRECTION"
EVENT_CATEGORY_EMPLOYMENT = "EMPLOYMENT"
EVENT_CATEGORY_PERSONNEL = "PERSONNEL"
EVENT_CATEGORY_CORRECTION = "CORRECTION"
EVENT_CATEGORY_LEAVE = "LEAVE"
AUTOMATIC_EFFECT = "AUTOMATIC_EFFECT"
NO_AUTOMATIC_EFFECT = "NO_AUTOMATIC_EFFECT"
HR_EVENT_REGISTRY_VERSION = "1.1"
EVENT_CATEGORY_LABELS = {
    EVENT_CATEGORY_EMPLOYMENT: {"ru": "Трудовые отношения", "kk": "Еңбек қатынастары"},
    EVENT_CATEGORY_PERSONNEL: {"ru": "Кадровые события", "kk": "Кадрлық оқиғалар"},
    EVENT_CATEGORY_CORRECTION: {"ru": "Исправления", "kk": "Түзетулер"},
    EVENT_CATEGORY_LEAVE: {"ru": "Отпуска", "kk": "Демалыстар"},
}
LEAVE_KIND_LABELS = {
    "ANNUAL": {"ru": "Ежегодный оплачиваемый отпуск", "kk": "Жыл сайынғы ақылы демалыс"},
    "UNPAID": {"ru": "Отпуск без сохранения заработной платы", "kk": "Жалақы сақталмайтын демалыс"},
    "PAID_OTHER": {"ru": "Иной оплачиваемый отпуск", "kk": "Өзге ақылы демалыс"},
    "MATERNITY": {"ru": "Отпуск по беременности и родам", "kk": "Жүктілікке және босануға байланысты демалыс"},
    "CHILDCARE": {"ru": "Отпуск по уходу за ребёнком", "kk": "Бала күтіміне байланысты демалыс"},
}
LEAVE_OPERATION_LABELS = {
    "GRANT": {"ru": "Предоставление", "kk": "Берілетін"},
    "POSTPONE": {"ru": "Перенос", "kk": "Ауыстыру"},
    "EXTEND": {"ru": "Продление", "kk": "Ұзарту"},
    "RECALL": {"ru": "Отзыв", "kk": "Кері шақыру"},
    "EARLY_RETURN": {"ru": "Досрочный выход", "kk": "Мерзімінен бұрын шығу"},
}

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
    category: str = EVENT_CATEGORY_EMPLOYMENT
    label_kk: Optional[str] = None
    leave_kind: Optional[str] = None
    operation: Optional[str] = None
    automatic_effect: str = AUTOMATIC_EFFECT
    journal_filterable: bool = False


HR_EVENT_REGISTRY: Dict[str, HREventDef] = {
    "HIRE": HREventDef(
        code="HIRE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Приём на работу",
        affects_snapshot=True,
        required_fields=("org_unit_id", "position_id", "effective_date"),
        optional_fields=("employment_rate", "department_id"),
        category=EVENT_CATEGORY_EMPLOYMENT,
        label_kk="Жұмысқа қабылдау",
        journal_filterable=True,
    ),
    "TRANSFER": HREventDef(
        code="TRANSFER",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Перевод",
        affects_snapshot=True,
        required_fields=("to_org_unit_id", "effective_date"),
        optional_fields=("to_position_id", "to_rate", "order_ref", "comment"),
        category=EVENT_CATEGORY_EMPLOYMENT,
        label_kk="Ауыстыру",
        journal_filterable=True,
    ),
    "POSITION_CHANGE": HREventDef(
        code="POSITION_CHANGE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Смена должности",
        affects_snapshot=True,
        required_fields=("to_position_id", "effective_date"),
        optional_fields=("to_rate", "order_ref", "comment"),
        category=EVENT_CATEGORY_EMPLOYMENT,
        label_kk="Лауазымды өзгерту",
        journal_filterable=True,
    ),
    "RATE_CHANGE": HREventDef(
        code="RATE_CHANGE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Изменение ставки",
        affects_snapshot=True,
        required_fields=("to_rate", "effective_date"),
        optional_fields=("order_ref", "comment"),
        category=EVENT_CATEGORY_EMPLOYMENT,
        label_kk="Мөлшерлемені өзгерту",
        journal_filterable=True,
    ),
    "TERMINATION": HREventDef(
        code="TERMINATION",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Увольнение",
        affects_snapshot=True,
        required_fields=("effective_date",),
        optional_fields=("metadata", "comment"),
        category=EVENT_CATEGORY_EMPLOYMENT,
        label_kk="Жұмыстан босату",
        journal_filterable=True,
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
        category=EVENT_CATEGORY_LEAVE,
        label_kk="Еңбек демалысы",
        leave_kind="ANNUAL",
        operation="GRANT",
    ),
    "MATERNITY_LEAVE": HREventDef(
        code="MATERNITY_LEAVE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Декретный отпуск",
        affects_snapshot=True,
        required_fields=("period_start", "period_end", "effective_date"),
        optional_fields=("order_ref", "comment"),
        category=EVENT_CATEGORY_LEAVE,
        label_kk="Жүктілікке және босануға байланысты демалыс",
        leave_kind="MATERNITY",
        operation="GRANT",
    ),
    "UNPAID_LEAVE": HREventDef(
        code="UNPAID_LEAVE",
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru="Отпуск без сохранения зарплаты",
        affects_snapshot=True,
        required_fields=("period_start", "period_end", "effective_date"),
        optional_fields=("order_ref", "comment"),
        category=EVENT_CATEGORY_LEAVE,
        label_kk="Жалақы сақталмайтын демалыс",
        leave_kind="UNPAID",
        operation="GRANT",
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
        category=EVENT_CATEGORY_CORRECTION,
        label_kk="Деректерді түзету",
        journal_filterable=True,
    ),
    "EMPLOYEE_ENROLLED_FROM_IMPORT": HREventDef(
        code="EMPLOYEE_ENROLLED_FROM_IMPORT",
        event_class=EVENT_CLASS_PERSONNEL,
        label_ru="Добавлен в персонал из HR-импорта",
        affects_snapshot=False,
        required_fields=("effective_date",),
        optional_fields=("metadata", "comment"),
        category=EVENT_CATEGORY_PERSONNEL,
        label_kk="HR импортынан персоналға қосылды",
        journal_filterable=True,
    ),
}


def _leave_event(
    code: str,
    label_ru: str,
    label_kk: str,
    leave_kind: str | None,
    operation: str | None,
    *,
    automatic_effect: str = AUTOMATIC_EFFECT,
) -> HREventDef:
    return HREventDef(
        code=code,
        event_class=EVENT_CLASS_EMPLOYMENT,
        label_ru=label_ru,
        label_kk=label_kk,
        category=EVENT_CATEGORY_LEAVE,
        leave_kind=leave_kind,
        operation=operation,
        automatic_effect=automatic_effect,
        affects_snapshot=False,
        required_fields=("effective_date",),
        optional_fields=("metadata", "order_ref", "comment"),
        journal_filterable=True,
    )


HR_EVENT_REGISTRY.update(
    {
        "LEAVE.ANNUAL.GRANT": _leave_event(
            "LEAVE.ANNUAL.GRANT", "Ежегодный оплачиваемый отпуск", "Жыл сайынғы ақылы демалыс", "ANNUAL", "GRANT"
        ),
        "LEAVE.ANNUAL.POSTPONE": _leave_event(
            "LEAVE.ANNUAL.POSTPONE", "Перенос ежегодного отпуска", "Жыл сайынғы демалысты ауыстыру", "ANNUAL", "POSTPONE"
        ),
        "LEAVE.ANNUAL.EXTEND": _leave_event(
            "LEAVE.ANNUAL.EXTEND", "Продление ежегодного отпуска", "Жыл сайынғы демалысты ұзарту", "ANNUAL", "EXTEND"
        ),
        "LEAVE.ANNUAL.RECALL": _leave_event(
            "LEAVE.ANNUAL.RECALL", "Отзыв из ежегодного отпуска", "Жыл сайынғы демалыстан кері шақыру", "ANNUAL", "RECALL"
        ),
        "LEAVE.UNPAID.GRANT": _leave_event(
            "LEAVE.UNPAID.GRANT", "Отпуск без сохранения заработной платы", "Жалақы сақталмайтын демалыс", "UNPAID", "GRANT"
        ),
        "LEAVE.UNPAID.EARLY_RETURN": _leave_event(
            "LEAVE.UNPAID.EARLY_RETURN", "Досрочный выход из отпуска без сохранения заработной платы", "Жалақы сақталмайтын демалыстан мерзімінен бұрын шығу", "UNPAID", "EARLY_RETURN"
        ),
        "LEAVE.PAID_OTHER.GRANT": _leave_event(
            "LEAVE.PAID_OTHER.GRANT", "Иной оплачиваемый отпуск", "Өзге ақылы демалыс", "PAID_OTHER", "GRANT"
        ),
        "LEAVE.MATERNITY.GRANT": _leave_event(
            "LEAVE.MATERNITY.GRANT", "Отпуск по беременности и родам", "Жүктілікке және босануға байланысты демалыс", "MATERNITY", "GRANT"
        ),
        "LEAVE.CHILDCARE.GRANT": _leave_event(
            "LEAVE.CHILDCARE.GRANT", "Отпуск по уходу за ребёнком", "Бала күтіміне байланысты демалыс", "CHILDCARE", "GRANT"
        ),
        "LEAVE.UNCLASSIFIED": _leave_event(
            "LEAVE.UNCLASSIFIED", "Неклассифицированный отпуск", "Жіктелмеген демалыс", None, None,
            automatic_effect=NO_AUTOMATIC_EFFECT,
        ),
    }
)


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
                "label_kk": defn.label_kk,
                "category": defn.category,
                "category_label_ru": EVENT_CATEGORY_LABELS[defn.category]["ru"],
                "category_label_kk": EVENT_CATEGORY_LABELS[defn.category]["kk"],
                "event_class": defn.event_class,
                "subgroup": defn.subgroup,
                "leave_kind": defn.leave_kind,
                "operation": defn.operation,
                "leave_kind_label_ru": LEAVE_KIND_LABELS.get(defn.leave_kind or "", {}).get("ru"),
                "leave_kind_label_kk": LEAVE_KIND_LABELS.get(defn.leave_kind or "", {}).get("kk"),
                "operation_label_ru": LEAVE_OPERATION_LABELS.get(defn.operation or "", {}).get("ru"),
                "operation_label_kk": LEAVE_OPERATION_LABELS.get(defn.operation or "", {}).get("kk"),
                "automatic_effect": defn.automatic_effect,
                "journal_filterable": defn.journal_filterable,
                "affects_snapshot": defn.affects_snapshot,
                "supported_in_phase_1a": defn.code in PHASE_1A_CREATABLE,
                "required_fields": list(defn.required_fields),
                "optional_fields": list(defn.optional_fields),
            }
        )
    return items


def list_journal_registry_for_ui() -> List[Dict[str, Any]]:
    return [item for item in list_registry_for_ui() if item["journal_filterable"]]


def resolve_journal_event_codes(
    *,
    event_category: Optional[str] = None,
    event_type: Optional[str] = None,
    leave_kind: Optional[str] = None,
    leave_operation: Optional[str] = None,
) -> Optional[set[str]]:
    """Return the registry-backed code intersection for journal filters.

    ``None`` means that no classifier filter was supplied; an empty set is a
    valid, explicit no-match result.
    """
    raw_filters = (event_category, event_type, leave_kind, leave_operation)
    if not any(value is not None and str(value).strip() for value in raw_filters):
        return None

    normalized_category = (event_category or "").strip().upper() or None
    normalized_type = (event_type or "").strip().upper() or None
    normalized_kind = (leave_kind or "").strip().upper() or None
    normalized_operation = (leave_operation or "").strip().upper() or None
    items = [defn for defn in HR_EVENT_REGISTRY.values() if defn.journal_filterable]

    if normalized_category and normalized_category not in {defn.category for defn in items}:
        raise ValueError("Invalid event_category filter.")
    if normalized_type and normalized_type not in {defn.code for defn in items}:
        raise ValueError("Invalid event_type filter.")
    if normalized_kind and normalized_kind not in {defn.leave_kind for defn in items if defn.leave_kind}:
        raise ValueError("Invalid leave_kind filter.")
    if normalized_operation and normalized_operation not in {defn.operation for defn in items if defn.operation}:
        raise ValueError("Invalid leave_operation filter.")

    return {
        defn.code
        for defn in items
        if (normalized_category is None or defn.category == normalized_category)
        and (normalized_type is None or defn.code == normalized_type)
        and (normalized_kind is None or defn.leave_kind == normalized_kind)
        and (normalized_operation is None or defn.operation == normalized_operation)
    }

"""Single registry for the common personnel-order template editor contract.

Initial RU/KK draft texts and catalog projections are stored in the registry
verbatim.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.db.models.personnel_orders import ORDER_TYPE_COMPOSITE, PERSONNEL_ORDER_ITEM_TYPE_CODES
from app.services.personnel_order_template_catalog_data import CATALOG_PROJECTIONS
from app.services.personnel_order_template_initial_data import INITIAL_TEXTS_BY_TYPE

DraftTexts = Mapping[str, str]
RequiredVariables = Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class PersonnelOrderTemplateSpec:
    item_type_code: str
    support_level: str
    editor_available: bool
    allowed_variables: tuple[str, ...]
    required_variables: RequiredVariables
    initial_texts: DraftTexts
    preview_context: Mapping[str, Mapping[str, str]]
    required_fields: tuple[str, ...] = ()
    is_pilot: bool = False
    catalog_projection: Mapping[str, Any] | None = None



_COMMON = ("employee.full_name", "position.title_ru", "position.title_kk", "org_unit.title_ru", "org_unit.title_kk", "rate", "effective_date", "basis")
_LEAVE = ("employee.full_name", "position.title_ru", "position.title_kk", "org_unit.title_ru", "org_unit.title_kk", "leave.start_ru", "leave.start_kk", "leave.end_ru", "leave.end_kk", "leave.days", "basis")
_PREVIEW = {"ru": {"effective_date": "[[Дата выхода]]"}, "kk": {"effective_date": "[[Жұмысқа шығу күні]]"}}

def _spec(code: str, variables: tuple[str, ...], *, required: RequiredVariables = {}, preview: Mapping[str, Mapping[str, str]] = _PREVIEW) -> PersonnelOrderTemplateSpec:
    projection = CATALOG_PROJECTIONS[code]
    return PersonnelOrderTemplateSpec(code, projection['support_level'], projection['editor_available'], variables, required, INITIAL_TEXTS_BY_TYPE[code], preview, tuple(projection['required_fields']), projection['is_pilot'], projection)

from app.services.personnel_order_recall_contract import VARIABLES as RECALL_VARIABLES, REQUIRED_VARIABLES as RECALL_REQUIRED

PERSONNEL_ORDER_TEMPLATE_SPECS = {
    'LEAVE.ANNUAL.RECALL': _spec('LEAVE.ANNUAL.RECALL', RECALL_VARIABLES, required=RECALL_REQUIRED, preview={'ru': {'effective_date': '[[Дата отзыва]]'}, 'kk': {'effective_date': '[[Шақырту күні]]'}}),
    "HIRE": _spec("HIRE", _COMMON), "TRANSFER": _spec("TRANSFER", _COMMON),
    "TERMINATION": _spec("TERMINATION", ("employee.full_name", "position.title_ru", "position.title_kk", "org_unit.title_ru", "org_unit.title_kk", "effective_date", "effective_date_local", "termination.reason", "termination.unused_leave_days", "basis"), preview={"ru": {"effective_date": "[[Дата увольнения]]", "effective_date_local": "[[Дата увольнения]]"}, "kk": {"effective_date": "[[Жұмыстан босату күні]]", "effective_date_local": "[[Жұмыстан босату күні]]"}}),
    "CONCURRENT_DUTY_START": _spec("CONCURRENT_DUTY_START", ("employee.full_name", "effective_date", "concurrent.rate", "total.rate", "basis")),
    "CONCURRENT_DUTY_END": _spec("CONCURRENT_DUTY_END", ("employee.full_name", "effective_date", "concurrent.rate", "remaining.rate", "basis")),
    "LEAVE.ANNUAL.GRANT": _spec("LEAVE.ANNUAL.GRANT", _LEAVE),
    "LEAVE.CHILDCARE.GRANT": _spec("LEAVE.CHILDCARE.GRANT", _LEAVE[:-2]),
    "SUPPLEMENTARY_PAY": _spec("SUPPLEMENTARY_PAY", ("employee.full_name",)),
    "LEAVE.UNPAID.GRANT": _spec("LEAVE.UNPAID.GRANT", _LEAVE[:-1] + (
        "leave.period_text_ru", "leave.period_text_kk", "leave.period_clause_ru", "leave.period_clause_kk",
        "org_unit.document_genitive_kk", "position.document_possessive_kk", "position.document_nominative_ru",
        "employee.full_name_dative_ru", "employee.full_name_dative_kk", "employee.full_name_genitive_kk",
        "basis.application_date_ru", "basis.application_date_kk", "basis.application_number_suffix",
    ), required={
        "body_template_ru": ("employee.full_name_dative_ru", "position.document_nominative_ru", "org_unit.title_ru", "leave.period_clause_ru", "leave.days"),
        "body_template_kk": ("org_unit.document_genitive_kk", "position.document_possessive_kk", "employee.full_name_dative_kk", "leave.period_clause_kk"),
        "basis_template_kk": ("employee.full_name_genitive_kk",),
    }),
    "RETURN_FROM_CHILDCARE_LEAVE": _spec("RETURN_FROM_CHILDCARE_LEAVE", _COMMON, required={"body_template_ru": ("employee.full_name", "position.title_ru", "org_unit.title_ru", "rate", "effective_date"), "body_template_kk": ("employee.full_name", "position.title_kk", "org_unit.title_kk", "rate", "effective_date"), "basis_template_ru": ("basis",), "basis_template_kk": ("basis",)}),
}

def get_personnel_order_template_spec(item_type_code: str) -> PersonnelOrderTemplateSpec:
    try: return PERSONNEL_ORDER_TEMPLATE_SPECS[item_type_code]
    except KeyError as exc: raise ValueError("TEMPLATE_EDITOR_NOT_AVAILABLE") from exc

def assert_personnel_order_template_specs() -> None:
    expected = set(PERSONNEL_ORDER_ITEM_TYPE_CODES) - {ORDER_TYPE_COMPOSITE}
    assert set(PERSONNEL_ORDER_TEMPLATE_SPECS) == expected
    assert set(CATALOG_PROJECTIONS) == expected
    projection_keys = {
        "title_ru", "title_kk", "source", "support_level", "supported_locales",
        "uses_specialized_generator", "is_pilot", "editor_available", "required_fields",
        "notes", "pilot_detail", "template_detail",
    }
    for spec in PERSONNEL_ORDER_TEMPLATE_SPECS.values():
        assert all(set(required) <= set(spec.allowed_variables) for required in spec.required_variables.values())
        assert set(spec.initial_texts) == {"title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk"}
        assert isinstance(spec.required_fields, tuple)
        assert spec.catalog_projection is not None
        assert set(spec.catalog_projection) == projection_keys
        assert spec.catalog_projection["support_level"] == spec.support_level
        assert spec.catalog_projection["editor_available"] == spec.editor_available
        assert spec.catalog_projection["is_pilot"] == spec.is_pilot
        assert tuple(spec.catalog_projection["required_fields"]) == spec.required_fields

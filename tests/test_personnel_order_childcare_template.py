"""Childcare contract regressions: no production data or inferred child DOB."""
from copy import deepcopy
from datetime import date

import pytest

from app.services.personnel_order_childcare_contract import TYPE, TEXTS, childcare_values
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_draft_service import preview_draft, _validate, TemplateDraftError
from app.services.personnel_order_template_application_service import _render
from app.services.personnel_orders_editorial.mapper import build_item_ctx
from app.services.personnel_orders_editorial.generators import generate_item_body, generate_basis_text, generate_order_block
from app.services.personnel_orders_command_service import _validate_leave_draft_item


def childcare_payload():
    return {
        "leave_start": "2026-08-01", "leave_end": "2029-02-13", "leave_days": (date(2029, 2, 13) - date(2026, 8, 1)).days + 1,
        "org_unit_name": "Общебольничное отделение блока А отделения терапии и паллиативной помощи",
        "position_name": "Медицинская сестра",
        "basis": {"kind": "PERSONAL_APPLICATION", "date": "2026-07-28", "number": "APP-17", "birth_certificate": {"date": "2026-02-13", "number": "9967264"}},
        "document_forms_kk": {"org_unit_document_genitive_kk": "Терапия және паллиативтік көмек бөлімшесі А блогының жалпы аурухана бөлімшесінің", "position_document_possessive_kk": "мейіргері", "employee_full_name_dative_kk": "Асем Бауыржановна Садырбаеваға", "employee_full_name_genitive_kk": "Асем Бауыржановна Садырбаеваның"},
        "document_forms_ru": {"employee_full_name_dative_ru": "Садырбаевой Асем Бауыржановне", "employee_full_name_genitive_ru": "Садырбаевой Асем Бауыржановны", "position_document_nominative_ru": "медицинская сестра"},
    }


def test_childcare_both_generators_use_saved_forms_and_both_grounds():
    payload = childcare_payload()
    ctx = build_item_ctx({"item_type_code": TYPE, "payload": payload}, "Не использовать каноническое ФИО")
    values = childcare_values(payload, org_unit_ru=payload["org_unit_name"])
    rendered = _render({"item_type_code": TYPE, **TEXTS}, values)
    for lang in ("ru", "kk"):
        body = generate_item_body(lang, ctx)["generated_text"]
        basis = generate_basis_text(lang, ctx)["generated_text"]
        assert body == rendered[f"body_template_{lang}"]
        assert basis == rendered[f"basis_template_{lang}"]
        assert "APP-17" in basis and "9967264" in basis
        assert "{{" not in body + basis
        assert "Не использовать" not in body + basis
    assert "2026 жылғы 1 тамыз бен 2029 жылғы 13 ақпан аралығында" in rendered["body_template_kk"]
    assert "Асем Бауыржановна Садырбаеваға" in rendered["body_template_kk"]
    assert "2026 жылғы 13 ақпандағы № 9967264 туу туралы куәлік" in rendered["basis_template_kk"]


def test_certificate_issue_date_does_not_change_leave_end_or_application():
    payload = childcare_payload()
    before = deepcopy(payload)
    payload["basis"]["birth_certificate"]["date"] = "2027-04-20"
    values = childcare_values(payload, org_unit_ru=payload["org_unit_name"])
    assert values["leave.end_ru"] == "13 февраля 2029 года"
    assert values["basis.application_date_ru"] == " от 28 июля 2026 года"
    assert values["basis.birth_certificate_date_kk"] == "2027 жылғы 20 сәуірдегі"
    assert payload["leave_end"] == before["leave_end"]


@pytest.mark.parametrize("path", ["leave_start", "leave_end", "basis.date", "basis.birth_certificate.date", "basis.birth_certificate.number", "document_forms_kk.employee_full_name_genitive_kk", "document_forms_ru.employee_full_name_dative_ru"])
def test_required_childcare_requisites_block_incomplete_generation(path):
    payload = childcare_payload()
    parent = payload
    parts = path.split(".")
    for part in parts[:-1]: parent = parent[part]
    parent[parts[-1]] = ""
    with pytest.raises(ValueError): childcare_values(payload, org_unit_ru=payload["org_unit_name"])


def test_childcare_template_contract_preview_and_optional_application_number():
    spec = get_personnel_order_template_spec(TYPE)
    assert spec.support_level == "SUPPORTED" and spec.required_fields
    _validate(TEXTS, TYPE)
    preview = preview_draft(TYPE, TEXTS)
    for lang in ("ru", "kk"):
        assert "{{" not in str(preview[lang])
        assert preview[lang]["preamble"] == TEXTS[f"preamble_{lang}"]
    custom = dict(TEXTS, preamble_ru=TEXTS["preamble_ru"] + ", ПРИКАЗЫВАЮ:")
    assert preview_draft(TYPE, custom)["ru"]["preamble"] == TEXTS["preamble_ru"]
    assert custom["preamble_ru"].endswith("ПРИКАЗЫВАЮ:")  # never modify the user's stored fields
    for field in ("body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk"):
        invalid = dict(TEXTS, **{field: "Текст без обязательных переменных"})
        with pytest.raises(TemplateDraftError): _validate(invalid, TYPE)
    payload = childcare_payload()
    payload["basis"]["number"] = None
    rendered = _render({"item_type_code": TYPE, **TEXTS}, childcare_values(payload, org_unit_ru=payload["org_unit_name"]))
    assert "APP-17" not in rendered["basis_template_ru"]
    assert "9967264" in rendered["basis_template_ru"]


def test_childcare_command_validates_both_grounds_and_dates():
    payload = childcare_payload()
    kwargs = dict(item_type_code=TYPE, employee_id=123, effective_date=date(2026, 8, 1), period_start=date(2026, 8, 1), period_end=date(2029, 2, 13), payload=payload)
    _validate_leave_draft_item(**kwargs)
    with pytest.raises(ValueError): _validate_leave_draft_item(**{**kwargs, "period_end": date(2029, 2, 14)})
    assert generate_order_block("preamble", "kk", {"order_type_code": TYPE})["generated_text"] == TEXTS["preamble_kk"]

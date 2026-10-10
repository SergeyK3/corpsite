import pytest
from app.services.personnel_order_transfer_contract import transfer_values
from app.services.personnel_order_template_application_service import _render, TemplateApplicationError
from app.services.personnel_order_template_specs import get_personnel_order_template_spec

DATA = dict(position_ru="Врач", position_kk="Дәрігер", org_unit_ru="Терапия", org_unit_kk="Терапия бөлімшесі", rate=0.5, basis_ru="Заявление сотрудника", basis_kk="Қызметкердің өтініші")

def test_transfer_renders_bilingual_destination_rate_and_basis():
    values = {"employee.full_name": "Ильясова Ассель Адиловна", "effective_date": "2026-10-09", **transfer_values(DATA)}
    rendered = _render({**get_personnel_order_template_spec("TRANSFER").initial_texts, "item_type_code":"TRANSFER"}, values)
    assert "0.5" in rendered["body_template_ru"] and "0.5" in rendered["body_template_kk"]
    assert "Врач" in rendered["body_template_ru"] and "Дәрігер" in rendered["body_template_kk"]
    assert "Заявление сотрудника" in rendered["basis_template_ru"]
    assert "Қызметкердің өтініші" in rendered["basis_template_kk"]
    assert not any("{{" in v for v in rendered.values())

@pytest.mark.parametrize("rate", [0, -1, "NaN", "Infinity", "bad"])
def test_invalid_rate_is_rejected(rate):
    with pytest.raises(ValueError, match="Ставка после перевода"):
        transfer_values({**DATA, "rate": rate})

def test_missing_data_names_fields_in_russian():
    with pytest.raises(ValueError, match="основание перевода \\(KK\\)"):
        transfer_values({**DATA, "basis_kk": ""})
    with pytest.raises(TemplateApplicationError, match="ставка после перевода"):
        _render({**get_personnel_order_template_spec("TRANSFER").initial_texts, "item_type_code":"TRANSFER"}, {"employee.full_name":"Сотрудник", "effective_date":"2026-10-09"})

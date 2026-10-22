"""The template context must use Russian document wording on both transfer paths."""
from copy import deepcopy

import pytest

from app.services.personnel_order_template_application_service import _render, _values
from app.services.personnel_order_template_specs import get_personnel_order_template_spec


class NoEmployeeConnection:
    def execute(self, statement, parameters):
        assert parameters == {"id": None}
        return self

    def mappings(self):
        return self

    def first(self):
        return None


@pytest.mark.parametrize("rate,ru", [("1.0", "1,0"), ("0.5", "0,5")])
@pytest.mark.parametrize("manual_transfer", [False, True])
def test_transfer_preview_formats_dictionary_names_and_rate(rate, ru, manual_transfer):
    template = {
        **get_personnel_order_template_spec("TRANSFER").initial_texts,
        "item_type_code": "TRANSFER",
        "body_template_ru": (
            "Перевести {{employee.full_name}} в подразделение „{{org_unit.title_ru}}“ "
            "на должность „{{position.title_ru}}“ со ставкой {{rate}} с {{effective_date}}."
        ),
    }
    payload = {
        "document_forms_ru": {"employee_full_name_accusative_ru": "Ару Мұратқызы Амантай"},
        "employee": {"name": {"canonical": "Ару Мұратқызы Амантай"}},
        "source_position_name": "Медсестра",
        "source_org_unit_name": "Приемное",
        "position_name": {"ru": "Медсестра", "kk": "Мейіргер"},
        "org_unit_name": {"ru": "Приемное", "kk": "Қабылдау бөлімшесі"},
        "to_rate": rate,
        "basis": "Заявление сотрудника",
    }
    if manual_transfer:
        payload["transfer"] = {
            "position_id": 27, "org_unit_id": 56,
            "position_ru": "Медсестра", "position_kk": "Мейіргер",
            "org_unit_ru": "Приемное", "org_unit_kk": "Қабылдау бөлімшесі",
            "rate": rate, "basis_ru": "Заявление сотрудника", "basis_kk": "Өтініш",
        }
    item = {"item_id": 2294, "employee_id": None, "item_type_code": "TRANSFER",
            "effective_date": "2026-02-01", "payload": payload}
    before = deepcopy(item)
    values, warnings, missing = _values(NoEmployeeConnection(), item, template)
    rendered = _render(template, values, draft_preview=True)
    assert rendered["body_template_ru"] == (
        "Перевести Ару Мұратқызы Амантай в подразделение „приемное отделение“ "
        f"на должность „Медсестра“ со ставкой {ru} с 01.02.2026."
    )
    assert values["org_unit.title_kk"] == "Қабылдау бөлімшесі"
    assert values["rate"] == ("1" if manual_transfer and rate == "1.0" else rate)
    assert not warnings and not missing
    assert item == before

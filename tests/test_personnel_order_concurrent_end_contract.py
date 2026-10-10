from types import SimpleNamespace

import pytest

from app.services.personnel_order_concurrent_end_contract import BODY_RU, BODY_KK, PREVIEW_DATA, cessation_values
from app.services.personnel_order_template_application_service import _values, _render
from app.services.personnel_order_template_draft_service import preview_draft
from app.services.personnel_order_template_specs import get_personnel_order_template_spec


def texts():
    return {**get_personnel_order_template_spec("CONCURRENT_DUTY_END").initial_texts, "body_template_ru": BODY_RU, "body_template_kk": BODY_KK}


def test_preview_and_actual_render_match_without_main_assignment():
    class Conn:
        def execute(self, *args, **kwargs):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: dict(full_name="Турымов Алибек Рапхатович", position_name="Директор", org_unit_name="Администрация")))
    values, warnings, missing = _values(Conn(), dict(item_type_code="CONCURRENT_DUTY_END", employee_id=1, effective_date="2026-07-01", payload={"concurrent": PREVIEW_DATA}))
    rendered = _render({**texts(), "item_type_code": "CONCURRENT_DUTY_END"}, values, draft_preview=True)
    preview = preview_draft("CONCURRENT_DUTY_END", texts())
    assert not warnings and not missing
    assert rendered["body_template_ru"] == preview["ru"]["body"] == "Прекратить с 01.07.2026 совмещение Турымова Алибека Рапхатовича должности врача отделения терапии в объёме 0,5 ставки. (Всего: 1,0 ставки)."
    assert rendered["body_template_kk"] == preview["kk"]["body"] == "Алибек Рапхатович Турымовтан 2026 жылғы 1 шілдеден бастап терапия бөлімшесінің дәрігері қызметінен 0,5 ставкасы алынып тасталсын. (Барлығы: 1,0 ставка)."
    assert rendered["basis_template_ru"] == "Основание: личное заявление."
    assert rendered["basis_template_kk"] == "Негіз: жеке өтініш."
    for key in ("body_template_ru", "body_template_kk"):
        assert all(token not in rendered[key] for token in ("[", "{", "Директор", "Администрация", "контроль", "доплат"))


@pytest.mark.parametrize("remaining", ["0", "0.2", "0,75", "1.0", "2.5"])
def test_remaining_total_is_explicit_and_independent_of_removed_rate(remaining):
    values = cessation_values({**PREVIEW_DATA, "remaining_rate": remaining}, "2026-07-01")
    assert values["remaining.rate"] == (remaining.replace(".", ",") if "." in remaining or "," in remaining else remaining + ",0")


@pytest.mark.parametrize("key,value", [("remaining_rate", ""), ("remaining_rate", "NaN"), ("remaining_rate", -1), ("rate", 0), ("rate", "Infinity"), ("employee_genitive_ru", ""), ("employee_ablative_kk", ""), ("position_genitive_ru", ""), ("org_unit_kk", ""), ("basis_kk", "")])
def test_incomplete_or_invalid_inputs_require_confirmation(key, value):
    with pytest.raises(ValueError):
        cessation_values({**PREVIEW_DATA, key: value}, "2026-07-01")

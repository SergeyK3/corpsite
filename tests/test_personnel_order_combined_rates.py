from copy import deepcopy
import pytest

from app.services.personnel_order_combined_rates import validate_combined_rates
from app.services.personnel_order_template_application_service import _render
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_rate_format import format_template_rate


def items(rate="0.25", total="1.25", primary="1.0"):
    return [
        dict(item_id=1,item_number=1,item_type_code="TRANSFER",employee_id=1000,effective_date="2026-11-01",payload={"transfer":{"rate":primary}}),
        dict(item_id=2,item_number=2,item_type_code="CONCURRENT_DUTY_START",employee_id=1000,effective_date="2026-11-01",payload={"concurrent":{"rate":rate,"total_rate":total}}),
    ]


@pytest.mark.parametrize("rate,total", [("0.25","1.25"),("0.5","1.5"),("0.75","1.75"),("0.2","0.3")])
def test_exact_total_does_not_mutate_payload(rate,total):
    rows=items(rate,total,"0.1" if total=="0.3" else "1.0")
    before=deepcopy(rows)
    validate_combined_rates(rows)
    assert rows==before


def test_decimal_sum_exceeding_default_context_is_not_rounded():
    validate_combined_rates(items("0.00000000000000000000000000001", "1.00000000000000000000000000001"))


@pytest.mark.parametrize("total", ["1.1", "1.250000000000000000000000001", None, "NaN", "Infinity", "bad", "0"])
def test_incorrect_or_invalid_total_is_rejected(total):
    with pytest.raises(ValueError):validate_combined_rates(items(total=total))


@pytest.mark.parametrize("change", ["other_employee","other_date","replacement","standalone","cancelled"])
def test_unrelated_contracts_and_subjects_are_not_combined(change):
    rows=items(total="1.1")
    if change=="other_employee":rows[1]["employee_id"]=2000
    if change=="other_date":rows[1]["effective_date"]="2026-11-02"
    if change=="replacement":rows[1]["payload"]["replacement"]={"mode":"WORK_ALLOWANCE"}
    if change=="standalone":rows=rows[1:]
    if change=="cancelled":rows[0]["item_status"]="CANCELLED"
    validate_combined_rates(rows)


@pytest.mark.parametrize("rate,total", [("0.25","1.25"),("0.5","1.5"),("0.75","1.75")])
def test_renderer_formats_only_rate_variables_in_both_languages(rate,total):
    template={**get_personnel_order_template_spec("CONCURRENT_DUTY_START").initial_texts,"item_type_code":"CONCURRENT_DUTY_START"}
    template.update(body_template_ru="{{concurrent.rate}} / {{total.rate}}; 25.5%; 2026.11.01",body_template_kk="{{concurrent.rate}} / {{total.rate}}; 25.5%; 2026.11.01")
    values={"employee.full_name":"Тестов Тест Тестович","position.title_ru":"Врач","position.title_kk":"дәрігер","org_unit.title_ru":"Терапия","org_unit.title_kk":"Терапия","rate":"1","effective_date":"2026-11-01","basis":"Тест","concurrent.rate":rate,"total.rate":total}
    rendered=_render(template,values)
    for locale in ("ru","kk"):
        assert rendered[f"body_template_{locale}"]==f"{rate.replace('.', ',')} / {total.replace('.', ',')}; 25.5%; 2026.11.01"


def test_transfer_replaces_legacy_ru_dative_token_without_changing_kk():
    template={**get_personnel_order_template_spec("TRANSFER").initial_texts,"item_type_code":"TRANSFER"}
    template["body_template_ru"]="Перевести {{employee.full_name_dative_ru}}."
    template["body_template_kk"]="{{employee.full_name}}."
    values={"employee.full_name":"Тестов Тест Тестович","employee.full_name_accusative_ru":"Тестова Теста Тестовича","employee.full_name_dative_ru":"Тестову Тесту Тестовичу","position.title_ru":"Врач","position.title_kk":"дәрігер","org_unit.title_ru":"Терапия","org_unit.title_kk":"Терапия","rate":"1","effective_date":"2026-11-01","basis":"Тест"}
    rendered=_render(template,values)
    assert rendered["body_template_ru"]=="Перевести Тестова Теста Тестовича."
    assert rendered["body_template_kk"]=="Тестов Тест Тестович."


@pytest.mark.parametrize('token',['allowance.percent','leave.days','basis','effective_date'])
def test_non_rate_tokens_are_not_reformatted(token):
    assert format_template_rate('CONCURRENT_DUTY_START',token,'25.5')=='25.5'

from types import SimpleNamespace
import pytest
from app.services.personnel_order_concurrent_contract import concurrent_values
from app.services.personnel_order_template_application_service import _values, _render
from app.services.personnel_order_template_draft_service import preview_draft

DATA = dict(position_ru="Врач",position_kk="дәрігер",org_unit_ru="Терапия",org_unit_kk="терапия бөлімшесінің",position_genitive_ru="врача",org_unit_genitive_ru="отделения терапии",employee_dative_ru="Тулеутаеву Мухтару Есенжановичу",employee_dative_kk="Мухтар Есенжанович Тулеутаевқа",rate=0.5,total_rate=1.5,basis_ru="личное заявление",basis_kk="жеке өтініш")
TEXTS = dict(title_ru="О совмещении",title_kk="Қоса атқару туралы",preamble_ru="В соответствии со статьей 111 Трудового кодекса Республики Казахстан",preamble_kk="Қазақстан Республикасының Еңбек Кодексінің 111 - бабына сәйкес",body_template_ru="Разрешить {{employee.full_name_dative_ru}} с {{effective_date}} совмещение должности {{concurrent.position_genitive_ru}} {{concurrent.org_unit_genitive_ru}} на {{concurrent.rate}} ставки. (Всего: {{total.rate}} ставки).",body_template_kk="{{employee.full_name_dative_kk}} {{effective_date}} бастап {{concurrent.rate}} ставкада {{concurrent.org_unit_kk}} {{concurrent.position_kk}} қызметін қоса атқаруға рұқсат берілсін. (Барлығы: {{total.rate}} ставка).",basis_template_ru="Основание: {{basis}}.",basis_template_kk="Негіз: {{basis}}.")

def test_renderer_uses_additional_placement_and_never_main_position():
    class Conn:
        def execute(self,*args,**kwargs):
            return SimpleNamespace(mappings=lambda:SimpleNamespace(first=lambda:dict(full_name="Тулеутаев Мухтар Есенжанович",position_name="Директор",org_unit_name="Администрация")))
    values,_,missing=_values(Conn(),dict(item_type_code="CONCURRENT_DUTY_START",employee_id=1,effective_date="2026-05-21",payload={"concurrent":DATA}))
    texts=_render({**TEXTS,"item_type_code":"CONCURRENT_DUTY_START"},values,draft_preview=True)
    assert not missing
    assert "Тулеутаеву Мухтару Есенжановичу" in texts['body_template_ru']
    assert "2026 жылғы 21 мамырдан" in texts['body_template_kk']
    assert "врача отделения терапии" in texts['body_template_ru']
    assert "терапия бөлімшесінің дәрігер" in texts['body_template_kk']
    for key in ('body_template_ru','body_template_kk'):
        assert '0.5' in texts[key] and '1.5' in texts[key]
        assert 'Директор' not in texts[key] and 'Администрация' not in texts[key] and '{{' not in texts[key]

def test_saved_preview_has_dative_date_and_real_rates():
    preview=preview_draft('CONCURRENT_DUTY_START',TEXTS)
    assert '2026 жылғы 21 мамырдан' in preview['kk']['body']
    assert 'Иванову Ивану Ивановичу' in preview['ru']['body']
    assert 'с 21.05.2026' in preview['ru']['body']
    assert '0.5' in preview['ru']['body'] and '1.5' in preview['kk']['body']

@pytest.mark.parametrize('rate,total',[(0,1.5),(-1,1.5),('NaN',1.5),(0.5,0.5),(0.5,'Infinity')])
def test_invalid_rates_block_creation(rate,total):
    with pytest.raises(ValueError):concurrent_values({**DATA,'rate':rate,'total_rate':total},'2026-05-21')

def test_missing_document_form_names_the_field():
    with pytest.raises(ValueError,match='дополнительная должность в родительном падеже'):
        concurrent_values({**DATA,'position_genitive_ru':''},'2026-05-21')

def test_concurrent_july_start_date_is_localized_without_iso():
    texts=_render({**TEXTS,"item_type_code":"CONCURRENT_DUTY_START"},concurrent_values(DATA,'2026-07-03'),draft_preview=True)
    assert 'с 03.07.2026' in texts['body_template_ru']
    assert '2026 жылғы 3 шілдеден бастап' in texts['body_template_kk']
    assert '2026-07-03' not in texts['body_template_ru'] and '2026-07-03' not in texts['body_template_kk']

from types import SimpleNamespace
import pytest
from app.services.personnel_order_template_application_service import _values,_render
from app.services.personnel_order_template_specs import get_personnel_order_template_spec

@pytest.mark.parametrize('day,ru,kk',[('2026-07-03','03.07.2026','2026 жылғы 3 шілдеден'),('2026-05-21','21.05.2026','2026 жылғы 21 мамырдан')])
def test_transfer_date_substitution_preserves_storage(day,ru,kk):
    class Conn:
        def execute(self,*args,**kwargs):return SimpleNamespace(mappings=lambda:SimpleNamespace(first=lambda:dict(full_name='Сотрудник',position_name='Врач',org_unit_name='Терапия')))
    payload={'transfer':dict(position_ru='Врач',position_kk='дәрігер',org_unit_ru='Терапия',org_unit_kk='терапия бөлімшесі',rate=1,basis_ru='заявление',basis_kk='өтініш')}
    item=dict(item_type_code='TRANSFER',employee_id=1,effective_date=day,payload=payload)
    values,_,missing=_values(Conn(),item)
    texts=_render({**get_personnel_order_template_spec('TRANSFER').initial_texts,'item_type_code':'TRANSFER'},values)
    assert not missing and item['effective_date']==day
    assert ru in texts['body_template_ru'] and kk in texts['body_template_kk']
    assert day not in texts['body_template_ru'] and day not in texts['body_template_kk']

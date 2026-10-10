from copy import deepcopy
import pytest
from app.services.personnel_order_replacement_contract import RATE_RU,RATE_KK,PAY_RU,PAY_KK,SAMPLE_CONCURRENT,SAMPLE_REPLACEMENT,replacement_values,validate_bodies
from app.services.personnel_order_template_application_service import _render
from app.services.personnel_order_template_draft_service import preview_draft
from app.services.personnel_order_template_specs import get_personnel_order_template_spec


def texts(mode):
    return {**get_personnel_order_template_spec('CONCURRENT_DUTY_START').initial_texts,'body_template_ru':RATE_RU if mode=='RATE' else PAY_RU,'body_template_kk':RATE_KK if mode=='RATE' else PAY_KK}


@pytest.mark.parametrize('mode,percent,term',[('RATE',None,'DATE'),('RATE',None,'UNTIL_RETURN'),('PAY',25,'DATE'),('PAY',50,'DATE'),('PAY',25,'UNTIL_RETURN'),('PAY',50,'UNTIL_RETURN')])
def test_bilingual_matrix_formats_and_variant_specific_variables(mode,percent,term):
    concurrent=dict(SAMPLE_CONCURRENT);replacement={**SAMPLE_REPLACEMENT,'term_type':term,'allowance_percent':percent}
    if mode=='PAY': concurrent.pop('rate');concurrent.pop('total_rate')
    values=replacement_values(concurrent,replacement,'2026-07-03',mode)
    rendered=_render({**texts(mode),'item_type_code':'CONCURRENT_DUTY_START'},values,draft_preview=True)
    ru,kk=rendered['body_template_ru'],rendered['body_template_kk']
    assert 'с 03.07.2026' in ru and '2026 жылғы 3 шілдеден бастап' in kk
    assert 'Иванова Ивана Ивановича, врача отделения терапии' in ru
    assert 'Иван Иванович Ивановтың еңбек демалысы кезеңінде' in kk
    assert 'дәрігері қызметін қоса атқаруға рұқсат берілсін' in kk
    assert all(token not in ru+kk for token in ('[','{','2026-07-03','санитарка'))
    if mode=='RATE':
        assert '0,25 ставки' in ru and '(Всего: 1,25 ставки)' in ru
        assert '0,25 ставкада' in kk and '1,25 ставка)' in kk
        assert '%' not in ru+kk
    else:
        assert f'{percent}% от должностного оклада замещаемого работника' in ru
        assert f'{percent}% мөлшерінде қосымша ақы белгіленсін' in kk
        assert 'лауазымдық жалақысының' in kk
        assert 'ставки' not in ru and 'ставка' not in kk
    if term=='DATE':assert 'по 31.07.2026 включительно' in ru and '2026 жылғы 31 шілдеге дейін' in kk
    else:assert 'до выхода замещаемого работника из отпуска' in ru and 'жұмысқа шығуына дейін' in kk
    assert concurrent.get('rate')!=1 and concurrent.get('total_rate')!=1


@pytest.mark.parametrize('mode',['RATE','PAY'])
def test_standard_preview_uses_the_same_saved_contract(mode):
    preview=preview_draft('CONCURRENT_DUTY_START',texts(mode))
    rendered=_render({**texts(mode),'item_type_code':'CONCURRENT_DUTY_START'},replacement_values(SAMPLE_CONCURRENT,SAMPLE_REPLACEMENT,'2026-07-03',mode),draft_preview=True)
    assert preview['ru']['body']==rendered['body_template_ru']
    assert preview['kk']['body']==rendered['body_template_kk']


@pytest.mark.parametrize('section,key,mode',[('concurrent','employee_dative_ru','RATE'),('concurrent','position_genitive_ru','PAY'),('replacement','employee_genitive_kk','RATE'),('replacement','org_unit_kk','PAY'),('replacement','end_date','RATE'),('replacement','term_type','PAY'),('concurrent','total_rate','RATE'),('replacement','allowance_percent','PAY'),('replacement','allowance_basis_ru','PAY'),('replacement','allowance_basis_kk','PAY')])
def test_missing_confirmed_fields_block_preview(section,key,mode):
    c,r=deepcopy(SAMPLE_CONCURRENT),deepcopy(SAMPLE_REPLACEMENT)
    (c if section=='concurrent' else r)[key]=''
    with pytest.raises(ValueError):replacement_values(c,r,'2026-07-03',mode)


def test_pay_template_cannot_accidentally_request_rates():
    broken=texts('PAY');broken['body_template_ru']+=' {{total.rate}}'
    with pytest.raises(ValueError,match='не должен содержать ставки'):validate_bodies(broken)


def test_non_unit_main_rate_and_term_validation():
    values=replacement_values({**SAMPLE_CONCURRENT,'rate':'0,25','total_rate':'0,75'},SAMPLE_REPLACEMENT,'2026-07-03','RATE')
    assert values['total.rate']=='0,75'
    with pytest.raises(ValueError,match='раньше'):replacement_values(SAMPLE_CONCURRENT,{**SAMPLE_REPLACEMENT,'end_date':'2026-07-02'},'2026-07-03','RATE')


@pytest.mark.parametrize('percent',[25,50])
@pytest.mark.parametrize('position,unit',[(False,False),(True,True),(True,False),(False,True)])
def test_optional_pay_placement_produces_complete_bilingual_phrases(percent,position,unit):
    from app.services.personnel_order_replacement_contract import OPTIONAL_PAY_RU,OPTIONAL_PAY_KK,optional_placement
    c={**SAMPLE_CONCURRENT}; c.pop('rate');c.pop('total_rate')
    if not position:
        for key in ('position_ru','position_kk','position_genitive_ru'):c[key]=''
    if not unit:
        for key in ('org_unit_ru','org_unit_kk','org_unit_genitive_ru'):c[key]=''
    t={**texts('PAY'),'body_template_ru':OPTIONAL_PAY_RU,'body_template_kk':OPTIONAL_PAY_KK,'item_type_code':'CONCURRENT_DUTY_START'}
    validate_bodies(t);assert optional_placement(t)
    values=replacement_values(c,{**SAMPLE_REPLACEMENT,'allowance_percent':percent},'2026-07-03','PAY',optional_placement=True)
    rendered=_render(t,values,draft_preview=True);ru,kk=rendered['body_template_ru'],rendered['body_template_kk']
    assert f'с доплатой в размере {percent}%' in ru and f'{percent}% мөлшерінде қосымша ақы' in kk
    assert 'ставк' not in ru+kk and '{{' not in ru+kk and '  ' not in ru+kk
    assert ('совмещение должности' in ru)==position
    assert ('қызметін қоса атқаруға' in kk)==position
    if not position:assert 'исполнение обязанностей замещаемого работника' in ru and 'міндеттерін атқаруға' in kk
    assert ('concurrent.rate' not in values) and ('total.rate' not in values)


@pytest.mark.parametrize('percent',['',0,30,75,'25.5'])
def test_fixed_allowance_rejects_other_values(percent):
    with pytest.raises(ValueError):replacement_values(SAMPLE_CONCURRENT,{**SAMPLE_REPLACEMENT,'allowance_percent':percent},'2026-07-03','PAY',optional_placement=True)


def test_optional_placement_requires_genitive_only_when_nominal_is_present():
    c={**SAMPLE_CONCURRENT,'position_ru':'','org_unit_ru':'','position_kk':'','org_unit_kk':'','position_genitive_ru':'','org_unit_genitive_ru':''}
    replacement_values(c,SAMPLE_REPLACEMENT,'2026-07-03','PAY',optional_placement=True)
    for nominal in ('position_ru','org_unit_ru'):
        with pytest.raises(ValueError):replacement_values({**c,nominal:'Заполнено'},SAMPLE_REPLACEMENT,'2026-07-03','PAY',optional_placement=True)

import pytest
from app.services.personnel_order_supplementary_pay_contract import BODY_RU, BODY_KK, values
from app.services.personnel_order_service_area_contract import SAMPLE_RECIPIENT
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_validation import validate_template_texts
from app.services.personnel_order_template_draft_service import preview_draft
from app.services.personnel_order_template_application_service import _render

def texts():
    return {**get_personnel_order_template_spec('SUPPLEMENTARY_PAY').initial_texts,
            'body_template_ru':BODY_RU,'body_template_kk':BODY_KK}

def allowance(percent=25):
    return {'percent':percent,'employee_dative_ru':'Касымовой Раушан Тастемировне',
            'employee_dative_kk':'Раушан Тастемировна Касымоваға',
            'basis_ru':'Служебная записка','basis_kk':'Қызметтік хат'}

@pytest.mark.parametrize('percent',[25,50])
def test_simple_allowance_complete_bilingual_contract(percent):
    t=texts();validate_template_texts('SUPPLEMENTARY_PAY',t)
    result=_render({'item_type_code':'SUPPLEMENTARY_PAY',**t},values(allowance(str(percent)),SAMPLE_RECIPIENT,'2026-02-02'))
    assert f'{percent}% от собственного должностного оклада' in result['body_template_ru']
    assert f'лауазымдық айлық ақыдан {percent}% көлемінде қосымша ақы төленсін' in result['body_template_kk']
    assert 'с 02.02.2026' in result['body_template_ru']
    assert '2026 жылғы 2 ақпаннан бастап' in result['body_template_kk']
    assert result['basis_template_ru']=='Основание: Служебная записка.'
    assert result['basis_template_kk']=='Негіз: Қызметтік хат.'
    assert all(token not in result['body_template_ru']+result['body_template_kk'] for token in ('{{','[','ставк','отпуск','демалыс'))
    assert '25%' in preview_draft('SUPPLEMENTARY_PAY',t)['kk']['body']

@pytest.mark.parametrize('percent',[None,'',0,30,75])
def test_percent_is_required_and_restricted(percent):
    with pytest.raises(ValueError):values(allowance(percent),SAMPLE_RECIPIENT,'2026-02-02')

@pytest.mark.parametrize('field',['employee_dative_ru','employee_dative_kk','basis_ru','basis_kk'])
def test_required_names_and_bilingual_evidence(field):
    a=allowance();a[field]=''
    with pytest.raises(ValueError):values(a,SAMPLE_RECIPIENT,'2026-02-02')

def test_rate_replacement_unknown_and_incomplete_templates_fail_compatibility():
    from app.services.personnel_order_template_draft_service import _validate
    for body in ('{{concurrent.rate}}','{{replacement.employee_genitive_ru}}','{{unknown}}',BODY_RU.replace('{{allowance.percent}}','25')):
        t=texts();t['body_template_ru']=body
        with pytest.raises(ValueError):validate_template_texts('SUPPLEMENTARY_PAY',t)
        with pytest.raises(ValueError):_validate(t,'SUPPLEMENTARY_PAY',require_complete=True)

def test_own_salary_and_automatic_cases():
    data=values({**allowance(),'basis_type':'REPLACED_SALARY'}, {**SAMPLE_RECIPIENT,'position_dative_ru':''}, '2026-02-02')
    assert data['allowance.basis.ru']=='собственного должностного оклада'
    assert 'врачу' in data['allowance.recipient.ru']
    assert not any(key.startswith(('replacement.','allowance.term')) for key in data)

def test_laundry_head_cases_are_automatic_and_unit_is_not_repeated():
    recipient={**SAMPLE_RECIPIENT,'position_ru':'Заведующая прачечной','org_unit_ru':'Прачечная','position_dative_ru':'','org_unit_genitive_ru':''}
    data=values(allowance(),recipient,'2026-02-02')
    assert data['allowance.recipient.ru']=='Касымовой Раушан Тастемировне, заведующей прачечной'


@pytest.mark.parametrize('percent', [25, 50])
def test_missing_kk_position_omits_whole_placement_without_losing_other_data(percent):
    recipient = {**SAMPLE_RECIPIENT, 'position_kk': '', 'position_ru': 'Машинист по стирке белья',
                 'position_dative_ru': '', 'org_unit_ru': 'Прачечная', 'org_unit_genitive_ru': ''}
    data = values(allowance(percent), recipient, '2026-02-02')
    assert data['allowance.recipient.ru'] == 'Касымовой Раушан Тастемировне, машинисту по стирке белья прачечной'
    assert data['allowance.recipient.kk'] == allowance()['employee_dative_kk']
    rendered = _render({'item_type_code': 'SUPPLEMENTARY_PAY', **texts()}, data)
    assert rendered['body_template_kk'].startswith(allowance()['employee_dative_kk']+' 2026')
    assert f'{percent}%' in rendered['body_template_kk']
    assert 'машинист' not in rendered['body_template_kk']
    assert not any(token in rendered['body_template_kk'] for token in ('{{', 'DOCX', '(должность:'))
    assert rendered['basis_template_kk'] == 'Негіз: Қызметтік хат.'


def test_unknown_ru_form_omits_placement_independently_of_kk_and_preserves_manual_forms():
    recipient = {**SAMPLE_RECIPIENT, 'position_ru': 'Неизвестный код', 'position_dative_ru': '',
                 'position_kk': 'кір жуу машинисі'}
    data = values(allowance(), recipient, '2026-02-02')
    assert data['allowance.recipient.ru'] == allowance()['employee_dative_ru']
    assert 'кір жуу машинисі' in data['allowance.recipient.kk']
    recipient['position_dative_ru'] = 'машинисту по стирке белья'
    data = values(allowance(), recipient, '2026-02-02')
    assert 'машинисту по стирке белья' in data['allowance.recipient.ru']
    assert 'кір жуу машинисі' in data['allowance.recipient.kk']

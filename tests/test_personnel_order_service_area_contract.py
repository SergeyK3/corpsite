import pytest
from app.services.personnel_order_service_area_contract import BODY_RU,BODY_KK,SAMPLE_RECIPIENT,values,validate_bodies
from app.services.personnel_order_replacement_contract import SAMPLE_CONCURRENT,SAMPLE_REPLACEMENT
from app.services.personnel_order_template_application_service import _render
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_draft_service import preview_draft

def texts():return {**get_personnel_order_template_spec('CONCURRENT_DUTY_START').initial_texts,'body_template_ru':BODY_RU,'body_template_kk':BODY_KK,'item_type_code':'CONCURRENT_DUTY_START'}

@pytest.mark.parametrize('percent',[25,50])
@pytest.mark.parametrize('term,worker',[('NONE',False),('NONE',True),('DATE',False),('DATE',True),('UNTIL_RETURN',True)])
def test_service_area_matrix(percent,term,worker):
    replacement={**(SAMPLE_REPLACEMENT if worker else {}),'term_type':term,'end_date':'2026-06-30','allowance_percent':percent}
    data=values({**SAMPLE_CONCURRENT,'position_ru':'','org_unit_ru':''},replacement,'2026-06-15',SAMPLE_RECIPIENT)
    t=texts();validate_bodies(t);rendered=_render(t,data,draft_preview=True);ru,kk=rendered['body_template_ru'],rendered['body_template_kk']
    assert 'Турымову Алибеку Рапхатовичу, врачу отделения терапии, с 15.06.2026' in ru
    assert '2026 жылғы 15 маусымнан бастап' in kk
    assert f'{percent}% от собственного должностного оклада' in ru
    assert f'лауазымдық айлық ақыдан {percent}% көлемінде қосымша ақы төленсін' in kk
    assert ('на время трудового отпуска' in ru)==worker
    assert ('кезекті еңбек демалысы кезеңінде' in kk)==worker
    assert all(marker not in ru+kk for marker in ('{{','[','  ','дежур','ставк'))
    if term=='NONE':assert 'включительно' not in ru and 'шығуына дейін' not in kk and 'маусымға дейін' not in kk
    elif term=='DATE':assert 'по 30.06.2026 включительно' in ru and '2026 жылғы 30 маусымға дейін' in kk
    else:assert 'до выхода замещаемого работника' in ru and 'жұмысқа шығуына дейін' in kk

@pytest.mark.parametrize('term',['','UNTIL_RETURN'])
def test_unset_term_and_return_without_worker_are_distinct_and_invalid(term):
    with pytest.raises(ValueError):values(SAMPLE_CONCURRENT,{'term_type':term,'allowance_percent':25},'2026-06-15',SAMPLE_RECIPIENT)

def test_own_salary_ignores_arbitrary_basis_and_non_date_end_date():
    data=values(SAMPLE_CONCURRENT,{'term_type':'NONE','end_date':'invalid','allowance_percent':50,'allowance_basis_ru':'Чужой оклад'},'2026-06-15',SAMPLE_RECIPIENT)
    assert data['allowance.basis.ru']=='собственного должностного оклада' and data['allowance.term.ru']==''
    with pytest.raises(ValueError):values(SAMPLE_CONCURRENT,{'term_type':'NONE','allowance_percent':30},'2026-06-15',SAMPLE_RECIPIENT)
    with pytest.raises(ValueError):values(SAMPLE_CONCURRENT,{'term_type':'NONE','allowance_percent':25},'',SAMPLE_RECIPIENT)
    with pytest.raises(ValueError):values(SAMPLE_CONCURRENT,{'term_type':'DATE','allowance_percent':25,'end_date':'2026-06-14'},'2026-06-15',SAMPLE_RECIPIENT)

def test_saved_forms_are_rendered_once_and_standard_preview_is_compatible():
    data=values({**SAMPLE_CONCURRENT,'employee_dative_ru':'Иванову Ивану Ивановичу'},{'term_type':'NONE','allowance_percent':25},'2026-06-15',{**SAMPLE_RECIPIENT,'position_dative_ru':'заведующему'})
    assert data['allowance.recipient.ru'].startswith('Иванову Ивану Ивановичу, заведующему ')
    preview=preview_draft('CONCURRENT_DUTY_START',texts())
    assert 'от собственного должностного оклада' in preview['ru']['body']
    assert '{{' not in preview['ru']['body']+preview['kk']['body']

@pytest.mark.parametrize('percent',[25,50])
@pytest.mark.parametrize('term',['NONE','DATE','UNTIL_RETURN'])
def test_worker_name_only_has_no_empty_placement_or_punctuation(percent,term):
    replacement={**SAMPLE_REPLACEMENT,'term_type':term,'end_date':'2026-06-30','allowance_percent':percent}
    for key in ('position_ru','position_kk','org_unit_ru','org_unit_kk','position_genitive_ru','org_unit_genitive_ru','position_genitive_kk','org_unit_genitive_kk'):replacement[key]=''
    rendered=_render(texts(),values(SAMPLE_CONCURRENT,replacement,'2026-06-15',SAMPLE_RECIPIENT),draft_preview=True)
    assert 'на время трудового отпуска Иванова Ивана Ивановича.' in rendered['body_template_ru']
    assert ' Иван Иванович Ивановтың кезекті еңбек демалысы кезеңінде ' in rendered['body_template_kk']
    assert all(marker not in rendered['body_template_ru']+rendered['body_template_kk'] for marker in ('{{','  ', ', .', ', ,'))

@pytest.mark.parametrize('locale',['ru','kk'])
def test_basis_stays_required(locale):
    with pytest.raises(ValueError,match='Основание'):
        values({**SAMPLE_CONCURRENT,'basis_'+locale:''},{'term_type':'NONE','allowance_percent':25},'2026-06-15',SAMPLE_RECIPIENT)

@pytest.mark.parametrize('form',[None,'','   '])
def test_manager_dative_is_automatic_without_client_case(form):
    from app.services.personnel_order_service_area_contract import normalize_recipient
    recipient={**SAMPLE_RECIPIENT,'position_ru':'Менеджер','position_dative_ru':form,'org_unit_genitive_ru':'отдела кадров'}
    assert normalize_recipient(recipient)['position_dative_ru']=='менеджеру'
    data=values(SAMPLE_CONCURRENT,{'term_type':'NONE','allowance_percent':25},'2026-06-15',recipient)
    rendered=_render(texts(),data,draft_preview=True)
    assert 'Турымову Алибеку Рапхатовичу, менеджеру отдела кадров, с 15.06.2026' in rendered['body_template_ru']

def test_unknown_recipient_case_omits_the_whole_placement_in_both_languages():
    recipient={**SAMPLE_RECIPIENT,'position_ru':'Неизвестный код','position_dative_ru':''}
    data=values(SAMPLE_CONCURRENT,{'term_type':'NONE','allowance_percent':25},'2026-06-15',recipient)
    rendered=_render(texts(),data,draft_preview=True)
    assert rendered['body_template_ru'].startswith('Турымову Алибеку Рапхатовичу, с 15.06.2026')
    assert rendered['body_template_kk'].startswith('Алибек Рапхатович Турымовқа 2026 жылғы 15 маусымнан бастап')
    assert all(token not in rendered['body_template_ru']+rendered['body_template_kk'] for token in ('Неизвестный','{{',', ,','  ','врачу','дәрігері'))

def test_manual_recipient_dative_refinement_wins_over_calculation():
    from app.services.personnel_order_service_area_contract import normalize_recipient
    assert normalize_recipient({'position_ru':'Менеджер','position_dative_ru':'уточнённой форме'})['position_dative_ru']=='уточнённой форме'

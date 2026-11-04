import pytest
from app.services.personnel_order_hire_terms import hire_rate, hire_basis_text, validate_hire_terms


def test_historical_certificate_names_override_dictionary_snapshot_and_allow_no_selection():
    from app.services.personnel_order_hire_terms import normalize_hire_details,normalize_hire_basis
    for specialty in (None,{'medical_specialty_id':41,'name_ru':'Радиология','name_kk':'Радиология'}):
        certificate={'specialty':specialty,'issued_on':'','name_ru':'Лучевая диагностика','name_kk':'Сәулелік диагностика'}
        assert normalize_hire_details({'certificate':certificate})['certificate']==certificate
    pair={'ru':'личное заявление, трудовой договор','kk':'','kk_intentionally_empty':True}
    assert normalize_hire_basis(pair)==pair
    assert validate_hire_terms({'employment_rate':1,'hire_basis':pair})==1
    assert hire_basis_text({'hire_basis':pair},'kk')==''


def test_hire_basis_locales_are_independent_and_never_fall_back():
    from app.services.personnel_order_hire_terms import normalize_hire_basis
    payload={'hire_basis':{'ru':'Ручное RU','kk':'Қолмен KK'},'basis_other_text':'STALE RU'}
    assert normalize_hire_basis(payload['hire_basis'])==payload['hire_basis']
    assert hire_basis_text(payload,'kk')=='Қолмен KK'
    payload['hire_basis']['kk']=''
    assert hire_basis_text(payload,'kk')==''
    assert hire_basis_text(payload,'ru')=='Ручное RU'
    assert hire_basis_text({'basis_other_text':'OLD RU'},'kk',source_locale='ru')==''
    assert hire_basis_text({'basis_other_text':'OLD KK'},'kk',source_locale='kk')=='OLD KK'


def test_hire_certificate_is_optional_snapshot_without_kk_translation_or_required_date():
    from app.services.personnel_order_hire_terms import normalize_hire_details
    assert normalize_hire_details({'certificate':{}})['certificate']=={'specialty':None,'issued_on':''}
    specialty={'medical_specialty_id':7,'name_ru':'Медицина TEST','name_kk':''}
    for day in ('','2026-02-02'):
        value={'certificate':{'specialty':specialty,'issued_on':day}}
        assert normalize_hire_details(value)['certificate']==value['certificate']
    with pytest.raises(ValueError,match='дату выдачи'):
        normalize_hire_details({'certificate':{'issued_on':'2026-02-30'}})


def test_optional_hire_details_preserve_both_locales_and_do_not_supply_missing_values():
    from app.services.personnel_order_hire_terms import normalize_hire_details
    assert normalize_hire_details({}) == {'education': {'code':'','ru':'','kk':''}, 'service_length': {'ru':'','kk':''}}
    saved = {'education': {'code':'HIGHER','ru':'Высшее','kk':''}, 'service_length': {'ru':'  5 лет  ','kk':'5 жыл'}}
    assert normalize_hire_details(saved) == saved
    for malformed in (None, [], {'education':[]}, {'service_length':{'ru':5}}):
        with pytest.raises(ValueError, match='Некорректные данные'):
            normalize_hire_details(malformed)


@pytest.mark.parametrize('raw, expected', [('17,3','17.3'),('17.3','17.3'),('0','0'),(0,'0'),('', ''),('  0017,30  ','17.30')])
def test_hire_decimal_years_are_optional_and_keep_legacy_texts(raw, expected):
    from app.services.personnel_order_hire_terms import normalize_hire_details
    legacy = {'education':{}, 'service_length':{'ru':'17 лет и 3 месяца','kk':'Ескі мәтін'}}
    value = normalize_hire_details({**legacy, 'service_length_years':raw})
    assert value['service_length_years'] == expected
    assert value['service_length'] == legacy['service_length']
    assert 'service_length_years' not in normalize_hire_details(legacy)


@pytest.mark.parametrize('raw', ['-1','NaN','Infinity','17 лет','17,3,2','1e2',[],True])
def test_hire_decimal_years_reject_invalid_values(raw):
    from app.services.personnel_order_hire_terms import normalize_hire_details
    with pytest.raises(ValueError, match='количество лет'):
        normalize_hire_details({'service_length_years':raw})


@pytest.mark.parametrize('locale, expected', [
    ('ru', 'личное заявление, трудовой договор'),
    ('kk', 'жеке өтініші, еңбек шарты'),
])
def test_hire_template_preview_uses_initial_basis_without_fixing_it_in_template(locale, expected):
    from app.services.personnel_order_template_draft_service import preview_draft
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec

    texts = dict(get_personnel_order_template_spec('HIRE').initial_texts)
    texts.update(basis_template_ru='Основание: {{basis}}.', basis_template_kk='Негіз: {{basis}}.')
    assert expected in preview_draft('HIRE', texts)[locale]['basis']
    assert texts['basis_template_' + locale].count('{{basis}}') == 1
    assert hire_basis_text({'basis_other_text': 'SYNTHETIC MANUAL'}, locale, source_locale=locale) == 'SYNTHETIC MANUAL'
    assert hire_basis_text({'basis': 'SYNTHETIC SAVED'}, locale, source_locale=locale) == 'SYNTHETIC SAVED'


@pytest.mark.parametrize('value', [None, '', '  '])
def test_missing_rate_is_readable(value):
    with pytest.raises(ValueError, match='Укажите ставку'):
        validate_hire_terms({'employment_rate': value, 'basis_other_text': 'SYNTHETIC'})


@pytest.mark.parametrize('value', ['0', '-1', '2.1', 'nan', 'inf', 'text', True])
def test_invalid_rate_is_rejected(value):
    with pytest.raises(ValueError, match='Ставка должна'):
        hire_rate(value)


def test_comma_rate_and_basis_selection():
    assert validate_hire_terms({'employment_rate': '0,75', 'basis_other_text': 'SYNTHETIC'}) == 0.75
    with pytest.raises(ValueError, match='Заполните основание'):
        validate_hire_terms({'employment_rate': '0,75', 'basis_other_text': ' '})
    documents = [{'basis_id': 'app', 'description': {'ru': 'RU SYNTHETIC', 'kk': 'KK SYNTHETIC'}}]
    payload = {'basis_entries': [{'document_type': 'PERSONAL_APPLICATION', 'basis_id': 'app'},
                                 {'document_type': 'OTHER', 'other_text': 'SYNTHETIC OTHER'}], 'basis_other_text': 'STALE'}
    assert hire_basis_text(payload, 'ru', documents) == 'RU SYNTHETIC\nSYNTHETIC OTHER'
    assert hire_basis_text(payload, 'kk', documents) == 'KK SYNTHETIC'
    assert hire_basis_text({'basis': 'LEGACY'}, 'kk') == ''
    assert hire_basis_text({'basis': 'LEGACY'}, 'kk', source_locale='kk') == 'LEGACY'
    assert hire_basis_text({'basis_other_text': '', 'basis': 'STALE'}, 'ru') == ''


@pytest.mark.parametrize('nominal_kk', ['', 'SYNTHETIC NOMINAL KK'])
def test_hire_manual_position_kk_takes_precedence_over_title_snapshot(nominal_kk):
    from unittest.mock import MagicMock
    from app.services.personnel_order_template_application_service import _values, _render
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    template = {**get_personnel_order_template_spec('HIRE').initial_texts, 'item_type_code': 'HIRE'}
    item = {'item_type_code': 'HIRE', 'employee_id': None, 'effective_date': '2026-11-04', 'payload': {
        'source_employee_name': 'SYNTHETIC PERSON', 'source_position_name': 'SYNTHETIC RU POSITION',
        'org_unit_name': {'ru': 'SYNTHETIC RU UNIT', 'kk': 'SYNTHETIC KK UNIT'},
        'document_forms_kk': {'position_document_possessive_kk': 'Сынақ лауазымы'},
        'document_position': {'name': 'SYNTHETIC RU POSITION', 'name_kk': nominal_kk, 'document_possessive_kk': ''},
        'employment_rate': 1, 'basis_other_text': 'SYNTHETIC BASIS', 'hire_basis':{'ru':'SYNTHETIC BASIS','kk':'SYNTHETIC BASIS'},
    }}
    values, _, _ = _values(conn, item, template)
    assert values['position.title_kk'] == 'Сынақ лауазымы'
    assert values['position.document_possessive_kk'] == 'Сынақ лауазымы'
    assert 'Сынақ лауазымы' in _render(template, values)['body_template_kk']


def test_hire_legacy_position_without_kk_cannot_use_russian_fallback():
    from unittest.mock import MagicMock
    from app.services.personnel_order_template_application_service import _values, _render, TemplateApplicationError
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    template = {**get_personnel_order_template_spec('HIRE').initial_texts, 'item_type_code': 'HIRE'}
    item = {'item_type_code': 'HIRE', 'employee_id': None, 'effective_date': '2026-11-04', 'payload': {
        'source_employee_name': 'SYNTHETIC PERSON', 'position_name': {'ru': 'SYNTHETIC RU POSITION'},
        'org_unit_name': {'ru': 'SYNTHETIC RU UNIT', 'kk': 'SYNTHETIC KK UNIT'},
        'employment_rate': 1, 'basis_other_text': 'SYNTHETIC BASIS', 'hire_basis':{'ru':'SYNTHETIC BASIS','kk':'SYNTHETIC BASIS'},
    }}
    values, _, _ = _values(conn, item, template)
    assert values['position.title_kk'] == ''
    with pytest.raises(TemplateApplicationError, match='position.title_kk'):
        _render(template, values)


@pytest.mark.parametrize('iso, ru, kk', [
    ('2026-02-02', 'с 02.02.2026', '2026 жылғы 2 ақпаннан бастап'),
    ('2020-01-05', 'с 05.01.2020', '2020 жылғы 5 қаңтардан бастап'),
])
def test_hire_effective_date_uses_common_formatters_for_template_and_generated_text(iso, ru, kk):
    from datetime import date
    from unittest.mock import MagicMock
    from app.services.personnel_order_template_application_service import _values, _render
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec
    from app.services.personnel_orders_editorial.generators import generate_item_body

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = None
    template = {**get_personnel_order_template_spec('HIRE').initial_texts, 'item_type_code': 'HIRE'}
    for day in (iso, date.fromisoformat(iso)):
        item = {'item_type_code': 'HIRE', 'employee_id': None, 'effective_date': day, 'payload': {
            'source_employee_name': 'SYNTHETIC PERSON', 'position_name': {'ru': 'SYNTHETIC RU', 'kk': 'SYNTHETIC KK'},
            'org_unit_name': {'ru': 'SYNTHETIC RU UNIT', 'kk': 'SYNTHETIC KK UNIT'},
            'employment_rate': 1, 'basis_other_text': 'SYNTHETIC BASIS', 'hire_basis':{'ru':'SYNTHETIC BASIS','kk':'SYNTHETIC BASIS'},
        }}
        values, _, _ = _values(conn, item, template)
        rendered = _render(template, values)
        for locale, expected in (('ru', ru), ('kk', kk)):
            assert expected in rendered['body_template_' + locale]
            assert iso not in rendered['body_template_' + locale]
            generated = generate_item_body(locale, {'item_type_code': 'HIRE', 'effective_date': day})
            assert expected in generated['generated_text']
        assert item['effective_date'] == day


def test_hire_position_manual_forms_validate_and_apply_only_to_new_wording_contract():
    from unittest.mock import MagicMock
    from app.services.personnel_order_hire_terms import normalize_hire_position_manual_forms
    from app.services.personnel_order_template_application_service import _values
    assert normalize_hire_position_manual_forms({'ru':True,'kk':False}) == {'ru':True,'kk':False}
    for value in (None, {}, {'ru':1,'kk':False}, {'ru':False,'kk':'true'}):
        with pytest.raises(ValueError): normalize_hire_position_manual_forms(value)
    conn=MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value=None
    payload={'hire_basis':{'ru':'Основание','kk':'Негіз'},'employment_rate':1,
        'document_position':{'position_id':8,'name':'Уточнение RU','name_kk':'Нақтылау KK','document_nominative_ru':'Каталог RU','document_possessive_kk':'Каталог KK'},
        'document_forms_ru':{'position_document_nominative_ru':'Ручная форма RU'},'document_forms_kk':{'position_document_possessive_kk':'Қолмен KK'}}
    item={'item_type_code':'HIRE','employee_id':None,'effective_date':'2026-11-04','payload':payload}
    template={'item_type_code':'HIRE'}
    assert _values(conn,item,template)[0]['position.title_ru']=='Уточнение RU'
    payload['hire_position_manual_forms']={'ru':True,'kk':True}
    values=_values(conn,item,template)[0]
    assert values['position.title_ru']=='Ручная форма RU'
    assert values['position.document_nominative_ru']=='Ручная форма RU'
    assert values['position.title_kk']=='Қолмен KK'

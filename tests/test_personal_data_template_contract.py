from copy import deepcopy
import pytest
from app.services.personnel_order_personal_data_contract import TYPE,TEXTS,REQUIRED,VARIABLES,SAMPLE,personal_data_values,corrected_personal_data_texts
from app.services.personnel_order_template_specs import get_personnel_order_template_spec,assert_personnel_order_template_specs,TEMPLATE_ONLY_TYPES
from app.services.personnel_order_template_draft_service import _validate,preview_draft,TemplateDraftError
from app.services.personnel_order_template_validation import validate_template_texts,TemplateValidationError
from app.services.personnel_order_template_application_service import _render


@pytest.mark.parametrize('source',[
    {'source_employee_name':'Изжанова Айгерим Мукановна'},
    {'unresolved_subject':{'full_name':'Изжанова Айгерим Мукановна'}},
    {'document_forms_ru':{'employee_full_name_genitive_ru':'Изжановой Айгерим Мукановны'},'document_forms_kk':{'employee_full_name_genitive_kk':'Айгерим Мукановна Изжанованың'}},
])
def test_manual_fio_order_resolves_the_original_given_name_without_manual_initials(source):
    from app.services.personnel_order_personal_data_contract import with_source_given_names
    resolved=with_source_given_names(None,source,None)
    assert resolved['source_given_name_ru']=='Айгерим'
    assert resolved['source_given_name_kk']=='Айгерим'


def test_original_given_names_are_structured_snapshots_and_are_not_reparsed_or_overwritten():
    from unittest.mock import Mock
    from app.services.personnel_order_personal_data_contract import with_source_given_names
    conn=Mock();conn.execute.return_value.mappings.return_value.first.return_value={'employee':{'full_name':'НЕ РАЗБИРАТЬ','first_name':'Айдар'},'person':{'first_name':'Айдар','first_name_kk':'Әли'}}
    snapshot=with_source_given_names(conn,{},123)
    assert snapshot=={'source_given_name_ru':'Айдар','source_given_name_kk':'Әли'}
    conn.reset_mock();assert with_source_given_names(conn,snapshot,123)==snapshot;conn.execute.assert_not_called()
    conn.execute.return_value.mappings.return_value.first.return_value={'employee':{'full_name':'Неизвестный'},'person':{}}
    assert with_source_given_names(conn,{},123)=={'source_given_name_ru':'','source_given_name_kk':''}


def test_new_names_are_independent_manual_values_and_never_translated_or_declined():
    sample=deepcopy(SAMPLE)
    sample['personal_data'].update(new_full_name_ru='TEST Новое Имя RU',new_full_name_kk='СЫНАҚ Жаңа Аты KK')
    values=personal_data_values(sample)
    rendered=_render({**TEXTS,'item_type_code':TYPE},values)
    for locale in ('ru','kk'):
        assert sample['personal_data']['new_full_name_'+locale] in rendered['body_template_'+locale]
        assert sample['personal_data']['changes_'+locale] in rendered['body_template_'+locale]
    sample['personal_data'].pop('new_full_name_kk')
    assert personal_data_values(sample)['personal_data.new_full_name_kk']==''
    from app.services.personnel_order_template_application_service import TemplateApplicationError
    with pytest.raises(TemplateApplicationError):_render({**TEXTS,'item_type_code':TYPE},personal_data_values(sample))


def test_legacy_texts_and_orders_work_without_new_names_and_draft_conversion_preserves_source():
    from app.services.personnel_order_personal_data_contract import with_new_personal_names
    legacy={**TEXTS,'body_template_ru':TEXTS['body_template_ru'].split(' ФИО после изменения:')[0],
            'body_template_kk':TEXTS['body_template_kk'].split(' Өзгерістен кейінгі Т.А.Ә.:')[0]}
    sample=deepcopy(SAMPLE)
    for locale in ('ru','kk'):sample['personal_data'].pop('new_full_name_'+locale)
    rendered=_render({**legacy,'item_type_code':TYPE},personal_data_values(sample))
    assert 'ФИО после изменения:' not in rendered['body_template_ru']
    original=deepcopy(legacy);draft=with_new_personal_names(legacy)
    assert original==legacy and with_new_personal_names(draft)==draft
    assert draft==TEXTS
    _validate(draft,TYPE)


@pytest.mark.parametrize('status,ru,kk',[
    ('ABSENT','данные о дате выдачи отсутствуют','берілген күні туралы мәліметтер жоқ'),
    ('TO_CLARIFY','дату выдачи следует уточнить','берілген күнін нақтылау қажет'),
])
def test_identity_date_status_renders_bilingual_basis_without_fake_date_or_template_mutation(status,ru,kk):
    sample=deepcopy(SAMPLE);sample['identity_document'].update(issued_at='',issued_at_status=status)
    original=deepcopy(TEXTS)
    rendered=_render({**TEXTS,'item_type_code':TYPE},personal_data_values(sample))
    assert ru in rendered['basis_template_ru'] and kk in rendered['basis_template_kk']
    assert 'выданное' not in rendered['basis_template_ru']
    assert ' берілген №' not in rendered['basis_template_kk']
    assert '10.05.2026' not in str(rendered) and TEXTS==original


@pytest.mark.parametrize('status',['ABSENT','TO_CLARIFY','UNKNOWN'])
def test_identity_date_rejects_conflicting_date_or_invalid_status(status):
    sample=deepcopy(SAMPLE);sample['identity_document']['issued_at_status']=status
    with pytest.raises(ValueError):personal_data_values(sample)


def test_existing_identity_date_without_status_remains_supported():
    assert personal_data_values(SAMPLE)['identity_document.issued_ru']=='10.05.2026'


def test_independent_contract_supports_order_creation_and_has_no_education_or_diploma_variables():
    assert_personnel_order_template_specs()
    spec=get_personnel_order_template_spec(TYPE)
    from app.db.models.personnel_orders import PERSONNEL_ORDER_ITEM_TYPE_CODES
    assert TYPE not in TEMPLATE_ONLY_TYPES and TYPE in PERSONNEL_ORDER_ITEM_TYPE_CODES
    assert spec.allowed_variables==VARIABLES and spec.required_variables==REQUIRED
    assert not any(code.startswith(('education.','education_document.')) for code in VARIABLES)
    assert all('identity_document.' in code for code in REQUIRED['basis_template_ru'])
    assert all('identity_document.' in code for code in REQUIRED['basis_template_kk'])


def test_real_render_context_uses_personal_data_payload_without_education_fields():
    from app.services.personnel_order_template_application_service import _values
    values,warnings,missing=_values(None,{'item_type_code':TYPE,'payload':deepcopy(SAMPLE)},{})
    assert values['personal_data.changes_ru']==SAMPLE['personal_data']['changes_ru']
    assert values['identity_document.number']=='TEST-ID-0001'
    assert not warnings and not missing


def test_new_contract_passes_the_same_publication_validators_without_publishing():
    _validate(TEXTS,TYPE)
    validate_template_texts(TYPE,TEXTS)
    preview=preview_draft(TYPE,{**TEXTS,'print_title_ru':TEXTS['title_ru'],'print_title_kk':TEXTS['title_kk']})
    for locale in ('ru','kk'):
        assert 'TEST-ID-0001' in preview[locale]['basis']
        assert '19.05.2026' in preview['ru']['body']
        assert '[' not in ''.join(preview[locale].values())


@pytest.mark.parametrize('field,token',[(field,token) for field,tokens in REQUIRED.items() for token in tokens])
def test_each_locale_requires_its_own_personal_data_variables(field,token):
    bad={**TEXTS,field:TEXTS[field].replace('{{'+token+'}}','')}
    with pytest.raises(TemplateDraftError) as error:_validate(bad,TYPE)
    assert error.value.code=='TEMPLATE_VARIABLE_REQUIRED'


@pytest.mark.parametrize('locale',['ru','kk'])
@pytest.mark.parametrize('token',['education.level_ru','education.specialty_kk','education_document.number'])
def test_education_variables_are_unknown_in_personal_data_contract(locale,token):
    bad={**TEXTS,'basis_template_'+locale:TEXTS['basis_template_'+locale]+' {{'+token+'}}'}
    with pytest.raises(TemplateDraftError) as error:_validate(bad,TYPE)
    assert error.value.code=='TEMPLATE_VARIABLE_UNKNOWN'


@pytest.mark.parametrize('field,marker',[('body_template_ru','[новая фамилия]'),('body_template_kk','[жаңа тегі]'),('basis_template_ru','[дата]'),('basis_template_kk','[жеке куәлік нөмірі]')])
def test_editorial_square_placeholders_are_rejected_in_validation_and_preview(field,marker):
    bad={**TEXTS,field:TEXTS[field]+' '+marker}
    with pytest.raises(TemplateDraftError) as error:_validate(bad,TYPE)
    assert error.value.code=='TEMPLATE_EDITORIAL_PLACEHOLDER'
    with pytest.raises(TemplateValidationError):validate_template_texts(TYPE,bad)
    with pytest.raises(TemplateDraftError):preview_draft(TYPE,bad)
    _validate(bad,TYPE,check_variables=False,require_complete=False) # Manual draft editing stays available.


def test_changes_of_name_and_patronymic_are_explicit_manual_text_not_automatic_declension():
    sample=deepcopy(SAMPLE)
    sample['personal_data'].update(changes_ru='Имя заменить на TEST-ИМЯ; отчество — на TEST-ОТЧЕСТВО', changes_kk='Аты TEST-АТЫ; әкесінің аты TEST-ӘКЕСІ')
    texts={**TEXTS,'body_template_ru':TEXTS['body_template_ru'].replace('внести изменения','По уточнённой кадровиком формулировке внести изменения')}
    rendered=_render({**texts,'item_type_code':TYPE},personal_data_values(sample))
    assert sample['personal_data']['changes_ru'] in rendered['body_template_ru']
    assert sample['personal_data']['changes_kk'] in rendered['body_template_kk']
    assert 'По уточнённой кадровиком формулировке' in rendered['body_template_ru']
    assert 'TEST-ID-0001' in rendered['basis_template_ru']
    assert '{{' not in str(rendered)


def test_conversion_removes_fixed_dates_and_placeholders_but_preserves_source_and_other_contracts():
    source={**TEXTS,'title_ru':'О смене фамилии и отчества','title_kk':'Тегін және әкесінің атын ауыстыру туралы','body_template_ru':'19 мая 2026 года [новая фамилия]','print_title_kk':'[күні] [номер]'}
    before=deepcopy(source)
    corrected=corrected_personal_data_texts(source)
    _validate(corrected,TYPE)
    assert source==before
    assert corrected['print_title_kk']==source['title_kk']
    assert '[' not in str(corrected) and '19 мая' not in str(corrected)
    from app.services.personnel_order_education_template_contract import TEXTS as EDUCATION_TEXTS,TYPE as EDUCATION_TYPE
    _validate(EDUCATION_TEXTS,EDUCATION_TYPE)
    assert get_personnel_order_template_spec(EDUCATION_TYPE).required_variables!=REQUIRED

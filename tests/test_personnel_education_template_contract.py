"""Education templates keep the common gates, without category requirements."""
import pytest

from app.services.personnel_order_education_template_contract import TYPE, TEXTS
from app.services.personnel_order_template_specs import get_personnel_order_template_spec, assert_personnel_order_template_specs, TEMPLATE_ONLY_TYPES
from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
from app.services.personnel_order_template_draft_service import _validate, TemplateDraftError
from app.services.personnel_order_print_titles import print_title_errors
from app.db.models.personnel_orders import PERSONNEL_ORDER_ITEM_TYPE_CODES


def test_education_contract_covers_only_data_used_by_id60():
    assert_personnel_order_template_specs()
    spec = get_personnel_order_template_spec(TYPE)
    assert TYPE not in TEMPLATE_ONLY_TYPES and TYPE in PERSONNEL_ORDER_ITEM_TYPE_CODES
    assert spec.required_variables and spec.required_fields
    assert 'education.level_ru' in spec.allowed_variables
    assert not any('qualification_category' in token or 'medical_specialty' in token for token in spec.allowed_variables)
    catalog = next(row for row in list_personnel_order_template_catalog() if row['type_code'] == TYPE)
    assert catalog['required_variables'] and catalog['required_fields']
    assert catalog['support_level'] == 'SUPPORTED'
    assert catalog['template_detail'] is None and catalog['pilot_detail'] is None
    _validate(TEXTS, TYPE)
    assert '[уровень образования]' in TEXTS['body_template_ru']
    assert '[білім деңгейі]' in TEXTS['body_template_kk']


@pytest.mark.parametrize('field,value,code', [
    ('body_template_ru', '', 'TEMPLATE_TEXT_REQUIRED'),
    ('preamble_kk', '   ', 'TEMPLATE_TEXT_REQUIRED'),
    ('body_template_ru', '{{qualification_category.level_ru}}', 'TEMPLATE_VARIABLE_UNKNOWN'),
    ('body_template_kk', '{{education.unapproved_required_field}}', 'TEMPLATE_VARIABLE_UNKNOWN'),
    ('preamble_ru', '<script>alert(1)</script>', 'TEMPLATE_TEXT_UNSAFE'),
])
def test_education_publication_still_validates_text(field, value, code):
    with pytest.raises(TemplateDraftError) as error:
        _validate({**TEXTS, field: value}, TYPE)
    assert error.value.code == code


def test_print_headings_still_require_values_and_category_validation_is_unchanged():
    assert len(print_title_errors(TEXTS)) == 2
    assert print_title_errors({**TEXTS, 'print_title_ru': TEXTS['title_ru'], 'print_title_kk': TEXTS['title_kk']}) == []
    with pytest.raises(TemplateDraftError) as error:
        _validate(TEXTS, 'QUALIFICATION_CATEGORY')
    assert error.value.code == 'TEMPLATE_VARIABLE_REQUIRED'
    category = get_personnel_order_template_spec('QUALIFICATION_CATEGORY')
    assert any(code.startswith('qualification_category.') for codes in category.required_variables.values() for code in codes)


def education_snapshot():
    return dict(effective_date='2026-11-01',
        document_forms_ru=dict(employee_full_name_genitive_ru='TEST RU CASE', position_document_genitive_ru='TEST RU POSITION'),
        document_forms_kk=dict(employee_full_name_genitive_kk='TEST KK CASE', position_document_possessive_kk='TEST KK POSITION'),
        document_org_unit=dict(document_genitive_ru='TEST RU UNIT', document_genitive_kk='TEST KK UNIT'),
        education=dict(level_ru='TEST RU LEVEL', level_kk='TEST KK LEVEL', specialty_ru='TEST RU SPECIALTY', specialty_kk='TEST KK SPECIALTY'),
        education_document=dict(kind_ru='TEST RU DOCUMENT', kind_kk='TEST KK DOCUMENT', number='TEST-01', issued_at='2026-06-20'))


def test_render_binds_literal_markers_without_rewriting_id60_or_grammatical_forms():
    from app.services.personnel_order_education_template_contract import education_values
    from app.services.personnel_order_template_application_service import _render
    source = dict(TEXTS)
    values = education_values(education_snapshot())
    rendered = _render({**TEXTS, 'item_type_code': TYPE}, values)
    assert TEXTS == source
    assert rendered['preamble_ru'] == TEXTS['preamble_ru']
    assert rendered['preamble_kk'] == TEXTS['preamble_kk']
    assert rendered['body_template_ru'] == 'С 01.11.2026 считать образование TEST RU POSITION TEST RU UNIT TEST RU CASE TEST RU LEVEL по специальности «TEST RU SPECIALTY».'
    assert rendered['basis_template_ru'] == 'Основание: диплом TEST RU DOCUMENT № TEST-01 от 20.06.2026, подтверждающий образование по специальности «TEST RU SPECIALTY».'
    assert rendered['basis_template_kk'] == 'Негіз: «TEST KK SPECIALTY» мамандығы бойынша TEST KK DOCUMENT № TEST-01 дипломы, 2026 жылғы 20 маусым.'
    assert values['effective_date.kk'] == '2026 жылғы 1 қарашадан'


@pytest.mark.parametrize('group,key,value', [
    ('education_document', 'issued_at', '2026-02-30'), ('education_document', 'number', ''),
    ('document_forms_ru', 'employee_full_name_genitive_ru', ''),
    ('document_forms_kk', 'position_document_possessive_kk', ''),
    ('document_org_unit', 'document_genitive_kk', ''),
])
def test_runtime_contract_requires_each_used_value_without_guessing(group, key, value):
    from app.services.personnel_order_education_template_contract import education_values
    payload = education_snapshot()
    payload[group][key] = value
    with pytest.raises(ValueError):
        education_values(payload)


def test_optional_education_and_missing_specialty_translation_render_without_guessing():
    from app.services.personnel_order_education_template_contract import education_values
    from app.services.personnel_order_template_application_service import _render
    payload = education_snapshot()
    payload['education'].update(level_code=None, level_ru='', level_kk='', specialty_kk='')
    values = education_values(payload)
    rendered = _render({**TEXTS, 'item_type_code': TYPE}, values)
    assert values['education.level_ru'] == values['education.level_kk'] == values['education.specialty_kk'] == ''
    assert 'TEST RU SPECIALTY' in rendered['body_template_ru']
    assert 'TEST RU SPECIALTY' not in rendered['body_template_kk']
    assert '[' not in rendered['body_template_ru'] + rendered['body_template_kk']
    payload['education'].update(level_code='NO_EDUCATION', level_ru='Без образования', level_kk='Білімі жоқ', specialty_ru='')
    assert education_values(payload)['education.level_ru'] == 'Без образования'
    _render({**TEXTS, 'item_type_code': TYPE}, education_values(payload))


def test_optional_values_still_reject_unsafe_content():
    from app.services.personnel_order_education_template_contract import education_values
    payload = education_snapshot()
    payload['education']['specialty_kk'] = '<script>unsafe</script>'
    with pytest.raises(ValueError):
        education_values(payload)


def test_explicit_to_clarify_date_is_separate_and_renders_without_a_fake_date():
    from app.services.personnel_order_education_template_contract import education_values
    from app.services.personnel_order_template_application_service import _render
    payload = education_snapshot()
    payload['education_document'].update(issued_at_status='TO_CLARIFY', issued_at='')
    original = dict(TEXTS)
    values = education_values(payload)
    assert values['education_document.issued_ru'] == 'Уточнить'
    assert values['education_document.issued_kk'] == 'Нақтылау қажет'
    rendered = _render({**TEXTS, 'item_type_code': TYPE}, values)
    assert 'Уточнить' in rendered['basis_template_ru']
    assert 'Нақтылау қажет' in rendered['basis_template_kk']
    assert '20.06.2026' not in rendered['basis_template_ru']
    assert payload['education_document']['issued_at'] == ''
    assert TEXTS == original


@pytest.mark.parametrize('status,issued_at', [('TO_CLARIFY', '2026-06-20'), ('UNKNOWN', ''), ('KNOWN', ''), (None, '')])
def test_issue_date_state_rejects_ambiguous_or_incomplete_values(status, issued_at):
    from app.services.personnel_order_education_template_contract import education_values
    payload = education_snapshot()
    payload['education_document'].update(issued_at_status=status, issued_at=issued_at)
    with pytest.raises(ValueError):
        education_values(payload)

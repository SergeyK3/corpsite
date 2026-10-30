from copy import deepcopy

import pytest

from app.services.personnel_order_service_length_contract import (
    TYPE, REQUIRED, TEXTS, TOKENS, bind_editor_texts, service_length_values,
    prepare_service_length_payload,
)
from app.services.personnel_order_template_specs import assert_personnel_order_template_specs, get_personnel_order_template_spec
from app.services.personnel_order_template_validation import validate_template_texts, TemplateValidationError
from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
from app.services.personnel_orders_editorial.basis_policy import resolve_basis_required


def payload():
    return dict(effective_date='2026-11-01',
        document_forms_ru=dict(employee_full_name_genitive_ru='Тестова Айдара Ерлановича', position_document_genitive_ru='врача'),
        document_forms_kk=dict(employee_full_name_genitive_kk='Тестовтың', position_document_possessive_kk='дәрігері'),
        document_org_unit=dict(document_genitive_ru='отделения', document_genitive_kk='бөлімшесінің'),
        service_length=dict(new_ru='10 лет 2 месяца', new_kk='10 жыл 2 ай'),
        basis=dict(ru='Тестовый документ № TEST-1', kk='Сынақ құжаты № TEST-1'))


def test_registry_and_bilingual_basis_are_independent_of_category():
    assert_personnel_order_template_specs()
    spec = get_personnel_order_template_spec(TYPE)
    assert dict(spec.required_variables) == REQUIRED
    assert not any('qualification_category' in token or 'medical_specialty' in token for token in spec.allowed_variables)
    assert resolve_basis_required(TYPE) == (True, None)
    values = service_length_values(payload())
    assert values['service_length.new_ru'] == '10 лет 2 месяца'
    assert values['basis.ru'] != values['basis.kk']
    assert values['effective_date.ru'] == '01.11.2026'
    validate_template_texts(TYPE, TEXTS)
    category = get_personnel_order_template_spec('QUALIFICATION_CATEGORY')
    assert 'qualification_category.level_ru' in category.allowed_variables
    assert 'service_length.new_ru' not in category.allowed_variables
    rows = {row['type_code']: row for row in list_personnel_order_template_catalog()}
    assert rows[TYPE]['support_level'] == 'SUPPORTED'
    assert rows[TYPE]['formalization_warning'] is None
    assert 'вручную отдельно на RU и KK' in rows[TYPE]['notes']
    assert 'не рассчитывает стаж по датам' in rows[TYPE]['notes']
    assert rows[TYPE]['computed_fields'] == []
    assert 'сертификат' not in ' '.join(rows[TYPE]['required_fields']).lower()
    assert rows['QUALIFICATION_CATEGORY']['formalization_warning'] != rows[TYPE]['formalization_warning']


def test_effective_date_never_calculates_or_changes_manual_length_and_grounds():
    source = payload()
    original = service_length_values(source)
    source['effective_date'] = '2035-12-31'
    changed = service_length_values(source)
    for token in ('service_length.new_ru', 'service_length.new_kk', 'basis.ru', 'basis.kk'):
        assert changed[token] == original[token]
    assert changed['effective_date.ru'] != original['effective_date.ru']
    # One locale cannot supply or replace the other's manually entered value.
    source['service_length']['new_ru'] = 'РУЧНОЙ СТАЖ RU'
    assert service_length_values(source)['service_length.new_kk'] == original['service_length.new_kk']


class NoDirectoryAccess:
    def execute(self, *args, **kwargs):
        raise AssertionError('Manual document subject must not read or write personnel records')


def test_manual_subject_is_an_unlinked_snapshot_without_directory_access_or_declension():
    source = payload()
    source['subject_mode'] = 'MANUAL'
    manual = {'full_name': 'Ручной Тестовый Сотрудник'}
    prepared = prepare_service_length_payload(NoDirectoryAccess(), source, None, '2026-11-01', manual)
    assert prepared['employee_id'] is None and prepared['subject_mode'] == 'MANUAL'
    assert prepared['source_employee_name'] == manual['full_name']
    assert prepared['unresolved_subject']['full_name'] == manual['full_name']
    assert prepared['unresolved_subject']['needs_employee_link'] is False
    assert prepared['document_forms_ru'] == source['document_forms_ru']
    assert prepared['document_forms_kk'] == source['document_forms_kk']
    # Saving again restores the snapshot without requiring an outer subject or ID.
    assert prepare_service_length_payload(NoDirectoryAccess(), prepared, None, '2026-11-01') == prepared


@pytest.mark.parametrize('change', ['name', 'form_ru', 'form_kk', 'employee_id', 'assignment_id', 'person_id'])
def test_manual_subject_requires_explicit_name_and_cases_and_rejects_personnel_links(change):
    source = payload()
    subject, employee_id = {'full_name': 'Ручной Тест'}, None
    if change == 'name': subject['full_name'] = ''
    if change == 'form_ru': source['document_forms_ru']['employee_full_name_genitive_ru'] = ''
    if change == 'form_kk': source['document_forms_kk']['employee_full_name_genitive_kk'] = ''
    if change == 'employee_id': employee_id = 900001
    if change in {'assignment_id', 'person_id'}: source[change] = 123
    with pytest.raises(ValueError):
        prepare_service_length_payload(NoDirectoryAccess(), source, employee_id, '2026-11-01', subject)


@pytest.mark.parametrize('namespace,key', [
    ('basis', 'ru'), ('basis', 'kk'), ('service_length', 'new_ru'), ('service_length', 'new_kk'),
    ('document_forms_ru', 'employee_full_name_genitive_ru'), ('document_forms_kk', 'employee_full_name_genitive_kk'),
    ('document_forms_ru', 'position_document_genitive_ru'), ('document_forms_kk', 'position_document_possessive_kk'),
    ('document_org_unit', 'document_genitive_ru'), ('document_org_unit', 'document_genitive_kk'),
])
def test_document_data_is_required_on_each_language(namespace, key):
    source = payload()
    source[namespace][key] = ' '
    with pytest.raises(ValueError, match='Заполните'):
        service_length_values(source)


@pytest.mark.parametrize('day', ['', '2026-02-30', '20261101', '1899-01-01'])
def test_invalid_effective_date_is_rejected(day):
    source = payload()
    source['effective_date'] = day
    with pytest.raises(ValueError):
        service_length_values(source)


def test_binding_preserves_every_other_character_and_remains_idempotent():
    source = deepcopy(TEXTS)
    for locale, tokens in TOKENS.items():
        for key in ('preamble_', 'body_template_'):
            for marker, token in tokens.items():
                source[key + locale] = source[key + locale].replace('{{' + token + '}}', marker)
            source[key + locale] += '\nСОХРАНИТЬ / САҚТАУ [неизвестный маркер]'
        source['basis_template_' + locale] = source['basis_template_' + locale].replace('{{basis.' + locale + '}}', '{{basis}}')
    result = bind_editor_texts(source)
    assert result['body_template_ru'] == TEXTS['body_template_ru'] + '\nСОХРАНИТЬ / САҚТАУ [неизвестный маркер]'
    assert result['body_template_kk'] == TEXTS['body_template_kk'] + '\nСОХРАНИТЬ / САҚТАУ [неизвестный маркер]'
    assert result['basis_template_ru'] == TEXTS['basis_template_ru']
    assert bind_editor_texts(result) == result


def test_category_tokens_and_unilingual_basis_are_not_accepted():
    source = dict(TEXTS, basis_template_kk='Негіз: {{basis.ru}}.')
    with pytest.raises(TemplateValidationError, match='basis.kk'):
        validate_template_texts(TYPE, source)
    source = dict(TEXTS, body_template_ru=TEXTS['body_template_ru'] + '{{qualification_category.level_ru}}')
    with pytest.raises(TemplateValidationError, match='Unknown variable'):
        validate_template_texts(TYPE, source)

from copy import deepcopy

import pytest

from app.services.personnel_order_transfer_name import confirmed_transfer_accusative
from app.services.personnel_order_template_application_service import _render, TemplateApplicationError
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_orders_editorial.generators import generate_item_body
from app.services.personnel_orders_editorial.mapper import build_item_ctx


@pytest.mark.parametrize('token', ['employee.full_name', 'employee.full_name_dative_ru', 'employee.full_name_accusative_ru'])
def test_female_transfer_uses_confirmed_accusative_and_preserves_kk(token):
    payload = {'document_forms_ru': {'employee_full_name_accusative_ru': 'Тестову Анну Ивановну'}}
    before = deepcopy(payload)
    template = {**get_personnel_order_template_spec('TRANSFER').initial_texts, 'item_type_code': 'TRANSFER',
                'body_template_ru': 'Перевести {{' + token + '}} с {{effective_date}}.',
                'body_template_kk': '{{employee.full_name}} ауыстырылсын.',
                'basis_template_ru': '{{basis}}', 'basis_template_kk': '{{basis}}'}
    values = {'employee.full_name': 'Тестова Анна Ивановна',
              'employee.full_name_accusative_ru': confirmed_transfer_accusative(payload),
              'employee.full_name_dative_ru': 'Тестовой Анне Ивановне',
              'effective_date': '01.11.2026', 'basis': 'Синтетическое заявление'}
    result = _render(template, values)
    assert result['body_template_ru'] == 'Перевести Тестову Анну Ивановну с 01.11.2026.'
    assert result['body_template_kk'] == 'Тестова Анна Ивановна ауыстырылсын.'
    assert payload == before


@pytest.mark.parametrize('payload', [{}, {'document_forms_ru': {'employee_full_name_dative_ru': 'Тестовой Анне Ивановне'}}])
def test_missing_confirmed_accusative_requires_manual_input(payload):
    assert confirmed_transfer_accusative(payload) == ''
    template = {**get_personnel_order_template_spec('TRANSFER').initial_texts, 'item_type_code': 'TRANSFER'}
    with pytest.raises(TemplateApplicationError, match='винительном падеже'):
        _render(template, {'employee.full_name': 'Тестова Анна Ивановна'})


def test_saved_sources_and_editorial_generator():
    saved = {'employee': {'name': {'full_name_accusative_ru': 'Тестову Анну Ивановну'}}}
    assert confirmed_transfer_accusative(saved) == 'Тестову Анну Ивановну'
    item = {'item_type_code': 'TRANSFER', 'effective_date': '2026-11-01', 'payload': saved}
    ctx = build_item_ctx(item, 'Тестова Анна Ивановна')
    assert generate_item_body('ru', ctx)['generated_text'].startswith('Перевести Тестову Анну Ивановну ')
    assert generate_item_body('kk', ctx)['generated_text'].startswith('Тестова Анна Ивановна ')


@pytest.mark.parametrize('payload', [
    {'employee_full_name_accusative_ru': 'Тестову Анну Ивановну'},
    {'employee': {'employee_full_name_accusative_ru': 'Тестову Анну Ивановну'}},
    {'employee': {'document_forms_ru': {'employee_full_name_accusative_ru': 'Тестову Анну Ивановну'}}},
])
def test_direct_and_employee_saved_forms(payload):
    assert confirmed_transfer_accusative(payload) == 'Тестову Анну Ивановну'

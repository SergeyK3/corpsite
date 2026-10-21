from copy import deepcopy
from datetime import date

import pytest

from app.services.personnel_order_work_allowance_contract import BODY_RU, BODY_KK, MODE, values
from app.services.personnel_order_replacement_contract import variant, validate_bodies, SAMPLE_CONCURRENT
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_draft_service import preview_draft, _validate, TEXT_FIELDS
from app.services.personnel_order_template_application_service import _values, _render
from app.services import personnel_order_manual_draft_service as manual


def texts():
    return {**get_personnel_order_template_spec('CONCURRENT_DUTY_START').initial_texts,
            'body_template_ru': BODY_RU, 'body_template_kk': BODY_KK,
            'item_type_code': 'CONCURRENT_DUTY_START'}


def payload():
    concurrent = {**SAMPLE_CONCURRENT, 'total_rate': '1.25', 'position_id': 17, 'org_unit_id': 19}
    concurrent.pop('rate')
    return {'concurrent': concurrent, 'replacement': {'mode': MODE, 'allowance_percent': 25,
            'allowance_basis_ru': 'должностного оклада', 'allowance_basis_kk': 'лауазымдық айлық ақыдан'}}


class MemoryConnection:
    def execute(self, statement, params):
        self.statement = str(statement)
        return self

    def mappings(self): return self

    def first(self):
        if 'personnel_order_template_versions' in self.statement:
            return texts()
        return {'full_name': 'Тестовый Сотрудник', 'position_name': 'Основная должность', 'org_unit_name': 'Основное подразделение'}


def test_mode_preview_and_real_item_values_without_additional_rate():
    template = texts()
    _validate({k: template[k] for k in TEXT_FIELDS}, 'CONCURRENT_DUTY_START')
    assert variant(template) == MODE
    validate_bodies(template)
    preview = preview_draft('CONCURRENT_DUTY_START', {k:v for k,v in template.items() if k != 'item_type_code'})
    assert '25%' in preview['ru']['body'] and '1,25' in preview['ru']['body']
    assert 'лауазымдық айлық ақыдан 25 %' in preview['kk']['body']
    source = payload()
    before = deepcopy(source)
    rendered_values, _, missing = _values(MemoryConnection(), {'item_type_code': 'CONCURRENT_DUTY_START', 'employee_id': 1, 'effective_date': date(2026, 2, 2), 'payload': source}, template)
    rendered = _render(template, rendered_values, draft_preview=True)
    assert not missing
    assert 'с 02.02.2026' in rendered['body_template_ru']
    assert '2026 жылғы 2 ақпаннан бастап' in rendered['body_template_kk']
    assert '1,25' in rendered['body_template_ru'] and '25%' in rendered['body_template_ru']
    assert 'төленсін.' in rendered['body_template_kk'] and 'төленсін..' not in rendered['body_template_kk']
    assert rendered_values['concurrent.rate'] == ''
    assert not any('замещаем' in t or 'еңбек демалысы' in t for t in rendered.values())
    assert source == before


@pytest.mark.parametrize('rate', [None, '', '0.2'])
def test_payload_normalization_preserves_total_percent_basis_and_dictionary_ids(monkeypatch, rate):
    monkeypatch.setattr(manual, '_selected_employee_payload', lambda *a, **k: {})
    source = payload()
    source['concurrent']['rate'] = rate
    before = deepcopy(source)
    saved = manual.prepare_manual_item_payload(MemoryConnection(), item_type_code='CONCURRENT_DUTY_START', employee_id=1,
            effective_date=date(2026, 2, 2), item_payload=source, template_version_id=123, capabilities={'job_catalog_supported': False})
    assert saved['concurrent']['total_rate'] == saved['total_rate'] == '1.25'
    assert saved['replacement'] == source['replacement']
    assert saved['concurrent']['position_id'] == 17 and saved['concurrent']['org_unit_id'] == 19
    if rate:
        assert saved['concurrent_rate'] == saved['concurrent']['rate'] == rate
    else:
        assert 'rate' not in saved['concurrent'] and 'concurrent_rate' not in saved
    assert source == before


@pytest.mark.parametrize('section,key,value', [('concurrent','total_rate',None),('concurrent','total_rate','NaN'),
    ('concurrent','rate',0),('concurrent','rate','1.25'),('replacement','allowance_percent',101),
    ('replacement','allowance_basis_kk',''),('concurrent','position_kk','')])
def test_invalid_values_are_rejected(section, key, value):
    source = payload()
    source[section][key] = value
    with pytest.raises(ValueError): values(source['concurrent'], source['replacement'], '2026-02-02')


@pytest.mark.parametrize('lang', ['ru','kk'])
def test_each_language_must_keep_total_and_allowance(lang):
    template = texts()
    template['body_template_'+lang] = template['body_template_'+lang].replace('{{total.rate}}', '1,25')
    with pytest.raises(ValueError, match='total.rate'): validate_bodies(template)


def test_optional_rate_token_does_not_force_an_invented_value():
    template = texts()
    template['body_template_ru'] += ' {{concurrent.rate}}'
    source = payload()
    rendered = _render(template, values(source['concurrent'],source['replacement'],'2026-02-02'), draft_preview=True)
    assert '0,25' not in rendered['body_template_ru']


@pytest.mark.parametrize('mode', ['RATE','PAY'])
def test_existing_replacement_payload_normalization_is_unchanged(monkeypatch, mode):
    from app.services.personnel_order_replacement_contract import RATE_RU, RATE_KK, PAY_RU, PAY_KK, SAMPLE_REPLACEMENT
    monkeypatch.setattr(manual, '_selected_employee_payload', lambda *a, **k: {})
    class LegacyConnection(MemoryConnection):
        def first(self):
            return {'body_template_ru': RATE_RU if mode == 'RATE' else PAY_RU,
                    'body_template_kk': RATE_KK if mode == 'RATE' else PAY_KK}
    source = {'concurrent':dict(SAMPLE_CONCURRENT), 'replacement':dict(SAMPLE_REPLACEMENT)}
    saved = manual.prepare_manual_item_payload(LegacyConnection(), item_type_code='CONCURRENT_DUTY_START', employee_id=1,
            effective_date=date(2026, 2, 2), item_payload=source, template_version_id=123, capabilities={'job_catalog_supported': False})
    assert saved['replacement']['mode'] == mode
    assert saved['replacement']['employee_name_ru'] == SAMPLE_REPLACEMENT['employee_name_ru']
    if mode == 'PAY':
        assert 'rate' not in saved['concurrent'] and 'total_rate' not in saved['concurrent']
        assert 'total_rate' not in saved and 'concurrent_rate' not in saved
    else:
        assert saved['concurrent_rate'] == SAMPLE_CONCURRENT['rate']
        assert saved['total_rate'] == SAMPLE_CONCURRENT['total_rate']

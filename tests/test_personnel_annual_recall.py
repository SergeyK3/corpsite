"""Annual recall is a bilingual document draft, never a personnel action."""
from datetime import date
import importlib.util
from pathlib import Path

import pytest

from app.services.personnel_order_recall_contract import TEXTS, values, render
from app.services.personnel_order_template_application_service import _render
from app.services.personnel_order_template_draft_service import _validate, TemplateDraftError
from app.services.personnel_orders_editorial.generators import generate_item_body, generate_basis_text


@pytest.fixture
def payload():
    return {
        'source_employee_name': 'Тестов Тест Тестович',
        'source_position_name': 'врач', 'source_org_unit_name': 'Терапия',
        'recall_position_kk': 'дәрігер', 'recall_org_unit_kk': 'Терапия',
        'basis_ru': 'Докладная записка и личное согласие Тестова Теста Тестовича',
        'basis_kk': 'Баяндау хат және Тесттің жеке келісімі',
    }


def test_recall_full_template_uses_separate_bases_and_scoped_date(payload):
    data=values(payload,date(2026,10,12))
    result=_render({'item_type_code':'LEAVE.ANNUAL.RECALL',**TEXTS},data)
    assert result['body_template_kk'].startswith('2026 жылғы 12 қазаннан бастап')
    assert result['body_template_ru'].startswith('Отозвать из ежегодного оплачиваемого трудового отпуска с 12 октября 2026 года')
    for locale in ['ru','kk']:
        assert len(result['body_template_'+locale].split('\n\n'))==2
        assert 'Тестов Тест Тестович' in result['body_template_'+locale]
        assert payload['basis_'+locale] in result['basis_template_'+locale]
        assert '{{' not in ' '.join(result.values())
    assert result['body_template_kk'].count('бөлімше')==1
    assert 'бөлімшесі бөлімшесі' not in result['body_template_kk']
    _validate(TEXTS,'LEAVE.ANNUAL.RECALL')
    assert 'rate' not in data


@pytest.mark.parametrize('field',['source_employee_name','source_position_name','source_org_unit_name','recall_position_kk','recall_org_unit_kk','basis_ru','basis_kk'])
def test_recall_requires_document_values_without_fallback(payload,field):
    payload[field]=''
    with pytest.raises(ValueError,match='Заполните поля отзыва'):
        values(payload,'2026-10-12')


def test_recall_does_not_repeat_basis_label_or_period(payload):
    payload.update(basis_ru='Основание: Докладная записка.',basis_kk='Негіз: Баяндау хат.')
    data=values(payload,'2026-10-12')
    assert render('basis_template_ru',data)=='Основание: Докладная записка.'
    assert render('basis_template_kk',data)=='Негіз: Баяндау хат.'


def test_recall_rejects_foreign_tokens_at_publication():
    texts=dict(TEXTS);texts['body_template_ru']+=' {{rate}}'
    with pytest.raises(TemplateDraftError,match='Неизвестная переменная'):
        _validate(texts,'LEAVE.ANNUAL.RECALL')


def test_recall_generators_share_the_contract(payload):
    context={'item_type_code':'LEAVE.ANNUAL.RECALL','recall_payload':payload,'effective_date':'2026-10-12'}
    data=values(payload,'2026-10-12')
    for locale in ['ru','kk']:
        assert generate_item_body(locale,context)['generated_text']==render('body_template_'+locale,data)
        assert generate_basis_text(locale,context)['generated_text']==render('basis_template_'+locale,data)


def test_recall_migration_extends_existing_constraint_without_losing_codes(monkeypatch):
    spec=importlib.util.spec_from_file_location('recall_migration',Path('alembic/versions/hrrecall001_annual_leave_recall_drafts.py'))
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    statements=[]
    class Result:
        def scalar_one(self):return "CHECK (kind = ANY (ARRAY['HIRE'::text, 'LEAVE.ANNUAL.GRANT'::text, 'OTHER_EXISTING_KIND'::text]))"
    class Conn:
        def execute(self,*args):return Result()
    monkeypatch.setattr(migration.op,'get_bind',lambda:Conn())
    monkeypatch.setattr(migration.op,'execute',statements.append)
    migration.upgrade()
    additions=[s for s in statements if 'ADD CONSTRAINT' in s]
    assert len(additions)==2
    assert all('LEAVE.ANNUAL.RECALL' in s and 'OTHER_EXISTING_KIND' in s for s in additions)
    assert 'DEFERRABLE INITIALLY IMMEDIATE' in statements[-1]
    assert all('UPDATE ' not in s and 'INSERT ' not in s for s in statements)

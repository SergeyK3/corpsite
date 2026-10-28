"""Qualification-category document snapshots; no changes to the employee dossier."""
import re
from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Mapping

TYPE = "QUALIFICATION_CATEGORY"
LEVELS = {"highest": ("высшей", "жоғары"), "first": ("первой", "бірінші"), "second": ("второй", "екінші")}
BODY_RU = 'С {{effective_date.ru}} категория {{position.document_genitive_ru}} («{{medical_specialty.name_ru}}») {{org_unit.document_genitive_ru}} {{employee.full_name_genitive_ru}} будет считаться {{qualification_category.category_code_ru}} „{{qualification_category.level_ru}}“ до {{qualification_category.valid_until_ru}}.'
BODY_KK = '{{effective_date.kk}} бастап {{org_unit.document_genitive_kk}} {{position.document_possessive_kk}} («{{medical_specialty.name_kk}}») {{employee.full_name_genitive_kk}} санаты {{qualification_category.category_code_kk}} „{{qualification_category.level_kk}}“ {{qualification_category.valid_until_kk}} дейін болып есептелсін.'
TEXTS = dict(title_ru='Об изменении квалификационной категории', title_kk='Біліктілік санатын өзгерту туралы',
             preamble_ru='На основании {{basis}}', preamble_kk='{{basis}} негізінде',
             body_template_ru=BODY_RU, body_template_kk=BODY_KK,
             basis_template_ru='Основание: {{basis}}.', basis_template_kk='Негіз: {{basis}}.')
REQUIRED = {"body_template_ru": tuple(re.findall(r'\{\{([\w.]+)\}\}', BODY_RU)),
            "body_template_kk": tuple(re.findall(r'\{\{([\w.]+)\}\}', BODY_KK))}
VARIABLES = tuple(dict.fromkeys((*REQUIRED['body_template_ru'], *REQUIRED['body_template_kk'], 'basis',
    'employee.full_name', 'org_unit.title_ru', 'org_unit.title_kk', 'qualification_category.category')))


def valid_until(value: str) -> date:
    start = date.fromisoformat(value)
    year = start.year + 5
    return start.replace(year=year, day=min(start.day, monthrange(year, start.month)[1])) - timedelta(days=1)


def category_values(payload: Mapping[str, Any]) -> dict[str, str]:
    """Render only saved snapshots; never resolve names from a live dictionary."""
    if isinstance(payload, Mapping) and (payload.get('contract') == 'medical-qualification-category-v2' or isinstance(payload.get('qualification_category'), Mapping) and 'code' in payload['qualification_category']):
        from app.services.personnel_order_category_classifier_contract import classifier_values
        return classifier_values(payload)
    def required(source, key):
        value = source.get(key) if isinstance(source, Mapping) else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Заполните {key}.')
        return value.strip()
    if not isinstance(payload, Mapping):
        raise ValueError('Некорректные данные проверки.')
    for key in ('qualification_category','medical_specialty','document_org_unit','document_forms_ru','document_forms_kk'):
        if not isinstance(payload.get(key), Mapping):
            raise ValueError(f'Заполните {key}.')
    category = payload.get('qualification_category') or {}
    level = required(category, 'category')
    if level not in LEVELS:
        raise ValueError('Допустимы только highest, first, second.')
    assigned = required(category, 'assigned_at')
    start = date.fromisoformat(assigned)
    end = valid_until(assigned)
    specialty = payload.get('medical_specialty') or {}
    if type(specialty.get('medical_specialty_id')) is not int or specialty['medical_specialty_id'] < 1:
        raise ValueError('Выберите специальность из справочника.')
    unit = payload.get('document_org_unit') or {}
    ru = payload.get('document_forms_ru') or {}
    kk = payload.get('document_forms_kk') or {}
    months_from = ('қаңтардан','ақпаннан','наурыздан','сәуірден','мамырдан','маусымнан','шілдеден','тамыздан','қыркүйектен','қазаннан','қарашадан','желтоқсаннан')
    months_to = ('қаңтарға','ақпанға','наурызға','сәуірге','мамырға','маусымға','шілдеге','тамызға','қыркүйекке','қазанға','қарашаға','желтоқсанға')
    return {
        'employee.full_name': required(payload, 'source_employee_name'),
        'employee.full_name_genitive_ru': required(ru, 'employee_full_name_genitive_ru'),
        'employee.full_name_genitive_kk': required(kk, 'employee_full_name_genitive_kk'),
        'position.document_genitive_ru': required(ru, 'position_document_genitive_ru'),
        'position.document_possessive_kk': required(kk, 'position_document_possessive_kk'),
        'org_unit.title_ru': required(unit, 'name'), 'org_unit.title_kk': required(unit, 'name_kk'),
        'org_unit.document_genitive_ru': required(unit, 'document_genitive_ru'),
        'org_unit.document_genitive_kk': required(unit, 'document_genitive_kk'),
        'medical_specialty.name_ru': required(specialty, 'name_ru'), 'medical_specialty.name_kk': required(specialty, 'name_kk'),
        'effective_date.ru': start.strftime('%d.%m.%Y'),
        'effective_date.kk': f'{start.year} жылғы {start.day} {months_from[start.month-1]}',
        'qualification_category.category': level,
        'qualification_category.level_ru': LEVELS[level][0], 'qualification_category.level_kk': LEVELS[level][1],
        'qualification_category.category_code_ru': required(category, 'category_code_ru'),
        'qualification_category.category_code_kk': required(category, 'category_code_kk'),
        'qualification_category.valid_until_ru': end.strftime('%d.%m.%Y'),
        'qualification_category.valid_until_kk': f'{end.year} жылғы {end.day} {months_to[end.month-1]}',
        'basis': required(category, 'category_code_source'),
    }


SAMPLE = {
    'source_employee_name': 'Тестов Айдар Ерланович',
    'document_forms_ru': {'employee_full_name_genitive_ru': 'Тестова Айдара Ерлановича', 'position_document_genitive_ru': 'врача-терапевта'},
    'document_forms_kk': {'employee_full_name_genitive_kk': 'Айдар Ерланұлы Тестовтың', 'position_document_possessive_kk': 'дәрігер-терапевті'},
    'document_org_unit': {'name': 'Тестовое отделение терапии', 'name_kk': 'Тестілік терапия бөлімшесі', 'document_genitive_ru': 'тестового отделения терапии', 'document_genitive_kk': 'Тестілік терапия бөлімшесінің'},
    'medical_specialty': {'medical_specialty_id': 900003, 'name_ru': 'Терапия', 'name_kk': 'Терапия'},
    'qualification_category': {'category': 'highest', 'assigned_at': '2026-06-11', 'category_code_ru': '7.2 (Р)', 'category_code_kk': '7.2 (R)', 'category_code_source': 'TEST сертификат № TEST-01 от 11.06.2026'},
}
PREVIEW = {locale: category_values(SAMPLE) for locale in ('ru', 'kk')}


def prepare_category_payload(conn, payload, employee_id, effective_date, previous=None):
    """Capture a new dictionary choice once; preserve the old snapshot on edits."""
    if isinstance(payload, Mapping) and (payload.get('contract') == 'medical-qualification-category-v2' or isinstance(payload.get('qualification_category'), Mapping) and 'code' in payload['qualification_category']):
        from app.services.personnel_order_category_classifier_contract import prepare_classifier_payload
        return prepare_classifier_payload(conn, payload, employee_id, effective_date, previous)
    from copy import deepcopy
    from sqlalchemy import text
    out = deepcopy(dict(payload or {}))
    if not employee_id:
        raise ValueError('Выберите сотрудника из справочника.')
    employee = conn.execute(text('SELECT full_name FROM employees WHERE employee_id=:id'), {'id':employee_id}).scalar_one_or_none()
    if not employee:
        raise ValueError('Сотрудник не найден.')
    out['employee_id'] = employee_id
    out['source_employee_name'] = out.get('source_employee_name') or employee
    incoming = out.get('medical_specialty')
    if not isinstance(incoming, Mapping) or type(incoming.get('medical_specialty_id')) is not int:
        raise ValueError('Выберите медицинскую специальность из справочника.')
    old = (previous or {}).get('medical_specialty')
    if isinstance(old, Mapping) and old.get('medical_specialty_id') == incoming['medical_specialty_id']:
        out['medical_specialty'] = deepcopy(dict(old))
    else:
        row = conn.execute(text('SELECT medical_specialty_id,name,name_kk FROM medical_specialties WHERE medical_specialty_id=:id AND is_active'), {'id':incoming['medical_specialty_id']}).mappings().one_or_none()
        if row is None or not row['name'] or not row['name_kk']:
            raise ValueError('У выбранной специальности необходимы названия RU и KK.')
        out['medical_specialty'] = dict(medical_specialty_id=row['medical_specialty_id'], name_ru=row['name'], name_kk=row['name_kk'])
    category_values(out)
    assigned = out['qualification_category']['assigned_at']
    if str(effective_date) != assigned:
        raise ValueError('Дата действия должна совпадать с датой присвоения категории.')
    out['qualification_category']['valid_until'] = valid_until(assigned).isoformat()
    return out

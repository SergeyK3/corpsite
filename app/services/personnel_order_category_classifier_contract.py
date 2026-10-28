"""Opt-in classifier contract for the new draft; legacy snapshots stay unchanged."""
import re
from copy import deepcopy
from datetime import date
from typing import Mapping
from sqlalchemy import text
from app.db.medical_qualification_categories_schema import CATEGORIES
from app.services.personnel_order_category_contract import valid_until

CONTRACT = 'medical-qualification-category-v2'
BODY_RU = 'С {{effective_date.ru}} категория {{position.document_genitive_ru}}{{medical_specialty.clause_ru}} {{org_unit.document_genitive_ru}} {{employee.full_name_genitive_ru}} будет считаться „{{qualification_category.level_ru}}“ до {{qualification_category.valid_until_ru}}.'
BODY_KK = '{{effective_date.kk}} бастап {{org_unit.document_genitive_kk}} {{position.document_possessive_kk}}{{medical_specialty.clause_kk}} {{employee.full_name_genitive_kk}} санаты „{{qualification_category.level_kk}}“ {{qualification_category.valid_until_kk}} дейін болып есептелсін.'
REQUIRED = {field: tuple(re.findall(r'\{\{([\w.]+)\}\}', body)) for field, body in (
    ('body_template_ru', BODY_RU), ('body_template_kk', BODY_KK))}
VARIABLES = ('medical_specialty.clause_ru', 'medical_specialty.clause_kk')
LEVELS = {2: ('второй', 'екінші'), 3: ('первой', 'бірінші'), 4: ('высшей', 'жоғары')}
REQUIRED_ORDER_FIELDS = (
    'Сотрудник из справочника', 'Категория из справочника: код 2, 3 или 4',
    'Дата присвоения', 'Дата начала действия',
    'ФИО в родительном падеже RU и в ілік септік KK',
    'Должность в родительном падеже RU и в притяжательной форме KK',
    'Подразделение в родительном падеже RU и в ілік септік KK',
)
OPTIONAL_ORDER_FIELDS = ('Медицинская специальность из справочника (ID и снимки названий RU/KK)',)
COMPUTED_ORDER_FIELDS = ('Дата окончания: дата присвоения + 5 календарных лет − 1 день; вручную не вводится',)
FORMALIZATION_WARNING = (
    'PARTIAL: подтверждающий документ и его номер/дата пока задаются текстом основания шаблона; '
    'их подстановка и проверка не формализованы. Перед публикацией проверьте основания RU/KK '
    'и замените шаблонные реквизиты, если они остались. '
    'Автоматическое обновление кадрового досье не входит в документный приказ.'
)
ORDER_NOTES = (
    'Медицинская специальность необязательна. Коды сертификата RU/KK и источник кода не используются. '
    'Даты присвоения и начала действия раздельные; дата окончания вычисляется от даты присвоения. '
    'Проверяются только падежные формы ФИО, должности и подразделения, используемые в распорядительном тексте.'
)


def is_classifier_template(values):
    return any('medical_specialty.clause_' in (values.get(field) or '') for field in REQUIRED)


def required_variables(values, legacy):
    return REQUIRED if is_classifier_template(values) else legacy


def classifier_values(payload):
    def optional(source, key):
        value = source.get(key) if isinstance(source, Mapping) else None
        return value.strip() if isinstance(value, str) else ''
    def required(source, key):
        value = source.get(key) if isinstance(source, Mapping) else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Заполните {key}.')
        return value.strip()
    def order_date(source, key):
        value = required(source, key)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError(f'Укажите полную дату {key} в формате ГГГГ-ММ-ДД.')
        parsed = date.fromisoformat(value)
        if not 1900 <= parsed.year <= 9994:
            raise ValueError(f'Некорректная дата {key}.')
        return parsed
    category = payload.get('qualification_category')
    if not isinstance(category, Mapping) or type(category.get('code')) is not int or category['code'] not in LEVELS:
        raise ValueError('Выберите категорию с кодом 2, 3 или 4 из справочника.')
    code = category['code']
    _, name, name_kk = CATEGORIES[code - 1]
    if (category.get('name_ru'), category.get('name_kk')) != (name, name_kk):
        raise ValueError('Название категории не соответствует справочнику.')
    assigned = order_date(category, 'assigned_at')
    effective = order_date(payload, 'effective_date')
    end = valid_until(assigned.isoformat())
    specialty = payload.get('medical_specialty')
    clauses = {'ru': '', 'kk': ''}
    if specialty is not None:
        if not isinstance(specialty, Mapping) or type(specialty.get('medical_specialty_id')) is not int or specialty['medical_specialty_id'] < 1:
            raise ValueError('Выберите специальность из справочника или оставьте поле пустым.')
        clauses = {locale: f' («{required(specialty, "name_" + locale)}»)' for locale in ('ru', 'kk')}
    ru, kk, unit = (payload.get(key) for key in ('document_forms_ru', 'document_forms_kk', 'document_org_unit'))
    months_from = ('қаңтардан','ақпаннан','наурыздан','сәуірден','мамырдан','маусымнан','шілдеден','тамыздан','қыркүйектен','қазаннан','қарашадан','желтоқсаннан')
    months_to = ('қаңтарға','ақпанға','наурызға','сәуірге','мамырға','маусымға','шілдеге','тамызға','қыркүйекке','қазанға','қарашаға','желтоқсанға')
    return {
        'employee.full_name': optional(payload, 'source_employee_name'),
        'employee.full_name_genitive_ru': required(ru, 'employee_full_name_genitive_ru'),
        'employee.full_name_genitive_kk': required(kk, 'employee_full_name_genitive_kk'),
        'position.document_genitive_ru': required(ru, 'position_document_genitive_ru'),
        'position.document_possessive_kk': required(kk, 'position_document_possessive_kk'),
        'org_unit.title_ru': optional(unit, 'name'), 'org_unit.title_kk': optional(unit, 'name_kk'),
        'org_unit.document_genitive_ru': required(unit, 'document_genitive_ru'),
        'org_unit.document_genitive_kk': required(unit, 'document_genitive_kk'),
        'medical_specialty.clause_ru': clauses['ru'], 'medical_specialty.clause_kk': clauses['kk'],
        'effective_date.ru': effective.strftime('%d.%m.%Y'),
        'effective_date.kk': f'{effective.year} жылғы {effective.day} {months_from[effective.month-1]}',
        'qualification_category.level_ru': LEVELS[code][0], 'qualification_category.level_kk': LEVELS[code][1],
        'qualification_category.valid_until_ru': end.strftime('%d.%m.%Y'),
        'qualification_category.valid_until_kk': f'{end.year} жылғы {end.day} {months_to[end.month-1]}',
        'basis': str(payload.get('basis') or '').strip(),
        '__category_classifier': '1',
    }


def prepare_classifier_payload(conn, payload, employee_id, effective_date, previous=None):
    out = deepcopy(dict(payload))
    if not employee_id:
        raise ValueError('Выберите сотрудника из справочника.')
    employee = conn.execute(text('SELECT full_name FROM employees WHERE employee_id=:id'), {'id': employee_id}).scalar_one_or_none()
    if not employee:
        raise ValueError('Сотрудник не найден.')
    out['employee_id'] = employee_id
    out['source_employee_name'] = out.get('source_employee_name') or employee
    if not effective_date:
        raise ValueError('Укажите дату начала действия категории.')
    out['effective_date'] = str(effective_date)
    out['contract'] = CONTRACT
    category = out.get('qualification_category')
    code = category.get('code') if isinstance(category, Mapping) else None
    if type(code) is not int or code not in LEVELS:
        raise ValueError('Выберите категорию с кодом 2, 3 или 4 из справочника.')
    row = conn.execute(text('SELECT code,name,name_kk FROM public.medical_qualification_categories WHERE code=:code'), {'code': code}).mappings().one()
    out['qualification_category'] = dict(code=code, name_ru=row['name'], name_kk=row['name_kk'], assigned_at=category.get('assigned_at'))
    incoming = out.get('medical_specialty')
    if incoming is not None:
        if not isinstance(incoming, Mapping) or type(incoming.get('medical_specialty_id')) is not int:
            raise ValueError('Выберите медицинскую специальность из справочника.')
        old = (previous or {}).get('medical_specialty')
        if isinstance(old, Mapping) and old.get('medical_specialty_id') == incoming['medical_specialty_id']:
            out['medical_specialty'] = deepcopy(dict(old))
        else:
            row = conn.execute(text('SELECT medical_specialty_id,name,name_kk FROM medical_specialties WHERE medical_specialty_id=:id AND is_active'), {'id': incoming['medical_specialty_id']}).mappings().one_or_none()
            if row is None or not row['name'] or not row['name_kk']:
                raise ValueError('У выбранной специальности необходимы названия RU и KK.')
            out['medical_specialty'] = dict(medical_specialty_id=row['medical_specialty_id'], name_ru=row['name'], name_kk=row['name_kk'])
    classifier_values(out)
    out['qualification_category']['valid_until'] = valid_until(category['assigned_at']).isoformat()
    return out


def classifier_template_texts(texts, values):
    """Render new orders against historical published text without editing it."""
    if values.get('__category_classifier') != '1':
        return texts
    result = dict(texts)
    for locale in ('ru', 'kk'):
        field = 'body_template_' + locale
        result[field] = result[field].replace(
            ' («{{medical_specialty.name_' + locale + '}}»)',
            '{{medical_specialty.clause_' + locale + '}}',
        ).replace('{{qualification_category.category_code_' + locale + '}} ', '')
    return result

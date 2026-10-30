"""Document-only education change. Preserve ID60 wording and literal markers.

Grammar is taken from saved forms or entered explicitly; never inferred.
Rendering binds markers in memory; the author's stored texts are unchanged.
"""
from copy import deepcopy
from datetime import date
from collections.abc import Mapping
from sqlalchemy import text

TYPE = 'EDUCATION_INFORMATION_CHANGE'
CONTRACT = 'education-information-change-v1'
TEXTS = dict(
    title_ru='Об изменении информации об образовании',
    title_kk='Білімі туралы мәліметіне өзгеріс енгізу туралы',
    preamble_ru='В связи с получением «послесреднего образования»',
    preamble_kk='«Орта білімнен кейінгі білім» білім алуларына байланысты',
    body_template_ru='С [дата начала действия] считать образование [должность] [подразделение] [Ф.И.О. сотрудника в родительном падеже] [уровень образования] по специальности «[специальность]».',
    body_template_kk='[күні] бастап [лауазымы] [бөлімшесі] [қызметкердің аты-жөні, ілік септігінде] білімі «[мамандық]» мамандығы бойынша [білім деңгейі] болып есептелсін.',
    basis_template_ru='Основание: диплом [вид документа] № [номер] от [дата выдачи], подтверждающий образование по специальности «[специальность]».',
    basis_template_kk='Негіз: «[мамандық]» мамандығы бойынша [құжат түрі] № [нөмір] дипломы, [берілген күні].',
)
TOKENS = {
    'ru': {'[дата начала действия]': 'effective_date.ru', '[должность]': 'position.document_genitive_ru',
           '[подразделение]': 'org_unit.document_genitive_ru', '[Ф.И.О. сотрудника в родительном падеже]': 'employee.full_name_genitive_ru',
           '[уровень образования]': 'education.level_ru', '[специальность]': 'education.specialty_ru',
           '[вид документа]': 'education_document.kind_ru', '[номер]': 'education_document.number', '[дата выдачи]': 'education_document.issued_ru'},
    'kk': {'[күні]': 'effective_date.kk', '[лауазымы]': 'position.document_possessive_kk',
           '[бөлімшесі]': 'org_unit.document_genitive_kk', '[қызметкердің аты-жөні, ілік септігінде]': 'employee.full_name_genitive_kk',
           '[білім деңгейі]': 'education.level_kk', '[мамандық]': 'education.specialty_kk',
           '[құжат түрі]': 'education_document.kind_kk', '[нөмір]': 'education_document.number', '[берілген күні]': 'education_document.issued_kk'},
}


def bind_editor_texts(source):
    out = dict(source)
    for locale, markers in TOKENS.items():
        for field in ('preamble_', 'body_template_', 'basis_template_'):
            key = field + locale
            if isinstance(out.get(key), str):
                for marker, token in markers.items():
                    out[key] = out[key].replace(marker, '{{' + token + '}}')
    return out


REQUIRED = {field: tuple(dict.fromkeys(token for marker, token in TOKENS[locale].items() if marker in TEXTS[field]))
            for locale in ('ru', 'kk') for field in ('body_template_' + locale, 'basis_template_' + locale)}
VARIABLES = tuple(dict.fromkeys(token for markers in TOKENS.values() for token in markers.values()))
PREVIEW = {locale: {token: '[[' + token + ']]' for token in VARIABLES} for locale in ('ru', 'kk')}
REQUIRED_FIELDS = ('Сотрудник из справочника или ручное ФИО', 'Сохранённые или явно введённые формы ФИО, должности и подразделения RU/KK',
                   'Дата начала действия', 'Уровень образования RU/KK', 'Специальность RU/KK', 'Вид документа RU/KK', 'Номер документа', 'Дата выдачи документа')
NOTES = ('Создание, редактирование, сохранение, повторное открытие, предпросмотр и печать RU/KK. '
         'Формы ФИО, должности и подразделения берутся из сохранённых данных или заполняются вручную, '
         'без автоматического склонения. Все значения сохраняются в снимке приказа. '
         'Сведения об образовании, специальность и реквизиты основания вводятся явно. '
         'Кадровое досье не изменяется. Обозначения полей ID60 подставляются без изменения формулировок.')


def _required(source, key, label):
    value = source.get(key) if isinstance(source, Mapping) else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Заполните: {label}.')
    if any(part in value for part in ('{{', '}}', '<script', 'javascript:')):
        raise ValueError(f'Недопустимое содержимое: {label}.')
    return value.strip()


def _day(source, key, label):
    value = _required(source, key, label)
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value or parsed.year < 1900:
            raise ValueError()
        return parsed
    except ValueError as exc:
        raise ValueError(f'Укажите полную дату: {label} (ГГГГ-ММ-ДД).') from exc


def _optional(source, key, label):
    value = source.get(key) if isinstance(source, Mapping) else None
    if value is None or value == '':
        return ''
    return _required(source, key, label)


def education_values(payload):
    from app.services.personnel_orders_editorial.generators import _format_date_from
    from app.services.personnel_order_unpaid_leave_contract import format_leave_date
    effective = _day(payload, 'effective_date', 'Дата начала действия')
    document = payload.get('education_document')
    issued_status = document.get('issued_at_status', 'KNOWN') if isinstance(document, Mapping) else 'KNOWN'
    if issued_status not in ('KNOWN', 'TO_CLARIFY'):
        raise ValueError('Выберите состояние даты выдачи документа.')
    if issued_status == 'TO_CLARIFY':
        if document.get('issued_at') not in (None, ''):
            raise ValueError('Для состояния «Уточнить» дата выдачи должна быть пустой.')
        issued_ru, issued_kk = 'Уточнить', 'Нақтылау қажет'
    else:
        issued = _day(document, 'issued_at', 'Дата выдачи документа')
        issued_ru, issued_kk = issued.strftime('%d.%m.%Y'), format_leave_date(issued, 'kk')
    values = {
        'effective_date.ru': effective.strftime('%d.%m.%Y'), 'effective_date.kk': _format_date_from(effective.isoformat(), 'kk'),
        'education_document.number': _required(document, 'number', 'Номер документа'),
        'education_document.issued_ru': issued_ru,
        'education_document.issued_kk': issued_kk,
    }
    for locale, name, position, unit in (
        ('ru', 'employee_full_name_genitive_ru', 'position_document_genitive_ru', 'document_genitive_ru'),
        ('kk', 'employee_full_name_genitive_kk', 'position_document_possessive_kk', 'document_genitive_kk'),
    ):
        forms = payload.get('document_forms_' + locale)
        values.update({
            'employee.full_name_genitive_' + locale: _required(forms, name, 'Форма ФИО ' + locale.upper()),
            ('position.document_genitive_ru' if locale == 'ru' else 'position.document_possessive_kk'): _required(forms, position, 'Форма должности ' + locale.upper()),
            'org_unit.document_genitive_' + locale: _required(payload.get('document_org_unit'), unit, 'Форма подразделения ' + locale.upper()),
            'education.level_' + locale: _optional(payload.get('education'), 'level_' + locale, 'Уровень образования ' + locale.upper()),
            'education.specialty_' + locale: _optional(payload.get('education'), 'specialty_' + locale, 'Специальность ' + locale.upper()),
            'education_document.kind_' + locale: _required(document, 'kind_' + locale, 'Вид документа ' + locale.upper()),
        })
    return values


def prepare_education_payload(conn, payload, employee_id, effective_date, unresolved_subject=None):
    source = payload or {}
    if not isinstance(source, Mapping):
        raise ValueError('Заполните данные приказа об образовании.')
    manual = unresolved_subject if unresolved_subject is not None else source.get('unresolved_subject')
    out = {key: deepcopy(source.get(key)) for key in ('document_forms_ru', 'document_forms_kk', 'document_org_unit',
            'source_position_id', 'source_position_name', 'source_position_name_kk', 'education', 'education_document')}
    if manual is not None:
        if employee_id is not None:
            raise ValueError('Укажите сотрудника из списка или ручное ФИО, но не оба варианта.')
        from app.services.personnel_order_manual_subject import manual_subject_payload, validate_manual_subject_links
        validate_manual_subject_links(source)
        subject = manual_subject_payload(manual)
        subject['unresolved_subject']['needs_employee_link'] = False
        subject.pop('source_position_name', None)
        out.update(subject)
    else:
        if source.get('subject_mode') == 'MANUAL' or type(employee_id) is not int or employee_id < 1:
            raise ValueError('Выберите сотрудника из списка или введите ФИО вручную.')
        employee = conn.execute(text('SELECT full_name FROM employees WHERE employee_id=:id'), {'id': employee_id}).scalar_one_or_none()
        if not employee:
            raise ValueError('Сотрудник не найден.')
        out['source_employee_name'] = employee
    out.update(contract=CONTRACT, employee_id=employee_id, subject_mode='MANUAL' if manual is not None else 'DIRECTORY', effective_date=str(effective_date or ''))
    education_values(out)
    return out

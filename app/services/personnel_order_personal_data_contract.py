"""Independent personal-data template contract; no education or diploma fields.

Name changes and grammatical forms are supplied explicitly by HR. No identity,
employee card or published template is changed by these pure helpers.
"""
from datetime import date
from collections.abc import Mapping
import re

TYPE = 'PERSONAL_DATA_CHANGE'
TEXTS = {
    'title_ru': 'Об изменении персональных данных',
    'title_kk': 'Жеке деректерді өзгерту туралы',
    'preamble_ru': 'В связи с изменением персональных данных работника',
    'preamble_kk': 'Қызметкердің жеке деректерінің өзгеруіне байланысты',
    'body_template_ru': 'С {{effective_date.ru}} внести изменения в персональные данные {{position.document_genitive_ru}} {{org_unit.document_genitive_ru}} {{employee.full_name_genitive_ru}}: {{personal_data.changes_ru}}. ФИО после изменения: {{personal_data.new_full_name_ru}}.',
    'body_template_kk': '{{effective_date.kk}} бастап {{org_unit.document_genitive_kk}} {{position.document_possessive_kk}} {{employee.full_name_genitive_kk}} жеке деректеріне мынадай өзгерістер енгізілсін: {{personal_data.changes_kk}}. Өзгерістен кейінгі Т.А.Ә.: {{personal_data.new_full_name_kk}}.',
    'basis_template_ru': 'Основание: личное заявление работника, {{identity_document.kind_ru}} № {{identity_document.number}}, выданное {{identity_document.issued_ru}}.',
    'basis_template_kk': 'Негіз: қызметкердің жеке өтініші, {{identity_document.issued_kk}} берілген № {{identity_document.number}} {{identity_document.kind_kk}}.',
}
REQUIRED = {
    'body_template_ru': ('effective_date.ru', 'employee.full_name_genitive_ru', 'position.document_genitive_ru', 'org_unit.document_genitive_ru', 'personal_data.changes_ru'),
    'body_template_kk': ('effective_date.kk', 'employee.full_name_genitive_kk', 'position.document_possessive_kk', 'org_unit.document_genitive_kk', 'personal_data.changes_kk'),
    'basis_template_ru': ('identity_document.kind_ru', 'identity_document.number', 'identity_document.issued_ru'),
    'basis_template_kk': ('identity_document.kind_kk', 'identity_document.number', 'identity_document.issued_kk'),
}
VARIABLES = tuple(dict.fromkeys(token for tokens in REQUIRED.values() for token in tokens)) + ('identity_document.issuer_ru', 'identity_document.issuer_kk', 'personal_data.new_full_name_ru', 'personal_data.new_full_name_kk')
REQUIRED_FIELDS = ('Дата действия', 'Сотрудник и сохранённые формы ФИО RU/KK', 'Должность и подразделение RU/KK',
                   'Изменяемые персональные данные — ручной текст RU/KK', 'Новое ФИО RU/KK — ручной ввод без перевода и склонения', 'Вид, номер и дата либо статус даты выдачи удостоверения личности RU/KK')
NOTES = ('Самостоятельный контракт шаблона без сведений об образовании и дипломе. '
         'При смене фамилии, имени или отчества кадровик явно редактирует формулировки RU/KK; '
         'автоматическое склонение и изменение личной карточки не выполняются. '
         'Доступны создание и редактирование черновика приказа по опубликованной версии, RU/KK-предпросмотр. '
         'Создание кадровых событий и изменение личной карточки этим контрактом не выполняются.')


def validate_placeholders(values):
    for field, value in values.items():
        if isinstance(value, str) and re.search(r'\[[^\]\n]+\]', value):
            raise ValueError(f'{field}: замените редакционные placeholders в квадратных скобках на поддерживаемые переменные.')


def _text(source, key, label):
    value = source.get(key) if isinstance(source, Mapping) else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Заполните: {label}.')
    if any(part in value.lower() for part in ('{{', '}}', '<script', 'javascript:')):
        raise ValueError(f'Недопустимое содержимое: {label}.')
    return value.strip()


def _day(source, key, label):
    value = _text(source, key, label)
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value or parsed.year < 1900:
            raise ValueError()
        return parsed
    except ValueError as exc:
        raise ValueError(f'Укажите полную дату: {label}.') from exc


def personal_data_values(payload):
    from app.services.personnel_orders_editorial.generators import _format_date_from
    from app.services.personnel_order_unpaid_leave_contract import format_leave_date
    effective = _day(payload, 'effective_date', 'Дата действия')
    identity = payload.get('identity_document')
    status = identity.get('issued_at_status', 'KNOWN') if isinstance(identity, Mapping) else 'KNOWN'
    if status not in ('KNOWN', 'ABSENT', 'TO_CLARIFY'):
        raise ValueError('Выберите статус даты выдачи удостоверения личности.')
    if status == 'KNOWN':
        issued = _day(identity, 'issued_at', 'Дата выдачи удостоверения личности')
        issued_ru, issued_kk = issued.strftime('%d.%m.%Y'), format_leave_date(issued, 'kk')
    else:
        if identity.get('issued_at') not in (None, ''):
            raise ValueError('При отсутствии или уточнении даты выдачи оставьте дату пустой.')
        issued_ru, issued_kk = {
            'ABSENT': ('данные о дате выдачи отсутствуют', 'берілген күні туралы мәліметтер жоқ'),
            'TO_CLARIFY': ('дату выдачи следует уточнить', 'берілген күнін нақтылау қажет'),
        }[status]
    result = {
        'effective_date.ru': effective.strftime('%d.%m.%Y'),
        'effective_date.kk': _format_date_from(effective.isoformat(), 'kk'),
        'identity_document.number': _text(identity, 'number', 'Номер удостоверения личности'),
        'identity_document.issued_ru': issued_ru,
        'identity_document.issued_kk': issued_kk,
        '__identity_issued_status': status,
    }
    for locale, position in (('ru', 'position_document_genitive_ru'), ('kk', 'position_document_possessive_kk')):
        forms = payload.get('document_forms_' + locale)
        personal = payload.get('personal_data')
        new_name = personal.get('new_full_name_' + locale) if isinstance(personal, Mapping) else None
        for part in ('new_surname_', 'new_given_name_'):
            if isinstance(personal, Mapping) and personal.get(part + locale) not in (None, ''):
                _text(personal, part + locale, ('Новая фамилия ' if part == 'new_surname_' else 'Новое имя ') + locale.upper())
        result.update({
            'employee.full_name_genitive_' + locale: _text(forms, 'employee_full_name_genitive_' + locale, 'Форма ФИО ' + locale.upper()),
            ('position.document_genitive_ru' if locale == 'ru' else 'position.document_possessive_kk'): _text(forms, position, 'Форма должности ' + locale.upper()),
            'org_unit.document_genitive_' + locale: _text(payload.get('document_org_unit'), 'document_genitive_' + locale, 'Форма подразделения ' + locale.upper()),
            'personal_data.changes_' + locale: _text(payload.get('personal_data'), 'changes_' + locale, 'Изменяемые персональные данные ' + locale.upper()),
            # Old orders/templates have no new-name tokens. Never derive their value.
            'personal_data.new_full_name_' + locale: _text(personal, 'new_full_name_' + locale, 'Новое ФИО ' + locale.upper()) if new_name not in (None, '') else '',
            'identity_document.kind_' + locale: _text(identity, 'kind_' + locale, 'Вид удостоверения личности ' + locale.upper()),
            'identity_document.issuer_' + locale: _text(identity, 'issuer_' + locale, 'Кем выдано удостоверение ' + locale.upper()) if identity.get('issuer_' + locale) else '',
        })
    return result


def adapt_identity_date_clause(source, values):
    """Keep saved templates intact while rendering a status instead of a date."""
    if values.get('__identity_issued_status', 'KNOWN') == 'KNOWN':
        return source
    source = re.sub(r'выданное\s+(\{\{\s*identity_document\.issued_ru\s*\}\})', r'\1', source)
    return re.sub(r'(\{\{\s*identity_document\.issued_kk\s*\}\})\s+берілген', r'\1', source)


SAMPLE = {
    'effective_date': '2026-05-19',
    'document_forms_ru': {'employee_full_name_genitive_ru': 'Тестовой Айгуль Сергеевны', 'position_document_genitive_ru': 'врача'},
    'document_forms_kk': {'employee_full_name_genitive_kk': 'Сынақ Айгүл Серікқызының', 'position_document_possessive_kk': 'дәрігері'},
    'document_org_unit': {'document_genitive_ru': 'тестового отделения', 'document_genitive_kk': 'сынақ бөлімшесінің'},
    'personal_data': {'changes_ru': 'фамилию «Тестовая» изменить на «Примерова», имя «Айгуль» — на «Айгуль-TEST», отчество «Сергеевна» — на «Сериковна»',
                      'changes_kk': '«Сынақ» тегін «Үлгі» деп, «Айгүл» атын «Айгүл-TEST» деп, «Серікқызы» әкесінің атын «Серікқызы-TEST» деп өзгерту',
                      'new_full_name_ru': 'Примерова Айгуль-TEST Сериковна', 'new_full_name_kk': 'Үлгі Айгүл-TEST Серікқызы-TEST'},
    'identity_document': {'kind_ru': 'удостоверение личности', 'kind_kk': 'жеке куәлігі', 'number': 'TEST-ID-0001', 'issued_at': '2026-05-10', 'issuer_ru': 'Тестовый орган', 'issuer_kk': 'Сынақ органы'},
}


def preview_context():
    values = personal_data_values(SAMPLE)
    return {'ru': dict(values), 'kk': dict(values)}


def corrected_personal_data_texts(source):
    """Explicit conversion for a reviewable synthetic copy, never automatic rebinding."""
    result = dict(TEXTS)
    for locale in ('ru', 'kk'):
        result['title_' + locale] = source['title_' + locale]
        result['print_title_' + locale] = source['title_' + locale]
    return result


def with_new_personal_names(source):
    """Prepare an explicit new draft; preserve all existing texts and variables."""
    result = dict(source)
    for locale, sentence in (
        ('ru', 'ФИО после изменения: {{personal_data.new_full_name_ru}}.'),
        ('kk', 'Өзгерістен кейінгі Т.А.Ә.: {{personal_data.new_full_name_kk}}.'),
    ):
        key = 'body_template_' + locale
        if 'personal_data.new_full_name_' + locale not in result[key]:
            result[key] = result[key].rstrip() + ' ' + sentence
    return result


def with_source_given_names(conn,payload,employee_id):
    """Use structured components first, then the project's canonical/localized FIO order."""
    from sqlalchemy import text
    out=dict(payload)
    fields=('source_given_name_ru','source_given_name_kk')
    if all(isinstance(out.get(key),str) and out[key].strip() for key in fields):
        return out
    row=conn.execute(text("""SELECT to_jsonb(e) employee,
        (SELECT to_jsonb(p) FROM persons p WHERE p.person_id=NULLIF(to_jsonb(e)->>'person_id','')::bigint) person
        FROM employees e WHERE e.employee_id=:id"""),{'id':employee_id}).mappings().first() if employee_id else None
    if row:
        employee=row['employee'] or {};person=row['person'] or {}
        for locale in ('ru','kk'):
            key='source_given_name_'+locale
            if not isinstance(out.get(key),str) or not out[key].strip():
                candidates=(person.get('first_name_'+locale),employee.get('first_name_'+locale),person.get('first_name'),employee.get('first_name'))
                out[key]=next((value.strip() for value in candidates if isinstance(value,str) and value.strip()),'')
    def component(value,index):
        parts=value.split() if isinstance(value,str) else []
        return parts[index] if len(parts)>=2 else ''
    manual=out.get('unresolved_subject') or {}
    canonical=out.get('source_employee_name') or (manual.get('full_name') if isinstance(manual,Mapping) else '') or ((row['person'] or {}).get('full_name') or (row['employee'] or {}).get('full_name') if row else '')
    for locale in ('ru','kk'):
        key='source_given_name_'+locale
        if isinstance(out.get(key),str) and out[key].strip():continue
        forms=out.get('document_forms_'+locale) or {}
        cases=next((name for form in ('genitive','dative','ablative','accusative')
                    if (name:=component(forms.get('employee_full_name_'+form+'_'+locale),0 if locale=='kk' else 1))), '') if isinstance(forms,Mapping) else ''
        out[key]=(cases or component(canonical,1)) if locale=='kk' else (component(canonical,1) or cases)
    return out


def prepare_personal_data_payload(conn,payload,employee_id,effective_date,unresolved_subject=None):
    from copy import deepcopy
    from sqlalchemy import text
    if not isinstance(payload,Mapping):raise ValueError('Заполните данные приказа об изменении персональных данных.')
    out={key:deepcopy(payload.get(key)) for key in ('document_forms_ru','document_forms_kk','document_org_unit','source_position_id','source_position_name','source_position_name_kk','source_given_name_ru','source_given_name_kk','personal_data','identity_document')}
    manual=unresolved_subject if unresolved_subject is not None else payload.get('unresolved_subject')
    if manual is not None:
        if employee_id is not None:raise ValueError('Укажите сотрудника из справочника или ручное ФИО, но не оба варианта.')
        from app.services.personnel_order_manual_subject import manual_subject_payload,validate_manual_subject_links
        validate_manual_subject_links(payload)
        subject=manual_subject_payload(manual);subject['unresolved_subject']['needs_employee_link']=False
        subject.pop('source_position_name',None);out.update(subject)
    else:
        if payload.get('subject_mode')=='MANUAL' or type(employee_id) is not int or employee_id<1:raise ValueError('Выберите сотрудника или введите ФИО вручную.')
        name=conn.execute(text('SELECT full_name FROM employees WHERE employee_id=:id'),{'id':employee_id}).scalar_one_or_none()
        if not name:raise ValueError('Сотрудник не найден.')
        out['source_employee_name']=name
    out.update(contract='personal-data-change-v1',employee_id=employee_id,subject_mode='MANUAL' if manual is not None else 'DIRECTORY',effective_date=str(effective_date or ''))
    out=with_source_given_names(conn,out,employee_id)
    personal_data_values(out)
    out['identity_document'].setdefault('issued_at_status', 'KNOWN')
    if out['identity_document']['issued_at_status'] != 'KNOWN':
        out['identity_document']['issued_at'] = ''
    return out

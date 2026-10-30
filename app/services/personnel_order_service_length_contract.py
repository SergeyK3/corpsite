"""Document-only change of service length, entered manually on both languages.

The effective date never determines service length. Neither service length nor
grounds are calculated, translated or inferred; both RU/KK values are required.
"""
from copy import deepcopy
from datetime import date
from typing import Mapping

from sqlalchemy import text

TYPE = 'SERVICE_LENGTH_CHANGE'
CONTRACT = 'service-length-change-v1'
TITLE_RU = 'Об изменении стажа'
TITLE_KK = 'Жұмыс тәжірибесін өзгерту туралы'
TOKENS = {
    'ru': {'[должность]': 'position.document_genitive_ru',
           '[наименование подразделения]': 'org_unit.document_genitive_ru',
           '[Ф.И.О. сотрудника в родительном падеже]': 'employee.full_name_genitive_ru',
           '[дата]': 'effective_date.ru', '[новый стаж]': 'service_length.new_ru'},
    'kk': {'[Бөлімше атауы]': 'org_unit.document_genitive_kk',
           '[лауазымы]': 'position.document_possessive_kk',
           '[қызметкердің аты-жөні, ілік септігінде]': 'employee.full_name_genitive_kk',
           '[күні]': 'effective_date.kk', '[жаңа еңбек өтілі]': 'service_length.new_kk'},
}


def bind_editor_texts(source):
    """Bind existing markers, preserving all other entered text verbatim."""
    out = dict(source)
    for locale, tokens in TOKENS.items():
        for field in ('preamble_', 'body_template_'):
            for marker, token in tokens.items():
                out[field + locale] = out[field + locale].replace(marker, '{{' + token + '}}')
        key = 'basis_template_' + locale
        out[key] = out[key].replace('{{basis}}', '{{basis.' + locale + '}}')
    return out


TEXTS = bind_editor_texts(dict(
    title_ru=TITLE_RU, title_kk=TITLE_KK,
    preamble_ru='В связи с изменением сведений о трудовом стаже [должность] [наименование подразделения] [Ф.И.О. сотрудника в родительном падеже], ПРИКАЗЫВАЮ:',
    preamble_kk='[Бөлімше атауы] [лауазымы] [қызметкердің аты-жөні, ілік септігінде] еңбек өтілі туралы мәліметтердің өзгеруіне байланысты, БҰЙЫРАМЫН:',
    body_template_ru='Считать трудовой стаж [должность] [наименование подразделения] [Ф.И.О. сотрудника в родительном падеже] с [дата] составляющим [новый стаж].',
    body_template_kk='[Бөлімше атауы] [лауазымы] [қызметкердің аты-жөні, ілік септігінде] еңбек өтілі [күні] бастап [жаңа еңбек өтілі] болып есептелсін.',
    basis_template_ru='Основание: {{basis}}.', basis_template_kk='Негіз: {{basis}}.',
))
REQUIRED = {f'body_template_{locale}': tuple(tokens.values()) for locale, tokens in TOKENS.items()}
REQUIRED.update({f'basis_template_{locale}': (f'basis.{locale}',) for locale in ('ru', 'kk')})
VARIABLES = tuple(dict.fromkeys(token for tokens in REQUIRED.values() for token in tokens))
REQUIRED_FIELDS = ('Сотрудник из справочника или ФИО, введённое вручную', 'ФИО в родительном падеже RU и в ілік септік KK',
    'Должность в родительном падеже RU и в притяжательной форме KK',
    'Подразделение в родительном падеже RU и в ілік септік KK',
    'Дата начала действия', 'Новый стаж RU/KK', 'Основание RU/KK')
NOTES = ('Новый стаж вводится вручную отдельно на RU и KK. Система не рассчитывает стаж по датам '
    'и не выводит его автоматически. Дата начала действия — отдельное поле. '
    'Основание вводится вручную отдельно на RU и KK; отдельные реквизиты документа не требуются. '
    'Поддерживаются создание, редактирование, сохранение, повторное открытие, предпросмотр и печать '
    'документного приказа. Сотрудник выбирается из списка либо указывается вручную; '
    'ручные ФИО и формы RU/KK сохраняются только в приказе, без вычисления склонений и создания карточки. '
    'Кадровое досье автоматически не изменяется.')
PREVIEW = {locale: {token: '[[' + token + ']]' for token in VARIABLES} for locale in ('ru', 'kk')}


def service_length_values(payload):
    def required(source, key, label):
        value = source.get(key) if isinstance(source, Mapping) else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Заполните: {label}.')
        return value.strip()
    day = required(payload, 'effective_date', 'Дата начала действия')
    try:
        parsed = date.fromisoformat(day)
        if parsed.isoformat() != day or not 1900 <= parsed.year <= 9999:
            raise ValueError()
    except ValueError as exc:
        raise ValueError('Укажите полную дату начала действия в формате ГГГГ-ММ-ДД.') from exc
    forms_ru, forms_kk, unit = (payload.get(key) for key in ('document_forms_ru', 'document_forms_kk', 'document_org_unit'))
    from app.services.personnel_orders_editorial.generators import _format_date_from
    return {
        'employee.full_name_genitive_ru': required(forms_ru, 'employee_full_name_genitive_ru', 'ФИО в родительном падеже RU'),
        'employee.full_name_genitive_kk': required(forms_kk, 'employee_full_name_genitive_kk', 'ФИО в ілік септік KK'),
        'position.document_genitive_ru': required(forms_ru, 'position_document_genitive_ru', 'Должность RU'),
        'position.document_possessive_kk': required(forms_kk, 'position_document_possessive_kk', 'Должность KK'),
        'org_unit.document_genitive_ru': required(unit, 'document_genitive_ru', 'Подразделение RU'),
        'org_unit.document_genitive_kk': required(unit, 'document_genitive_kk', 'Подразделение KK'),
        'effective_date.ru': parsed.strftime('%d.%m.%Y'), 'effective_date.kk': _format_date_from(day, 'kk'),
        **{f'service_length.new_{locale}': required(payload.get('service_length'), f'new_{locale}', f'Новый стаж {locale.upper()}') for locale in ('ru', 'kk')},
        **{f'basis.{locale}': required(payload.get('basis'), locale, f'Основание {locale.upper()}') for locale in ('ru', 'kk')},
    }


def prepare_service_length_payload(conn, payload, employee_id, effective_date, unresolved_subject=None):
    source = payload or {}
    manual = unresolved_subject if unresolved_subject is not None else source.get('unresolved_subject')
    if manual is not None:
        if employee_id is not None:
            raise ValueError('Укажите сотрудника из списка или ручное ФИО, но не оба варианта.')
        from app.services.personnel_order_manual_subject import manual_subject_payload, validate_manual_subject_links
        validate_manual_subject_links(source)
        snapshot = manual_subject_payload(manual)
        snapshot['unresolved_subject']['needs_employee_link'] = False
        employee = snapshot['source_employee_name']
    else:
        if source.get('subject_mode') == 'MANUAL':
            raise ValueError('Укажите ФИО сотрудника вручную.')
        if type(employee_id) is not int or employee_id < 1:
            raise ValueError('Выберите сотрудника из справочника или введите ФИО вручную.')
        employee = conn.execute(text('SELECT full_name FROM employees WHERE employee_id=:id'), {'id': employee_id}).scalar_one_or_none()
        if not employee:
            raise ValueError('Сотрудник не найден.')
        snapshot = {}
    out = {key: deepcopy((payload or {}).get(key)) for key in (
        'document_forms_ru', 'document_forms_kk', 'document_org_unit', 'service_length', 'basis')}
    out.update(snapshot, contract=CONTRACT, employee_id=employee_id, source_employee_name=employee,
               subject_mode='MANUAL' if manual is not None else 'DIRECTORY',
               effective_date=str(effective_date or ''))
    service_length_values(out)
    return out

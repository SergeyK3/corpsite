"""Document-only annual-leave recall: no balance calculation or HR events."""
from datetime import date
import re
from collections.abc import Mapping

CODE = 'LEAVE.ANNUAL.RECALL'
VARIABLES = ('employee.full_name', 'position.title_ru', 'position.title_kk', 'org_unit.title_ru', 'org_unit.title_kk', 'effective_date', 'basis')
REQUIRED_VARIABLES = {
    'body_template_ru': ('employee.full_name', 'position.title_ru', 'org_unit.title_ru', 'effective_date'),
    'body_template_kk': ('employee.full_name', 'position.title_kk', 'org_unit.title_kk', 'effective_date'),
    'basis_template_ru': ('basis',), 'basis_template_kk': ('basis',),
}
TEXTS = {
    'title_ru': 'Об отзыве из отпуска',
    'title_kk': 'Еңбек демалысынан шақырту туралы',
    'preamble_ru': 'В соответствии со ст. 95 Трудового кодекса Республики Казахстан и производственной необходимостью',
    'preamble_kk': 'Қазақстан Республикасы Еңбек кодексінің 95-бабына сәйкес, өндірістік қажеттілікке байланысты',
    'body_template_ru': 'Отозвать из ежегодного оплачиваемого трудового отпуска с {{effective_date}} следующего работника: {{employee.full_name}}, {{position.title_ru}}, подразделение: {{org_unit.title_ru}}.\n\nНеиспользованную часть трудового отпуска предоставить в течение текущего или следующего рабочего года в любое время по соглашению сторон.',
    'body_template_kk': '{{effective_date}} бастап келесі қызметкер жыл сайынғы ақылы еңбек демалысынан жұмысқа шақыртылсын: {{employee.full_name}}, {{position.title_kk}}, бөлімше: {{org_unit.title_kk}}.\n\nЕңбек демалысының пайдаланылмаған бөлігі тараптардың келісімі бойынша ағымдағы немесе келесі жұмыс жылы ішінде кез келген уақытта берілсін.',
    'basis_template_ru': 'Основание: {{basis}}.', 'basis_template_kk': 'Негіз: {{basis}}.',
}

def values(payload, effective_date):
    # Use nominative names explicitly supplied for this document. Do not reuse
    # genitive/possessive forms from the leave-grant constructors.
    def name(key, locale, fallback=''):
        raw = payload.get(key)
        return str(raw.get(locale) or '' if isinstance(raw, Mapping) else fallback or raw or '').strip()
    result = {
        'employee.full_name': str(payload.get('source_employee_name') or '').strip(),
        'position.title_ru': name('position_name', 'ru', payload.get('source_position_name')),
        'position.title_kk': str(payload.get('recall_position_kk') or name('position_name', 'kk')).strip(),
        'org_unit.title_ru': name('org_unit_name', 'ru', payload.get('source_org_unit_name')),
        'org_unit.title_kk': str(payload.get('recall_org_unit_kk') or name('org_unit_name', 'kk')).strip(),
        'basis.ru': str(payload.get('basis_ru') or '').strip(),
        'basis.kk': str(payload.get('basis_kk') or '').strip(),
    }
    for key in ('basis.ru', 'basis.kk'):
        result[key] = re.sub(r'^(?:Основание|Негіз)\s*:\s*', '', result[key], flags=re.I).rstrip('.').rstrip()
    missing = [key for key, value in result.items() if not value]
    if not effective_date:
        missing.append('effective_date')
    if missing:
        raise ValueError('Заполните поля отзыва / Шақырту деректерін толтырыңыз: ' + ', '.join(missing))
    day = date.fromisoformat(str(effective_date))
    from app.services.personnel_orders_editorial.generators import _format_date_from
    result.update({'effective_date.ru': _format_date_from(day.isoformat(), 'ru'), 'effective_date.kk': _format_date_from(day.isoformat(), 'kk')})
    return result

def render(field, data):
    locale = 'kk' if field.endswith('_kk') else 'ru'
    return re.sub(r'\{\{([\w.]+)\}\}', lambda match: data.get(match[1] + '.' + locale, data.get(match[1], '')), TEXTS[field])

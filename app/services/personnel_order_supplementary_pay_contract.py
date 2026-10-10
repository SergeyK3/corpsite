"""Simple service-area allowance, without replacement or rates."""
from collections.abc import Mapping
import re

from app.services.personnel_order_service_area_contract import BASE_TYPE, SAMPLE_RECIPIENT, normalize_recipient

VARIABLES = ('employee.full_name', 'employee.full_name_dative_ru', 'employee.full_name_dative_kk',
             'allowance.recipient', 'effective_date', 'allowance.percent', 'allowance.basis', 'basis')
BODY_RU = '{{allowance.recipient}}, с {{effective_date}} установить доплату в размере {{allowance.percent}}% от {{allowance.basis}} в связи с расширением зоны обслуживания.'
BODY_KK = '{{allowance.recipient}} {{effective_date}} бастап қызмет ету аймағының кеңеюіне байланысты {{allowance.basis}} {{allowance.percent}}% көлемінде қосымша ақы төленсін.'

def validate_bodies(texts):
    # Legacy custom texts remain editable; typed allowance texts must be complete.
    if not any('allowance.' in texts.get('body_template_'+lang, '') for lang in ('ru','kk')):
        return
    required = {'allowance.recipient','effective_date','allowance.percent','allowance.basis'}
    for lang in ('ru','kk'):
        tokens = set(re.findall(r'\{\{\s*([\w.]+)\s*\}\}', texts['body_template_'+lang]))
        if required - tokens:
            raise ValueError('Отсутствуют подстановки доплаты: '+', '.join(sorted(required-tokens)))

def values(allowance, recipient, effective_date):
    allowance = dict(allowance) if isinstance(allowance, Mapping) else {}
    recipient = dict(recipient) if isinstance(recipient, Mapping) else {}
    from datetime import date
    from app.services.personnel_order_replacement_contract import number, decimal_text
    from app.services.personnel_order_russian_reference_forms import russian_reference_case
    from app.services.personnel_orders_editorial.generators import _format_date_from, format_personnel_order_date_numeric
    recipient=normalize_recipient(recipient)
    def t(row,key):return str(row.get(key) or '').strip()
    missing=[key for key in ('employee_dative_ru','employee_dative_kk','basis_ru','basis_kk') if not t(allowance,key)]
    missing += [key for key in ('position_ru','org_unit_ru','position_kk','org_unit_kk') if not t(recipient,key)]
    if missing:raise ValueError('Заполните данные доплаты: '+', '.join(missing)+'.')
    percent=number(allowance.get('percent'),'Доплата')
    if percent not in (25,50):raise ValueError('Выберите доплату +25% или +50%.')
    try:start=date.fromisoformat(str(effective_date))
    except ValueError:raise ValueError('Укажите дату начала доплаты.') from None
    unit=t(recipient,'org_unit_genitive_ru') or russian_reference_case(t(recipient,'org_unit_ru'),'genitive') or 'подразделения «'+t(recipient,'org_unit_ru')+'»'
    role=t(recipient,'position_dative_ru')
    placement=(role if role.endswith(' '+unit) else ' '.join((role,unit))) if role else '(должность: '+t(recipient,'position_ru')+'; подразделение: '+t(recipient,'org_unit_ru')+')'
    return {'allowance.recipient.ru':t(allowance,'employee_dative_ru')+', '+placement,
            'allowance.recipient.kk':' '.join((t(recipient,'org_unit_kk'),t(recipient,'position_kk'),t(allowance,'employee_dative_kk'))),
            'employee.full_name_dative_ru':t(allowance,'employee_dative_ru'),'employee.full_name_dative_kk':t(allowance,'employee_dative_kk'),
            'effective_date.ru':format_personnel_order_date_numeric(start),'effective_date.kk':_format_date_from(start,'kk'),
            'allowance.percent':decimal_text(percent),'allowance.basis.ru':'собственного должностного оклада','allowance.basis.kk':'лауазымдық айлық ақыдан',
            'basis.ru':t(allowance,'basis_ru'),'basis.kk':t(allowance,'basis_kk')}

def preview_context():
    from app.services.personnel_order_replacement_contract import SAMPLE_CONCURRENT
    data = values({**SAMPLE_CONCURRENT,'percent':25}, SAMPLE_RECIPIENT, '2026-06-15')
    return {lang:{key:data.get(key+'.'+lang,data.get(key,'')) for key in VARIABLES if key!='employee.full_name'} for lang in ('ru','kk')}

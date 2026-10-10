"""Document-only allowance from the recipient's own salary; version-scoped."""
from collections.abc import Mapping
from datetime import date

VARIABLES = ("allowance.recipient", "allowance.term", "replacement.clause")
BASE_TYPE = "RECIPIENT_BASE_SALARY"
BODY_RU = "{{allowance.recipient}}, с {{effective_date}}{{allowance.term}} установить доплату в размере {{allowance.percent}}% от {{allowance.basis}} в связи с расширением зоны обслуживания{{replacement.clause}}."
BODY_KK = "{{allowance.recipient}} {{effective_date}} бастап{{allowance.term}}{{replacement.clause}} қызмет ету аймағының кеңеюіне байланысты {{allowance.basis}} {{allowance.percent}}% көлемінде қосымша ақы төленсін."

def enabled(texts):
    import re
    return all(re.search(r"\{\{\s*allowance\.recipient\s*\}\}", str(texts.get('body_template_'+lang) or '')) for lang in ('ru','kk'))

def validate_bodies(texts):
    import re
    for lang in ('ru','kk'):
        tokens=set(re.findall(r"\{\{\s*([\w.]+)\s*\}\}",texts['body_template_'+lang]))
        required={'allowance.recipient','effective_date','allowance.percent','allowance.basis','allowance.term','replacement.clause'}
        if required-tokens:raise ValueError('Отсутствуют подстановки доплаты: '+', '.join(sorted(required-tokens)))
        if tokens & {'concurrent.rate','total.rate'}:raise ValueError('Доплата за расширение зоны обслуживания не должна содержать ставки.')

def text(row,key):return str(row.get(key) or '').strip()
def join(*parts):return ' '.join(p for p in parts if p)

def normalize_recipient(recipient):
    """Accept a manual refinement; otherwise calculate a case or use FIO-only wording."""
    from app.services.personnel_order_russian_reference_forms import russian_reference_case
    result=dict(recipient) if isinstance(recipient,Mapping) else {}
    result['position_dative_ru']=text(result,'position_dative_ru') or russian_reference_case(text(result,'position_ru'),'dative')
    return result

def values(concurrent,replacement,effective_date,recipient):
    from app.services.personnel_order_replacement_contract import number,decimal_text
    from app.services.personnel_orders_editorial.generators import _format_date_from,format_personnel_order_date_numeric
    c=concurrent if isinstance(concurrent,Mapping) else {}
    r=replacement if isinstance(replacement,Mapping) else {}
    recipient=normalize_recipient(recipient)
    required_c={'employee_dative_ru':'ФИО получателя (дательный, RU)','employee_dative_kk':'ФИО получателя (барыс септік, KK)','basis_ru':'Основание (RU)','basis_kk':'Основание (KK)'}
    required_recipient={'position_ru':'Должность получателя (RU)','org_unit_ru':'Подразделение получателя (RU)','position_kk':'Должность получателя (KK)','org_unit_kk':'Подразделение получателя (KK)','org_unit_genitive_ru':'Подразделение получателя для текста (RU)'}
    missing=[label for key,label in required_c.items() if not text(c,key)] + [label for key,label in required_recipient.items() if not text(recipient,key)]
    if missing:raise ValueError('Заполните данные получателя доплаты: '+', '.join(missing)+'.')
    try:start=date.fromisoformat(str(effective_date))
    except ValueError:raise ValueError('Укажите дату начала доплаты.') from None
    percent=number(r.get('allowance_percent'),'Доплата')
    if percent not in (25,50):raise ValueError('Выберите доплату +25% или +50%.')
    term=text(r,'term_type');term_ru=term_kk=''
    has_worker=bool(text(r,'employee_name_ru') or text(r,'employee_name_kk') or r.get('employee_id'))
    if term=='DATE':
        try:end=date.fromisoformat(text(r,'end_date'))
        except ValueError:raise ValueError('Укажите дату окончания доплаты.') from None
        if end<start:raise ValueError('Дата окончания раньше даты начала.')
        months=('қаңтарға','ақпанға','наурызға','сәуірге','мамырға','маусымға','шілдеге','тамызға','қыркүйекке','қазанға','қарашаға','желтоқсанға')
        term_ru=' по '+end.strftime('%d.%m.%Y')+' включительно'
        term_kk=f' {end.year} жылғы {end.day} {months[end.month-1]} дейін'
    elif term=='UNTIL_RETURN':
        if not has_worker:raise ValueError('Выберите замещаемого сотрудника для срока до его выхода из отпуска.')
        term_ru=' до выхода замещаемого работника из отпуска'
        term_kk=' орны алмастырылатын қызметкердің еңбек демалысынан жұмысқа шығуына дейін'
    elif term!='NONE':raise ValueError('Выберите срок: без указания срока, до даты или до выхода работника.')
    clause_ru=clause_kk=''
    if has_worker:
        required={'employee_name_ru':'Замещаемый сотрудник (RU)','employee_name_kk':'Замещаемый сотрудник (KK)','employee_genitive_ru':'ФИО замещаемого (родительный, RU)','employee_genitive_kk':'ФИО замещаемого (ілік септік, KK)'}
        for nominal,form in (('position_ru','position_genitive_ru'),('org_unit_ru','org_unit_genitive_ru')):
            if text(r,nominal):required[form]=form
        absent=[label for key,label in required.items() if not text(r,key)]
        if absent:raise ValueError('Уточните данные замещаемого сотрудника: '+', '.join(absent))
        placement_ru=join(text(r,'position_genitive_ru') if text(r,'position_ru') else '',text(r,'org_unit_genitive_ru') if text(r,'org_unit_ru') else '')
        clause_ru=' на время трудового отпуска '+text(r,'employee_genitive_ru')+(', '+placement_ru if placement_ru else '')
        clause_kk=' '+join(text(r,'org_unit_kk'),text(r,'position_kk'),text(r,'employee_genitive_kk'))+' кезекті еңбек демалысы кезеңінде'
    placement_ru=join(text(recipient,'position_dative_ru'),text(recipient,'org_unit_genitive_ru')) if text(recipient,'position_dative_ru') else ''
    return {'employee.full_name_dative_ru':text(c,'employee_dative_ru'),'employee.full_name_dative_kk':text(c,'employee_dative_kk'),
            'allowance.recipient.ru':text(c,'employee_dative_ru')+(', '+placement_ru if placement_ru else ''),
            'allowance.recipient.kk':join(text(recipient,'org_unit_kk'),text(recipient,'position_kk'),text(c,'employee_dative_kk')) if placement_ru else text(c,'employee_dative_kk'),
            'effective_date.ru':format_personnel_order_date_numeric(start),'effective_date.kk':_format_date_from(start,'kk'),
            'allowance.percent':decimal_text(percent),'allowance.basis.ru':'собственного должностного оклада','allowance.basis.kk':'лауазымдық айлық ақыдан',
            'allowance.term.ru':term_ru,'allowance.term.kk':term_kk,'replacement.clause.ru':clause_ru,'replacement.clause.kk':clause_kk,'basis.ru':text(c,'basis_ru'),'basis.kk':text(c,'basis_kk')}

SAMPLE_RECIPIENT={'position_ru':'Врач','position_kk':'дәрігері','org_unit_ru':'Отделение терапии','org_unit_kk':'терапия бөлімшесінің','position_dative_ru':'врачу','org_unit_genitive_ru':'отделения терапии'}

def preview_context():
    from app.services.personnel_order_replacement_contract import SAMPLE_CONCURRENT,SAMPLE_REPLACEMENT
    data=values(SAMPLE_CONCURRENT,{**SAMPLE_REPLACEMENT,'term_type':'NONE'},'2026-06-15',SAMPLE_RECIPIENT)
    keys=(*VARIABLES,'allowance.percent','allowance.basis','effective_date','basis')
    return {lang:{key:data.get(key+'.'+lang,data.get(key,'')) for key in keys} for lang in ('ru','kk')}

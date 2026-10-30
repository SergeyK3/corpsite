"""Manage only levels and document kinds; program kinds are a separate service."""
import json,re
from fastapi import HTTPException
from sqlalchemy import text
from app.db.engine import engine

_SPECS={
    'levels':dict(table='education_levels',ru='name_ru',audit='education_level_audit'),
    'document-kinds':dict(table='document_kinds',ru='name',audit='document_kind_audit'),
}

def _spec(kind):
    if kind not in _SPECS: raise HTTPException(404,'Справочник не найден.')
    return _SPECS[kind]

def _ready(conn,kind):
    if kind=='levels':return conn.execute(text("SELECT to_regclass('public.education_levels') IS NOT NULL")).scalar_one()
    return conn.execute(text("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='document_kinds' AND column_name='revision')")).scalar_one()

def _row(kind,row):
    result=dict(row)
    result['name_ru']=result[_spec(kind)['ru']]
    return result

def _usage(conn,kind,code,row):
    if kind=='document-kinds':
        # Count actual identifiers, not guesses from similar free-form labels.
        return conn.execute(text('''SELECT
            (SELECT count(*) FROM employee_documents WHERE document_kind_id=:id) +
            (SELECT count(*) FROM personnel_order_items WHERE payload->'education_document'->>'kind_code'=:code)'''),{'id':row['document_kind_id'],'code':code}).scalar_one()
    return conn.execute(text('''SELECT
        (SELECT count(*) FROM person_education WHERE metadata->>'education_level_code'=:code) +
        (SELECT count(*) FROM personnel_order_items WHERE payload->'education'->>'level_code'=:code)'''),{'code':code}).scalar_one()

def list_values(kind,*,state='all',q=''):
    spec=_spec(kind)
    with engine.connect() as conn:
        if not _ready(conn,kind):return dict(items=[],total=0,schema_ready=False)
        rows=[_row(kind,r) for r in conn.execute(text(f"SELECT * FROM {spec['table']} ORDER BY sort_order,code")).mappings()]
        for row in rows:row['usage_count']=_usage(conn,kind,row['code'],row)
    rows=[r for r in rows if (state=='all' or r['is_active']==(state=='active')) and
          (not q or any(q.casefold() in str(r.get(k) or '').casefold() for k in ('code','name_ru','name_kk')))]
    return dict(items=rows,total=len(rows),schema_ready=True)

def save_value(kind,*,code,actor_user_id,expected_revision=None,**patch):
    spec=_spec(kind)
    if expected_revision is None and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}',code):
        raise HTTPException(422,'Код: заглавные латинские буквы, цифры и подчёркивание.')
    allowed={'name_ru','name_kk','sort_order','is_active'}|({'description_ru','description_kk'} if kind=='levels' else set())
    if set(patch)-allowed:raise HTTPException(422,'Пояснения допустимы только в справочнике уровней образования.')
    with engine.begin() as conn:
        if not _ready(conn,kind):raise HTTPException(503,'Требуется миграция hrlocal309.')
        conn.execute(text('SELECT pg_advisory_xact_lock(hashtext(:key))'),{'key':f'education-ref:{kind}:{code}'})
        old=conn.execute(text(f"SELECT * FROM {spec['table']} WHERE code=:code FOR UPDATE"),{'code':code}).mappings().one_or_none()
        if expected_revision is None and old:raise HTTPException(409,'Код уже существует, в том числе среди неактивных значений.')
        if expected_revision is not None:
            if not old:raise HTTPException(404,'Значение не найдено.')
            if old['revision']!=expected_revision:raise HTTPException(409,'Значение изменено. Загрузите актуальную версию.')
        values={**dict(name_ru='',name_kk='',sort_order=0,is_active=True),**(_row(kind,old) if old else {}),**patch}
        for key in ('name_ru','name_kk'):
            if not isinstance(values[key],str) or not values[key].strip():raise HTTPException(422,'Заполните названия RU и KK.')
        if kind=='levels' and code in {'BASIC_SECONDARY','GENERAL_SECONDARY'}:
            if any(not str(values.get(k) or '').strip() for k in ('description_ru','description_kk')):
                raise HTTPException(422,'Для школьных уровней нужны пояснения о классах на RU и KK.')
        fields={spec['ru']:values['name_ru'],'name_kk':values['name_kk'],'sort_order':values['sort_order'],'is_active':values['is_active']}
        if kind=='levels':fields.update({k:values.get(k) for k in ('description_ru','description_kk')})
        params={**fields,'code':code,'actor':actor_user_id}
        if old:
            sql=f"UPDATE {spec['table']} SET "+','.join(f'{key}=:{key}' for key in fields)+',revision=revision+1,updated_at=clock_timestamp(),updated_by_user_id=:actor WHERE code=:code RETURNING *'
        else:
            columns=['code',*fields,'updated_by_user_id']
            sql=f"INSERT INTO {spec['table']} ("+','.join(columns)+') VALUES('+','.join(':'+('actor' if k=='updated_by_user_id' else k) for k in columns)+') RETURNING *'
        row=conn.execute(text(sql),params).mappings().one()
        conn.execute(text(f"INSERT INTO {spec['audit']}(code,action,before_value,after_value,actor_user_id) VALUES(:code,:action,CAST(:before AS jsonb),CAST(:after AS jsonb),:actor)"),
            dict(code=code,action='CREATE' if old is None else 'UPDATE',before=json.dumps(dict(old),default=str) if old else None,after=json.dumps(dict(row),default=str),actor=actor_user_id))
        result=_row(kind,row);result['usage_count']=_usage(conn,kind,code,row)
        return result

def selection_value(kind,code,locale):
    """Names-only output for future consumers. Notes can never enter an order."""
    spec=_spec(kind)
    if code is None or not code.strip():return dict(code=None,name=None)
    code=code.strip()
    with engine.connect() as conn:
        if not _ready(conn,kind):raise HTTPException(503,'Требуется миграция hrlocal309.')
        row=conn.execute(text(f"SELECT * FROM {spec['table']} WHERE code=:code"),{'code':code}).mappings().one_or_none()
        if not row:raise HTTPException(404,'Значение не найдено.')
        if not row['is_active']:raise HTTPException(422,'Выберите активное значение.')
        name=row[spec['ru'] if locale=='ru' else 'name_kk']
        if not name or not name.strip():raise HTTPException(422,'Название на выбранном языке не заполнено.')
        return dict(code=code,name=name)

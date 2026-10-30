"""Reference lookups share the caller transaction; no cached mutable allowlists."""
import json
import re
from sqlalchemy import text
from fastapi import HTTPException
from app.db.engine import engine
from app.db.education_program_kind_migration import SEED


def available(conn):
    return conn.execute(text("SELECT to_regclass('public.education_program_kinds') IS NOT NULL")).scalar_one()


def entries(conn, *, lock=False):
    if not available(conn):
        # Rolling-upgrade compatibility only. No new writes or reference editing.
        return [dict(code=c,name_ru=ru,name_kk=kk,is_active=True,sort_order=s,revision=0) for c,ru,kk,s in SEED if c!='aspirantura']
    return [dict(r) for r in conn.execute(text('SELECT * FROM education_program_kinds ORDER BY sort_order,code' + (' FOR SHARE' if lock else ''))).mappings()]


def lookup(conn, code, *, lock=False):
    return next((row for row in entries(conn,lock=lock) if row['code']==code),None)


def list_entries(*, state='all', q=''):
    with engine.connect() as conn:
        rows=entries(conn)
        for row in rows:
            row['usage_count']=conn.execute(text('SELECT count(*) FROM person_education WHERE education_kind=:code'), {'code':row['code']}).scalar_one()
        ready=available(conn)
    rows=[r for r in rows if (state=='all' or r['is_active']==(state=='active')) and (not q or any(q.casefold() in str(r[k]).casefold() for k in ('code','name_ru','name_kk')))]
    return dict(items=rows,total=len(rows),schema_ready=ready)


def save_entry(*, code, actor_user_id, name_ru=None, name_kk=None, sort_order=None, expected_revision=None, is_active=None):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',code):
        raise HTTPException(422,'Код: латинские строчные буквы, цифры и подчёркивание.')
    with engine.begin() as conn:
        if not available(conn): raise HTTPException(503,'Требуется миграция hrlocal308.')
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {'key':'education-program-kind:'+code})
        old=conn.execute(text('SELECT * FROM education_program_kinds WHERE code=:code FOR UPDATE'), {'code':code}).mappings().one_or_none()
        if expected_revision is not None and old:
            name_ru = old['name_ru'] if name_ru is None else name_ru
            name_kk = old['name_kk'] if name_kk is None else name_kk
            sort_order = old['sort_order'] if sort_order is None else sort_order
            is_active = old['is_active'] if is_active is None else is_active
        else:
            sort_order = 0 if sort_order is None else sort_order
            is_active = True if is_active is None else is_active
        if not isinstance(name_ru,str) or not isinstance(name_kk,str) or not name_ru.strip() or not name_kk.strip():
            raise HTTPException(422,'Заполните названия RU и KK.')
        if expected_revision is None:
            if old: raise HTTPException(409,'Код уже существует, в том числе среди неактивных значений.')
            row=conn.execute(text('INSERT INTO education_program_kinds(code,name_ru,name_kk,sort_order,is_active,updated_by_user_id) VALUES(:code,:ru,:kk,:sort,:active,:actor) RETURNING *'),dict(code=code,ru=name_ru,kk=name_kk,sort=sort_order,active=is_active,actor=actor_user_id)).mappings().one()
        else:
            if not old: raise HTTPException(404,'Вид программы не найден.')
            if old['revision']!=expected_revision: raise HTTPException(409,'Значение изменено. Загрузите актуальную версию.')
            row=conn.execute(text('UPDATE education_program_kinds SET name_ru=:ru,name_kk=:kk,is_active=:active,sort_order=:sort,revision=revision+1,updated_at=clock_timestamp(),updated_by_user_id=:actor WHERE code=:code RETURNING *'),dict(code=code,ru=name_ru,kk=name_kk,sort=sort_order,active=is_active,actor=actor_user_id)).mappings().one()
        conn.execute(text('INSERT INTO education_program_kind_audit(code,action,before_value,after_value,actor_user_id) VALUES(:code,:action,CAST(:before AS jsonb),CAST(:after AS jsonb),:actor)'),dict(code=code,action='CREATE' if old is None else 'UPDATE',before=json.dumps(dict(old),default=str) if old else None,after=json.dumps(dict(row),default=str),actor=actor_user_id))
    return dict(row)

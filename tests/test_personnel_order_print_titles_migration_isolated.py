"""Run the real migration only in a freshly created, disposable PostgreSQL DB."""
from pathlib import Path
from uuid import uuid4
import importlib.util
import os
import re

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from dotenv import dotenv_values
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError


@pytest.fixture
def fresh_database():
    config = dotenv_values(Path(__file__).resolve().parents[1] / '.env')
    raw = os.environ.get('TEST_DATABASE_URL') or config.get('TEST_DATABASE_URL')
    if not raw:
        pytest.fail('An explicit local TEST_DATABASE_URL is required for the isolated migration test')
    source = make_url(raw)
    if source.host not in {'localhost','127.0.0.1','::1'} or not (source.database or '').endswith('_test'):
        pytest.fail('Migration tests require local dedicated test credentials')
    work = os.environ.get('DATABASE_URL') or config.get('DATABASE_URL')
    if work:
        target = make_url(work)
        assert (source.host, source.port, source.database) != (target.host, target.port, target.database), 'Test and working databases must differ'
    name = 'corpsite_print_migration_' + uuid4().hex + '_test'
    assert re.fullmatch(r'corpsite_print_migration_[a-f0-9]{32}_test', name)
    # The only pre-existing database connected here is PostgreSQL's maintenance
    # database. No connection is made to the working or shared test database.
    admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT', hide_parameters=True)
    isolated = create_engine(source.set(database=name), hide_parameters=True)
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield isolated
    finally:
        isolated.dispose()
        with admin.connect() as conn:
            conn.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()'), {'name':name})
            conn.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def migration():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/poprint001_version_print_titles.py'
    spec=importlib.util.spec_from_file_location('isolated_print_title_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_real_upgrade_version_freeze_snapshot_and_downgrade(fresh_database, monkeypatch):
    import json
    from app.services import personnel_order_template_draft_service as service
    from app.services.personnel_order_print_titles import pin_print_titles, printable_template, template_text_snapshot
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec
    configured=dict(get_personnel_order_template_spec('HIRE').initial_texts)
    with fresh_database.begin() as conn:
        conn.execute(text('CREATE TABLE public.personnel_order_templates(template_id bigint PRIMARY KEY,item_type_code text,name_ru text,name_kk text,is_default boolean)'))
        conn.execute(text('''CREATE TABLE public.personnel_order_template_versions(
            template_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            template_id bigint REFERENCES public.personnel_order_templates,item_type_code text,version_number int,status text,
            revision int DEFAULT 1,title_ru text,title_kk text,preamble_ru text,preamble_kk text,
            body_template_ru text,body_template_kk text,basis_template_ru text,basis_template_kk text,
            based_on_built_in boolean DEFAULT false,created_at timestamptz DEFAULT now(),updated_at timestamptz DEFAULT now(),
            created_by_user_id bigint,updated_by_user_id bigint,published_at timestamptz,published_by_user_id bigint)'''))
        conn.execute(text('CREATE TABLE public.personnel_order_template_applications(application_id bigint PRIMARY KEY,template_snapshot jsonb,rendered_snapshot jsonb)'))
        conn.execute(text('CREATE TABLE public.personnel_order_items(item_id bigint PRIMARY KEY,payload jsonb)'))
        conn.execute(text("INSERT INTO public.personnel_order_templates VALUES(1,'HIRE','TEST internal (variant)','TEST internal KK',true)"))
        sql='''INSERT INTO public.personnel_order_template_versions(template_id,item_type_code,version_number,status,
               title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
               VALUES(1,'HIRE',1,'PUBLISHED',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk)'''
        conn.execute(text(sql),configured)
        before=dict(conn.execute(text('SELECT * FROM public.personnel_order_template_versions')).mappings().one())
        with Operations.context(MigrationContext.configure(conn)):
            migration().upgrade()
        after=dict(conn.execute(text('SELECT * FROM public.personnel_order_template_versions')).mappings().one())
        assert {key:after[key] for key in before}==before
        assert after['print_title_ru'] is None and after['print_title_kk'] is None
        conn.execute(text(sql.replace("1,'PUBLISHED'","2,'DRAFT'")),configured)
    monkeypatch.setattr(service,'engine',fresh_database)
    # Use the real save and publish SQL, exclusively against this fresh DB.
    draft=service.save_draft.__wrapped__('HIRE',1,{**configured,'title_ru':'TEST detailed internal (variant)',
        'print_title_ru':'О приёме (по совместительству)','print_title_kk':configured['title_kk']},1,1)
    published=service.publish_draft.__wrapped__('HIRE',draft['revision'],1,1)
    assert published['title_ru']=='TEST detailed internal (variant)'
    assert published['print_title_ru']=='О приёме (по совместительству)'
    snapshot=template_text_snapshot(published,service.TEXT_FIELDS)
    with fresh_database.begin() as conn:
        with pytest.raises(DBAPIError,match='immutable'):
            with conn.begin_nested():
                conn.execute(text("UPDATE public.personnel_order_template_versions SET print_title_ru='Changed' WHERE status='PUBLISHED'"))
        conn.execute(text('INSERT INTO public.personnel_order_template_applications VALUES(1,CAST(:s AS jsonb),CAST(:r AS jsonb))'),
                     {'s':json.dumps(snapshot),'r':json.dumps({'title_ru':published['print_title_ru'],'title_kk':published['print_title_kk']})})
        conn.execute(text("UPDATE public.personnel_order_templates SET name_ru='TEST renamed internal (variant)'"))
        saved=conn.execute(text('SELECT * FROM public.personnel_order_template_applications')).mappings().one()
        for _ in range(2):
            pinned=printable_template(pin_print_titles({**published,'print_title_ru':'Different later version'},saved['template_snapshot']))
            assert pinned['title_ru']=='О приёме (по совместительству)'
            assert pinned['title_kk']==configured['title_kk']
        with Operations.context(MigrationContext.configure(conn)):
            migration().downgrade()
        assert 'print_title_ru' not in {column['name'] for column in inspect(conn).get_columns('personnel_order_template_versions',schema='public')}
        assert conn.execute(text('SELECT template_snapshot FROM public.personnel_order_template_applications')).scalar_one()==snapshot
        assert conn.execute(text('SELECT title_ru FROM public.personnel_order_template_versions WHERE template_version_id=1')).scalar_one()==configured['title_ru']

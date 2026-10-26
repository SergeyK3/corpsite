"""Rehearse posdir001 on a disposable copy of production position dictionaries.

Never opens production or the working local DB. Restore input comes from a
read-only snapshot; all mutations target new random loopback *_test databases.
This is a scoped copy, with synthetic personnel references, not a full PII dump.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

TABLES=('positions','position_aliases','position_job_catalog','job_positions_catalog')
PROTECTED=('employees','person_assignments','personnel_orders','personnel_order_items')


def fingerprint(conn):
    result={}
    for table in (*TABLES,*PROTECTED):
        rows=list(conn.exec_driver_sql(f'SELECT to_jsonb(t) FROM public.{table} t ORDER BY to_jsonb(t)::text').scalars())
        result[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()}
    result['columns']=[list(r) for r in conn.exec_driver_sql("SELECT table_name,column_name,data_type,column_default,is_nullable FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position")]
    result['constraints']=[list(r) for r in conn.exec_driver_sql("SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conrelid::regclass::text,conname")]
    result['view_exists']=conn.exec_driver_sql("SELECT to_regclass('public.position_directory') IS NOT NULL").scalar()
    result['sequences']={}
    for table,column in (('positions','position_id'),('position_aliases','alias_id')):
        sequence=conn.exec_driver_sql(f"SELECT pg_get_serial_sequence('public.{table}','{column}')").scalar_one()
        assert re.fullmatch(r'public\.[a-z_]+',sequence)
        result['sequences'][sequence]=dict(conn.exec_driver_sql('SELECT last_value,is_called FROM '+sequence).mappings().one())
    return result


def restore(conn,snapshot):
    from sqlalchemy import text
    sql='\n'.join(line for line in snapshot['rehearsal_schema_sql'].splitlines() if not line.startswith(('\\restrict ','\\unrestrict ')))
    assert not any(line.startswith('\\') for line in sql.splitlines()),'Unexpected psql command'
    conn.exec_driver_sql(sql)
    for table in ('job_positions_catalog','positions','position_job_catalog','position_aliases'):
        for row in snapshot['dictionaries'][table]['rows']:
            columns=list(row)
            conn.execute(text(f'INSERT INTO public.{table} ('+','.join(columns)+') OVERRIDING SYSTEM VALUE VALUES ('+','.join(':'+k for k in columns)+')'),row)
    for sequence,state in snapshot['identity_sequences'].items():
        assert re.fullmatch(r'public\.[a-z_]+',sequence)
        conn.execute(text('SELECT setval(CAST(:sequence AS regclass),:value,:called)'),{'sequence':sequence,'value':state['last_value'],'called':state['is_called']})
    # Synthetic references exercise FK stability without copying real personnel.
    conn.exec_driver_sql('''CREATE TABLE public.employees(employee_id bigint PRIMARY KEY,position_id bigint REFERENCES public.positions(position_id),marker text);
        CREATE TABLE public.person_assignments(assignment_id bigint PRIMARY KEY,position_id bigint REFERENCES public.positions(position_id),rate numeric);
        CREATE TABLE public.personnel_orders(order_id bigint PRIMARY KEY,snapshot jsonb);
        CREATE TABLE public.personnel_order_items(item_id bigint PRIMARY KEY,order_id bigint REFERENCES public.personnel_orders,position_id bigint REFERENCES public.positions(position_id),payload jsonb);
        INSERT INTO public.employees VALUES (1,24,'SYNTHETIC'),(2,52,'SYNTHETIC'),(3,47,'SYNTHETIC');
        INSERT INTO public.person_assignments VALUES (1,24,1),(2,52,0.5),(3,47,1);
        INSERT INTO public.personnel_orders VALUES (1,'{"marker":"SYNTHETIC","title":"frozen snapshot"}');
        INSERT INTO public.personnel_order_items VALUES (1,1,24,'{"marker":"SYNTHETIC"}');''')


def main():
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    snapshot=json.loads(args.snapshot.read_text(encoding='utf-8'))
    assert snapshot['transaction_read_only']=='on' and snapshot['database_revision']==['podup001']
    config=dotenv_values(root/'.env');raw=os.environ.get('TEST_DATABASE_URL') or config.get('TEST_DATABASE_URL')
    assert raw,'Local test credentials required'
    source=make_url(raw)
    assert source.host in ('127.0.0.1','localhost','::1') and source.database.endswith('_test')
    work=make_url(os.environ.get('DATABASE_URL') or config['DATABASE_URL'])
    assert (work.host,work.port,work.database)!=(source.host,source.port,source.database)
    admin=create_engine(source.set(database='postgres'),isolation_level='AUTOCOMMIT',hide_parameters=True)
    names=[];engines=[]
    def create_copy():
        name='corpsite_posdir_'+uuid4().hex+'_test'
        assert re.fullmatch(r'corpsite_posdir_[a-f0-9]{32}_test',name)
        with admin.connect() as conn:conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
        names.append(name)
        engine=create_engine(source.set(database=name),hide_parameters=True);engines.append(engine)
        with engine.begin() as conn:
            assert conn.exec_driver_sql('SELECT current_database()').scalar()==name
            restore(conn,snapshot)
        return engine
    result={'snapshot_time_utc':snapshot['time_utc'],'scope':'Exact production schema and rows of four position dictionaries; synthetic personnel references only','production_read_only':True}
    try:
        engine=create_copy()
        os.environ['CORPSITE_SKIP_DOTENV']='1';os.environ['DATABASE_URL']=engine.url.render_as_string(hide_password=False)
        path=root/'alembic/versions/posdir001_unified_position_directory.py'
        spec=importlib.util.spec_from_file_location('posdir_rehearsal',path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with engine.connect() as conn:before=fingerprint(conn)
        # Actual upgrade + rollback restores DDL/data. PostgreSQL nextval() on
        # an existing identity sequence is deliberately not transactional.
        with engine.connect() as conn:
            tx=conn.begin()
            with Operations.context(MigrationContext.configure(conn)):migration.upgrade()
            assert conn.exec_driver_sql("SELECT to_regclass('public.position_directory') IS NOT NULL").scalar()
            tx.rollback()
            rolled_back=fingerprint(conn)
            assert {k:v for k,v in rolled_back.items() if k!='sequences'}=={k:v for k,v in before.items() if k!='sequences'}
        result['transaction_rollback_schema_and_rows_exact']=True
        result['transaction_rollback_sequence_changes']={k:{'before':v,'after':rolled_back['sequences'][k]} for k,v in before['sequences'].items() if v!=rolled_back['sequences'][k]}
        result['transaction_rollback_including_sequences_exact']=rolled_back==before
        # Commit the real migration in this disposable copy only.
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):migration.upgrade()
        with engine.connect() as conn:
            after=fingerprint(conn)
            rows=list(conn.exec_driver_sql('SELECT to_jsonb(t) FROM public.positions t ORDER BY position_id').scalars())
            aliases=list(conn.exec_driver_sql('SELECT to_jsonb(t) FROM public.position_aliases t ORDER BY alias_id').scalars())
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):migration.upgrade()
            assert fingerprint(conn)==after
        result['repeat_upgrade_exact_noop']=True
        # Compare every populated/empty text against the historical backfill.
        legacy=create_copy()
        from app.db.position_directory_migration import upgrade as legacy_upgrade
        with legacy.begin() as conn:legacy_upgrade(conn)
        with legacy.connect() as conn:
            legacy_rows=list(conn.exec_driver_sql('SELECT to_jsonb(t) FROM public.positions t ORDER BY position_id').scalars())
        text_fields=('position_id','name','category','name_kk','document_nominative_ru','document_possessive_kk','record_kind','revision')
        assert [{k:r[k] for k in text_fields} for r in rows]==[{k:r[k] for k in text_fields} for r in legacy_rows]
        assert all(r['translation_status']==r['document_form_status']=='needs_review' for r in rows)
        result['all_111_text_values_equal_legacy_backfill']=True
        source_rows={r['position_id']:r for r in snapshot['dictionaries']['positions']['rows']}
        fields=('name_kk','document_nominative_ru','document_possessive_kk','translation_status','document_form_status','record_kind','revision')
        result['position_changes']=[{'position_id':r['position_id'],'name':r['name'],'category':r['category'],
            'fields':{k:{'before':source_rows[r['position_id']].get(k),'before_column_exists':k in source_rows[r['position_id']],'after':r.get(k)} for k in fields if k not in source_rows[r['position_id']] or source_rows[r['position_id']].get(k)!=r.get(k)}} for r in rows]
        result['aliases_after']=aliases
        result['counts']={k:sum(bool(r.get(k)) for r in rows) for k in ('name_kk','document_nominative_ru','document_possessive_kk')}
        result['counts'].update(positions=len(rows),changed_existing_name_kk=sum(r.get('name_kk')!=source_rows[r['position_id']].get('name_kk') for r in rows),
            translation_confirmed=sum(r['translation_status']=='confirmed' for r in rows),translation_needs_review=sum(r['translation_status']=='needs_review' for r in rows),
            document_form_confirmed=sum(r['document_form_status']=='confirmed' for r in rows),document_form_needs_review=sum(r['document_form_status']=='needs_review' for r in rows))
        result['record_kind_counts']={k:sum(r['record_kind']==k for r in rows) for k in ('standalone','variant','search_synonym')}
        assert all(source_rows[r['position_id']][k]==r[k] for r in rows for k in ('position_id','name','category'))
        assert all(before[t]==after[t] for t in (*PROTECTED,'position_job_catalog','job_positions_catalog'))
        result['ids_names_categories_and_protected_records_unchanged']=True
        result['protected_fingerprints']={t:after[t] for t in PROTECTED}
        # The shipped downgrade must refuse, without changing the migrated DB.
        try:
            with engine.begin() as conn:
                with Operations.context(MigrationContext.configure(conn)):migration.downgrade()
        except RuntimeError as exc:result['downgrade_refused']=str(exc)
        else:raise AssertionError('Expected explicit data-preserving downgrade refusal')
        with engine.connect() as conn:assert fingerprint(conn)==after
        result['downgrade_refusal_preserves_state']=True
        # Recovery after COMMIT: restore the pre-migration schema/data copy into
        # another new test DB and compare complete scoped schema/row fingerprints.
        recovered=create_copy()
        with recovered.connect() as conn:assert fingerprint(conn)==before
        result['post_commit_scoped_backup_restore_exact']=True
        result['temporary_databases']=names.copy()
        result['plan_recalculated']=False
    finally:
        for engine in engines:engine.dispose()
        with admin.connect() as conn:
            for name in names:
                assert re.fullmatch(r'corpsite_posdir_[a-f0-9]{32}_test',name)
                conn.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()'),{'name':name})
                conn.exec_driver_sql(f'DROP DATABASE "{name}"')
        admin.dispose()
    result['temporary_databases_removed']=True
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('position_changes','aliases_after','protected_fingerprints')},ensure_ascii=True))


if __name__=='__main__':main()

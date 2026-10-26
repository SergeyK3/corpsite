"""Full backup/recovery-copy helpers that are deliberately VPS-local only.

Never downloads a dump, never drops/overwrites a database. Restore targets must
be new verification/recovery DBs. All generated files stay in the VPS backup dir.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from dotenv import dotenv_values,set_key
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

BACKUPS=Path('/opt/projects/corpsite/backups')


def server_path(path):
    if os.name=='nt' or not Path('/opt/projects/corpsite/app').exists():
        raise RuntimeError('VPS-local operation only; no local-computer production dumps')
    result=path.resolve()
    if not result.is_relative_to(BACKUPS.resolve()):raise RuntimeError('Backup files must remain under the VPS backup directory')
    return result


def pg_env(url,database=None,readonly=True):
    if url.host not in ('localhost','127.0.0.1','::1'):raise RuntimeError('VPS loopback PostgreSQL required')
    return {**os.environ,'PGHOST':url.host,'PGPORT':str(url.port or 5432),'PGUSER':url.username,
            'PGPASSWORD':url.password or '','PGDATABASE':database or url.database,
            'PGOPTIONS':'-c default_transaction_read_only=on -c lock_timeout=5000' if readonly else ''}


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def table_digests(conn):
    conn.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
    result={}
    for table in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars():
        if not re.fullmatch(r'[a-z_][a-z0-9_]*',table):raise RuntimeError('Unexpected public table name')
        result[table]=dict(conn.exec_driver_sql(f"SELECT count(*) AS count,md5(COALESCE(string_agg(h,'|' ORDER BY h),'')) AS digest FROM (SELECT md5(to_jsonb(t)::text) h FROM public.{table} t) rows").mappings().one())
    return result


def sequence_states(conn):
    states={}
    for name in conn.execute(text("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")).scalars():
        if not re.fullmatch(r'[a-z_][a-z0-9_]*',name):raise RuntimeError('Unexpected sequence identifier')
        states[name]=dict(conn.exec_driver_sql(f'SELECT last_value,is_called FROM public.{name}').mappings().one())
    return states


def schema_signature(conn):
    """Compare restored schema without putting schema definitions into reports."""
    queries=[
        "SELECT table_name,column_name,data_type,column_default,is_nullable FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
        "SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY conrelid::regclass::text,conname",
        "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",
        "SELECT tgname,pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal ORDER BY tgrelid::regclass::text,tgname",
        "SELECT viewname,definition FROM pg_views WHERE schemaname='public' ORDER BY viewname",
    ]
    rows=[[list(row) for row in conn.exec_driver_sql(sql)] for sql in queries]
    return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('backup','verify','restore-copy','recovery-env'))
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--output',type=Path);parser.add_argument('--backup',type=Path)
    parser.add_argument('--database');parser.add_argument('--server-local-only',action='store_true',required=True)
    args=parser.parse_args();os.umask(0o077)
    url=make_url(dotenv_values(args.env_file)['DATABASE_URL'])
    env=pg_env(url)
    if args.action=='backup':
        output=server_path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():raise RuntimeError('Refusing to overwrite a backup')
        db=create_engine(url,hide_parameters=True,connect_args={'options':'-c default_transaction_read_only=on'})
        with db.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            snapshot=conn.exec_driver_sql('SELECT pg_export_snapshot()').scalar_one()
            with output.open('xb') as stream:
                subprocess.run(['pg_dump','-Fc','--no-owner','--no-privileges','--snapshot='+snapshot],env=env,stdout=stream,check=True)
            revision=list(conn.execute(text('SELECT version_num FROM public.alembic_version')).scalars())
            digests=table_digests(conn)
            sequences=sequence_states(conn)
            schema= schema_signature(conn)
            locale=dict(conn.exec_driver_sql("SELECT pg_encoding_to_char(encoding) AS encoding,datcollate AS collate,datctype AS ctype,datlocprovider AS provider FROM pg_database WHERE datname=current_database()").mappings().one())
            if locale['provider']!='c':raise RuntimeError('ICU locale requires a separately reviewed CREATE DATABASE command')
        subprocess.run(['pg_restore','--list',str(output)],stdout=subprocess.DEVNULL,check=True)
        db.dispose()
        manifest={'backup':str(output),'bytes':output.stat().st_size,'sha256':sha256(output),'revision':revision,'table_digests':digests,'sequences':sequences,'schema_signature':schema,'database_locale':locale,'server_local_only':True}
        output.with_suffix(output.suffix+'.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        print(json.dumps({k:manifest[k] for k in ('backup','bytes','sha256','revision','server_local_only')} | {'verified_table_count':len(digests)}));return
    if args.action=='recovery-env':
        output=server_path(args.output)
        if not re.fullmatch(r'corpsite_recovery_[a-z0-9_]{1,40}',args.database or ''):raise RuntimeError('Invalid recovery DB name')
        if output.exists():raise RuntimeError('Recovery env already exists')
        shutil.copyfile(args.env_file,output);os.chmod(output,0o600)
        set_key(str(output),'DATABASE_URL',url.set(database=args.database).render_as_string(hide_password=False),quote_mode='always')
        print('Recovery env written on VPS; credentials are not printed');return
    backup=server_path(args.backup)
    manifest=json.loads(backup.with_suffix(backup.suffix+'.manifest.json').read_text())
    if sha256(backup)!=manifest['sha256']:raise RuntimeError('Backup checksum mismatch')
    subprocess.run(['pg_restore','--list',str(backup)],stdout=subprocess.DEVNULL,check=True)
    if args.action=='verify':print('Backup checksum and archive list verified');return
    if not re.fullmatch(r'corpsite_(release_verify|recovery)_[a-z0-9_]{1,35}',args.database or '') or args.database==url.database:
        raise RuntimeError('Restore is allowed only into a new verification/recovery DB')
    admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT',hide_parameters=True)
    with admin.connect() as conn:
        if conn.execute(text('SELECT 1 FROM pg_database WHERE datname=:name'),{'name':args.database}).scalar():raise RuntimeError('Restore target already exists; no overwrite/drop allowed')
        locale=manifest['database_locale']
        if locale['provider']!='c':raise RuntimeError('Unsupported restore locale provider')
        conn.execute(text('CREATE DATABASE "'+args.database+'" TEMPLATE template0 ENCODING :encoding LC_COLLATE :collate LC_CTYPE :ctype'),{k:locale[k] for k in ('encoding','collate','ctype')})
    admin.dispose()
    subprocess.run(['pg_restore','--no-owner','--no-privileges','--exit-on-error','--dbname',args.database,str(backup)],env=pg_env(url,args.database,False),check=True)
    restored=create_engine(url.set(database=args.database),hide_parameters=True,connect_args={'options':'-c default_transaction_read_only=on'})
    with restored.connect() as conn:
        revisions=list(conn.execute(text('SELECT version_num FROM alembic_version')).scalars())
        if revisions!=manifest['revision']:raise RuntimeError('Restored Alembic revision differs from backup')
        if table_digests(conn)!=manifest['table_digests']:raise RuntimeError('Restored table counts/digests differ from backup')
        if sequence_states(conn)!=manifest['sequences']:raise RuntimeError('Restored identity/serial counters differ from backup')
        if schema_signature(conn)!=manifest['schema_signature']:raise RuntimeError('Restored schema/constraints/indexes/triggers/views differ from backup')
    restored.dispose();print(json.dumps({'restored_database':args.database,'revision':revisions,'backup_verified':True}))


if __name__=='__main__':main()

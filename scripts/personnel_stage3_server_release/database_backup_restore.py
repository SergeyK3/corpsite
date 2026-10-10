"""Operator-only backup/restore of loopback corpsite; secrets never appear in argv."""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from database_state import STAGING_TABLES

def checksum(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def connection_commands(repo,container):
    url=make_url(dotenv_values(repo/'.env')['DATABASE_URL'])
    if url.host not in {'localhost','127.0.0.1','::1'} or url.database!='corpsite':raise RuntimeError('STOP: expected loopback corpsite from server .env')
    native=all(shutil.which(name) for name in ['pg_dump','pg_restore','psql'])
    env=dict(os.environ)
    if native:
        env['PGPASSWORD']=url.password or ''
        connection=['--host',url.host,'--port',str(url.port or 5432),'--username',url.username,'--dbname',url.database]
        return {name:[shutil.which(name)]+([] if name=='pg_restore' else connection) for name in ['pg_dump','pg_restore','psql']},env
    ports=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .NetworkSettings.Ports}}',container]))
    bindings=ports.get('5432/tcp') or []
    if not any(b['HostPort']==str(url.port or 5432) and b['HostIp'] in {'127.0.0.1','::1','0.0.0.0','::'} for b in bindings):raise RuntimeError('STOP: container PostgreSQL port differs from .env')
    prefix=['docker','exec','-i',container]
    return {name:prefix+[name]+([] if name=='pg_restore' else ['--username',url.username,'--dbname',url.database]) for name in ['pg_dump','pg_restore','psql']},env

def archive_list(commands,env,path):
    with path.open('rb') as handle:
        return subprocess.check_output(commands['pg_restore']+['--list'],stdin=handle,env=env).decode('utf8')

def verify_archive(commands,env,path):
    expected=path.with_suffix(path.suffix+'.sha256').read_text(encoding='ascii').split()[0]
    if checksum(path)!=expected:raise RuntimeError('STOP: database archive checksum differs')
    listing=archive_list(commands,env,path)
    records=[]
    for line in listing.splitlines():
        if not line or line.startswith(';'):continue
        match=re.fullmatch(r'\d+;\s+\d+\s+\d+\s+([A-Z][A-Z ]*)\s+(\S+)\s+(.+)',line)
        if match is None:raise RuntimeError('STOP: unsupported PostgreSQL archive TOC entry')
        records.append(tuple(match.groups()))
    explicit={value.split()[0] for kind,namespace,value in records if kind=='SCHEMA' and namespace=='-'}
    used=explicit|{namespace for _,namespace,_ in records if namespace!='-'}
    if used!={'public','staging'}:raise RuntimeError('STOP: expected exactly public and staging in full archive; found '+repr(sorted(used)))
    if 'staging' not in explicit:raise RuntimeError('STOP: staging schema definition is absent from full archive')
    tables={(namespace,value.split()[0]) for kind,namespace,value in records if kind=='TABLE'}
    data={(namespace,value.split()[0]) for kind,namespace,value in records if kind=='TABLE DATA'}
    required={('public','alembic_version')}|{('staging',name) for name in STAGING_TABLES}
    if not required.issubset(tables):raise RuntimeError('STOP: required migration/staging table definitions absent: '+repr(sorted(required-tables)))
    if not required.issubset(data):raise RuntimeError('STOP: required migration/staging table data absent (schema-only/partial archive): '+repr(sorted(required-data)))
    if any(kind.startswith(('BLOB','LARGE OBJECT')) for kind,_,_ in records):raise RuntimeError('STOP: large objects require a separately reviewed full-database restore')
    # Decode every data stream, not only the TOC. Nothing is executed in a DB.
    with path.open('rb') as archive:
        subprocess.run(commands['pg_restore']+['--file','-'],stdin=archive,stdout=subprocess.DEVNULL,env=env,check=True)
    print('OK: SHA256, public/staging definitions+data and full archive decode verified (PG16 public SCHEMA entry optional)')
    return {'schemas':sorted(used),'explicit_schemas':sorted(explicit),'staging_tables':sorted(name for ns,name in tables if ns=='staging')}

def restore_archive(commands,env,path):
    """Restore both schemas atomically; keep all archived ownership/ACL statements."""
    verify_archive(commands,env,path)
    # Standard PG16 public SCHEMA is omitted or ownership-only. Reconstruct its
    # initdb owner, ACL and comment first; archived ALTER OWNER/ACL/COMMENT then
    # restore custom settings. This helper accepts full, unfiltered pg_dump only.
    with tempfile.TemporaryFile() as sql:
        sql.write(b"DROP SCHEMA IF EXISTS staging CASCADE;\nDROP SCHEMA public CASCADE;\n"
                  b"CREATE SCHEMA public AUTHORIZATION pg_database_owner;\n"
                  b"GRANT USAGE ON SCHEMA public TO PUBLIC;\n"
                  b"COMMENT ON SCHEMA public IS 'standard public schema';\n")
        sql.flush()
        with path.open('rb') as archive:
            subprocess.run(commands['pg_restore']+['--file','-'],stdin=archive,stdout=sql,env=env,check=True)
        sql.seek(0)
        subprocess.run(commands['psql']+['--no-psqlrc','--single-transaction','--set','ON_ERROR_STOP=1'],stdin=sql,stdout=subprocess.DEVNULL,env=env,check=True)
    print('OK: public+staging restored in one transaction with archived owners/ACL; Alembic marker came from the backup')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['backup','verify','restore'])
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--file',type=Path,required=True);p.add_argument('--container',default='corpsite-pg')
    p.add_argument('--confirm-restore',default='');args=p.parse_args();commands,env=connection_commands(args.repo.resolve(),args.container);path=args.file.resolve()
    if args.action=='backup':
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as handle:subprocess.run(commands['pg_dump']+['--format=custom'],stdout=handle,env=env,check=True)
        if not path.stat().st_size:raise RuntimeError('STOP: empty database backup')
        path.with_suffix(path.suffix+'.sha256').write_text(checksum(path)+'  '+path.name+'\n',encoding='ascii',newline='\n')
        verify_archive(commands,env,path);return
    if args.action=='verify':verify_archive(commands,env,path);return
    if args.confirm_restore!='corpsite':raise RuntimeError('STOP: restore requires --confirm-restore corpsite and stopped writers')
    restore_archive(commands,env,path)

if __name__=='__main__':main()

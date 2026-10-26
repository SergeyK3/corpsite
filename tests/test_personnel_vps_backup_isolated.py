"""Exercise the VPS helper against a disposable synthetic DB, never production."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine,text
from tests.test_personnel_order_print_titles_migration_isolated import fresh_database
from scripts import personnel_vps_backup as helper


def test_backup_verify_restore_and_recovery_env(fresh_database,tmp_path,monkeypatch):
    container=os.environ.get('PERSONNEL_TEST_PG_CONTAINER')
    if not container and not (shutil.which('pg_dump') and shutil.which('pg_restore')):
        pytest.skip('Native PostgreSQL tools or explicit isolated test container required')
    if container:
        assert container.startswith('corpsite-release-rehearsal-')
        native_run=subprocess.run

        def docker_pg(command,**kwargs):
            if command[0] not in ('pg_dump','pg_restore'):
                return native_run(command,**kwargs)
            environment=kwargs.pop('env',{})
            translated=['docker','exec','-i','--env','PGHOST=/var/run/postgresql',
                '--env','PGPORT=5432','--env','PGUSER=postgres',
                '--env','PGDATABASE='+environment.get('PGDATABASE','postgres'),
                '--env','PGOPTIONS='+environment.get('PGOPTIONS',''),container,*command]
            # Test-only transport for the local container's native pg tools.
            # Production uses the same helper directly on VPS, without Docker.
            if command[0]=='pg_restore':
                archive=Path(command[-1])
                assert archive.is_relative_to(tmp_path)
                translated.pop()
                with archive.open('rb') as stream:
                    return native_run(translated,stdin=stream,**kwargs)
            return native_run(translated,**kwargs)
        monkeypatch.setattr(helper.subprocess,'run',docker_pg)

    def isolated_path(path):
        result=path.resolve()
        assert result.is_relative_to(tmp_path.resolve())
        return result
    monkeypatch.setattr(helper,'server_path',isolated_path)
    url=fresh_database.url
    with fresh_database.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE alembic_version(version_num text PRIMARY KEY); INSERT INTO alembic_version VALUES('podup001')")
        conn.exec_driver_sql("CREATE TABLE synthetic_rows(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,value text); INSERT INTO synthetic_rows(value) VALUES('synthetic only'),(NULL)")
    env=tmp_path/'synthetic.env'
    env.write_text('DATABASE_URL='+url.render_as_string(hide_password=False)+'\nOTHER=keep\n',encoding='utf-8')
    backup=tmp_path/'synthetic.dump'
    restored_name='corpsite_release_verify_'+uuid4().hex[:20]
    recovery_name='corpsite_recovery_'+uuid4().hex[:20]

    def invoke(action,*args):
        monkeypatch.setattr(sys,'argv',['backup-helper',action,'--server-local-only','--env-file',str(env),*map(str,args)])
        helper.main()

    try:
        invoke('backup','--output',backup)
        manifest=json.loads(backup.with_suffix('.dump.manifest.json').read_text())
        assert manifest['revision']==['podup001'] and manifest['table_digests']['synthetic_rows']['count']==2
        invoke('verify','--backup',backup)
        invoke('restore-copy','--backup',backup,'--database',restored_name)
        with pytest.raises(RuntimeError,match='already exists'):
            invoke('restore-copy','--backup',backup,'--database',restored_name)
        recovered=tmp_path/'recovered.env'
        invoke('recovery-env','--database',recovery_name,'--output',recovered)
        from dotenv import dotenv_values
        from sqlalchemy.engine import make_url
        values=dotenv_values(recovered)
        assert make_url(values['DATABASE_URL']).database==recovery_name and values['OTHER']=='keep'
        with backup.open('ab') as stream:stream.write(b'SYNTHETIC corruption')
        with pytest.raises(RuntimeError,match='checksum mismatch'):
            invoke('verify','--backup',backup)
    finally:
        admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
        with admin.connect() as conn:
            assert restored_name.startswith('corpsite_release_verify_')
            conn.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name'),{'name':restored_name})
            conn.exec_driver_sql('DROP DATABASE IF EXISTS "'+restored_name+'"')
        admin.dispose()

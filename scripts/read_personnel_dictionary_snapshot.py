"""Read-only production probe, run through SSH stdin with python -B -.

Prints only release/schema metadata and non-personal dictionary rows. Writes no
server files, imports no application modules, and exposes no connection URL.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

TABLES = ('positions', 'position_aliases', 'position_job_catalog',
          'job_positions_catalog', 'medical_specialties', 'medical_specialty_groups')
READ_ONLY_OPTIONS = '-c default_transaction_read_only=on -c statement_timeout=20000'


def revision_metadata(source):
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('revision', 'down_revision'):
                    values[target.id] = ast.literal_eval(node.value)
    return values


def main():
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text
    root = Path.cwd().resolve()
    active_release = Path('/opt/projects/corpsite/app')
    assert active_release.resolve() == root, 'Run from the active production release'
    assert (root / 'alembic/versions').is_dir(), 'Run from the active release directory'
    env = {**os.environ, 'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
           'PGOPTIONS': READ_ONLY_OPTIONS}
    commands = {
        'sha': ['git', 'rev-parse', 'HEAD'],
        'services': ['systemctl', 'show', 'corpsite-backend', 'corpsite-frontend',
                     '-p', 'Id', '-p', 'MainPID', '-p', 'WorkingDirectory', '-p', 'ActiveState'],
        'alembic_current': ['.venv/bin/alembic', 'current'],
        'alembic_heads': ['.venv/bin/alembic', 'heads'],
        'alembic_history': ['.venv/bin/alembic', 'history', '--verbose'],
    }
    result = {'format': 'personnel-dictionaries-readonly-snapshot-v1',
              'time_utc': datetime.now(timezone.utc).isoformat(),
              'release_path': str(root), 'commands': {}, 'migration_graph': [], 'dictionaries': {}}
    for name, args in commands.items():
        command = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=60)
        if command.returncode:
            raise RuntimeError(f'{name} failed; stop preflight: {command.stderr[-500:]}')
        result['commands'][name] = {'returncode': 0, 'stdout': command.stdout, 'stderr': command.stderr}
    for path in sorted((root / 'alembic/versions').glob('*.py')):
        source = path.read_bytes().replace(b'\r\n', b'\n')
        meta = revision_metadata(source)
        if 'revision' in meta:
            result['migration_graph'].append({**meta, 'file': path.name,
                                              'sha256': hashlib.sha256(source).hexdigest()})
    url = os.environ.get('DATABASE_URL') or dotenv_values(root / '.env').get('DATABASE_URL')
    assert url, 'Production connection is unavailable'
    db = create_engine(url, hide_parameters=True, connect_args={'options': READ_ONLY_OPTIONS})
    try:
        with db.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            result['transaction_read_only'] = conn.exec_driver_sql('SHOW transaction_read_only').scalar()
            assert result['transaction_read_only'] == 'on', 'Read-only enforcement required'
            result['database_revision'] = list(conn.execute(text('SELECT version_num FROM public.alembic_version ORDER BY version_num')).scalars())
            result['dictionary_columns'] = [dict(r) for r in conn.execute(text(
                "SELECT table_name,column_name,data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name IN "
                "('positions','position_aliases','position_directory','job_positions_catalog',"
                "'position_job_catalog','medical_specialties','medical_specialty_groups','personnel_order_template_versions') "
                "ORDER BY table_name,ordinal_position")).mappings()]
            for table in TABLES:
                present = bool(conn.execute(text('SELECT to_regclass(:name)'), {'name': 'public.' + table}).scalar())
                rows = list(conn.execute(text(f'SELECT to_jsonb(t) FROM public.{table} t ORDER BY to_jsonb(t)::text')).scalars()) if present else []
                result['dictionaries'][table] = {'exists': present, 'count': len(rows), 'rows': rows}
            conn.rollback()
    finally:
        db.dispose()
    # A changed active symlink/release invalidates this capture.
    assert active_release.resolve() == root, 'Active production release changed during capture'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == result['commands']['sha']['stdout'].strip()
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()

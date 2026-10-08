"""Generate a review-only DDL proposal. Reads corpsite; never executes the DDL."""
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'runtime/personnel-stage3-preparation'
    before = json.loads((folder / 'preflight.json').read_text(encoding='utf-8'))
    if before['revision'] != ['za0b1c2d3e4f']:
        raise SystemExit('STOP: unexpected baseline')
    url = make_url(dotenv_values(root / '.env')['DATABASE_URL'])
    if url.host not in {'localhost', '127.0.0.1', '::1'} or url.database != 'corpsite':
        raise SystemExit('STOP: expected loopback corpsite')
    statements = []
    sources = {}
    with create_engine(url).connect() as conn:
        conn.execute(text('SET TRANSACTION READ ONLY'))
        for name in ['hrtpl001_independent_personnel_templates.py', 'hrrecall001_annual_leave_recall_drafts.py']:
            source = root / 'alembic/versions' / name
            sources[name] = hashlib.sha256(source.read_bytes()).hexdigest()
            spec = importlib.util.spec_from_file_location(name[:-3], source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # The only calls through the real connection are introspection SELECTs.
            with patch.object(module.op, 'get_bind', return_value=conn), \
                 patch.object(module.op, 'execute', side_effect=lambda sql: statements.append(str(sql))):
                module.upgrade()
    header = '''-- REVIEW ONLY: generated from the canonical stage-3 migrations.
-- Do not execute this file directly: no Alembic history recovery is performed here.
-- The audited recovery revision must validate its baseline, run these changes
-- in ONE transaction, verify old rows, and let Alembic advance its own marker.
-- No orgkk001/hrlang001 DDL: both physical changes already exist and must be validated.
-- Existing selected_template_version_id values will be NULL; no speculative backfill.
'''
    (folder / 'stage3-reviewed.sql').write_text(header + '\n\n'.join(s.rstrip().rstrip(';') + ';' for s in statements) + '\n', encoding='utf-8')
    (folder / 'migration-source-hashes.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    paths = ['runtime/personnel-stage3-preparation/preflight.json',
             'runtime/personnel-stage3-preparation/stage3-reviewed.sql',
             'docs/deploy/personnel-stage3-local-recovery-plan.txt',
             'scripts/preflight_personnel_stage3_local.py',
             'scripts/prepare_personnel_stage3_local_sql.py',
             'scripts/check_personnel_stage3_local_preparation.py']
    paths += [str(p.relative_to(root)).replace('\\', '/') for p in
              (root / 'scripts/personnel_stage3_local_recovery').rglob('*')
              if p.is_file() and p.suffix in {'.py', '.ini'}]
    paths += ['alembic/versions/' + name for name in sources]
    backup = json.loads((folder / 'backup-verification.json').read_text(encoding='utf-8'))
    manifest = {'status': 'REHEARSED_WORKING_NOT_APPLIED' if (folder / 'rehearsal-result.json').exists() else 'PREPARATION_ONLY_NOT_REHEARSED', 'observed_revision': 'za0b1c2d3e4f',
                'proposed_revision': 'hrlocal301', 'backup': backup,
                'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}
    (folder / 'recovery-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'statements': len(statements), 'sql': str(folder / 'stage3-reviewed.sql'),
                      'source_hashes': sources}))


if __name__ == '__main__':
    main()
